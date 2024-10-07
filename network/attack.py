import numpy as np


class Attack:
    Available_Attack_Areas = [
        # "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        # "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        # "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        # "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        # "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        'AL', 'AR', 'AX', 'CA', 'CO', 'GA', 'IA', 'ID', 'IL', 'KY',
        'LA', 'MD', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NF',
        'NJ', 'NM', 'NV', 'NY', 'OR', 'PA', 'RA', 'SC', 'TN', 'TX',
        'UT', 'WA', 'WI'
    ]
    Available_Attack_Strategy = ["random"]

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

    def atk_area(self, strategy: str):
        if strategy not in self.Available_Attack_Strategy:
            raise ValueError
        return getattr(self, "_"+strategy)()

    def _random(self):
        return np.random.choice(self.Available_Attack_Areas)