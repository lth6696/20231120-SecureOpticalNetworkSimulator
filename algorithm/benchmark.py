import logging

import networkx as nx


class Benchmark:
    def __init__(self):
        self._infinitesimal = 1e-5
        self.algorithmName = "benchmark"

    def routeCall(self, physicalTopology, event, routeTable):
        # 重路由
        break_calls = self._find_calls(physicalTopology.G, physicalTopology.calls)
        for call in break_calls:
            try:
                reroute = nx.shortest_path(prune_topo, call.src, call.dst)
                call.path = reroute
            except:
                call.path = None
            finally:
                call.restore_times += 1

    def removeCall(self, physicalTopology, event, routeTable):
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
        return target_calls