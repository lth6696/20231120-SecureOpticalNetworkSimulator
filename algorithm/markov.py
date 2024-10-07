import numpy as np


class Markov:
    def __init__(self):
        self.states = []
        self.trans_prob = None
        self.chain = None

    def add_states(self, states: list):
        self.states = states

    def init_trans_prob(self):
        if not self.states:
            raise ValueError
        self.trans_prob = np.zeros((len(self.states), len(self.states)))

    def set_prob(self, row: int, col: int, value: float):
        shape = np.shape(self.trans_prob)
        if row > shape[0] or col > shape[1]:
            raise ValueError
        self.trans_prob[row][col] = value
