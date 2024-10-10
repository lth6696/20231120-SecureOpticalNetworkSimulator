import logging

import numpy as np


class Fuzzy:
    def __init__(self):
        self.grades = []
        self.factors = []
        self.fuzzy_evaluation = {}
        self.weights = []

    def add_grade(self, grade: str):
        self.grades.append(grade)

    def add_grades(self, grades: list):
        self.grades += grades

    def add_factor(self, factor: str):
        self.factors.append(factor)

    def add_factors(self, factors: list):
        self.factors += factors

    def add_evaluation(self, grade: str, factor: str, value: float):
        # add one evaluation of the factor for the grade
        # 使用 0 到 1 评分（0 代表低，1 代表高）
        if grade not in self.grades or factor not in self.factors:
            raise ValueError
        if self.fuzzy_evaluation == {}:
            raise ValueError
        self.fuzzy_evaluation[grade][factor] = value

    def init_fuzzy_evaluation(self, grades: list = None, factors: list = None):
        # 1. 定义模糊评价指标及其模糊化
        """
        fuzzy_evaluation = {
            'City A': {'importance': 5, 'defense': 3, 'cost': 2},
            'City B': {'importance': 4, 'defense': 4, 'cost': 3},
            'City C': {'importance': 3, 'defense': 2, 'cost': 5},
            'City D': {'importance': 2, 'defense': 5, 'cost': 4}
        }
        """
        if not self.grades and grades:
            self.grades = grades
        else:
            raise ValueError
        if not self.factors and factors:
            self.factors = factors
        else:
            raise ValueError
        self.fuzzy_evaluation = {grade: {factor: 0 for factor in self.factors} for grade in self.grades}

    def set_weight(self, weights: list):
        # 2. 定义评价指标的权重向量
        # 权重向量表示每个指标对攻击者决策的影响程度
        if len(weights) != len(self.factors):
            raise ValueError
        self.weights = weights

    def build_fuzzy_matrix(self):
        # 3. 构造模糊评价矩阵
        fuzzy_matrix = np.zeros((len(self.factors), len(self.grades)))
        for i, grade in enumerate(self.fuzzy_evaluation):
            fuzzy_matrix[:, i] = np.array([self.fuzzy_evaluation[grade][factor] for factor in self.factors]).T
        return fuzzy_matrix

    def evaluate(self, weights: list = None):
        # 4. 进行模糊综合评价
        # 将模糊评价矩阵和权重向量相乘，得到每个城市的模糊评价值
        # 这里我们将模糊评价值归一化为概率值
        if weights:
            self.set_weight(weights)
        if not self.weights:
            self.weights = [1 for _ in self.factors]
        fuzzy_matrix = self._normalization(self.build_fuzzy_matrix())
        fuzzy_scores = np.dot(np.array(self.weights), np.array(fuzzy_matrix))
        evaluation_probabilities = fuzzy_scores / np.sum(fuzzy_scores) * 100
        return evaluation_probabilities

    @staticmethod
    def _normalization(data):
        norm_data = np.zeros(shape=data.shape)
        for i, row in enumerate(data):
            _range = np.max(row) - np.min(row)
            norm_data[i] = (row - np.min(row)) / _range
        return norm_data
