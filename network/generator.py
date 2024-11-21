import xml.etree.ElementTree as et
import os.path
import numpy as np
import logging

from network.topology import PhysicalTopology
from network.traffic import OTNCalls
from event.event import Event
from event.scheduler import Scheduler


class TrafficGenerator:
    """
    业务生成器
    """
    def __init__(self):
        self._callsInfoModuleName = "traffic"
        self.trafficType = None
        self.callsNum = None
        self.load = None
        self.meanRate = 0.0
        self.maxRate = None
        self.meanHoldingTime = 0.0
        self.meanArrivalTime = 0.0
        self.statisticStart = None
        self.callsType = {}
        self.totalWeight = 0
        self.weightVector = []

    def generate(self, configFile: str, topology: PhysicalTopology, scheduler: Scheduler):
        # 参数合法检测
        if not os.path.exists(configFile):
            raise Exception("Config file does not exist.")
        # 读取配置文件
        logging.info("{} - {} - Read the config file {}.".format(__file__, __name__, configFile))
        xmlParser = et.parse(configFile)
        elementCalls = xmlParser.getroot().find(self._callsInfoModuleName)
        if elementCalls is None:
            raise Exception("Config file does not include the traffic information.")
        trafficAttr = elementCalls.attrib
        try:
            self.trafficType = trafficAttr["type"]
            self.callsNum = int(trafficAttr["calls"])
            self.load = int(trafficAttr["load"])
            self.maxRate = int(trafficAttr["max-rate"])
            self.statisticStart = int(trafficAttr["statisticStart"])
        except:
            raise Exception("Traffic config information are not complete.")
        # 读取业务类型
        for i, callType in enumerate(elementCalls):
            callTypeAttr = callType.attrib
            try:
                self.callsType[i] = {
                    "holding-time": int(callTypeAttr["holding-time"]),
                    "rate": int(callTypeAttr["rate"]),
                    "weight": int(callTypeAttr["weight"])
                }
            except:
                raise Exception("Call's information missing.")
            self.totalWeight += int(callTypeAttr["weight"])
        logging.info("{} - {} - There are {} kinds of calls.".format(__file__, __name__, len(self.callsType)))
        # 生成业务事件
        self.weightVector = [aux for aux in self.callsType for _ in range(self.callsType[aux]["weight"])]
        self.meanRate = sum([self.callsType[aux]["rate"] * self.callsType[aux]["weight"] / self.totalWeight for aux in self.callsType])
        # 注意，λ/μ<1
        # 服务时间间隔μ
        self.meanHoldingTime  = sum([self.callsType[aux]["holding-time"] * self.callsType[aux]["weight"] / self.totalWeight for aux in self.callsType])
        # 到达时间间隔λ
        self.meanArrivalTime = (self.meanHoldingTime * (self.meanRate / self.maxRate)) / self.load
        logging.info("{} - {} - Mean arrival time (λ) is {} seconds, mean holding time (μ) is {} seconds, intensity (ρ) is {}."
                     .format(__file__, __name__, self.meanArrivalTime, self.meanHoldingTime, self.meanArrivalTime / self.meanHoldingTime))
        nodesNum = len(topology.G.nodes)
        time = 0.0
        sec_to_norm = 1

        # 确定每组数量
        sec_svc_count = np.ones(int(self.callsNum * sec_to_norm), dtype=int)
        nor_svc_count = np.zeros(self.callsNum - len(sec_svc_count), dtype=int)
        # 合并两个数组
        svc_count = list(np.concatenate((sec_svc_count, nor_svc_count)))
        for i in range(self.callsNum):
            nextCallType = self.callsType[np.random.choice(self.weightVector)]
            requestSecurity = svc_count.pop(np.random.randint(0, len(svc_count)))
            sourceNode = np.random.randint(nodesNum)
            destinationNode = np.random.randint(nodesNum)
            while (sourceNode == destinationNode):
                destinationNode = np.random.randint(nodesNum)
            startTime = np.random.exponential(self.meanArrivalTime, 1)[0] + time
            duration = np.random.exponential(nextCallType["holding-time"])
            endTime = startTime + duration
            time = startTime
            call = OTNCalls(i, sourceNode, destinationNode, duration, nextCallType["rate"], requestSecurity)
            eventArrival = Event(i, "callArrive", startTime, call)
            eventDeparture = Event(i, "callDeparture", endTime, call)
            scheduler.addEvent(eventArrival)
            scheduler.addEvent(eventDeparture)
        logging.info("{} - {} - Generate {} calls and {} events.".format(__file__, __name__, self.callsNum, scheduler.getEventNum()))