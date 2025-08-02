import logging
import networkx as nx

from utl.event import Event
from utl.call import Call
from network.generator import TopoGen, CallsGen


class MER:
    """
    Minimum Exposure-Ratio (MER) 算法实现
    根据伪代码实现路径选择算法，考虑安全需求类型
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.name = "Minimum Exposure-Ratio"

    def route(
            self,
            event: Event, topo_gen: TopoGen, tfk_gen: CallsGen,
            **kwargs
    ):
        """
        寻找满足请求的最佳路径

        参数:
            G: 网络拓扑图
            request: 包含以下键的字典:
                - 's': 源节点
                - 'd': 目标节点
                - 'w': 所需带宽
                - 't': 安全需求类型 ("No_Security", "Best-effort_Security", "Mandatory_Security")

        返回:
            最佳路径或None(如果没有满足条件的路径)
        """
        call = event.event
        G = topo_gen.G
        # 步骤1: 搜索所有简单路径
        try:
            P = list(nx.shortest_simple_paths(G, source=call.src, target=call.dst))
        except nx.NetworkXNoPath:
            logging.warning(f"No path found from {call.src} to {call.dst}")
            return False

        # 步骤2-7: 筛选满足带宽要求的路径
        P_prime = []
        for p in P:
            # 步骤3: 计算路径中的最小带宽
            min_bw = min(G[u][v]['link_available_bandwidth'] for u, v in zip(p[:-1], p[1:]))

            # 步骤4-6: 检查带宽是否满足要求
            if min_bw > call.rate:
                P_prime.append(p)

        if not P_prime:
            logging.warning(f"No path meets bandwidth requirement {call.rate}")
            return False

        # 步骤8-21: 根据安全需求类型筛选路径
        P_star = []
        for p in P_prime:
            # 步骤9-11: 计算路径总长度和不安全通道长度
            distance = [
                ((G.nodes[u]["Longitude"] - G.nodes[v]["Longitude"]) ** 2 +
                 (G.nodes[u]["Latitude"] - G.nodes[v]["Latitude"]) ** 2) ** 0.5
                for u, v in zip(p[:-1], p[1:])
            ]
            total_length = sum(distance)
            insecure_length = sum([distance[idx] for idx, (u, v) in enumerate(zip(p[:-1], p[1:])) if G[u][v]["link_security"] == 0])

            exposure_ratio = insecure_length / total_length if total_length > 0 else 0

            P_star.append((p, exposure_ratio, total_length))

        # # 步骤12-20: 根据安全需求类型选择路径
        # if t == "No_Security":
        #     # 选择暴露比最大的路径
        #     P_star.append((p, exposure_ratio, total_length))
        # elif t == "Best-effort_Security":
        #     # 选择暴露比最小的路径
        #     P_star.append((p, exposure_ratio, total_length))
        # elif t == "Mandatory_Security":
        #     # 只选择完全安全的路径(暴露比为0)
        #     if exposure_ratio == 0:
        #         P_star.append((p, exposure_ratio, total_length))

        if not P_star:
            logging.warning(f"No path meets security requirement {t}")
            return False

        P_star.sort(key=lambda x: x[1])

        # 步骤22-26: 如果有多个候选路径，选择最短的
        if call.security == 0:
            # 选择暴露比最大的路径中最短的
            path = P_star[-1]
        elif call.security == 1:
            # 选择暴露比最小的路径中最短的
            path = P_star[0]
        else:  # Mandatory_Security
            if P_star[0][1] == 0:
                path = P_star[0]
            else:
                return False

        self._reserve_bandwidth(G, path[0], call)

        return True

    def _reserve_bandwidth(
            self,
            graph: nx.Graph,
            path: list,
            call: Call
    ):
        """
        预留路径上的带宽
        参数: 原始图对象, 路径节点列表, 带宽需求
        """
        # 再次检查带宽
        for u_node, v_node in zip(path[:-1], path[1:]):
            if graph[u_node][v_node]["link_available_bandwidth"] < call.rate:
                logging.error(f"There are not enough bandwidth, check the path validity.")
                logging.error(f"Service path: {path}, link: {u_node}-{v_node}, link available bandwidth: {graph[u_node][v_node]["link_available_bandwidth"]}, req bandwidth: {req_bandwidth}")
        # 在路径所有边上预留指定带宽
        call.path = path
        call.is_routed = True
        for u_node, v_node in zip(path[:-1], path[1:]):
            graph[u_node][v_node]["link_available_bandwidth"] -= call.rate
            graph[u_node][v_node]["link_weight"] = 1 / graph[u_node][v_node]["link_available_bandwidth"]
            graph[u_node][v_node]["link_carried_calls"][call.id] = call
        return None

    def remove(
        self,
        event: Event,
        topo_gen: TopoGen,
        tfk_gen: CallsGen,
    ):
        call = event.event
        graph = topo_gen.G
        logging.debug(f"===== REMOVE SERVICE {call.id} =====")
        # 拓扑资源释放
        for u_node, v_node in zip(call.path[:-1], call.path[1:]):
            logging.debug(f"Current: link {u_node}-{v_node} has bandwidth: {graph[u_node][v_node]["link_available_bandwidth"]}"
                          f", weight: {graph[u_node][v_node]["link_weight"]}.")
            graph[u_node][v_node]["link_available_bandwidth"] += call.rate
            graph[u_node][v_node]["link_weight"] = 1 / graph[u_node][v_node]["link_available_bandwidth"]
            graph[u_node][v_node]["link_carried_calls"].pop(call.id)
            logging.debug(f"After release: link {u_node}-{v_node} has bandwidth: {graph[u_node][v_node]["link_available_bandwidth"]}"
                          f", weight: {graph[u_node][v_node]["link_weight"]}.")