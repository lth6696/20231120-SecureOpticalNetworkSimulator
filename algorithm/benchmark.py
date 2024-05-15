import networkx as nx


class Benchmark:
    def __init__(self):
        self.algorithmName = "benchmark"

    # def routeCall(self, physicalTopology: PhysicalTopology, opticalTopology: LightpathTopology, event: Event):
    def routeCall(self, physicalTopology, opticalTopology, event):
        """
        Algorithm pseudocode:
        1. 计算工作路径。若光路拓扑没有可用路径，则基于物理拓扑新建光路。对于物理拓扑，修建掉已占用的波长后，构建临时图。计算最短路径并基于FirstFit分配波长，更新光路拓扑。
        2. 基于路径加密情况，更新窃听风险链路共享组。
        3. 计算保护路径。删除工作路径所用光路，删除和工作路径共享风险的光路，构建临时光路图，若不存在路径，则基于物理拓扑新建光路。对于物理拓扑，删除已占用波长、与工作路径共享风险波长，构建临时图并计算路径。
        4. 更新窃听风险共享链路组。
        5. 若存在工作路径与保护路径，则输出并退出；若不存在，则锁定业务。
        :return:
        """
        sourceNode = event.call.sourceNode
        destinationNode = event.call.destinationNode
        try:
            workingPath = nx.dijkstra_path(opticalTopology.G, sourceNode, destinationNode)
        except:
            tempG = nx.DiGraph()
            tempG.add_nodes_from(physicalTopology.G.nodes)
            for link in physicalTopology.G.edges:
                start = link[0]
                end = link[1]
                usedWavelength = physicalTopology.G[start][end]["used-wavelength"]
                wavelengths = physicalTopology.G[start][end]["wavelengths"]
                for i in range(wavelengths):
                    if i in usedWavelength:
                        continue
                    

    def removeCall(self):
        pass