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