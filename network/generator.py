import sys

import numpy as np
import random
import networkx as nx
import logging

import utl
# from network.attack import Attack
from network.scheduler import Scheduler
from network.state import NetState

logger = logging.getLogger(__name__)

class CallsGen:
    def __init__(self):
        self.calls = []

    def generate(self, nodes: list, number: str, rate: str, req_sec: str, req_ratio: str):
        number = int(number)
        rate = float(rate)
        # 计算不同需求业务的比例
        req_sec = [int(level) for level in req_sec.split("|")]
        req_ratio = [int(ratio) for ratio in req_ratio.split("|")]
        req_weight = [ratio/sum(req_ratio) for ratio in req_ratio]
        service_security_requests = random.choices(req_sec, weights=req_weight, k=number)

        logging.info(f"Starting call generation with number={number}, rate={rate}, security demands={req_sec}, security ratio={req_weight}")
        if len(nodes) < 2 or number < 1 or rate <= 0:
            logging.error(f"Invalid parameters for call generation: nodes count={len(nodes)}, number={number}, rate={rate}")
            raise ValueError("Invalid parameters for call generation")
        for i in range(number):
            [src, dst] = random.sample(nodes, 2)
            call = utl.call.Call(id=i, src=src, dst=dst, rate=rate, security=service_security_requests[i])
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

    def generate(self, path_gml: str, path_graphml: str):
        # 生成拓扑
        logging.info("Starting topology generation.")
        if path_gml != "None" and path_graphml != "None":
            logging.error("Provided both GML and GraphML file paths. Only one is allowed.")
            raise ValueError
        elif path_gml != "None":
            logging.info(f"Generate topology from GML file: {path_gml}")
            self.G = nx.read_gml(path_gml)
            logging.debug(f"Success load GML topology with {len(self.G.nodes)} nodes and {len(self.G.edges)} edges.")
        elif path_graphml != "None":
            logging.info(f"Generate topology from GraphML file: {path_graphml}")
            self.G = nx.read_graphml(path_graphml)
            logging.debug(f"Success load GraphML topology with {len(self.G.nodes)} nodes and {len(self.G.edges)} edges.")
        else:
            logging.error("No topology file path was provided.")
            raise ValueError("No topology file path was provided.")

    def set(self, _type: str, isShow: bool = False, **kwargs):
        # 设置链路和节点属性
        for attr, val in kwargs.items():
            if _type == "node":
                for node in self.G.nodes:
                    self.G.nodes[node][attr] = val
            elif _type == "link":
                for u_node, v_node in self.G.edges:
                    self.G[u_node][v_node][attr] = val
            else:
                logging.warning(f"Unknown type {_type}.")
        self._log_topology_info()

        if isShow:
            pos = {node: (self.G.nodes[node]["Longitude"], self.G.nodes[node]["Latitude"]) for node in self.G.nodes}
            import matplotlib.pyplot as plt
            plt.rcParams['figure.figsize'] = (8.4 * 0.39370, 4.8 * 0.39370)
            plt.rcParams['figure.dpi'] = 300
            nx.draw(self.G, pos, width=0.5, linewidths=0.5, node_size=30, node_color="#0070C0", edge_color="k")
            plt.show()
            sys.exit()

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
        pass

    def generate(self, scheduler: Scheduler, calls: list, load: int, holding_time: float):
        # 读取配置文件
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
