"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import os.path

import algorithm
import event
import network


def simulator(configFile: str):
    # 检查输入
    if not os.path.exists(configFile):
        raise Exception("Config file does not exist.")
    # 生成物理拓扑
    physicalTopology = network.topology.PhysicalTopology()
    physicalTopology.constructGraph(configFile)
    # 生成光路拓扑
    opticalTopology = network.topology.LightpathTopology()
    # 生成业务请求事件
    scheduler = event.scheduler.Scheduler()
    traffic = network.generator.TrafficGenerator()
    traffic.generate(configFile, physicalTopology, scheduler)
    # 启动管控平台
    controller = network.controller.ControlPlane(configFile)
    controller.run(scheduler, physicalTopology, opticalTopology)


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')

    # 仿真配置文件
    configFile = "./topology/SimpleNet.xml"

    # 开始仿真
    simulator(configFile)