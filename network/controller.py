import algorithm
from event.scheduler import Scheduler
from network.topology import PhysicalTopology
from result.statistic import Statistic

import os.path
import xml.etree.ElementTree as et
import logging


class ControlPlane:
    """
    仿真管控平台，用于管理业务事件到达后路由、业务事件离去后资源释放功能
    """
    def __init__(self, configFile: str):
        self.__algorithmInfoModuleName = "ra"
        self.algorithmName = ""
        self.algorithm = None
        self.routeTable = {}    # {call_id: {"workingPath": [], "opticalPath": []}}

        self._setAlgorithm(configFile)

    def run(self, scheduler: Scheduler, physicalTopology: PhysicalTopology, statistic: Statistic):
        while scheduler.getEventNum() != 0:
            (time, event) = scheduler.popEvent()
            # logging.info("{} - {} - The {} event processed on {} second origin from {} to {} with id {}."
            #              .format(__file__, __name__, event.type, time, event.call.sourceNode, event.call.destinationNode, event.id))
            status = None
            if event.type == "eventArrive":
                status = self.algorithm.routeCall(physicalTopology, event, self.routeTable)
            elif event.type == "eventDeparture":
                status = self.algorithm.removeCall(physicalTopology, event, self.routeTable)
            statistic.snapshot(event, status, physicalTopology.G, self.routeTable)

    def _setAlgorithm(self, configFile: str):
        if not os.path.exists(configFile):
            raise Exception("Config file does not exist.")
        elementRa = et.parse(configFile).getroot().find(self.__algorithmInfoModuleName)
        if elementRa is None:
            raise Exception("Config file does not include the topology information.")
        # 加载算法名称
        try:
            self.algorithmName = elementRa.attrib["module"]
        except:
            raise Exception("Tag 'ra' does not include attribute 'module'.")
        # 实例化算法
        if self.algorithmName == "Benchmark":
            self.algorithm = algorithm.benchmark.Benchmark()
        elif self.algorithmName == "SOSR-U":
            self.algorithm = algorithm.sosr.SOSR("utilization")
        elif self.algorithmName == "SOSR-S":
            self.algorithm = algorithm.sosr.SOSR("security")
        elif self.algorithmName == "CAR":
            self.algorithm = algorithm.car.CAR()
        logging.info("{} - {} - Load the {} algorithm.".format(__file__, __name__, self.algorithmName))