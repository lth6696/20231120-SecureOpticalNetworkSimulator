import networkx as nx
import numpy as np


class CAR:
    def __init__(self):
        self.algorithmName = "CAR"
        self.status = [range(14)]

    def routeCall(self, physicalTopology, event, routeTable):
        # 计算转移概率
        self._cal_markov()
        atk_node = event.event.atk_node
        markov_chain = nx.Graph()
        markov_chain.add_node(0, id=atk_node)
        for step in range(4):
            for i, next_atk_area in enumerate(self.status):
                trans_prob = self._cal_fuzzy_evaluation()
                markov_chain.add_node(step*len(self.status)+i+1, id=i)
                markov_chain.add_edge(_, i, weight=trans_prob)
        trace = nx.shortest_path(markov_chain, source=0, target=any)
        atk_route = [markov_chain[i]["id"] for i in trace]
        prune_topo = physicalTopology
        break_calls = []
        for call in break_calls:
            reroute = nx.shortest_path(prune_topo, call.src, call.dst)

    def removeCall(self, physicalTopology, event, routeTable):
        pass

    def _cal_markov(self):
        pass

    def _cal_fuzzy_evaluation(self):
        eval_func = [
            "service_num",
            "node_num",
            "node_degree"
            "link_num",
            "link_distance",
            "atk_times"
        ]
        weight = []
        R = []
        for next_area in []:
            R.append([getattr(self, i)() for i in eval_func])
        S = np.matmul(R, weight)
        return S

    def _eval_func(self):
        pass
