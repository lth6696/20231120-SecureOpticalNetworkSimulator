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
     - risk: int, 节点是否存在风险
    """
    def __init__(self):
        self._topologyInfoModuleName = "topology"
        self._nodeInfoModuleName = "nodes"
        self._linkInfoModuleName = "links"
        self._infinitesimal = 1e-5
        self.G = nx.MultiDiGraph()
        self.maxBandwidth = 100000

    def constructGraph(self, configFile: str):
        # 检查输入
        if not os.path.exists(configFile):
            raise Exception("Config file does not exist.")
        logging.info("{} - {} - Read the config file \"{}\".".format(__file__, __name__, configFile))
        xmlParser = et.parse(configFile)
        # 读取配置文件中的拓扑信息
        elementTopo = xmlParser.getroot().find(self._topologyInfoModuleName)
        if elementTopo is None:
            raise Exception("Config file does not include the topology information.")
        # 添加节点和链路
        for element in elementTopo:
            if element.tag == self._nodeInfoModuleName:
                for id, node in enumerate(element):
                    nodeTag = node.attrib
                    self.G.add_node(id, **nodeTag)
            elif element.tag == self._linkInfoModuleName:
                wavelengths = int(element.attrib["wavelengths"])
                for link in element:
                    linkTag = link.attrib
                    # 设置链路属性
                    if "bandwidth" not in link.keys():
                        raise Exception("Links have no bandwidth attribute.")
                    linkTag["source"] = int(linkTag["source"])
                    linkTag["destination"] = int(linkTag["destination"])
                    linkTag["id"] = int(linkTag["id"])
                    linkTag["bandwidth"] = float(linkTag["bandwidth"])
                    linkTag["max-bandwidth"] = float(linkTag["max-bandwidth"])
                    linkTag["used"] = False
                    linkTag["weight"] = 1 / (linkTag["bandwidth"] + self._infinitesimal)
                    linkTag["risk"] = linkTag["risk"].split("_")
                    for i in range(wavelengths):
                        if "source" in link.keys() and "destination" in link.keys():
                            self.G.add_edge(int(link.attrib["source"]), int(link.attrib["destination"]), i, **linkTag)
                        else:
                            raise Exception("Tag 'link' does not have source and destination nodes.")
        logging.info("{} - {} - Add {} nodes and {} links.".format(__file__, __name__, len(self.G.nodes), len(self.G.edges)))