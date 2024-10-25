import numpy as np
import networkx as nx
import logging

import utl
from network.attack import Attack
from network.info import AreaInfo
from utl.event import Event
from network.scheduler import Scheduler


class CallsGen:
    def __init__(self):
        self.calls = []

    def generate(self, nodes: list, number: str, rate: str, **kwargs):
        number = int(number)
        rate = float(rate)
        if len(nodes) < 2 or number < 1 or rate <= 0:
            raise ValueError
        for i in range(number):
            [src, dst] = np.random.choice(nodes, 2)
            call = utl.call.Call(id=i, src=src, dst=dst, rate=rate, **kwargs)
            self.calls.append(call)
        return self.calls


class TopoGen:
    def __init__(self):
        self._infinitesimal = 1e-5
        self.G = nx.Graph()

    def generate(self, path_gml: str, path_graphml: str):
        if path_gml != "None":
            self.G = nx.read_gml(path_gml)
        elif path_graphml != "None":
            self.G = nx.read_graphml(path_graphml)
        else:
            raise ValueError

    # def route(self, calls: list, weight: str = None):
    #     for call in calls:
    #         try:
    #             path = nx.shortest_path(self.G, call.src, call.dst, weight=weight)
    #             if self.reserve(self.G, path, call.rate):
    #                 call.path = path
    #         except:
    #             pass
    #     self.calls = [call for call in calls if call.path is not None]
    #
    # def reserve(self, G, path, rate):
    #     if len(path) <= 1:
    #         return True
    #     u_node = path[0]
    #     v_node = path[1]
    #     if G[u_node][v_node]["bandwidth"] > rate:
    #         if self.reserve(G, path[1:], rate):
    #             G[u_node][v_node]["bandwidth"] -= rate
    #             G[u_node][v_node]["weight"] = 1 / G[u_node][v_node]["bandwidth"]
    #             return True
    #         else:
    #             return False
    #     else:
    #         return False


class EventGen:
    """
    业务生成器
    """
    def __init__(self):
        self._eventsInfoModuleName = "events"
        self._topologyInfoModuleName = "topology"
        self._nodeInfoModuleName = "nodes"
        self._linkInfoModuleName = "links"
        self.eventNum = None
        self.load = None
        self.meanHoldingTime = 0.0
        self.meanArrivalTime = 0.0
        self.eventsType = {}
        self.totalWeight = 0
        self.weightVector = []

    def generate(self, scheduler: Scheduler, ai: AreaInfo, strategy: str):
        # 读取配置文件
        logging.info("{} - {} - Read the config file {}.".format(__file__, __name__, configFile))
        # self.eventNum = int(element_attr["num"])
        # self.load = int(element_attr["load"])
        # 读取事件类型
        # for i, event_type in enumerate(element):
        #     event_attr = event_type.attrib
        #     try:
        #         self.eventsType[i] = {
        #             "holding-time": int(event_attr["holding-time"]),
        #             "weight": int(event_attr["weight"])
        #         }
        #     except:
        #         raise Exception("Call's information missing.")
        #     self.totalWeight += int(event_attr["weight"])
        logging.info("{} - {} - There are {} kinds of events.".format(__file__, __name__, len(self.eventsType)))
        # 生成业务事件
        self.weightVector = [aux for aux in self.eventsType for _ in range(self.eventsType[aux]["weight"])]
        # 注意，λ/μ<1
        # 服务时间间隔μ
        self.meanHoldingTime  = sum([self.eventsType[aux]["holding-time"] * self.eventsType[aux]["weight"] / self.totalWeight for aux in self.eventsType])
        # 到达时间间隔λ
        self.meanArrivalTime = self.meanHoldingTime / self.load
        logging.info("{} - {} - Mean arrival time (λ) is {} seconds, mean holding time (μ) is {} seconds, intensity (ρ) is {}."
                     .format(__file__, __name__, self.meanArrivalTime, self.meanHoldingTime, self.meanArrivalTime / self.meanHoldingTime))
        time = 0.0
        for i in range(self.eventNum):
            nextEventType = self.eventsType[np.random.choice(self.weightVector)]
            startTime = np.random.exponential(self.meanArrivalTime, 1)[0] + time
            duration = np.random.exponential(nextEventType["holding-time"])
            endTime = startTime + duration
            time = startTime
            atk = Attack()
            atk_area = atk.atk_area(strategy, ai.area_info)
            atk.set(i, atk_area, duration)
            ai.update(atk_area)
            eventArrival = Event(i, "eventArrive", startTime, atk)
            eventDeparture = Event(i, "eventDeparture", endTime, atk)
            scheduler.addEvent(eventArrival)
            scheduler.addEvent(eventDeparture)
        logging.info("{} - {} - Generate {} events.".format(__file__, __name__, scheduler.getEventNum()))

