import logging
import networkx as nx
import numpy as np

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

        self.is_subgraph = False

    def route(
            self,
            event: Event, topo_gen: TopoGen, tfk_gen: CallsGen,
            sec_link_ratio: float = 0.0,
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
        logging.debug(f"===== Routing Call {call.id} =====")

        # 第2行: 构建安全拓扑 (Algorithm 2)
        if sec_link_ratio == 0.0:
            # 默认拓扑
            pass
        elif not self.is_subgraph:
            prime_topo = self._generate_secure_subtopology(G, num_sec_links=int(len(G.edges) * sec_link_ratio),
                                                           is_show=False)
            # 更新链路安全属性
            logging.info(f"===== SUBGRAPH GENERATE =====")
            for (u_node, v_node) in G.edges:
                if prime_topo.has_edge(u_node, v_node):
                    G[u_node][v_node]["link_security"] = 1
                    G[v_node][u_node]["link_security"] = 1
                    # prime_topo[u_node][v_node]["link_security"] = 1
                    logging.debug(f"Link {u_node} - {v_node} is set security.")
                else:
                    G[u_node][v_node]["link_security"] = 0
                    G[v_node][u_node]["link_security"] = 0
                    logging.debug(f"Link {u_node} - {v_node} is set normal.")
            for u, v, attrs in G.edges(data=True):
                attr_str = ", ".join([f"{k}={v}" for k, v in attrs.items()])
                logging.debug(f"Edge: ({u} -- {v}) | Attributes: {attr_str}")
            self.is_subgraph = True

        # 步骤1: 搜索所有简单路径
        try:
            P = list(nx.shortest_simple_paths(G, source=call.src, target=call.dst))
        except nx.NetworkXNoPath:
            logging.warning(f"No path found from {call.src} to {call.dst}")
            return False
        logging.debug(f"KSP: {P}")

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
        logging.debug(f"KSP with enough bandwidth: {P_prime}")

        # 步骤8-21: 根据安全需求类型筛选路径
        P_star = []
        for i, p in enumerate(P_prime):
            # 步骤9-11: 计算路径总长度和不安全通道长度
            distance = [
                ((G.nodes[u]["Longitude"] - G.nodes[v]["Longitude"]) ** 2 +
                 (G.nodes[u]["Latitude"] - G.nodes[v]["Latitude"]) ** 2) ** 0.5
                for u, v in zip(p[:-1], p[1:])
            ]
            total_length = sum(distance)
            insecure_length = sum([distance[idx] for idx, (u, v) in enumerate(zip(p[:-1], p[1:])) if G[u][v]["link_security"] == 0])

            exposure_ratio = insecure_length / total_length if total_length > 0 else 0
            logging.debug(f"Link distance made up path {i} are: {distance}.")
            logging.debug(f"Insecure distance: {insecure_length}, total distance: {total_length}, exposure ratio: {exposure_ratio}.")
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
            logging.warning(f"No path meets security requirement {call.security}")
            return False

        P_star.sort(key=lambda x: x[1])
        logging.debug(f"Sort paths by exposure ratio: {P_star}.")

        # 步骤22-26: 根据安全需求类型选择路径
        if call.security == 0:
            # 无安全需求的业务选择选择暴露比较高的
            path = P_star[-1]
        elif call.security == 1:
            # 尽力而为的业务选择暴露比最低的
            path = P_star[0]
        else:  # Mandatory_Security
            # 严格安全的业务选择暴露比为0的
            if P_star[0][1] == 0:
                path = P_star[0]
            else:
                logging.debug(f"Call {call.id} with sec demand {call.security} has no suitable path.")
                return False

        logging.debug(f"Call {call.id} with sec demand {call.security} finds path {path}.")
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
                logging.error(f"Service path: {path}, link: {u_node}-{v_node}, link available bandwidth: {graph[u_node][v_node]["link_available_bandwidth"]}, req bandwidth: {call.rate}")
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

    def _generate_secure_subtopology(
            self,
            G: nx.Graph,
            num_sec_links: int = -1,
            weight: str = None,
            is_show: bool = False
    ) -> nx.Graph:
        """
        构建安全拓扑 (Algorithm 2)
        参数: 原始图对象, 安全链路数量
        返回: 符合安全需求的新拓扑
        """
        # 步骤2: 生成最小生成树 (伪代码第2行)
        G_prime = nx.minimum_spanning_tree(G, weight=weight)

        # 步骤3: 获取当前边集 (伪代码第3行)
        E = set(G_prime.edges())
        current_edges_count = len(E)

        # 步骤4-6: 边数过多时剪枝 (伪代码第4-6行)
        if num_sec_links < 0:
            pass
        elif current_edges_count > num_sec_links:
            # 步骤5: 决定要剪切的边 (此处需实现具体决策逻辑)
            E_cut = self.__decide_edges_to_cut(G, G_prime, current_edges_count - num_sec_links)

            # 步骤6: 移除选定边
            G_prime.remove_edges_from(E_cut)

        # 步骤7-9: 边数不足时添加 (伪代码第7-9行)
        elif current_edges_count < num_sec_links:
            # 步骤8: 根据Eq.12决定要添加的边 (需实现具体决策逻辑)
            E_add = self.__decide_edges_to_add(G, G_prime, num_sec_links - current_edges_count)

            # 步骤9: 添加选定边
            for (u, v) in E_add:
                G_prime.add_edge(u, v, **G[u][v])

        # 步骤10: 返回最终子图 (伪代码第10行)
        return G_prime

    def __decide_edges_to_cut(self, G: nx.Graph, G_prime: nx.Graph, num_cut: int):
        """
        决定要剪切的边
        参数: 原始图对象, 安全链路数量
        返回: 要剪切的边集
        """
        # 实现内容将基于具体决策逻辑
        candidate_edges = self.__sort_edges(G, strategy="cut")
        # 求交集
        candidate_edges = [(u, v) for (u, v) in candidate_edges if (u, v) in G_prime.edges]
        return candidate_edges[:num_cut]

    def __decide_edges_to_add(self, G: nx.Graph, G_prime: nx.Graph, num_add: int):
        # 实现内容将基于具体决策逻辑
        candidate_edges = self.__sort_edges(G, strategy="add")
        # 去重
        for (u, v) in G_prime.edges:
            if (u, v) in candidate_edges:
                candidate_edges.remove((u, v))
            else:
                pass
        return candidate_edges[:num_add]

    def __sort_edges(self, G: nx.Graph, strategy: str):
        # 最小割集
        edges_min_cut = nx.minimum_edge_cut(G)
        edges_min_cut = [(u, v) for (u, v) in G.edges if (u, v) in edges_min_cut or (v, u) in edges_min_cut]

        # 最大网络半径集合
        edges_max_dia = self.__maximum_edge_diameter(G)
        edges_max_dia = [(u, v) for (u, v) in edges_max_dia if (u, v) not in edges_min_cut]

        if strategy == "cut":
            return edges_max_dia + edges_min_cut
        elif strategy == "add":
            return edges_min_cut + edges_max_dia

    def __maximum_edge_diameter(self, G: nx.Graph):
        # 节点坐标存储在字典属性中，格式：{node: (x, y)}
        pos = {node: (G.nodes[node]["Longitude"], G.nodes[node]["Latitude"]) for node in G.nodes}

        # 计算每条边的长度并排序
        edges_with_length = []
        for u, v in G.edges():
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            edges_with_length.append((u, v, length))

        # 按长度从长到短排序
        sorted_edges = sorted(edges_with_length, key=lambda x: x[2], reverse=True)
        sorted_edge_list = [(u, v) for u, v, _ in sorted_edges]
        return sorted_edge_list