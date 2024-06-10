import networkx as nx
from collections import defaultdict


class SOSR:
    """
    Security Ordinary Symbiosis Survivable Routing Algorithm
    """

    def __init__(self, scheme="utilization"):
        if scheme not in ["utilization", "security"]:
            raise Exception("Unknown scheme.")
        self.algorithmName = "SOSR"
        self.secAvailableSymbiosisPaths = defaultdict(list)     # 安全业务可用共生路径，列表内记录业务ID，通过查询路由表获取路径信息, {(0,1): [1, 2, ...]}
        self.nomAvailableSymbiosisPaths = defaultdict(list)     # 普通业务可用共生路径，同上
        self.isSymbiosis = []                                   # 记录业务是否使用共生路径，以元组方式记录两个共生业务,(安全业务，普通业务)
        self.scheme = scheme
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
                self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)].append(event.call.id)
                self._updateNetState(workingPath, physicalTopology.G, event.call.requestBandwidth)
            elif self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)]:
                # 若原宿节点间存在共生路径，则占用
                paths = [routeTable[id]["backupPath"] for id in self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)]]
                workingPath = self._choosePath(paths, self._metricsHop)
                ID = [id for id in self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)] if routeTable[id]["backupPath"] == workingPath]
                self.isSymbiosis.append((ID[0], event.call.id))
                self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)].remove(ID[0])
            else:
                # 无法找到可用路径，阻塞业务
                return False
        if event.call.requestSecurity:
            # 对于安全需求业务
            if len(availablePaths) > 1:
                workingPath = self._choosePath(availablePaths, self._metricsRiskDivers, physicalTopology.G)
                backupPath = self._choosePath(availablePaths, self._metricsTotalRisk, physicalTopology.G, workingPath)
                self.nomAvailableSymbiosisPaths[(nodeSrc, nodeDst)].append(event.call.id)
                self._updateNetState(workingPath, physicalTopology.G, event.call.requestBandwidth)
                self._updateNetState(backupPath, physicalTopology.G, event.call.requestBandwidth)
            elif self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)] and availablePaths:
                # 若存在共生路径
                workingPath = availablePaths.pop()
                paths = [routeTable[id]["workingPath"] for id in self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)]]
                backupPath = self._choosePath(paths, self._metricsTotalRisk, physicalTopology.G, workingPath)
                ID = [id for id in self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)] if routeTable[id]["workingPath"] == backupPath]
                self.isSymbiosis.append((event.call.id, ID[0]))
                self.secAvailableSymbiosisPaths[(nodeSrc, nodeDst)].remove(ID[0])
                self._updateNetState(workingPath, physicalTopology.G, event.call.requestBandwidth)
            else:
                # 若不存在共生路径
                return False
        routeTable[event.call.id] = {"workingPath": workingPath, "backupPath": backupPath}
        return True

    def removeCall(self, physicalTopology, event, routeTable):
        if event.call.id not in routeTable:
            # 对于已阻塞业务
            return False

        workingPath = routeTable[event.call.id]["workingPath"]
        backupPath = routeTable[event.call.id]["backupPath"]
        symbiosisRelation = [smbo for smbo in self.isSymbiosis if event.call.id == smbo[0] or event.call.id == smbo[1]]

        if len(symbiosisRelation) == 1:
            symbioSecurityID = symbiosisRelation[0][0]
            symbioNormalID = symbiosisRelation[0][1]
            if event.call.id == symbioSecurityID:
                # 安全业务先离去
                self.isSymbiosis.remove(symbiosisRelation[0])
                backupPath = []
            elif event.call.id == symbioNormalID:
                # 普通业务先离去
                self.isSymbiosis.remove(symbiosisRelation[0])
                workingPath = []
                backupPath = []
            else:
                pass
        elif len(symbiosisRelation) > 1:
            raise Exception("Two more calls symbiosis one.")
        else:
            pass

        for (start, end, index) in workingPath:
            physicalTopology.G[start][end][index]["bandwidth"] += event.call.requestBandwidth
            physicalTopology.G[start][end][index]["used"] = False
            physicalTopology.G[start][end][index]["weight"] = 1 / (physicalTopology.G[start][end][index]["bandwidth"] + self._infinitesimal)
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
            if G[start][end][index]["bandwidth"] >= bandwidth:
                G[start][end][index]["bandwidth"] -= bandwidth
                G[start][end][index]["used"] = True
                G[start][end][index]["weight"] = 1 / (bandwidth + self._infinitesimal)
            else:
                raise Exception("There is no enough bandwidth.")

    def _choosePath(self, paths: list, metrics, *args):
        """
        从可选路径中依据指标选择一条路径
        """
        if not paths:
            return []
        metricsValue = metrics(paths, *args)
        path = []
        if self.scheme == "utilization":
            path = paths.pop(metricsValue.index(min(metricsValue)))
        elif self.scheme == "security":
            pass
        else:
            return []
        return path

    def _metricsHop(self, paths: list):
        return [len(path) for path in paths]

    def _metricsRiskLevel(self, paths: list, G: nx.MultiDiGraph):
        riskLevel = []
        for path in paths:
            aux = 0
            for (start, end, index) in path:
                aux += len([risk for risk in G[start][end][index]["risk"] if "H" in risk])
            riskLevel.append(aux)
        return riskLevel

    def _metricsDisjoint(self, paths: list, G: nx.MultiDiGraph, workingPath: list):
        disjointRisks = []
        pathRisk = [G[start][end][index]["risk"] for (start, end, index) in workingPath]
        for path in paths:
            aux = 0
            for (start, end, index) in path:
                aux += len([risk for risk in G[start][end][index]["risk"] if risk in pathRisk])
            disjointRisks.append(aux)
        return disjointRisks

    def _metricsRiskDivers(self, paths: list, G: nx.MultiDiGraph):
        hops = self._metricsHop(paths)
        risks = self._metricsRiskLevel(paths, G)
        metrics = [hops[i] / len(G.edges) + risks[i] / hops[i] for i in range(len(paths))]
        return metrics

    def _metricsTotalRisk(self, paths: list, G: nx.MultiDiGraph, workingPath: list):
        risks = self._metricsRiskLevel(paths, G)
        jointRisks = self._metricsDisjoint(paths, G, workingPath)
        metrics = [risks[i] + jointRisks[i] for i in range(len(paths))]
        return metrics