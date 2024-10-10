import xml.etree.ElementTree as et
import os.path
import numpy as np
import logging

from network.attack import Attack
from network.info import AreaInfo
from event.event import Event
from event.scheduler import Scheduler


class Generator:
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

    def generate(self, configFile: str, scheduler: Scheduler, ai: AreaInfo, strategy: str):
        # 参数合法检测
        if not os.path.exists(configFile):
            raise Exception("Config file does not exist.")
        # 读取配置文件
        logging.info("{} - {} - Read the config file {}.".format(__file__, __name__, configFile))
        xmlParser = et.parse(configFile)
        root = xmlParser.getroot()
        element = root.find(self._eventsInfoModuleName)
        if element is None:
            raise Exception("Config file does not include the traffic information.")
        element_attr = element.attrib
        self.eventNum = int(element_attr["num"])
        self.load = int(element_attr["load"])
        # 读取事件类型
        for i, event_type in enumerate(element):
            event_attr = event_type.attrib
            try:
                self.eventsType[i] = {
                    "holding-time": int(event_attr["holding-time"]),
                    "weight": int(event_attr["weight"])
                }
            except:
                raise Exception("Call's information missing.")
            self.totalWeight += int(event_attr["weight"])
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

