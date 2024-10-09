import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from .fuzzy import Fuzzy
from .markov import Markov


class CAR:
    def __init__(self):
        self.algorithmName = "CAR"
        self.states = []
        self.factors = ["service_num", "node_num", "node_degree", "link_num", "link_distance"]
        self.trans_matrix = None
        self.sim_step = 4

    def routeCall(self, physicalTopology, event, routeTable):
        if not self.states:
            self.states = event.event.Available_Attack_Areas
        # 计算转移概率
        if self.trans_matrix is None:
            self.trans_matrix = self._calculate_transition_matrix(physicalTopology.get_area_info())
        # 计算攻击战略
        atk_area = event.event.target
        atk_tactics = self._trace_atk_tactics(atk_area)
        # 减除概率攻击地域
        prune_topo = self._prune_graph(physicalTopology.G, atk_tactics)
        # 重路由
        break_calls = self._find_calls(physicalTopology.G, physicalTopology.calls, atk_tactics)
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

    def _evaluate_attack_probabilities(self, area_info: dict):
        fuzzy = Fuzzy()
        fuzzy.init_fuzzy_evaluation(self.states, self.factors)
        for grade in self.states:
            for factor in self.factors:
                fuzzy.add_evaluation(grade, factor, area_info[grade][factor])
        prob = fuzzy.evaluate()
        return prob

    def _calculate_transition_matrix(self, area_info: dict):
        markov = Markov()
        markov.add_states(self.states)
        markov.init_trans_prob()
        for row, _ in enumerate(self.states):
            trans_prob = self._evaluate_attack_probabilities(area_info)
            for col, value in enumerate(trans_prob):
                markov.set_prob(row, col, value)
        return markov.trans_prob

    def _trace_atk_tactics(self, root: str):
        chain = nx.DiGraph()
        chain.add_node("root", id=root)
        chain.add_node("final", id=root)
        self._build_tree(chain, "root", self.sim_step, self.states)
        path = nx.shortest_path(chain, source="root", target="final", weight="weight")
        trace = [chain.nodes[i]["id"] for i in path[:-1]]
        return trace

    def _build_tree(self, chain, node, depth, children):
        if depth == 0:
            chain.add_edge(node, "final", weight=0)
            return
        for child in children:
            next = str(self.sim_step - depth)+str(child)
            weight = 1 / self.trans_matrix[children.index(chain.nodes[node]["id"])][children.index(child)]
            chain.add_node(next, id=child)
            chain.add_edge(node, next, weight=weight)
            self._build_tree(chain, next, depth-1, children)

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

    @staticmethod
    def _find_calls(G: nx.Graph, calls: list, target: list):
        target_calls = []
        for call in calls:
            if call.path is None:
                continue
            traverse_node = [G.nodes[node]["area"] for node in call.path]
            traverse_link = [area for (u, v) in zip(call.path[:-1], call.path[1:]) for area in G[u][v]["area"]]
            if set(traverse_node+traverse_link) & set(target):
                target_calls.append(call)
        return target_calls
