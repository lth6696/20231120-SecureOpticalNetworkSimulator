import networkx as nx
import logging
import numpy as np

from .fuzzy import Fuzzy
from network.generator import TopoGen, CallsGen
from network.state import NetState
from utl.event import Event


class PRACA:
    def __init__(self):
        self.trans_matrix = None
        self.unable_areas = []
        self.potential_areas = []
        self._infinity = 1e-5

    def route(self, event: Event, topo_gen: TopoGen, tfk_gen: CallsGen, net_state: NetState, depth: int):
        atk_area = event.event.target
        self.unable_areas.append(atk_area)
        # 恢复
        self._restore_services_under_attack(topo_gen.G, tfk_gen.calls)
        # 调整
        self._adjust_services_potentially_under_attack(topo_gen.G, tfk_gen.calls, net_state, depth)

    def remove(self, event: Event, topo_gen: TopoGen, tfk_gen: CallsGen, **kwargs):
        self.unable_areas.remove(event.event.target)
        logging.info("After departure event {}, unable areas have {}.".format(event.event.id, self.unable_areas))
        # 拓扑剪枝
        prune_G = self._prune_graph(topo_gen.G, self.unable_areas)
        blocked_calls = [call for call in tfk_gen.calls if call.path == []]
        self._reroute(prune_G, blocked_calls, restore_or_adjust=False)

    def _restore_services_under_attack(self, G: nx.Graph, calls: list):
        """
        输入：受到攻击前的拓扑，所有业务，攻击导致不可用区域
        输出：为所有受到攻击的业务寻找恢复路径
        基于拓扑剪枝算法，删除受攻击链路节点，寻找受攻击业务，重路由业务路径
        """
        # 拓扑剪枝
        prune_G = self._prune_graph(G, self.unable_areas)
        # 寻找业务
        break_calls = self._find_calls(G, calls, self.unable_areas)
        # 重路由
        self._reroute(prune_G, break_calls, True)

    def _adjust_services_potentially_under_attack(self, G: nx.Graph, calls: list, net_state: NetState, depth: int):
        """
        输入：攻击前的拓扑，所有业务，攻击导致不可用区域，网络状态，预测长度
        输出：为潜在可能受到攻击的业务寻找恢复路径
        构建k-Markov攻击转移模型，删除潜在攻击链路节点，寻找受影响业务，重路由业务路径
        """
        # 计算转移概率
        net_state.update(G, calls, self.unable_areas)
        self.trans_matrix = self._calculate_transition_matrix(net_state, G, calls, self.unable_areas)
        # 计算攻击战略
        atk_tactics = self._trace_atk_tactics(net_state.regions, depth)
        self.potential_areas += atk_tactics
        logging.info("Attacked areas: {}".format(self.unable_areas))
        logging.info("Potential areas: {}".format(self.potential_areas))
        # 重路由
        prune_G = self._prune_graph(G, self.potential_areas + self.unable_areas)
        break_calls = self._find_calls(G, calls, self.potential_areas)
        self._reroute(prune_G, break_calls, False)

    def _evaluate_attack_probabilities(self, net_state: NetState, *args):
        fuzzy = Fuzzy()
        fuzzy.init_fuzzy_evaluation(net_state.regions, net_state.used_states)
        for grade in net_state.regions:
            # todo update state
            net_state.update(*args, specify="distance")
            for factor in net_state.used_states:
                fuzzy.add_evaluation(grade, factor, net_state.net_state[grade][factor])
        prob = fuzzy.evaluate()
        return prob

    def _calculate_transition_matrix(self, net_state: NetState, *args):
        num_region = len(net_state.regions)
        prob_matrix = np.zeros((num_region, num_region))
        for row, atk in enumerate(net_state.regions):
            probabilities = self._evaluate_attack_probabilities(net_state, *args)
            for col, value in enumerate(probabilities):
                prob_matrix[row][col] = value
        return prob_matrix

    def _trace_atk_tactics(self, regions: list, depth: int):
        root = self.unable_areas[-1]
        chain = nx.DiGraph()
        chain.add_node("root", id=root)
        chain.add_node("final", id=root)
        self._build_tree(chain, "root", depth, [area for area in regions if area != root], regions)
        path = nx.shortest_path(chain, source="root", target="final", weight="weight")
        trace = [chain.nodes[i]["id"] for i in path[1:-1] if chain.nodes[i]["id"] != root]
        return trace

    def _build_tree(self, chain, node, depth, children, regions):
        if depth == 0:
            chain.add_edge(node, "final", weight=0)
            return
        for child in children:
            next = str(depth)+str(node)+str(child)
            weight = 1 / (self.trans_matrix[regions.index(chain.nodes[node]["id"])][regions.index(child)] + self._infinity)
            chain.add_node(next, id=child)
            chain.add_edge(node, next, weight=weight)
            self._build_tree(chain, next, depth-1, [area for area in children if area != child], regions)

    @staticmethod
    def _prune_graph(G: nx.Graph, prune_loc: list):
        prune_topo = G.copy()
        # 剪掉指定归属地的节点
        nodes_to_remove = [node for node in prune_topo.nodes() if {node} & set(prune_loc)]
        prune_topo.remove_nodes_from(nodes_to_remove)
        # 剪掉指定归属地的链路
        edges_to_remove = [(u, v) for u, v in prune_topo.edges() if {u, v} & set(prune_loc)]
        prune_topo.remove_edges_from(edges_to_remove)
        return prune_topo

    @staticmethod
    def _find_calls(G: nx.Graph, calls: list, target: list):
        target_calls = []
        for call in calls:
            if call.path is None:
                continue
            traverse_node = [G.nodes[node]["Country"] for node in call.path]
            traverse_link = [region for node_pair in zip(call.path[:-1], call.path[1:]) for region in node_pair]
            if set(traverse_node+traverse_link) & set(target):
                target_calls.append(call)
                logging.info("The {} call passes areas: {}".format(call.id, set(traverse_node + traverse_link)))
        return target_calls

    def _reserve(self, G: nx.Graph, path: list, rate: float):
        if len(path) <= 1:
            return True
        u_node = path[0]
        v_node = path[1]
        if G[u_node][v_node]["bandwidth"] > rate:
            if self._reserve(G, path[1:], rate):
                G[u_node][v_node]["bandwidth"] -= rate
                G[u_node][v_node]["weight"] = 1 / G[u_node][v_node]["bandwidth"]
                return True
            else:
                return False
        else:
            return False

    def _reroute(self, G: nx.Graph, calls: list, restore_or_adjust: bool):
        """
                 恢复                  调整
        成功      set路径和恢复次数      set路径
        失败      set路径和恢复次数      set
        """
        for call in calls:
            try:    # 成功
                reroute = nx.shortest_path(G, call.src, call.dst)
                if not self._reserve(G, reroute, call.rate):
                    raise Exception
                call.path = reroute
                if restore_or_adjust:
                    call.restoration += 1
            except: # 失败
                if restore_or_adjust:
                    # 若恢复
                    call.path = []
                    call.restoration += 1
                else:
                    # 若调整
                    pass
