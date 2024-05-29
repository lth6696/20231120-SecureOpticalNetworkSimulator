"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import os.path

import event
import network
import result


def simulator(configFile: str):
    # 检查输入
    if not os.path.exists(configFile):
        raise Exception("Config file does not exist.")
    # 生成物理拓扑
    logging.info("{} - {} - Construct the physical topology.".format(__file__, __name__))
    physicalTopology = network.topology.PhysicalTopology()
    physicalTopology.constructGraph(configFile)
    logging.info("{} - {} - Done.".format(__file__, __name__))
    # 初始化节点窃听风险
    ESRLG = network.risk.EavesdroppingRisk()
    ESRLG.setLinkRelevanceERSLG(physicalTopology)
    # 生成光路拓扑
    logging.info("{} - {} - Construct the lightpath topology.".format(__file__, __name__))
    opticalTopology = network.topology.LightpathTopology()
    opticalTopology.constructGraph(physicalTopology)
    logging.info("{} - {} - Done.".format(__file__, __name__))
    # 生成业务请求事件
    logging.info("{} - {} - Generate the traffic events.".format(__file__, __name__))
    scheduler = event.scheduler.Scheduler()
    traffic = network.generator.TrafficGenerator()
    traffic.generate(configFile, physicalTopology, scheduler)
    logging.info("{} - {} - Done.".format(__file__, __name__))
    # 加载数据统计模块
    statistic = result.statistic.Statistic()
    # 启动管控平台
    logging.info("{} - {} - Start the control plane.".format(__file__, __name__))
    controller = network.controller.ControlPlane(configFile)
    controller.run(scheduler, physicalTopology, opticalTopology, statistic)
    logging.info("{} - {} - Done.".format(__file__, __name__))
    # 数据绘制
    rp = result.curve.PlotCurve()
    rp.plotRealTimeCarriedServiceNum(statistic.timeStamp, statistic.realTimeCallsCarried)
    rp.plotRealTimeCarriedServiceNum(statistic.timeStamp, statistic.realTimeCallsBlocked)
    rp.plotRealTimeCarriedServiceNum(statistic.timeStamp, statistic.realTimeSecurityCallsCarried)
    rp.plotRealTimeCarriedServiceNum(statistic.timeStamp, statistic.realTimeSecurityCallsBlocked)
    rp.plotRealTimeCarriedServiceNum(statistic.timeStamp, statistic.realTimeLinkUtilization)


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')

    # 仿真配置文件
    configFile = "./topology/SimpleNet.xml"

    # 开始仿真
    simulator(configFile)