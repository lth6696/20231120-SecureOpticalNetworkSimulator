import logging
import os.path
import networkx as nx
import xml.etree.ElementTree as et


class PhysicalTopology:
    """
    由光纤和节点组成的物理拓扑
    链路包含属性：
     - bandwidth: int, 链路可用带宽
     - used: bool, 链路是否被占用
     - risk: str, 链路风险（非必要？）
     - weight: float, 链路权重
    节点包含属性:
     - area: str
    """
    AreaInfoType = ["service_num", "node_num", "node_degree", "link_num", "link_distance"]
    Areas = [
        'AL', 'AR', 'AX', 'CA', 'CO', 'GA', 'IA', 'ID', 'IL', 'KY',
        'LA', 'MD', 'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NF',
        'NJ', 'NM', 'NV', 'NY', 'OR', 'PA', 'RA', 'SC', 'TN', 'TX',
        'UT', 'WA', 'WI'
    ]

    def __init__(self):
        self._topologyInfoModuleName = "topology"
        self._nodeInfoModuleName = "nodes"
        self._linkInfoModuleName = "links"
        self._infinitesimal = 1e-5
        self.G = nx.Graph()
        self.maxBandwidth = 100000
        self.calls = []

    def constructGraph(self, configFile: str):
        # 检查输入
        if not os.path.exists(configFile):
            raise Exception("Config file does not exist.")
        logging.info("{} - {} - Read the config file \"{}\".".format(__file__, __name__, configFile))
        xmlParser = et.parse(configFile)
        root = xmlParser.getroot()
        # 添加节点和链路
        def get_attr(element):
            attr = {child.tag: eval(child.attrib['type'])(child.text) for child in element}
            return attr
        for id, node in enumerate(root.find(self._topologyInfoModuleName).find(self._nodeInfoModuleName)):
            self.G.add_node(id, **get_attr(node))
        for link in root.find(self._topologyInfoModuleName).find(self._linkInfoModuleName):
            attr = get_attr(link)
            attr['area'] = attr['area'].split(',')
            self.G.add_edge(attr['u_node'], attr['v_node'], **attr)
        logging.info("{} - {} - Add {} nodes and {} links.".format(__file__, __name__, len(self.G.nodes), len(self.G.edges)))

    def route(self, calls: list):
        for call in calls:
            try:
                path = nx.shortest_path(self.G, call.src, call.dst)
            except:
                path = []
            if not path:
                continue
            call.path = path

    def get_area_info(self):
        # "service_num", "node_num", "node_degree" "link_num", "link_distance"
        area_info = {area: {info: 0 for info in self.AreaInfoType} for area in self.Areas}
        # 计算节点信息
        node_degree = dict(self.G.degree())
        for node in node_degree:
            area_info[self.G.nodes[node]["area"]]["node_degree"] += node_degree[node]
            area_info[self.G.nodes[node]["area"]]["node_num"] += 1
        # 计算链路信息
        for u, v, data in self.G.edges(data=True):
            for area in data["area"]:
                area_info[area]["link_num"] += 1
        # 计算业务信息
        for call in self.calls:
            for node in call.path:
                area_info[self.G.nodes[node]["area"]]["service_num"] += 1
        return area_info
