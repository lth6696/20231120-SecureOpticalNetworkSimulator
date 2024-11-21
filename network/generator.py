import sys

import numpy as np
import random
import networkx as nx
import logging

import utl
from network.attack import Attack
from network.scheduler import Scheduler
from network.state import NetState


class CallsGen:
    def __init__(self):
        self.calls = []

    def generate(self, nodes: list, number: str, rate: str, **kwargs):
        number = int(number)
        rate = float(rate)
        if len(nodes) < 2 or number < 1 or rate <= 0:
            raise ValueError
        for i in range(number):
            [src, dst] = random.sample(nodes, 2)
            call = utl.call.Call(id=i, src=src, dst=dst, rate=rate, **kwargs)
            self.calls.append(call)
        return self.calls


class TopoGen:
    def __init__(self):
        self._infinitesimal = 1e-5
        self.G = nx.Graph()

    def generate(self, path_gml: str, path_graphml: str):
        # 生成拓扑
        if path_gml != "None" and path_graphml != "None":
            raise ValueError
        elif path_gml != "None":
            self.G = nx.read_gml(path_gml)
        elif path_graphml != "None":
            self.G = nx.read_graphml(path_graphml)
        else:
            raise ValueError

    def set(self, _type: str, **kwargs):
        # 设置链路和节点属性
        for attr, val in kwargs.items():
            if _type == "node":
                for node in self.G.nodes:
                    self.G.nodes[node][attr] = val
            elif _type == "link":
                for u_node, v_node in self.G.edges:
                    self.G[u_node][v_node][attr] = val
            else:
                raise ValueError
        pos = {node: (self.G.nodes[node]["Longitude"], self.G.nodes[node]["Latitude"]) for node in self.G.nodes}
        import matplotlib.pyplot as plt
        plt.rcParams['figure.figsize'] = (16 * 0.39370, 9 * 0.39370)
        plt.rcParams['figure.dpi'] = 300
        nx.draw(self.G, pos, width=0.5, linewidths=0.5, node_size=100, node_color="#0070C0", edge_color="k")
        plt.show()
        sys.exit()


class EventGen:
    """
    业务生成器
    """
    def __init__(self):
        self.attacked_regions = []

    def generate(self, scheduler: Scheduler, net_state: NetState, number: int, load: int, holding_time: float, strategy: str):
        # 读取配置文件
        logging.info(f"{__file__} - {__name__} - Generate {number} events in {load} with {holding_time} time.")
        # 服务时间间隔μ, 到达时间间隔λ, 注意: λ/μ<1
        arrival_time = holding_time / load
        logging.info(f"{__file__} - {__name__} - Arrival time (λ) is {arrival_time}, holding time (μ) is {holding_time}, intensity (ρ) is {arrival_time / holding_time}.")
        time = 0.0
        for i in range(number):
            # 设置时刻
            start_time = np.random.exponential(arrival_time, 1)[0] + time
            duration = np.random.exponential(holding_time)
            end_time = start_time + duration
            time = start_time
            # 生成事件
            atk_event = Attack().set(id=i, duration=duration, strategy=strategy, net_state=net_state, attacked_regions=self.attacked_regions)
            self.attacked_regions.append(atk_event.target)
            event_arrival = utl.event.Event(i, "eventArrive", start_time, atk_event)
            event_departure = utl.event.Event(i, "eventDeparture", end_time, atk_event)
            scheduler.addEvent(event_arrival)
            scheduler.addEvent(event_departure)
        logging.info(f"{__file__} - {__name__} - Generate {scheduler.getEventNum()} events.")
