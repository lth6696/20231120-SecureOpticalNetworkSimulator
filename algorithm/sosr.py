import networkx as nx
from collections import defaultdict


class SOSR:
    """
    Security Ordinary Symbiosis Survivable Routing Algorithm
    """

    def __init__(self):
        self.algorithmName = "SOSR"
        self.secAvailableSymbiosisPaths = defaultdict(list)     # 安全业务可用共生路径
        self.nomAvailableSymbiosisPaths = defaultdict(list)     # 普通业务可用共生路径
        self.isSymbiosis = defaultdict(bool)                    # 记录业务是否使用共生路径
        self._infinitesimal = 1e-5

    def routeCall(self, physicalTopology, event, routeTable):
        nodeSrc = event.call.sourceNode
        nodeDst = event.call.destinationNode
        workingPath = []
        backupPath = []
        availablePaths = None

        # 计算多条路径
        try:
            availablePaths = [list(zip(path[:-1], path[1:])) for path in nx.node_disjoint_paths(physicalTopology.G, nodeSrc, nodeDst)]
            availablePaths = self._allocateWavelength(physicalTopology.G, availablePaths)
        except:
            availablePaths = []

        if not event.call.requestSecurity:
            # 对于普通需求业务
            if availablePaths:
                # 优先建立新的传输路径
                workingPath = self._choosePath(availablePaths, self._metricsHop)
                self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)].append(workingPath)
            elif self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)]:
                # 若原宿节点间存在共生路径，则占用
                workingPath = self._choosePath(self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)], self._metricsHop)
                self.isSymbiosis[event.call.id] = True
            else:
                # 无法找到可用路径，阻塞业务
                return False
            self._updateNetState(workingPath, physicalTopology.G, event.call.requestBandwidth)
        if event.call.requestSecurity:
            # 对于安全需求业务
            if len(availablePaths) > 1:
                workingPath = self._choosePath(availablePaths, self._metricsRiskLevel, physicalTopology.G)
                backupPath = self._choosePath(availablePaths, self._metricsDisjoint, physicalTopology.G, workingPath)
                self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)].append(backupPath)
            elif self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)] and availablePaths:
                # 若存在共生路径
                workingPath = availablePaths.pop()
                backupPath = self._choosePath(self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)], self._metricsDisjoint, physicalTopology.G, workingPath)
                self.isSymbiosis[event.call.id] = True
            else:
                # 若不存在共生路径
                return False
            self._updateNetState(workingPath, physicalTopology.G, event.call.requestBandwidth)
            self._updateNetState(backupPath, physicalTopology.G, event.call.requestBandwidth)
        routeTable[event.call.id] = {"workingPath": workingPath, "backupPath": backupPath}
        return True

    def removeCall(self, physicalTopology, event, routeTable):
        if event.call.id not in routeTable:
            # 对于已阻塞业务
            return False
        workingPath = routeTable[event.call.id]["workingPath"]
        backupPath = routeTable[event.call.id]["backupPath"]

        if not event.call.requestSecurity:
            # 普通业务使用共生路径
            if self.isSymbiosis[event.call.id]:
                del self.isSymbiosis[event.call.id]
                workingPath = []
        else:
            # 安全业务使用共生路径
            if self.isSymbiosis[event.call.id]:
                del self.isSymbiosis[event.call.id]
                backupPath = []

        for (start, end, index) in workingPath:
            physicalTopology.G[start][end][index]["bandwidth"] += event.call.requestBandwidth
            physicalTopology.G[start][end][index]["used"] = False
            physicalTopology.G[start][end][index]["weight"] = 1 / (physicalTopology.G[start][end][index]["bandwidth"] + self._infinitesimal)
        if backupPath is None:
            return True
        for (start, end, index) in backupPath:
            physicalTopology.G[start][end][index]["bandwidth"] += event.call.requestBandwidth
            physicalTopology.G[start][end][index]["used"] = False
            physicalTopology.G[start][end][index]["weight"] = 1 / (physicalTopology.G[start][end][index]["bandwidth"] + self._infinitesimal)
        return True

    def _allocateWavelength(self, G: nx.MultiDiGraph, paths: list):
        """
        路径列表格式为 [[(0,1),(1,2)]], 不包含波长信息
        基于FirstFit分配波长
        """
        newPaths = []
        for path in paths:
            p = []
            for (start, end) in path:
                for index in G[start][end]:
                    if G[start][end][index]["used"]:
                        continue
                    else:
                        p.append((start, end, index))
                        break
            if len(p) == len(path):
                newPaths.append(p)
            else:
                continue
        return newPaths

    def _updateNetState(self, path, G, bandwidth):
        for (start, end, index) in path:
            G[start][end][index]["bandwidth"] -= bandwidth
            G[start][end][index]["used"] = True
            G[start][end][index]["weight"] = 1 / (bandwidth + self._infinitesimal)

    def _choosePath(self, paths: list, metrics, *args):
        """
        从可选路径中依据指标选择一条路径
        """
        if not paths:
            return []
        metricsValue = metrics(paths, *args)
        path = paths.pop(metricsValue.index(min(metricsValue)))
        if not path:
            return []
        return path

    def _metricsHop(self, paths: list):
        return [len(path) for path in paths]

    def _metricsRiskLevel(self, paths: list, G: nx.MultiDiGraph):
        riskLevel = []
        for path in paths:
            for (start, end, index) in path:
                riskLevel.append(len([risk for risk in G[start][end][index]["risk"] if "H" in risk]))
        return riskLevel

    def _metricsDisjoint(self, paths: list, G: nx.MultiDiGraph, workingPath: list):
        disjointRisks = []
        pathRisk = [G[start][end][index]["risk"] for (start, end, index) in workingPath]
        for path in paths:
            for (start, end, index) in path:
                disjointRisks.append(len([risk for risk in G[start][end][index]["risk"] if risk in pathRisk]))
        return disjointRisks
