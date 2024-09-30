import xml.etree.ElementTree as et
import numpy as np


class Traffic:
    def __init__(self, id: int, src: int, dst: int, rate: int):
        self.id = id
        self.src = src
        self.dst = dst
        self.rate = rate
        self.path = {}

    def set_path(self, path: dict):
        self.path = path


class TrafficGenerator:
    def __init__(self, configFile: str):
        self.num = 0
        self.traffic_rate = 0
        self.node_num = 0
        self.configFile = configFile

    def set_static_traffic(self):
        self._read_config()
        for i in range(self.num):
            node_pair = np.random.choice(list(range(self.node_num)), 2)
            # call = Traffic()
            pass

    def _read_config(self):
        xmlParser = et.parse(self.configFile)
        root = xmlParser.getroot()
        self.num = int(root.find("traffic").find("num").text)
        self.traffic_rate = int(root.find("traffic").find("bandwidth").text)
        self.node_num = len(root.find("topology").find("nodes"))
