import logging
import networkx as nx

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

    def route(
            self,
            event: Event,
            topo_gen: TopoGen,
            tfk_gen: CallsGen,
            **kwargs
    ):
        """
        安全优先原则
        业务分类：从安全性分类，从安全带宽分类
        输入业务存在三类：1、强安全，2、尽力而为，3、无安全

        对于强安全和尽力而为，要保证100%加密，否则阻塞；
        对于无安全，要保证100%不加密，否则阻塞。
        """
        call = event.event      # 业务信息，包括以下属性：call.src、call.dst、call.rate、call.security
        G = topo_gen.G          # 拓扑图

        logging.debug(f"===== ROUTING {call.id} =====")
        # 步骤1: 搜索所有简单路径
        try:
            k_paths = list(nx.shortest_simple_paths(G, source=call.src, target=call.dst))
        except nx.NetworkXNoPath:
            logging.warning(f"No path found from {call.src} to {call.dst}")
            return False

        # 滤除所有安全路径和普通路径
        available_paths = []
        for path in k_paths:
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
            elif sum_link_sec == len(path) - 1:
                available_paths.append((1, path))
            else:
                continue

        # 检查可用路径集
        if available_paths:
            available_paths.sort(key=lambda x: x[0])
            logging.debug(f"The available paths: {available_paths}")
        else:
            logging.warning(f"No available paths.")

        # 步骤2：检查业务需求
        if 0 > call.security > tfk_gen.cfg_call_security:
            logging.warning(f"Unknown security requirement: {call.security}")

        if call.security == 0:
            # 业务不存在安全需求, 保证0%加密
            path_sec, path = available_paths.pop(0)
            if path_sec == 0:
                logging.debug(f"Path {path} is selected with the path sec {path_sec}.")
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