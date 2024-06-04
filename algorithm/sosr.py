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
        workingPath = None
        backupPath = None
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
            elif self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)]:
                # 若原宿节点间存在共生路径，则占用
                workingPath = self._choosePath(self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)], self._metricsHop)
            else:
                # 无法找到可用路径，阻塞业务
                return False
        if event.call.requestSecurity:
            # 对于安全需求业务
            if len(availablePaths) > 1:

            if self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)]:
                # 若存在共生路径
                backupPath = self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)][0]
                # 构建辅助图，其不包括与保护路径共享风险的链路
                auxG = nx.MultiDiGraph()
                auxG.add_nodes_from(physicalTopology.G)
                linkRisk = []
                for (start, end, index) in physicalTopology.G.edges:
                    if (start, end) in [(st, ed) for (st, ed, i) in backupPath]:
                        linkRisk.append(physicalTopology.G[start][end][index]["risk"])
                    if physicalTopology.G[start][end][index]["risk"] not in linkRisk:
                        attr = physicalTopology.G[start][end][index]
                        auxG.add_edge(start, end, index, **attr)
                try:
                    workingPath = nx.shortest_path(auxG, nodeSrc, nodeDst, weight="weight")
                except:
                    return False
            else:
                # 若不存在共生路径
                try:
                    workingPath = nx.shortest_path(physicalTopology.G, nodeSrc, nodeDst, weight="weight")
                except:
                    return False
                # 构建辅助图，图中不包含与工作路径共享风险的链路
                auxG = nx.MultiDiGraph()
                auxG.add_nodes_from(physicalTopology.G)
                linkRisk = []
                for (start, end, index) in physicalTopology.G.edges:
                    if (start, end) in list(zip(workingPath[:-1], workingPath[1:])):
                        linkRisk.append(physicalTopology.G[start][end][index]["risk"])
                    if physicalTopology.G[start][end][index]["risk"] not in linkRisk:
                        attr = physicalTopology.G[start][end][index]
                        auxG.add_edge(start, end, index, **attr)
                try:
                    backupPath = nx.shortest_path(auxG, nodeSrc, nodeDst, weight="weight")
                except:
                    return False
        """
        work            back
        [1 2 3]         None
        [(121) (231)]   None
        [1 2 3]         [1 3]
        [1 2 3]         [(121) (231)]
        """
        if not event.call.requestSecurity and isinstance(workingPath[0], tuple):
            self.isSymbiosis[event.call.id] = True
            self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)].remove(workingPath)
        else:
            # 余下均为新路由工作路径，首先分配资源
            workingPath = list(zip(workingPath[:-1], workingPath[1:]))
            usedWavelengths = self._allocateWavelength(workingPath, physicalTopology.G)
            if not usedWavelengths:
                return False
            workingPath = [(start, end, usedWavelengths[i]) for i, (start, end) in enumerate(workingPath)]
            if backupPath is None:
                # 若普通业务，其不存在保护路径
                self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)].append(workingPath)
            elif isinstance(backupPath[0], tuple):
                # 若安全业务，其使用共生路径
                self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)].remove(backupPath)
                self.isSymbiosis[event.call.id] = True
            else:
                # 若安全业务，其新路由保护路径
                backupPath = list(zip(backupPath[:-1], backupPath[1:]))
                usedWavelengths = self._allocateWavelength(backupPath, physicalTopology.G)
                if not usedWavelengths:
                    return False
                backupPath = [(start, end, usedWavelengths[i]) for i, (start, end) in enumerate(backupPath)]
                self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)].append(backupPath)
                self._updateNetState(backupPath, physicalTopology.G, event.call.requestBandwidth)
            self._updateNetState(workingPath, physicalTopology.G, event.call.requestBandwidth)
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
        path = paths[metricsValue.index(min(metricsValue))]
        if not path:
            return []
        return path

    def _metricsHop(self, paths: list):
        return [len(path) for path in paths]

    def _metricsExEncryptTime(self, call1, callList, paths: list):
        return []

    def _metricsRiskLevel(self, paths: list, G: nx.MultiDiGraph):
        for path in paths:
            for (start, end, index) in path:
                riskNum = G[start][end][index]["risk"]

    def _metricsDisjoint(self, G: nx.MultiDiGraph, workingPath, paths):
        pass

    # 两个业务 两条路径 待选路径