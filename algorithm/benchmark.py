import logging

import networkx as nx


class Benchmark:
    def __init__(self):
        self._infinitesimal = 1e-5
        self.algorithmName = "benchmark"
        self.unable_areas = []

    def route(self, physicalTopology, event, routeTable):
        self.unable_areas.append(event.event.target)
        logging.info("Attacked areas: {}".format(self.unable_areas))
        # 拓扑剪枝
        prune_topo = self._prune_graph(physicalTopology.G, self.unable_areas)
        # 重路由
        break_calls = self._find_calls(physicalTopology.G, physicalTopology.calls, self.unable_areas)
        for call in break_calls:
            try:
                reroute = nx.shortest_path(prune_topo, call.src, call.dst)
                if physicalTopology.reserve(prune_topo, reroute, call.rate):
                    call.path = reroute
            except:
                call.path = None
                # pass
            finally:
                call.restore_times += 1

    def remove(self, physicalTopology, event, routeTable):
        self.unable_areas.remove(event.event.target)
        # 拓扑剪枝
        prune_topo = self._prune_graph(physicalTopology.G, self.unable_areas)
        for call in physicalTopology.calls:
            if call.path:
                continue
            try:
                reroute = nx.shortest_path(prune_topo, call.src, call.dst)
                if physicalTopology.reserve(prune_topo, reroute, call.rate):
                    call.path = reroute
            except:
                pass

    @staticmethod
    def _find_calls(G: nx.Graph, calls: list, target: list):
        target_calls = []
        for call in calls:
            if call.path is None:
                continue
            traverse_node = [G.nodes[node]["area"] for node in call.path]
            traverse_link = [area for (u, v) in zip(call.path[:-1], call.path[1:]) for area in G[u][v]["area"]]
            if set(traverse_node + traverse_link) & set(target):
                target_calls.append(call)
                logging.info("The {} call passes areas: {}".format(call.id, set(traverse_node + traverse_link)))
        return target_calls

    @staticmethod
    def _prune_graph(G: nx.Graph, prune_loc: list):
        prune_topo = G.copy()
        # 剪掉指定归属地的节点
        nodes_to_remove = [node for node, data in prune_topo.nodes(data=True) if set(data['area']) & set(prune_loc)]
        prune_topo.remove_nodes_from(nodes_to_remove)
        # 剪掉指定归属地的链路
        edges_to_remove = [(u, v) for u, v, data in prune_topo.edges(data=True) if set(data['area']) & set(prune_loc)]
        prune_topo.remove_edges_from(edges_to_remove)
        return prune_topo
