import networkx as nx
from collections import defaultdict


class NetState:
    """
    记录网络状态信息
    """
    def __init__(self):
        # 配置信息
        self.name = ""

