import numpy as np


class Fuzzy:
    def __init__(self):
        """
        fuzzy_evaluation = {
            'City A': {'importance': 5, 'defense': 3, 'cost': 2},
            'City B': {'importance': 4, 'defense': 4, 'cost': 3},
            'City C': {'importance': 3, 'defense': 2, 'cost': 5},
            'City D': {'importance': 2, 'defense': 5, 'cost': 4}
        }
        """
        self.states = []
        self.factors = []
        self.fuzzy_evaluation = {}
        self.weights = []

    def add_state(self, state: str):
        self.states.append(state)

    def add_states(self, states: list):
        self.states += states

    def add_factor(self, factor: str):
        self.factors.append(factor)

    def add_factors(self, factors: list):
        self.factors += factors

    def build_fuzzy_evaluation(self, ):
        # 1. 定义模糊评价指标及其模糊化
        # 模糊评价等级：重要性、高防御、攻击成本
        # 使用 1 到 5 评分（1 代表低，5 代表高）
        if not self.states:
            raise ValueError
        if not self.factors:
            raise ValueError


    @staticmethod
    def build_fuzzy_matrix(fuzzy_evaluation: dict, n_metrics: int):
        n_status = len(fuzzy_evaluation)
        fuzzy_matrix = np.zeros((n_status, n_metrics))
        for i, state in enumerate(fuzzy_evaluation):
            fuzzy_matrix[i] = []