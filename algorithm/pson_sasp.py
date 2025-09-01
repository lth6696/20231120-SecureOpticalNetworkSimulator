"""
场景：部分安全光网络
问题：如何在部分安全光网络中实现安全路由
算法：Security Aware Service Provision
"""
import logging

import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

import utl.call
from network.generator import TopoGen, CallsGen
from utl.event import Event


class SASP:
    def __init__(self):
        self.name = "Security Aware Service Provision"
        self.is_subgraph = False
        self.is_show = True

    def route(
            self,
            event: Event, topo_gen: TopoGen, tfk_gen: CallsGen,
            method: str = "security_overflow", sec_link_ratio: float = 0.0
        ):
        """
        服务供应的主函数 - 实现Algorithm 1: Service Provision
        """
        call = event.event
        src = call.src
        dst = call.dst
        req_bandwidth = call.rate
        req_security = call.security
        graph = topo_gen.G

        # 第2行: 构建安全拓扑 (Algorithm 2)
        if not self.is_subgraph:
            prime_topo = self._generate_secure_subtopology(graph, num_sec_links=int(len(graph.edges)*sec_link_ratio))
            # 更新链路安全属性
            logging.info(f"===== SUBGRAPH GENERATE =====")
            for (u_node, v_node) in graph.edges:
                if prime_topo.has_edge(u_node, v_node):
                    graph[u_node][v_node]["link_security"] = 1
                    graph[v_node][u_node]["link_security"] = 1
                    # prime_topo[u_node][v_node]["link_security"] = 1
                    logging.debug(f"Link {u_node} - {v_node} is set security.")
                else:
                    graph[u_node][v_node]["link_security"] = 0
                    graph[v_node][u_node]["link_security"] = 0
                    logging.debug(f"Link {u_node} - {v_node} is set normal.")
            for u, v, attrs in graph.edges(data=True):
                attr_str = ", ".join([f"{k}={v}" for k, v in attrs.items()])
                logging.debug(f"Edge: ({u} -- {v}) | Attributes: {attr_str}")
            self.is_subgraph = True

        if self.is_show:
            pos = {node: (graph.nodes[node]["Longitude"], graph.nodes[node]["Latitude"]) for node in graph.nodes}
            plt.rcParams['figure.figsize'] = (8.4 * 0.39370, 4.8 * 0.39370)
            plt.rcParams['figure.dpi'] = 300
            edge_color = []
            for u, v in graph.edges:
                if graph[u][v]["link_security"] == 1:
                    edge_color.append("r")
                else:
                    edge_color.append("k")
            nx.draw(graph, pos, width=0.5, linewidths=0.5, node_size=30, node_color="#0070C0", edge_color=edge_color,
                    with_labels=True)
            plt.show()
            self.is_show = False

        # 第3行: 路由服务 (Algorithm 3 或 4)
        logging.debug(f"===== ROUTING {call.id} =====")
        path = self.__getattribute__("_route_" + method)(graph, src, dst, req_bandwidth, req_security, tfk_gen.cfg_call_security[-1], topo_gen.cfg_link_security[-1])
        logging.debug(f"Route service {call.id}: {path}.")
        
        # 第4-7行: 条件判断
        if path:
            # 第5行: 在原始图中预留带宽
            self._reserve_bandwidth(graph, path, call)
            return True
        else:
            # 第7行: 阻止服务
            logging.debug(f"Service {call.id} with security {call.security} is blocked.")
            return False

    # 以下为Algorithm 1中引用的子算法接口定义
    def _generate_secure_subtopology(
        self,
        G: nx.Graph, 
        num_sec_links: int = -1,
        weight: str = None
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

    def _route_security_overflow(
            self,
            graph: nx.Graph,
            src: int,
            dst: int,
            req_bandwidth: int,
            req_security: int,
            num_req_security: int,
            num_link_security: int
        ):
        """
        路由服务 (Algorithm 3)
        参数: 源节点, 目标节点, 安全拓扑
        返回: 找到的路径节点列表或None
        """
        # 步骤1: 计算K条最短路径 (伪代码第3行)
        available_paths = list(nx.shortest_simple_paths(graph, src, dst, weight="weight"))
        logging.debug(f"KSP: {available_paths}")
        # 步骤2：为每条路径评分
        path_scores = self.__score_paths(graph, available_paths, req_security, num_req_security, num_link_security)
        logging.debug(f"Score: {path_scores}")
        # 步骤3: 计算溢出值
        overflow_value = self.__calculate_overflow_value(graph)
        logging.debug(f"Overflow value is {overflow_value}.")

        # 步骤4: 筛选满足安全需求范围 [0, overflow] 的路径 (伪代码第5行)
        # 筛选满足安全条件的路径子集
        valid_paths = [
            (path_scores[i], path) for i, path in enumerate(available_paths)
            if 0 <= path_scores[i] <= overflow_value
        ]
        valid_paths.sort(key=lambda x: x[0])
        logging.debug(f"Valid paths are {valid_paths}")

        # 步骤5: 从有效路径中选择满足带宽需求 (伪代码第6行)
        for _, path in valid_paths:
            if self.__has_sufficient_bandwidth(graph, path, req_bandwidth):
                return path
        return None

    def __score_paths(
            self,
            G: nx.Graph, paths: list, req_security: int,
            num_req_security: int, num_link_security: int
    ):
        scores = []
        for path in paths:
            scores.append(self.__score_single_path(G, path, req_security, num_req_security, num_link_security))
        return scores

    def __score_single_path(
            self,
            G: nx.Graph, path: list, req_security: int,
            num_req_security: int, num_link_security: int
    ):
        path = list(zip(path[:-1], path[1:]))
        # 1. 安全偏差计算 Div(r,p) = [∑(l∈p)(l - L*r/RS)]
        div_value = 0.0
        # print(f"====== req_sec = {req_security} ==========")
        for (u, v) in path:
            div_value += G[u][v]['link_security'] - (num_link_security * req_security / num_req_security)
            # print(f"G[{u}][{v}][link_security] = {G[u][v]['link_security']}")
            # print(f"{G[u][v]['link_security']} - ({num_link_security} * {req_security} / {num_req_security}) = {div_value}")
        div_value = 1 - np.exp(- div_value / len(path))
        # print(div_value)

        """
        div_value = []
        for (u, v) in path:
            div_value.append(G[u][v]['link_security'] - (num_link_security * req_security / num_req_security))
            # div_value += np.abs(G[u][v]['link_security'] - (num_link_security * req_security / num_req_security))
        neg_or_pos = min(div_value) / np.abs(min(div_value)) if min(div_value) != 0 else 1
        div_value = 1 - np.exp(- np.sum([np.abs(x) for x in div_value]) / len(path) * neg_or_pos)

        """

        # 2. 路径长度计算 Utl(p) = 1-e^{-p}
        utl_value = 1 - np.exp(-0.5*len(path))

        logging.debug(f"Socre of sec deviation: {div_value}, hop: {utl_value}.")

        # 综合评分
        return div_value * utl_value

    def __calculate_overflow_value(
            self,
            G: nx.Graph
    ):
        # 1 计算可用安全带宽比率,0<=x<=1
        sec_bdw = 0.0
        tot_bdw = 0.0
        for (u, v) in G.edges:
            tot_bdw += G[u][v]["link_bandwidth"]
            if G[u][v]["link_security"] == 1:
                sec_bdw += G[u][v]["link_available_bandwidth"]
        sec_ratio = sec_bdw / tot_bdw

        # 2 计算非超额使用业务比率
        norm_ratio = []
        for (u, v) in G.edges:
            excess_call_num = 0
            norm_call_num = 0
            if len(G[u][v]["link_carried_calls"]) == 0:
                norm_ratio.append(1)
                continue
            for call_id in G[u][v]["link_carried_calls"]:
                # 若业务不存在安全需求但使用了安全链路，是为超额
                if G[u][v]["link_carried_calls"][call_id].security == 0 and G[u][v]["link_security"] == 1:
                    excess_call_num += 1
                else:
                    norm_call_num += 1
            norm_ratio.append(norm_call_num / len(G[u][v]["link_carried_calls"]))
        norm_ratio = np.mean(norm_ratio)

        # 3 计算超额限度
        overflow_value = (0.5*sec_ratio + 0.5*norm_ratio) ** 0.5
        logging.debug(f"The overflow of sec_ratio: {sec_ratio}, non_exc_ratio: {norm_ratio}.")
        return overflow_value

    def __has_sufficient_bandwidth(
            self,
            G: nx.Graph,
            path: list,
            req_bandwidth: int
    ):
        for (u, v) in zip(path[:-1], path[1:]):
            if G[u][v]["link_available_bandwidth"] >= req_bandwidth:
                continue
            else:
                return False
        return True

    def _reserve_bandwidth(
            self,
            graph: nx.Graph,
            path: list,
            call: utl.call.Call
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
            graph[u_node][v_node]["link_weight"] = 1 / graph[u_node][v_node]["link_available_bandwidth"] if graph[u_node][v_node]["link_available_bandwidth"] > 0 else 1e9
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
