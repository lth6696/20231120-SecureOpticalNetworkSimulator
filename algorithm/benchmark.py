import logging

import networkx as nx


class Benchmark:
    def __init__(self):
        self._infinitesimal = 1e-5
        self.algorithmName = "benchmark"

    def routeCall(self, physicalTopology, event, routeTable):
        """
        Algorithm pseudocode:
        1. 计算工作路径。基于物理拓扑路由路径。对于物理拓扑，修建掉已占用的波长后，构建临时图。计算最短路径并基于FirstFit分配波长。
        2. 计算保护路径。对于物理拓扑，删除已占用波长、与工作路径共享风险波长，构建临时图并计算路径。
        3. 若存在工作路径与保护路径，则输出并退出；若不存在，则锁定业务。
        """
        nodeSrc = event.call.sourceNode
        nodeDst = event.call.destinationNode
        workingPath = []
        backupPath = []

        # 计算工作路径
        try:
            auxG = self._constructAuxMultiDiG(physicalTopology.G, used=True)
            workingPath = nx.dijkstra_path(auxG, nodeSrc, nodeDst, "weight")
            workingPath = self._allocateWavelength(auxG, workingPath)
            if not workingPath:
                return False
        except:
            return False

        # 计算保护路径
        try:
            workingPathRisks = [risk for (start, end, index) in workingPath for risk in physicalTopology.G[start][end][index]["risk"]]
            auxG = self._constructAuxMultiDiG(physicalTopology.G, used=True, risk=workingPathRisks)
            backupPath = nx.dijkstra_path(auxG, nodeSrc, nodeDst, "weight")
            backupPath = self._allocateWavelength(auxG, backupPath)
            if not backupPath:
                return False
        except:
            return False

        # 更新拓扑信息
        self._updateNetState(workingPath, physicalTopology.G, event.call.requestBandwidth)
        self._updateNetState(backupPath, physicalTopology.G, event.call.requestBandwidth)
        # 更新路由表
        routeTable[event.call.id] = {"workingPath": workingPath, "backupPath": backupPath}
        return True

    def removeCall(self, physicalTopology, event, routeTable):
        if event.call.id not in routeTable.keys():
            # 若业务被阻塞
            return False

        workingPath = routeTable[event.call.id]["workingPath"]
        backupPath = routeTable[event.call.id]["backupPath"]
        for (start, end, index) in workingPath:
            physicalTopology.G[start][end][index]["bandwidth"] += event.call.requestBandwidth
            physicalTopology.G[start][end][index]["used"] = False
            physicalTopology.G[start][end][index]["weight"] = 1 / (
                        physicalTopology.G[start][end][index]["bandwidth"] + self._infinitesimal)
        for (start, end, index) in backupPath:
            physicalTopology.G[start][end][index]["bandwidth"] += event.call.requestBandwidth
            physicalTopology.G[start][end][index]["used"] = False
            physicalTopology.G[start][end][index]["weight"] = 1 / (
                        physicalTopology.G[start][end][index]["bandwidth"] + self._infinitesimal)
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
                risks = [risk for risk in G[start][end][index]["risk"] if risk in kargs["risk"]]
                if len(risks) > 0:
                    continue
            auxG.add_edge(start, end, index)
            auxG[start][end][index]["bandwidth"] = G[start][end][index]["bandwidth"]
            auxG[start][end][index]["weight"] = 1 / (G[start][end][index]["bandwidth"] + self._infinitesimal)
            auxG[start][end][index]["used"] = False
            auxG[start][end][index]["risk"] = G[start][end][index]["risk"]
        return auxG

    def _allocateWavelength(self, auxG: nx.MultiDiGraph, path: list):
        """
        路径列表格式为 [1, 2, 5], 不包含波长信息
        基于FirstFit分配波长
        """
        newPath = []
        for (start, end) in zip(path[:-1], path[1:]):
            for index in auxG[start][end]:
                if auxG[start][end][index]["used"]:
                    continue
                else:
                    newPath.append((start, end, index))
                    break
        if len(newPath) == len(path) - 1:
            return newPath
        else:
            return []

    def _updateNetState(self, path, G, bandwidth):
        for (start, end, index) in path:
            if G[start][end][index]["bandwidth"] >= bandwidth:
                G[start][end][index]["bandwidth"] -= bandwidth
                G[start][end][index]["used"] = True
                G[start][end][index]["weight"] = 1 / (bandwidth + self._infinitesimal)
            else:
                raise Exception("There is no enough bandwidth.")
