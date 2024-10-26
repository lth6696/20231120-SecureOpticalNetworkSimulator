import networkx as nx


class StaticSPF:
    def __init__(self):
        pass

    @staticmethod
    def route(G: nx.Graph, calls: list):
        for call in calls:
            try:
                path = nx.shortest_path(G, call.src, call.dst, weight="weight")
                if StaticSPF.reserve(G, path, call.rate):
                    call.path = path
            except:
                pass

    @staticmethod
    def reserve(G: nx.Graph, path: list, rate: float):
        if len(path) <= 1:
            return True
        u_node = path[0]
        v_node = path[1]
        if G[u_node][v_node]["bandwidth"] > rate:
            if StaticSPF.reserve(G, path[1:], rate):
                G[u_node][v_node]["bandwidth"] -= rate
                G[u_node][v_node]["weight"] = 1 / G[u_node][v_node]["bandwidth"]
                return True
            else:
                return False
        else:
            return False