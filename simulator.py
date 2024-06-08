"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import os.path

import matplotlib.pyplot as plt
import numpy as np
import threading
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
    # 数据绘制
    # rp = result.curve.PlotCurve()
    # rp.plotMultiRealTime(statistic.timeStamp, statistic.realTimeCallsCarried, statistic.realTimeSecurityCallsCarried, statistic.realTimeNormalCallsCarried)
    # rp.plotMultiRealTime(statistic.timeStamp, statistic.realTimeCallsBlocked, statistic.realTimeSecurityCallsBlocked, statistic.realTimeNormalCallsBlocked)
    # rp.plotRealTime(statistic.timeStamp, statistic.realTimeLinkUtilization)
    # print(np.mean(statistic.realTimeCallsCarried[5000:15000]))
    # print(np.mean(statistic.realTimeSecurityCallsCarried[5000:15000]))
    # print(np.mean(statistic.realTimeNormalCallsCarried[5000:15000]))
    res = [
        np.divide(statistic.totalCarriedCallsNum, statistic.callsNum) * 100,
        np.divide(statistic.totalCarriedSecCallsNum, statistic.secCallsNum) * 100,
        np.divide(statistic.totalCarriedNomCallsNum, statistic.nomCallsNum) * 100,
        statistic.pathHop,
        statistic.securityPathHop,
        np.mean(statistic.realTimeLinkUtilization),
        statistic.meanRiskLevel,
        statistic.meanJointRiskLevel
    ]
    print(res)
    logging.info("{} - {} - Numercial results are {}.".format(__file__, __name__, res))
    res = pd.DataFrame(res).transpose()
    res.to_csv('result_Load.csv', mode='a', header=False, index=False)


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')

    # 仿真配置文件
    configFile = "./topology/NSFNet.xml"

    processes = []
    # 开始仿真
    # for i in range(20):
    #     logging.info("-" * 500)
    #     logging.info("{} - {} - Starting the {}th round.".format(__file__, __name__, i))
    #     process = multiprocessing.Process(target=simulator, args=(configFile, ))
    #     processes.append(process)
    #     process.start()
    #
    # for process in processes:
    #     process.join()

    res = [50, 150, 300, 400]
    value = []
    for r in res:
        fileName = "result_Load" + str(r) + ".csv"
        data = pd.read_csv(fileName)
        value.append(list(data.mean(axis=0)))
    print(value)
    plt.plot(res, [col[7] for col in value])
    # plt.plot(res, [col[4] for col in value])
    # plt.plot(res, [col[2] for col in value])
    plt.show()