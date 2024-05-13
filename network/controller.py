from event.scheduler import Scheduler
from network.topology import PhysicalTopology, LightpathTopology
from algorithm.benchmark import Benchmark

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

        self._setAlgorithm(configFile)

    def run(self, scheduler: Scheduler, physicalTopology: PhysicalTopology, opticalTopology: LightpathTopology):
        while scheduler.getEventNum() != 0:
            (time, event) = scheduler.popEvent()
            logging.info("{} - {} - The {} event processed on {} second origin from {} to {} with id {}."
                         .format(__file__, __name__, event.type, time, event.call.sourceNode, event.call.destinationNode, event.id))
            if event.type == "callArrive":
                self.algorithm.routeCall()
            elif event.type == "callDeparture":
                self.algorithm.removeCall()

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
            self.algorithm = Benchmark()
        elif self.algorithmName == "EAST":
            self.algorithm = Benchmark()
        logging.info("{} - {} - Load the {} algorithm.".format(__file__, __name__, self.algorithmName))