import logging

import networkx as nx


class Benchmark:
    def __init__(self):
        self._infinitesimal = 1e-5
        self.algorithmName = "benchmark"

    def routeCall(self, physicalTopology, opticalTopology, event, routeTable):
        """
        Algorithm pseudocode:
        1. 计算工作路径。若光路拓扑没有可用路径，则基于物理拓扑新建光路。对于物理拓扑，修建掉已占用的波长后，构建临时图。计算最短路径并基于FirstFit分配波长，更新光路拓扑。
        2. 基于路径加密情况，更新窃听风险链路共享组。
        3. 计算保护路径。删除工作路径所用光路，删除和工作路径共享风险的光路，构建临时光路图，若不存在路径，则基于物理拓扑新建光路。对于物理拓扑，删除已占用波长、与工作路径共享风险波长，构建临时图并计算路径。
        4. 更新窃听风险共享链路组。
        5. 若存在工作路径与保护路径，则输出并退出；若不存在，则锁定业务。
        :return:
        """
        nodeSrc = event.call.sourceNode
        nodeDst = event.call.destinationNode
        workingPath = {"physical": [], "optical": []}
        backupPath = {"physical": [], "optical": []}
        eavesdroppingRiskLinkGroup = []
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
            auxG = self._constructAuxMultiDiG(opticalTopology.G, risk=eavesdroppingRiskLinkGroup)
            path = nx.dijkstra_path(auxG, nodeSrc, nodeDst, "weight")
            backupPath["optical"] = self._getAvailableLink(auxG, path, event.call.requestBandwidth)
        except:
            # 物理拓扑新建保护路径
            try:
                auxG = self._constructAuxMultiDiG(physicalTopology.G, risk=eavesdroppingRiskLinkGroup)
                path = nx.dijkstra_path(auxG, nodeSrc, nodeDst, "weight")
                backupPath["physical"] = self._getAvailableLink(auxG, path, event.call.requestBandwidth)
            except:
                # 若不存在保护路径，则阻塞业务
                logging.info("{} - {} - The {} service does not have backup path.".format(__file__, __name__, event.call.id))
                return False
        if backupPath["optical"]:
            # 若存在保护路径，则更新光路拓扑，并设置SRLG
            logging.info("{} - {} - The {} service is assigned the backup path {} using exist lightpath.".format(__file__, __name__, event.call.id, backupPath["optical"]))
        elif backupPath["physical"]:
            logging.info("{} - {} - The {} service is assigned the backup path {} established new lightpath.".format(__file__, __name__, event.call.id, backupPath["physical"]))
        else:
            logging.info("{} - {} - The {} service does not have backup path.".format(__file__, __name__, event.call.id))
            return False
        # 更新拓扑信息
        workingPath = self._updateNetState(workingPath, opticalTopology.G, physicalTopology.G, event)
        backupPath = self._updateNetState(backupPath, opticalTopology.G, physicalTopology.G, event)
        # 更新路由表
        routeTable[event.call.id] = {"workingPath": workingPath, "backupPath": backupPath}
        return True

    def removeCall(self, physicalTopology, opticalTopology, event, routeTable):
        if event.call.id not in routeTable.keys():
            # 若业务被阻塞
            return False
        # 光路：删减业务、增加带宽、更新权重。
        path = routeTable[event.call.id]
        for pathType in path.keys():
            for (start, end, index) in path[pathType]:
                opticalTopology.G[start][end][index]["calls"] = [call for call in opticalTopology.G[start][end][index]["calls"] if call.id != event.call.id]
                opticalTopology.G[start][end][index]["bandwidth"] += event.call.requestBandwidth
                opticalTopology.G[start][end][index]["weight"] = 1 / (opticalTopology.G[start][end][index]["bandwidth"] + self._infinitesimal)
                if not opticalTopology.G[start][end][index]["calls"]:
                    # 拆除光路
                    for (s, d, i) in opticalTopology.G[start][end][index]["link"]:
                        physicalTopology.G.add_edge(s, d, i)
                        physicalTopology.G[s][d][i]["bandwidth"] = physicalTopology.maxBandwidth
                        # physicalTopology.G[start][end][index]["used"] = False
                        physicalTopology.G[s][d][i]["weight"] = 1 / (physicalTopology.maxBandwidth + self._infinitesimal)
                    opticalTopology.G.remove_edge(start, end, index)
        return True

    def _constructAuxMultiDiG(self, G: nx.MultiDiGraph, **kargs):
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
                    riskName.append('_'.join(["link", str(start), str(end)]))
                elif type(linkRisk) == list:
                    riskName += linkRisk
                if len(set(riskName) & set(kargs["risk"])) != 0:
                    continue
            auxG.add_edge(start, end, index)
            auxG[start][end][index]["bandwidth"] = G[start][end][index]["bandwidth"]
        return auxG

    def _setEavesdroppingRiskSharedLinkGroup(self, G: nx.MultiDiGraph, path: list, ERSLG: list):
        for (start, end, index) in path:
            if type(G[start][end][index]["risk"]) == bool:
                ERSLG.append("_".join(["link", str(start), str(end)]))
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

    def _updateNetState(self, path: dict, opticalG: nx.MultiDiGraph, physicalG: nx.MultiDiGraph, event: object):
        lightpathPath = []
        if path["optical"]:
            # 基于光路拓扑承载业务，仅需要更新光路信息
            for (start, end, index) in path["optical"]:
                if opticalG[start][end][index]["bandwidth"] >= event.call.requestBandwidth:
                    opticalG[start][end][index]["bandwidth"] -= event.call.requestBandwidth
                    opticalG[start][end][index]["calls"].append(event.call)
                    opticalG[start][end][index]["weight"] = 1 / (opticalG[start][end][index]["bandwidth"] + self._infinitesimal)
                    lightpathPath.append((start, end, index))
                else:
                    raise Exception("No enough bandwidth provided to service.")
        elif path["physical"]:
            # 基于物理拓扑承载业务，需要删除物理链路、新建光路、更新光路信息
            wavelengthContinuous = [-1] + [i for (_, _, i) in path["physical"]] + [-1]
            newLightpath = (-1, -1, -1)
            bandwidth = 0
            risk = []
            usedLink = []
            for i, (start, end, index) in enumerate(path["physical"]):
                if index == wavelengthContinuous[i+2] and index != wavelengthContinuous[i]:
                    # 前不后同：当前链路与后续链路组成光路
                    newLightpath = (start, end, index)
                    bandwidth = physicalG[start][end][index]["bandwidth"]
                    risk.append("_".join(["link", str(start), str(end)]))
                    usedLink.append((start, end, index))
                    physicalG.remove_edge(start, end, index)
                elif index == wavelengthContinuous[i+2] and index == wavelengthContinuous[i]:
                    # 前同后同：当前链路与前后链路共同组成光路
                    newLightpath = (newLightpath[0], end, index)
                    bandwidth = min(bandwidth, physicalG[start][end][index]["bandwidth"])
                    risk.append("_".join(["link", str(start), str(end)]))
                    usedLink.append((start, end, index))
                    physicalG.remove_edge(start, end, index)
                elif index != wavelengthContinuous[i+2] and index == wavelengthContinuous[i]:
                    # 前同后不：当前链路组成光路末端
                    newLightpath = (newLightpath[0], end, index)
                    bandwidth = min(bandwidth, physicalG[start][end][index]["bandwidth"])
                    risk.append("_".join(["link", str(start), str(end)]))
                    usedLink.append((start, end, index))
                    physicalG.remove_edge(start, end, index)
                    opticalG.add_edge(newLightpath[0], newLightpath[1])
                    lightpathIndex = len(opticalG[newLightpath[0]][end]) - 1
                    opticalG[newLightpath[0]][end][lightpathIndex]["bandwidth"] = bandwidth - event.call.requestBandwidth
                    opticalG[newLightpath[0]][end][lightpathIndex]["used"] = index
                    opticalG[newLightpath[0]][end][lightpathIndex]["risk"] = risk
                    opticalG[newLightpath[0]][end][lightpathIndex]["calls"] = [event.call]
                    opticalG[newLightpath[0]][end][lightpathIndex]["link"] = usedLink
                    opticalG[newLightpath[0]][end][lightpathIndex]["weight"] = 1 / (bandwidth - event.call.requestBandwidth + self._infinitesimal)
                    usedLink = []
                    lightpathPath.append((newLightpath[0], end, lightpathIndex))
                else:
                    # 前不后不：链路单独组成光路
                    opticalG.add_edge(start, end)
                    lightpathIndex = len(opticalG[start][end]) - 1
                    opticalG[start][end][lightpathIndex]["bandwidth"] = physicalG[start][end][index]["bandwidth"] - event.call.requestBandwidth
                    opticalG[start][end][lightpathIndex]["used"] = index
                    opticalG[start][end][lightpathIndex]["risk"] = ["_".join(["link", str(start), str(end)])]
                    opticalG[start][end][lightpathIndex]["calls"] = [event.call]
                    opticalG[start][end][lightpathIndex]["link"] = [(start, end, index)]
                    opticalG[start][end][lightpathIndex]["weight"] = 1 / (physicalG[start][end][index]["bandwidth"] - event.call.requestBandwidth + self._infinitesimal)
                    physicalG.remove_edge(start, end, index)
                    lightpathPath.append((start, end, lightpathIndex))
        return lightpathPath
