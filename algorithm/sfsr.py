import networkx as nx


class SFSR:
    """
    Security First Survivable Routing Algorithm
    """
    def __init__(self):
        self.algorithmName = "SFSR"
        self._infinitesimal = 1e-5

    def routeCall(self, physicalTopology, opticalTopology, event, routeTable):
        nodeSrc = event.call.sourceNode
        nodeDst = event.call.destinationNode
        workingPath = None
        backupPath = None
        if not event.call.requestSecurity:
            # 若不存在安全需求
            try:
                path = nx.shortest_path(physicalTopology.G, nodeSrc, nodeDst, weight="weight")
                workingPath = list(zip(path[:-1], path[1:]))
            except:
                return False
        if event.call.requestSecurity:
            # 若存在安全需求
            auxG = nx.MultiDiGraph()
            auxG.add_nodes_from(physicalTopology.G.nodes)
            for (start, end, index) in physicalTopology.G.edges:
                if not physicalTopology.G[start][end][index]["risk"]:
                    attr = physicalTopology.G[start][end][index]
                    auxG.add_edge(start, end, index, **attr)
            try:
                paths = [path for path in nx.edge_disjoint_paths(auxG, nodeSrc, nodeDst)]
                if len(paths) <= 1:
                    return False
                paths.sort(key=lambda x: len(x))
                workingPath = list(zip(paths[0][:-1], paths[0][1:]))
                backupPath = list(zip(paths[1][:-1], paths[1][1:]))
            except:
                return False

        usedWavelengths = self._allocateWavelength(workingPath, physicalTopology.G)
        if not usedWavelengths:
            return False
        else:
            workingPath = [(start, end, usedWavelengths[i]) for i, (start, end) in enumerate(workingPath)]
        if event.call.requestSecurity:
            usedWavelengths = self._allocateWavelength(backupPath, physicalTopology.G)
            if not usedWavelengths:
                return False
            else:
                backupPath = [(start, end, usedWavelengths[i]) for i, (start, end) in enumerate(backupPath)]
            self._updateNetState(backupPath, physicalTopology.G, event.call.requestBandwidth)
        self._updateNetState(workingPath, physicalTopology.G, event.call.requestBandwidth)
        routeTable[event.call.id] = {"workingPath": workingPath, "backupPath": backupPath}
        return True

    def removeCall(self, physicalTopology, opticalTopology, event, routeTable):
        if event.call.id not in routeTable:
            return False
        workingPath = routeTable[event.call.id]["workingPath"]
        backupPath = routeTable[event.call.id]["backupPath"]
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

    def _allocateWavelength(self, path, G):
        usedWavelengths = []
        for (start, end) in path:
            for index in G[start][end]:
                if G[start][end][index]["used"]:
                    continue
                else:
                    usedWavelengths.append(index)
                    break
        if len(usedWavelengths) != len(path):
            return []
        return usedWavelengths

    def _updateNetState(self, path, G, bandwidth):
        for (start, end, index) in path:
            G[start][end][index]["bandwidth"] -= bandwidth
            G[start][end][index]["used"] = True
            G[start][end][index]["weight"] = 1 / (bandwidth + self._infinitesimal)