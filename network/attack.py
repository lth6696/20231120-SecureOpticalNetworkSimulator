import numpy as np

from network.state import NetState


class Attack:
    Available_Attack_Strategy = ["random", "node", "link"]

    def __init__(self):
        self.id = None
        self.target = None
        self.duration = None

    def set(self, id: int, duration: float, strategy: str, net_state: NetState, attacked_regions: list):
        if duration < 0.0:
            raise Exception("Invalid parameters set to the call.")
        self.id = id
        self.target = self._get_attack_region(strategy, net_state, attacked_regions)
        self.duration = duration
        return self

    def _get_attack_region(self, strategy: str, net_state: NetState, attacked_regions: list):
        if strategy not in self.Available_Attack_Strategy:
            raise ValueError
        return getattr(self, "_"+strategy)(net_state, attacked_regions)

    def _random(self, net_state: NetState, attacked_regions: list):
        available_regions = [region for region in net_state.net_state.keys() if region not in attacked_regions]
        return np.random.choice(available_regions)

    def _link(self, net_state: NetState, attacked_regions: list):
        services_within_region = [(region, net_state.net_state[region]["amount_service"]) for region in net_state.net_state.keys() if region not in attacked_regions]
        services_within_region.sort(key=lambda x: x[1], reverse=True)
        return services_within_region.pop(0)[0]

    def _node(self, net_state: NetState, attacked_regions: list):
        node_degree = [(region, net_state.net_state[region]["degree_node"]) for region in net_state.net_state.keys() if region not in attacked_regions]
        node_degree.sort(key=lambda x: x[1], reverse=True)
        return node_degree.pop(0)[0]
