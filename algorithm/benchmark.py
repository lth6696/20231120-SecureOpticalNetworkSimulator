import logging

import networkx as nx


class Benchmark:
    def __init__(self):
        self.algorithmName = "benchmark"

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
        workingPath = {"exist": None, "new": None}
        backupPath = {"exist": None, "new": None}
        sourceNode = event.call.sourceNode
        destinationNode = event.call.destinationNode
        erslg = []
        availableWavelengths = {"work": None, "backup": None}
        # 检查光路拓扑是否存在可用工作路径
        try:
            workingPath["exist"] = nx.dijkstra_path(opticalTopology.G, sourceNode, destinationNode, "weight")
        # 若光路拓扑不存在可用工作路径，则基于物理拓扑新建光路
        except:
            tempG = nx.DiGraph()
            tempG.add_nodes_from(physicalTopology.G.nodes)
            # 建立临时图，临时图不包括所有已用波长
            for link in physicalTopology.G.edges:
                start = link[0]
                end = link[1]
                usedWavelength = physicalTopology.G[start][end]["used-wavelength"]
                wavelengths = int(physicalTopology.G[start][end]["wavelengths"])
                weight = 1 / sum([1 for i in range(wavelengths) if i not in usedWavelength])
                tempG.add_edge(start, end)
                tempG[start][end]["weight"] = weight
            workingPath["new"] = nx.dijkstra_path(tempG, sourceNode, destinationNode, "weight")
        if workingPath["exist"] is None and workingPath["new"] is None:
            # 若不存在工作路径，则阻塞业务
            logging.info("{} - {} - The {} service does not have working path.".format(__file__, __name__, event.call.id))
            return False
        elif workingPath["exist"] is not None:
            # 若存在工作路径，则更新光路拓扑，并设置SRLG
            logging.info("{} - {} - The {} service is assigned the working path {} using exist lightpath.".format(__file__, __name__, event.call.id, workingPath["exist"]))
            for (start, end) in zip(workingPath["exist"][:-1], workingPath["exist"][1:]):
                for index in opticalTopology.G[start][end]:
                    if opticalTopology.G[start][end][index]["bandwidth"] >= event.call.requestBandwidth:
                        erslg += opticalTopology.G[start][end][index]["risk"]
        elif workingPath["new"] is not None:
            availableWavelengths["work"] = set(i for i in range(48))
            for (start, end) in zip(workingPath["new"][:-1], workingPath["new"][1:]):
                usedWavelength = physicalTopology.G[start][end]["used-wavelength"]
                wavelengths = int(physicalTopology.G[start][end]["wavelengths"])
                availableWavelengths["work"] = availableWavelengths["work"] & set(i for i in range(wavelengths) if i not in usedWavelength)
                erslg.append("link_"+str(start)+"_"+str(end))
            if len(availableWavelengths["work"]) == 0:
                logging.info("{} - {} - The {} service does not have working path.".format(__file__, __name__, event.call.id))
                return False
            logging.info("{} - {} - The {} service is assigned the working path {} established new lightpath.".format(__file__, __name__, event.call.id, workingPath["new"]))

        # 检查光路拓扑是否存在可用保护路径
        try:
            tempG = nx.MultiDiGraph()
            tempG.add_nodes_from(opticalTopology.G.nodes)
            for link in opticalTopology.G.edges:
                start = link[0]
                end = link[1]
                index = link[2]
                if len(set(opticalTopology.G[start][end][index]["risk"]) & set(erslg)) != 0:
                    continue
                if (start, end) in list(zip(workingPath["exist"][:-1], workingPath["exist"][1:])):
                    continue
            backupPath["exist"] = nx.dijkstra_path(tempG, sourceNode, destinationNode, "weight")
        # 若光路拓扑不存在，则新建光路
        except:
            tempG = nx.DiGraph()
            tempG.add_nodes_from(physicalTopology.G.nodes)
            # 建立临时图，临时图不包括所有已用波长、共享风险的波长
            for link in physicalTopology.G.edges:
                start = link[0]
                end = link[1]
                if "link_"+str(start)+"_"+str(end) in erslg:
                    continue
                usedWavelength = physicalTopology.G[start][end]["used-wavelength"]
                wavelengths = int(physicalTopology.G[start][end]["wavelengths"])
                weight = 1 / sum([1 for i in range(wavelengths) if i not in usedWavelength])
                tempG.add_edge(start, end)
                tempG[start][end]["weight"] = weight
            backupPath["new"] = nx.dijkstra_path(tempG, sourceNode, destinationNode, "weight")
        if backupPath["exist"] is None and backupPath["new"] is None:
            # 若不存在保护路径，则阻塞业务
            logging.info("{} - {} - The {} service does not have backup path.".format(__file__, __name__, event.call.id))
            return False
        elif backupPath["exist"] is not None:
            # 若存在保护路径，则更新光路拓扑，并设置SRLG
            logging.info("{} - {} - The {} service is assigned the backup path {} using exist lightpath.".format(__file__, __name__, event.call.id, backupPath["exist"]))
        elif backupPath["new"] is not None:
            availableWavelengths["backup"] = set(i for i in range(48))
            for (start, end) in zip(backupPath["new"][:-1], backupPath["new"][1:]):
                usedWavelength = physicalTopology.G[start][end]["used-wavelength"]
                wavelengths = int(physicalTopology.G[start][end]["wavelengths"])
                availableWavelengths["backup"] = availableWavelengths["backup"] & set(i for i in range(wavelengths) if i not in usedWavelength)
                erslg.append("link_"+str(start)+"_"+str(end))
            if len(availableWavelengths["backup"]) == 0:
                logging.info("{} - {} - The {} service does not have backup path.".format(__file__, __name__, event.call.id))
                return False
            logging.info("{} - {} - The {} service is assigned the backup path {} established new lightpath.".format(__file__, __name__, event.call.id, backupPath["new"]))

        if workingPath["new"] is not None:
            # 更新物理拓扑
            availableBandwidth = []
            risk = []
            for (start, end) in zip(workingPath["new"][:-1], workingPath["new"][1:]):
                physicalTopology.G[start][end]["used-wavelength"].append(list(availableWavelengths["work"])[0])
                if event.call.requestSecurity == 0:
                    risk.append("link_"+str(start)+"_"+str(end))
                availableBandwidth.append(int(physicalTopology.G[start][end]["bandwidth"]))
            # 更新光路拓扑
            wavelength = list(availableWavelengths["work"])[0]
            opticalTopology.G.add_edge(workingPath["new"][0], workingPath["new"][-1], wavelength)
            opticalTopology.G[workingPath["new"][0]][workingPath["new"][-1]][wavelength]["used-wavelength"] = wavelength
            opticalTopology.G[workingPath["new"][0]][workingPath["new"][-1]][wavelength]["bandwidth"] = min(availableBandwidth)
            opticalTopology.G[workingPath["new"][0]][workingPath["new"][-1]][wavelength]["weight"] = 1 / min(availableBandwidth)
            opticalTopology.G[workingPath["new"][0]][workingPath["new"][-1]][wavelength]["risk"] = risk
        if backupPath["new"] is not None:
            # 更新物理拓扑
            availableBandwidth = []
            risk = []
            for (start, end) in zip(backupPath["new"][:-1], backupPath["new"][1:]):
                physicalTopology.G[start][end]["used-wavelength"].append(list(availableWavelengths["backup"])[0])
                if event.call.requestSecurity == 0:
                    risk.append("link_" + str(start) + "_" + str(end))
                availableBandwidth.append(int(physicalTopology.G[start][end]["bandwidth"]))
            # 更新光路拓扑
            wavelength = list(availableWavelengths["backup"])[0]
            opticalTopology.G.add_edge(backupPath["new"][0], backupPath["new"][-1], wavelength)
            opticalTopology.G[backupPath["new"][0]][backupPath["new"][-1]][wavelength]["used-wavelength"] = wavelength
            opticalTopology.G[backupPath["new"][0]][backupPath["new"][-1]][wavelength]["bandwidth"] = min(availableBandwidth)
            opticalTopology.G[backupPath["new"][0]][backupPath["new"][-1]][wavelength]["weight"] = 1 / min(availableBandwidth)
            opticalTopology.G[backupPath["new"][0]][backupPath["new"][-1]][wavelength]["risk"] = risk

    def removeCall(self):
        pass