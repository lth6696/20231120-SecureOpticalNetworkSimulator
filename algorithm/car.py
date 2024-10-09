import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import logging

from .fuzzy import Fuzzy
from .markov import Markov


class CAR:
    def __init__(self):
        self.algorithmName = "CAR"
        self.states = []
        self.factors = ["service_num", "node_num", "node_degree", "link_num", "attack_num", "span_length"]
        self.area_info = None
        self.trans_matrix = None
        self.sim_step = 4
        self.unable_areas = []
        self.potential_areas = []

    def routeCall(self, physicalTopology, event, routeTable):
        if not self.states:
            self.states = event.event.Available_Attack_Areas
        if self.area_info is None:
            self.area_info = physicalTopology.get_area_info()
        atk_area = event.event.target
        self.unable_areas.append(atk_area)
        self.area_info[atk_area]["attack_num"] += 1
        # 恢复
        prune_topo = self._prune_graph(physicalTopology.G, self.unable_areas)
        logging.info("Prune topology has {} nodes.".format(prune_topo.nodes))
        break_calls = self._find_calls(physicalTopology.G, physicalTopology.calls, self.unable_areas)
        for call in break_calls:
            try:
                reroute = nx.shortest_path(prune_topo, call.src, call.dst)
                call.path = reroute
                logging.info("The {} call is restored.".format(call.id))
            except:
                call.path = None
                logging.info("The {} call is blocked.".format(call.id))
            finally:
                call.restore_times += 1
        # 计算转移概率
        self._update_area_info(atk_area, prune_topo, physicalTopology.calls)
        self.trans_matrix = self._calculate_transition_matrix(self.area_info)
        # 计算攻击战略
        atk_tactics = self._trace_atk_tactics(atk_area)
        self.potential_areas = list(set(atk_tactics))
        logging.info("Attacked areas: {}".format(self.unable_areas))
        logging.info("Potential areas: {}".format(self.potential_areas))
        # 调整
        prune_topo = self._prune_graph(physicalTopology.G, self.potential_areas+self.unable_areas)
        break_calls = self._find_calls(physicalTopology.G, physicalTopology.calls, self.potential_areas)
        for call in break_calls:
            try:
                reroute = nx.shortest_path(prune_topo, call.src, call.dst)
                call.path = reroute
                logging.info("The {} call is changed.".format(call.id))
            except:
                pass

    def removeCall(self, physicalTopology, event, routeTable):
        self.unable_areas.remove(event.event.target)
        logging.info("After departure event {}, unable areas have {}.".format(event.event.id, self.unable_areas))
        # 拓扑剪枝
        prune_topo = self._prune_graph(physicalTopology.G, self.unable_areas+self.potential_areas)
        for call in physicalTopology.calls:
            if call.path:
                continue
            try:
                reroute = nx.shortest_path(prune_topo, call.src, call.dst)
                call.path = reroute
                logging.info("The {} call find path.".format(call.id))
            except:
                pass

    def _update_area_info(self, atk_area, prune_topo=None, calls=None):
        areas = sorted([area for area in self.area_info.keys()])
        for area in self.area_info.keys():
            self.area_info[area]["span_length"] = max(0, self.sim_step - abs(areas.index(atk_area) - areas.index(area)) + 1)
        if prune_topo is None and calls is None:
            return self.area_info
        for area in self.area_info.keys():
            self.area_info[area]["link_num"] = 0
            self.area_info[area]["node_degree"] = 0
            self.area_info[area]["node_num"] = 0
            self.area_info[area]["service_num"] = 0
        # 计算节点信息
        node_degree = dict(prune_topo.degree())
        for node in node_degree:
            self.area_info[prune_topo.nodes[node]["area"]]["node_degree"] += node_degree[node]
            self.area_info[prune_topo.nodes[node]["area"]]["node_num"] += 1
        # 计算链路信息
        for u, v, data in prune_topo.edges(data=True):
            for area in data["area"]:
                self.area_info[area]["link_num"] += 1
        # 计算业务信息
        for call in calls:
            if call.path is None:
                continue
            for node in call.path:
                self.area_info[prune_topo.nodes[node]["area"]]["service_num"] += 1
        return self.area_info

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
        for row, atk in enumerate(self.states):
            self._update_area_info(atk)
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
        trace = [chain.nodes[i]["id"] for i in path[1:-1] if chain.nodes[i]["id"] != root]
        print(trace)
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
                logging.info("The {} call passes areas: {}".format(call.id, set(traverse_node + traverse_link)))
        return target_calls
