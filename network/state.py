import networkx as nx
from collections import defaultdict


class NetState:
    DEFAULT_STATE = {"amount_node", "amount_service", "amount_attack", "distance", "degree_node"}

    def __init__(self):
        self.regions = []
        self.used_states = []
        self.net_state = None

    def get(self, G: nx.Graph, calls: list, **kwargs):
        # 获取使用的网络状态
        self._get_states(**kwargs)
        # 获取网络地理位置信息
        self._get_regions(G)
        # 获取网络状态信息
        self.net_state = {region: {state: 0 for state in self.used_states} for region in self.regions}
        for state in self.used_states:
            if state == "amount_node":
                for node in G.nodes:
                    self.net_state[node][state] += 1
            elif state == "degree_node":
                node_degree = dict(G.degree())
                for node in node_degree:
                    self.net_state[node][state] += node_degree[node]
            elif state == "amount_service":
                for call in calls:
                    for node in call.path:
                        self.net_state[node]["amount_service"] += 1
            elif state == "amount_attack":
                pass
            elif state == "distance":
                pass
        return self.net_state

    def _get_states(self, **kwargs):
        for _, val in kwargs.items():
            if val not in self.DEFAULT_STATE:
                raise ValueError
            self.used_states.append(val)

    def _get_regions(self, G: nx.Graph):
        for node in G.nodes():
            if node not in self.regions:
                self.regions.append(node)

    def update(self, G: nx.Graph, calls: list, attacked_regions: list, specify: str = None):
        if specify is not None and specify in self.used_states:
            states = [specify]
        else:
            states = self.used_states
            self.net_state = {region: {state: 0 for state in self.used_states} for region in self.regions}
        for state in states:
            if state == "amount_node":
                for node in G.nodes:
                    self.net_state[node][state] += 1
            elif state == "degree_node":
                node_degree = dict(G.degree())
                for node in node_degree:
                    self.net_state[node][state] += node_degree[node]
            elif state == "amount_service":
                for call in calls:
                    for node in call.path:
                        self.net_state[node]["amount_service"] += 1
            elif state == "amount_attack":
                for atk_region in attacked_regions:
                    self.net_state[atk_region][state] += 1
            elif state == "distance":
                current_attacked_region = attacked_regions[-1]
                for node, data in G.nodes(data=True):
                    distance = ((G.nodes[current_attacked_region]["Latitude"] - G.nodes[node]["Latitude"])**2 +
                                (G.nodes[current_attacked_region]["Longitude"] - G.nodes[node]["Longitude"])**2)**0.5
                    self.net_state[node][state] += distance
        return self.net_state
