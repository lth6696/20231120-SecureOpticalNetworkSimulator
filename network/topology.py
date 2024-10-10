import logging
import os.path
import networkx as nx
import xml.etree.ElementTree as et


class PhysicalTopology:
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
        logging.info(
            "{} - {} - Add {} nodes and {} links.".format(__file__, __name__, len(self.G.nodes), len(self.G.edges)))

    def route(self, calls: list, weight: str = None):
        for call in calls:
            try:
                path = nx.shortest_path(self.G, call.src, call.dst, weight=weight)
                if self.reserve(self.G, path, call.rate):
                    call.path = path
            except:
                pass
        self.calls = [call for call in calls if call.path is not None]

    def reserve(self, G, path, rate):
        if len(path) <= 1:
            return True
        u_node = path[0]
        v_node = path[1]
        if G[u_node][v_node]["bandwidth"] > rate:
            if self.reserve(G, path[1:], rate):
                G[u_node][v_node]["bandwidth"] -= rate
                G[u_node][v_node]["weight"] = 1 / G[u_node][v_node]["bandwidth"]
                return True
            else:
                return False
        else:
            return False
