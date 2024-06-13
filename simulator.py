"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import os.path

import numpy as np
import multiprocessing
import pandas as pd

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
    controller.run(scheduler, physicalTopology, statistic)
    logging.info("{} - {} - Done.".format(__file__, __name__))
    # 仿真结果
    statistic.show()
    # a = result.curve.PlotCurve()
    # a.plotRealTime(statistic.time_stamp, statistic.realtime_num_carried_calls)


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')

    # 仿真配置文件
    configFile = "./topology/NSFNet.xml"
    eachRoundResultFile = "result_Load.csv"
    allRoundResultFile = "results.xlsx"

    iterRound = 20
    isSimulate = True

    if os.path.exists(eachRoundResultFile):
        os.remove(eachRoundResultFile)

    # 开始仿真
    if isSimulate:
        simulator(configFile)
        # processes = [multiprocessing.Process(target=simulator, args=(configFile, )) for _ in range(iterRound)]
        # for pro in processes:
        #     pro.start()
        # for pro in processes:
        #     pro.join()
        #
        # data = pd.read_csv(eachRoundResultFile)
        # for value in list(data.mean(axis=0)):
        #     print(value)
    else:
        if not os.path.exists(allRoundResultFile):
            raise Exception("File does not exist.")
        data = pd.read_excel(allRoundResultFile)
        x = [100 * (i + 1) for i in range(6)]
        y = [list(data.iloc[0+i*6 : 6+i*6, 11])[::-1] for i in range(3)]
        label = ["SOSR-U", "SOSR-S", "Benchmark"]
        pc = result.curve.PlotCurve()
        pc.plotMultiRealTime(x, *y, label=label)
