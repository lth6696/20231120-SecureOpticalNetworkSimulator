import logging

import networkx as nx


class Benchmark:
    def __init__(self):
        self._infinitesimal = 1e-5
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
        workingPath = {"physical": [], "optical": []}
        backupPath = {"physical": [], "optical": []}
        nodeSrc = event.call.sourceNode
        nodeDst = event.call.destinationNode
        eavesdroppingRiskLinkGroup = []
        availableWavelengths = {"work": None, "backup": None}
        try:
            # 光路拓扑计算可用工作路径
            path = nx.dijkstra_path(opticalTopology.G, nodeSrc, nodeDst, "weight")
            workingPath["optical"] = self._getAvailableLink(opticalTopology.G, path, event.call.requestBandwidth)
        except:
            # 物理拓扑新建工作路径
            try:
                path = nx.dijkstra_path(physicalTopology.G, nodeSrc, nodeDst, "weight")
                workingPath["physical"] = self._getAvailableLink(physicalTopology.G, path, event.call.requestBandwidth)
            except:
                # 若不存在工作路径，则阻塞业务
                logging.info("{} - {} - The {} service does not have working path.".format(__file__, __name__, event.call.id))
                return False
        if workingPath["optical"]:
            self._setEavesdroppingRiskSharedLinkGroup(opticalTopology.G, workingPath["optical"], eavesdroppingRiskLinkGroup)
            logging.info("{} - {} - The {} service is assigned the working path {} using exist lightpath.".format(__file__, __name__, event.call.id, workingPath["optical"]))
        elif workingPath["physical"]:
            self._setEavesdroppingRiskSharedLinkGroup(physicalTopology.G, workingPath["physical"], eavesdroppingRiskLinkGroup)
            logging.info("{} - {} - The {} service is assigned the working path {} established new lightpath.".format(__file__, __name__, event.call.id, workingPath["physical"]))
        else:
            logging.info("{} - {} - The {} service does not have working path.".format(__file__, __name__, event.call.id))
            return False

        # 光路拓扑计算可用保护路径
        try:
            auxG = self._constructAuxDiG(opticalTopology.G, risk=eavesdroppingRiskLinkGroup)
            path = nx.dijkstra_path(auxG, nodeSrc, nodeDst, "weight")
            backupPath["optical"] = path
        except:
            # 物理拓扑新建保护路径
            try:
                tempG = nx.DiGraph()
                tempG.add_nodes_from(physicalTopology.G.nodes)
                # 建立临时图，临时图不包括所有已用波长、共享风险的波长
                for link in physicalTopology.G.edges:
                    start = link[0]
                    end = link[1]
                    if "link_"+str(start)+"_"+str(end) in eavesdroppingRiskLinkGroup:
                        continue
                    usedWavelength = physicalTopology.G[start][end]["used-wavelength"]
                    wavelengths = int(physicalTopology.G[start][end]["wavelengths"])
                    weight = 1 / (sum([1 for i in range(wavelengths) if i not in usedWavelength]) + self._infinitesimal)
                    tempG.add_edge(start, end)
                    tempG[start][end]["weight"] = weight
                backupPath["new"] = nx.dijkstra_path(tempG, nodeSrc, nodeDst, "weight")
            except:
                pass
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
                eavesdroppingRiskLinkGroup.append("link_"+str(start)+"_"+str(end))
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

    def _constructAuxDiG(self, G: nx.MultiDiGraph, **kargs):
        # 建立临时图
        auxG = nx.MultiDiGraph()
        auxG.add_nodes_from(G.nodes)
        # 修剪波长
        for (start, end, index) in G.edges:
            # 去除已占用链路
            if "used" in kargs.keys() and G[start][end][index]["used"]:
                continue
            # 去除共享风险链路
            if "risk" in kargs.keys():
                riskName = []
                linkRisk = G[start][end][index]["risk"]
                if type(linkRisk) == bool:
                    riskName.append('_'.join(["link", start, end, index]))
                elif type(linkRisk) == list:
                    riskName += linkRisk
                if len(set(riskName) & set(kargs["risk"])) != 0:
                    continue
            auxG.add_edge(start, end, index)
        return auxG

    def _setEavesdroppingRiskSharedLinkGroup(self, G: nx.MultiDiGraph, path: list, ERSLG: list):
        for (start, end, index) in path:
            if type(G[start][end][index]["risk"]) == bool:
                ERSLG.append("link_"+str(start)+"_"+str(end)+"_"+str(index))
            elif type(G[start][end][index]["risk"]) == list:
                ERSLG += G[start][end][index]["risk"]

    def _getAvailableLink(self, G: nx.MultiDiGraph, path: list, requestBandwidth: int):
        pathTuple = []
        for (start, end) in zip(path[:-1], path[1:]):
            for index in G[start][end]:
                if G[start][end][index]["bandwidth"] >= requestBandwidth:
                    pathTuple.append((start, end, index))
                    break
        if len(pathTuple) != len(path) - 1:
            return None
        return pathTuple