import logging
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

from utl.event import Event
from utl.call import Call
from network.generator import TopoGen, CallsGen


class SF:
    """
    Security First Service Provision 算法实现
    根据伪代码实现路径选择算法，考虑安全需求类型
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.name = "Security First Service Provision"

        # 是否开启拓扑构建，开启设置为True，否则设置为False
        self.is_subgraph = False
        self.is_show = True

    def route(
            self,
            event: Event,
            topo_gen: TopoGen,
            tfk_gen: CallsGen,
            sec_link_ratio: float = 0.0,
            k: int = 10,    # 限制路径数量
            **kwargs
    ):
        """
        安全优先原则
        业务分类：从安全性分类，从安全带宽分类
        输入业务存在三类：1、强安全，2、尽力而为，3、无安全

        对于强安全和尽力而为，要保证100%加密，否则阻塞；
        对于无安全，可使用安全带宽，但不加密。
        """
        call = event.event      # 业务信息，包括以下属性：call.src、call.dst、call.rate、call.security
        G = topo_gen.G          # 拓扑图

        # 第2行: 构建安全拓扑 (Algorithm 2)
        if self.is_subgraph:
            prime_topo = self._generate_secure_subtopology(G, num_sec_links=round(len(G.edges) * sec_link_ratio),
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
            self.is_subgraph = False

        if self.is_show:
            pos = {node: (G.nodes[node]["Longitude"], G.nodes[node]["Latitude"]) for node in G.nodes}
            plt.rcParams['figure.figsize'] = (8.4 * 0.39370, 4.8 * 0.39370)
            plt.rcParams['figure.dpi'] = 300
            edge_color = []
            for u, v in G.edges:
                if G[u][v]["link_security"] == 1:
                    edge_color.append("r")
                else:
                    edge_color.append("k")
            nx.draw(G, pos, width=0.5, linewidths=0.5, node_size=30, node_color="#0070C0", edge_color=edge_color, with_labels=True)
            plt.show()
            self.is_show = False

        logging.debug(f"===== ROUTING {call.id} =====")
        # 步骤1: 搜索所有简单路径
        try:
            k_paths = list(nx.shortest_simple_paths(G, source=call.src, target=call.dst))
        except nx.NetworkXNoPath:
            logging.warning(f"No path found from {call.src} to {call.dst}")
            return False

        # 滤除所有安全路径和普通路径
        available_paths = []
        for path in k_paths[:k]:
            # 检查路径带宽可用性
            link_bdw = [
                G[u_node][v_node]["link_available_bandwidth"]
                for u_node, v_node in zip(path[:-1], path[1:])
            ]
            avl_link_bdw = [
                True
                for bdw in link_bdw if bdw >= call.rate
            ]
            logging.debug(f"For path: {path}, the link bdw: {link_bdw}, the avl of it is {avl_link_bdw}.")
            if len(avl_link_bdw) == len(path) - 1:
                logging.debug(f"Feasible.")
            else:
                logging.debug(f"Infeasible.")
                continue

            # 检查路径安全可用性
            link_sec = [
                G[u_node][v_node]["link_security"]
                for u_node, v_node in zip(path[:-1], path[1:])
            ]
            sum_link_sec = sum(link_sec)
            logging.debug(f"For path: {path}, the link sec: {link_sec}, the sum of it is {sum_link_sec}.")

            if sum_link_sec == 0:
                available_paths.append((0, path))
                logging.debug(f"Feasible.")
            elif sum_link_sec == len(path) - 1:
                available_paths.append((1, path))
                logging.debug(f"Feasible.")
            else:
                available_paths.append((0.5, path))
                logging.debug(f"Condition Feasible.")
                continue

        # 检查可用路径集
        if available_paths:
            available_paths.sort(key=lambda x: x[0])
            logging.debug(f"The available paths: {available_paths}")
        else:
            logging.warning(f"No available paths.")
            return False

        # 步骤2：检查业务需求
        if 0 > call.security > tfk_gen.cfg_call_security:
            logging.warning(f"Unknown security requirement: {call.security}")

        logging.debug(f"Call {call.id} has sec demand {call.security}.")
        if call.security == 0:
            # 业务不存在安全需求
            path_sec, path = available_paths.pop(0)
            if path_sec == 0:
                logging.debug(f"Path {path} is selected with the path sec {path_sec}.")
                self._reserve_bandwidth(G, path, call)
                return True
            elif path_sec == 0.5 or path_sec == 1:
                # 允许普通业务使用安全带宽，但不使用加密能力
                logging.debug(f"Path {path} is conditional selected with the path sec {path_sec}.")
                self._reserve_bandwidth(G, path, call)
                return True
            else:
                logging.debug(f"No path found.")
                return False
        elif call.security > 0:
            # 业务存在安全需求，保证100%加密
            for path_sec, path in available_paths:
                if path_sec == 1:
                    logging.debug(f"Path {path} is selected with the path sec {path_sec}.")
                    self._reserve_bandwidth(G, path, call)
                    return True
                else:
                    continue
            logging.debug(f"No path found.")
            return False

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
            graph[u_node][v_node]["link_weight"] = 1 / graph[u_node][v_node]["link_available_bandwidth"] if graph[u_node][v_node]["link_available_bandwidth"] > 0 else 999
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
            while current_edges_count > num_sec_links:
                odd_nodes = [node for node, deg in G_prime.degree() if deg == 1]
                if not odd_nodes:
                    logging.error(f"There is no odd nodes to be removed.")
                G_prime.remove_node(odd_nodes[0])
                current_edges_count = len(G_prime.edges())

        # 步骤7-9: 边数不足时添加 (伪代码第7-9行)
        elif current_edges_count < num_sec_links:
            # 步骤8: 根据Eq.12决定要添加的边 (需实现具体决策逻辑)
            E_add = list(set(G.edges()) - set(G_prime.edges()))

            # 步骤9: 添加选定边
            for (u, v) in E_add[:num_sec_links - current_edges_count]:
                G_prime.add_edge(u, v, **G[u][v])

        # 步骤10: 返回最终子图 (伪代码第10行)
        return G_prime
