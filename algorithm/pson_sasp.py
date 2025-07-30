"""
场景：部分安全光网络
问题：如何在部分安全光网络中实现安全路由
算法：Security Aware Service Provision
"""
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

from network.generator import TopoGen, CallsGen
from network.state import NetState
from utl.event import Event


class SASP:
    def __init__(self):
        self.name = "Security Aware Service Provision"

        self.prime_topo = None

    def route(
            self,
            event: Event,
            topo_gen: TopoGen,
            tfk_gen: CallsGen,
            net_state: NetState,
            depth: int,
            method: str = "security_overflow"
        ):
        """
        服务供应的主函数 - 实现Algorithm 1: Service Provision
        
        参数:
            self: 类实例引用
            event: 事件对象
            topo_gen: 拓扑生成器
            tfk_gen: 流量生成器
            net_state: 网络状态
            depth: 深度
        
        返回:
            成功时: 路径节点列表
            失败时: None
        """
        call = event.event
        src = call.src
        dst = call.dst
        req_bandwidth = call.rate
        req_security = call.security
        graph = topo_gen.G

        # 第2行: 构建安全拓扑 (Algorithm 2)
        if self.prime_topo is None:
            self.prime_topo = self._generate_secure_subtopology(graph, num_sec_links=-1, is_show=False)

            # 更新链路安全属性
            for (u, v) in self.prime_topo.edges:
                graph[u][v]["link_sec"] = 1

        # 第3行: 路由服务 (Algorithm 3 或 4)
        path = self.__getattribute__("_route_" + method)(graph, src, dst, req_bandwidth, req_security)
        
        # 第4-7行: 条件判断
        if path:
            # 第5行: 在原始图中预留带宽
            self._reserve_bandwidth(graph, path, req_bandwidth)
            return path
        else:
            # 第7行: 阻止服务
            self._block_service(req_bandwidth, req_security)
            return None

    # 以下为Algorithm 1中引用的子算法接口定义
    def _generate_secure_subtopology(
        self,
        G: nx.Graph, 
        num_sec_links: int = -1,
        weight: str = "weight",
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

        if is_show:
            self._show_topology(G_prime)

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

    def _show_topology(self, G: nx.Graph):
        pos = {node: (G.nodes[node]["Longitude"], G.nodes[node]["Latitude"]) for node in G.nodes}
        plt.rcParams['figure.figsize'] = (8.4 * 0.39370, 4.8 * 0.39370)
        plt.rcParams['figure.dpi'] = 300
        nx.draw(G, pos, width=0.5, linewidths=0.5, node_size=30, node_color="#0070C0", edge_color="y")
        plt.show()
        return None

    def _route_security_overflow(
            self,
            graph: nx.Graph,
            src: int,
            dst: int,
            req_bandwidth: int,
            req_security: int,
            available_paths: list = None,
            alpha: int = 0,
            # k: int = 20
        ):
        """
        路由服务 (Algorithm 3 或 4)
        参数: 源节点, 目标节点, 安全拓扑
        返回: 找到的路径节点列表或None
        """
        # 步骤1: 初始化条件 (对应伪代码第2行)
        if available_paths is None:
            available_paths = []
        if alpha == 0 and not available_paths:
            # 步骤2: 计算K条最短路径 (伪代码第3行)
            available_paths = nx.shortest_simple_paths(graph, src, dst, weight="weight")
            # 计算暴露比率

            # todo 为每个路径计算与安全需求的偏差，偏差值（考虑跳数）作为输入overflow的输入，计算可也用的偏差路径。要求需求为0时，偏差从0开始选择；需求为k时，偏差从0开始选择。
            # 步骤3: 计算溢出值 (伪代码第4行，假设的calculate_overflow_value函数)
            overflow_value = self.__calculate_overflow_value()

        # 步骤4: 筛选满足安全需求范围 [l, l + alpha] 的路径 (伪代码第5行)
        # 注意: 安全需求范围基于输入的安全需求等级(security_req)和溢出系数(alpha)
        min_security = security_req
        max_security = security_req + alpha

        # 筛选满足安全条件的路径子集
        valid_paths = [
            path for path in available_paths
            if min_security <= get_path_security_level(path) <= max_security
        ]

        # 步骤5: 从有效路径中选择满足带宽需求且安全值最小的路径 (伪代码第6行)
        min_security_path = None
        min_security_value = float('inf')

        for path in valid_paths:
            if not has_sufficient_bandwidth(path, bandwidth_req):
                continue

            path_security = get_path_security_level(path)
            if path_security < min_security_value:
                min_security_value = path_security
                min_security_path = path

        # 步骤6: 检查是否找到路径 (伪代码第7-13行)
        if min_security_path:
            return min_security_path  # 找到合适路径

        # 步骤7: 检查是否达到安全阈值上限 (伪代码第10行)
        # 假设MAX_SECURITY_LEVEL为最高安全等级（通常设为系统最大安全等级）
        MAX_SECURITY_LEVEL = 10  # 示例值，实际应来源于系统配置

        if security_req + alpha >= MAX_SECURITY_LEVEL:
            return None  # 无可用路径，返回None

        # 步骤8: 递归调用自身，增加安全溢出系数 (伪代码第13-14行)
        # 更新可用路径为排除已检查路径后的集合
        remaining_paths = available_paths - set(valid_paths)

        return self._route_security_overflow(
            graph,
            src, dst,
            req_bandwidth,
            req_security,
            remaining_paths,
            alpha + 1  # 增加安全溢出系数
        )

    def __calculate_overflow_value(self):
        return None

    def _reserve_bandwidth(
            self,
            graph: nx.Graph,
            path: list[int],
            bandwidth: float
        ) -> None:
            """
            预留路径上的带宽
            参数: 原始图对象, 路径节点列表, 带宽需求
            """
            # 在路径所有边上预留指定带宽
        pass

    def _block_service(
        self,
        bandwidth: float,
        security: int
    ) -> None:
        """
        阻止服务请求
        参数: 带宽需求, 安全需求
        """
        # 实现服务阻止逻辑 (如记录日志, 通知等)
        pass

    # def _route(
    #     src: Node,
    #     dst: Node,
    #     bandwidth_req: float,
    #     security_req: int,
    #     available_paths: Set[Path] = None,
    #     alpha: int = 0,
    #     k: int = 20
    # ):
        """
        Algorithm: Security Overflow Routing 实现
        
        参数:
            src (Node): 源节点
            dst (Node): 目标节点
            bandwidth_req (float): 带宽需求 (Gbps)
            security_req (int): 安全需求等级
            available_paths (Set[Path]): 可用路径集合 (默认为None)
            alpha (int): 安全溢出系数 (默认0)
            k (int): K条最短路径数 (默认20)
        
        返回:
            Optional[Path]: 满足条件的最小安全路径，或None（若无可用路径）
        """
        # # 步骤1: 初始化条件 (对应伪代码第2行)
        # if alpha == 0 and not available_paths:
        #     # 步骤2: 计算K条最短路径 (伪代码第3行)
        #     available_paths = nx.k_shortest_paths(src, dst, k)
        #     # 步骤3: 计算溢出值 (伪代码第4行，假设的calculate_overflow_value函数)
        #     overflow_value = calculate_overflow_value(available_paths, src, dst)

        # # 步骤4: 筛选满足安全需求范围 [l, l + alpha] 的路径 (伪代码第5行)
        # # 注意: 安全需求范围基于输入的安全需求等级(security_req)和溢出系数(alpha)
        # min_security = security_req
        # max_security = security_req + alpha

        # # 筛选满足安全条件的路径子集
        # valid_paths = [
        #     path for path in available_paths
        #     if min_security <= get_path_security_level(path) <= max_security
        # ]

        # # 步骤5: 从有效路径中选择满足带宽需求且安全值最小的路径 (伪代码第6行)
        # min_security_path = None
        # min_security_value = float('inf')

        # for path in valid_paths:
        #     if not has_sufficient_bandwidth(path, bandwidth_req):
        #         continue

        #     path_security = get_path_security_level(path)
        #     if path_security < min_security_value:
        #         min_security_value = path_security
        #         min_security_path = path

        # # 步骤6: 检查是否找到路径 (伪代码第7-13行)
        # if min_security_path:
        #     return min_security_path  # 找到合适路径

        # # 步骤7: 检查是否达到安全阈值上限 (伪代码第10行)
        # # 假设MAX_SECURITY_LEVEL为最高安全等级（通常设为系统最大安全等级）
        # MAX_SECURITY_LEVEL = 10  # 示例值，实际应来源于系统配置

        # if security_req + alpha >= MAX_SECURITY_LEVEL:
        #     return None  # 无可用路径，返回None

        # # 步骤8: 递归调用自身，增加安全溢出系数 (伪代码第13-14行)
        # # 更新可用路径为排除已检查路径后的集合
        # remaining_paths = available_paths - set(valid_paths)
        # return _route(
        #     src, dst,
        #     bandwidth_req,
        #     security_req,
        #     remaining_paths,
        #     alpha + 1,  # 增加安全溢出系数
        #     k
        # )

    def remove(
        self, 
        event: Event, 
        topo_gen: TopoGen, 
        tfk_gen: CallsGen, 
        **kwargs
        ):
        pass