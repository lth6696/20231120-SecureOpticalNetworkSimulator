import os
import xml.etree.ElementTree as et

from network import topology


class AreaInfo:
    def __init__(self, configFile: str):
        self._areaModuleName = "areas"
        self._areaNodeName = "area"
        self.areas = []
        self.info = []
        self.area_info = None

        self.init(configFile)

    def init(self, configFile: str):
        # 检查输入
        if not os.path.exists(configFile):
            raise Exception("Config file does not exist.")
        xmlParser = et.parse(configFile)
        root = xmlParser.getroot()
        self.info = root.find(self._areaModuleName).attrib['info'].split(",")
        for node in root.find(self._areaModuleName).findall(self._areaNodeName):
            self.areas.append(eval(node.attrib['type'])(node.text))

    def get(self, topo: topology.PhysicalTopology):
        self.area_info = {area: {info: 0 for info in self.info} for area in self.areas}
        # 计算节点信息
        node_degree = dict(topo.G.degree())
        for node in node_degree:
            self.area_info[topo.G.nodes[node]["area"]]["node_degree"] += node_degree[node]
            self.area_info[topo.G.nodes[node]["area"]]["node_num"] += 1
        # 计算链路信息
        for u, v, data in topo.G.edges(data=True):
            for area in data["area"]:
                self.area_info[area]["link_num"] += 1
        # 计算业务信息
        for call in topo.calls:
            for node in call.path:
                self.area_info[topo.G.nodes[node]["area"]]["service_num"] += 1
        return self.area_info

    def update(self, atk_area):
        for area in self.areas:
            self.area_info[area]["span_length"] = len(self.areas) - abs(self.areas.index(area) - self.areas.index(atk_area))
