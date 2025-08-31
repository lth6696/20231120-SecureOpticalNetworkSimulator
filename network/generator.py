import sys

import numpy as np
import random
import networkx as nx
import logging
import matplotlib.pyplot as plt

import utl
from network.scheduler import Scheduler

logger = logging.getLogger(__name__)


class CallsGen:
    def __init__(self):
        self.calls = []

        # 配置信息
        self.cfg_call_number: int = 0
        self.cfg_call_bandwidth: int = 0
        self.cfg_call_security: list = []
        self.cfg_call_ratio: list = []

    def generate(self, nodes: list, call_number: str, call_bandwidth: str, **kwargs):
        self.cfg_call_number = int(call_number)
        self.cfg_call_bandwidth = int(call_bandwidth)
        # 计算不同安全需求业务的比例
        if "call_security" and "call_ratio" in kwargs.keys():
            self.cfg_call_security = [x for x in range(int(kwargs["call_security"])+1)]
            self.cfg_call_ratio = [float(ratio) for ratio in kwargs["call_ratio"].split("|")]
            service_security_requests = random.choices(self.cfg_call_security, weights=self.cfg_call_ratio, k=self.cfg_call_number)
        else:
            logging.error(f"Security parameters is insufficient.")
            raise ValueError("Insufficient parameters for call generation")
        logging.info(f"Starting call generation with number={self.cfg_call_number}, rate={self.cfg_call_ratio}, security demands={self.cfg_call_security}, security ratio={self.cfg_call_ratio}")

        if len(nodes) < 2 or self.cfg_call_number < 1 or self.cfg_call_bandwidth <= 0:
            logging.error(f"Invalid parameters for call generation: nodes count={len(nodes)}, number={self.cfg_call_number}, rate={self.cfg_call_bandwidth}")
            raise ValueError("Invalid parameters for call generation")
        for i in range(self.cfg_call_number):
            [src, dst] = random.sample(nodes, 2)
            call = utl.call.Call(id=i, src=src, dst=dst, rate=self.cfg_call_bandwidth, security=service_security_requests[i])
            self.calls.append(call)
        self._log_call_info()
        return self.calls

    def _log_call_info(self):
        logging.debug("===== CALLS INFO =====")
        call_type_count = {}
        for call in self.calls:
            call_type_count[call.security] = call_type_count.get(call.security, 0) + 1
            logging.debug(call)
        logging.debug(f"Call type count: {call_type_count}")


class TopoGen:
    def __init__(self):
        self._infinitesimal = 1e-5
        self.G = nx.Graph()

        # 配置信息
        self.cfg_topo_file: str = ""
        self.cfg_link_bandwidth: int = 0
        self.cfg_link_weight: float = 0.0
        self.cfg_link_security: list = []
        self.cfg_link_ratio: list = []

    def generate(self, path_gml: str, path_graphml: str):
        # 生成拓扑
        logging.info("Starting topology generation.")
        if path_gml != "None" and path_graphml != "None":
            logging.error("Provided both GML and GraphML file paths. Only one is allowed.")
            raise ValueError
        elif path_gml != "None":
            logging.info(f"Generate topology from GML file: {path_gml}")
            self.cfg_topo_file = path_gml
            self.G = nx.read_gml(self.cfg_topo_file)
            logging.debug(f"Success load GML topology with {len(self.G.nodes)} nodes and {len(self.G.edges)} edges.")
        elif path_graphml != "None":
            logging.info(f"Generate topology from GraphML file: {path_graphml}")
            self.cfg_topo_file = path_graphml
            self.G = nx.read_graphml(self.cfg_topo_file)
            logging.debug(f"Success load GraphML topology with {len(self.G.nodes)} nodes and {len(self.G.edges)} edges.")
        else:
            logging.error("No topology file path was provided.")
            raise ValueError("No topology file path was provided.")

    def set(self, _type: str, is_show: bool = True, **kwargs):
        # 1 设置链路属性
        if _type == "link":
            if "link_bandwidth" in kwargs.keys():
                self.cfg_link_bandwidth = int(kwargs["link_bandwidth"])
                for u_node, v_node in self.G.edges:
                    self.G[u_node][v_node]["link_bandwidth"] = self.cfg_link_bandwidth
                    self.G[u_node][v_node]["link_available_bandwidth"] = self.cfg_link_bandwidth
                logging.debug(f"Set link bandwidth = {self.cfg_link_bandwidth}.")
            if "link_weight" in kwargs.keys():
                self.cfg_link_weight = float(kwargs["link_weight"])
                for u_node, v_node in self.G.edges:
                    self.G[u_node][v_node]["link_weight"] = self.cfg_link_weight
                logging.debug(f"Set link weight = {self.cfg_link_weight}.")
            if "link_security" and "link_ratio" in kwargs.keys():
                self.cfg_link_security = [x for x in range(int(kwargs["link_security"])+1)]
                self.cfg_link_ratio = [float(x) for x in str(kwargs["link_ratio"]).split("|")]
                # 依概率随机生成链路的安全性
                path_security = random.choices(self.cfg_link_security, weights=self.cfg_link_ratio, k=len(self.G.edges))
                # 设置属性
                for i, (u_node, v_node) in enumerate(self.G.edges):
                    self.G[u_node][v_node]["link_security"] = path_security[i]
                logging.debug(f"Set link security = {self.cfg_link_security} | ratio = {self.cfg_link_ratio}.")
                logging.debug(f"{len(self.G.edges)} links set security {path_security}.")
            # 添加属性link_carried_calls，用字典{call_id: path}的方式记录业务承载情况
            for u_node, v_node in self.G.edges:
                self.G[u_node][v_node]["link_carried_calls"] = {}

        # 2 设置节点属性
        if _type == "node":
            pass

        self._log_topology_info()

        if is_show:
            pos = {node: (self.G.nodes[node]["Longitude"], self.G.nodes[node]["Latitude"]) for node in self.G.nodes}
            plt.rcParams['figure.figsize'] = (8.4 * 0.39370, 4.8 * 0.39370)
            plt.rcParams['figure.dpi'] = 300
            edge_color = []
            for u, v in self.G.edges:
                if self.G[u][v]["link_security"] == 1:
                    edge_color.append("r")
                else:
                    edge_color.append("k")
            nx.draw(self.G, pos, width=0.5, linewidths=0.5, node_size=30, node_color="#0070C0", edge_color=edge_color)
            plt.show()
            # sys.exit()

    def _log_topology_info(self):
        # 记录节点信息
        logging.debug("===== TOPOLOGY NODES =====")
        for node, attrs in self.G.nodes(data=True):
            attr_str = ", ".join([f"{k}={v}" for k, v in attrs.items()])
            logging.debug(f"Node: {node} | Attributes: {attr_str}")
        
        # 记录边信息
        logging.debug("===== TOPOLOGY EDGES =====")
        for u, v, attrs in self.G.edges(data=True):
            attr_str = ", ".join([f"{k}={v}" for k, v in attrs.items()])
            logging.debug(f"Edge: ({u} -- {v}) | Attributes: {attr_str}")
        
        # 记录统计摘要
        logging.debug("===== TOPOLOGY SUMMARY =====")
        logging.debug(f"Total Nodes: {self.G.number_of_nodes()}")
        logging.debug(f"Total Edges: {self.G.number_of_edges()}")
        logging.debug(f"Connected Components: {nx.number_connected_components(self.G)}")


class EventGen:
    """
    业务生成器
    """
    def __init__(self):
        self.load = 0
        self.holding_time = 0.0

    def generate(self, scheduler: Scheduler, calls: list, load: int, holding_time: float):
        # 读取配置文件
        self.load = load
        self.holding_time = holding_time
        logging.info(f"Generate events in {load}(load) with {holding_time} holding time.")
        # 服务时间间隔μ, 到达时间间隔λ, 注意: λ/μ<1
        arrival_time = holding_time / load
        logging.info(f"Arrival time (lambda) is {arrival_time}, holding time (mu) is {holding_time}, intensity (rio) is {arrival_time / holding_time}.")

        time = 0.0
        for i in range(len(calls)):
            # 设置时刻
            start_time = np.random.exponential(arrival_time, 1)[0] + time
            duration = np.random.exponential(holding_time)
            end_time = start_time + duration
            time = start_time
            # 生成事件
            event_arrival = utl.event.Event(i, "eventArrive", start_time, calls[i])
            event_departure = utl.event.Event(i, "eventDeparture", end_time, calls[i])
            scheduler.addEvent(event_arrival)
            scheduler.addEvent(event_departure)
            logging.debug(f"Event {event_arrival.id if event_arrival.id == event_departure.id else -1} arrival {event_arrival.time} | depature {event_departure.time}.")
        logging.info(f"Generate {scheduler.getEventNum()} events.")
