import logging
import numpy as np

from network.topology import PhysicalTopology, LightpathTopology


class EavesdroppingRisk:
    """
    为节点与链路设置窃听风险共享链路组
    """
    def __init__(self):
        pass

    def setRiskNodeRandomly(self, physicalTopology: PhysicalTopology, ratio: float = 0.2):
        nodes = physicalTopology.G.nodes
        nodesNum = len(nodes)
        riskNodesNum = int(nodesNum * ratio)
        if riskNodesNum <= 0:
            raise Exception("The number of risk nodes can not be lower than 0.")
        riskNodes = np.random.choice(nodes, riskNodesNum)
        logging.info("{} - {} - Set {} eavesdropping risk nodes among {} nodes.".format(__file__, __name__, riskNodes, nodesNum))
        for i in range(nodesNum):
            if i in riskNodes:
                physicalTopology.G.nodes[i]["risk"] = True
            else:
                physicalTopology.G.nodes[i]["risk"] = False

    def setLinkRelevanceERSLG(self):
        """
        需要依据公式更新节点相关ESRLG和链路相关ESRLG
        :return:
        """
        pass