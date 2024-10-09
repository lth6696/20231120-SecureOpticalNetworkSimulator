import numpy as np


class Attack:
    Available_Attack_Areas = [
        # "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        # "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        # "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        # "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        # "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        'AL', 'AR', 'AX', 'CA', 'CO', 'GA', 'IA', 'ID', 'IL', 'KY',
        'LA', 'MD', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NF',
        'NJ', 'NM', 'NV', 'NY', 'OR', 'PA', 'RA', 'SC', 'TN', 'TX',
        'UT', 'WA', 'WI'
    ]
    Available_Attack_Strategy = ["random", "degree", "service", "number"]

    def __init__(self):
        self.id = None
        self.target = None
        self.duration = None

    def set(self, id: int, target: str, duration: float):
        if duration < 0.0:
            raise Exception("Invalid parameters set to the call.")
        self.id = id
        self.target = target
        self.duration = duration

    def atk_area(self, strategy: str, area_info: dict):
        if strategy not in self.Available_Attack_Strategy:
            raise ValueError
        return getattr(self, "_"+strategy)(area_info)

    def _random(self, area_info: dict):
        return np.random.choice(self.Available_Attack_Areas)

    def _degree(self, area_info: dict):
        node_degree = [(area, area_info[area]["node_degree"]) for area in area_info]
        degree_sum = sum([val[1] for val in node_degree])
        node_degree = [(area, degree/degree_sum) for (area, degree) in node_degree]
        return np.random.choice([area for (area, degree) in node_degree], p=[degree for (area, degree) in node_degree])

    def _service(self, area_info: dict):
        service_num = [(area, area_info[area]["service_num"]) for area in area_info]
        degree_sum = sum([val[1] for val in service_num])
        node_degree = [(area, degree / degree_sum) for (area, degree) in service_num]
        return np.random.choice([area for (area, degree) in node_degree], p=[degree for (area, degree) in node_degree])

    def _number(self, area_info: dict):
        num = [(area, area_info[area]["node_num"]+area_info[area]["link_num"]) for area in area_info]
        degree_sum = sum([val[1] for val in num])
        node_degree = [(area, degree / degree_sum) for (area, degree) in num]
        return np.random.choice([area for (area, degree) in node_degree], p=[degree for (area, degree) in node_degree])
