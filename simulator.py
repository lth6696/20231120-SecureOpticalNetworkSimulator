"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import os.path

import numpy as np

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
    rp = result.curve.PlotCurve()
    rp.plotMultiRealTime(statistic.timeStamp, statistic.realTimeCallsCarried, statistic.realTimeSecurityCallsCarried, statistic.realTimeNormalCallsCarried)
    rp.plotMultiRealTime(statistic.timeStamp, statistic.realTimeCallsBlocked, statistic.realTimeSecurityCallsBlocked, statistic.realTimeNormalCallsBlocked)
    rp.plotRealTime(statistic.timeStamp, statistic.realTimeLinkUtilization)
    print(np.mean(statistic.realTimeCallsCarried[5000:15000]))
    print(np.mean(statistic.realTimeSecurityCallsCarried[5000:15000]))
    print(np.mean(statistic.realTimeNormalCallsCarried[5000:15000]))
    print(statistic.totalCarriedCallsNum / statistic.callsNum * 100)
    print(statistic.pathHop)
    print(statistic.securityPathHop)


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')

    # 仿真配置文件
    configFile = "./topology/NSFNet.xml"

    # 开始仿真
    simulator(configFile)

    """
    sfsr
    业务数量     负载      业务承载        安全业务承载     普通业务承载        成功率       跳数       安全业务跳数
    20000       100      68.648         17.933          50.715          67.485      1.512       1.851
    20000       120      85.958         25.986          59.973          71.325      1.051       1.626
    20000       140      92.374         26.993          65.381          67.07       1.008       2.388
    20000       160      112.725        37.304          75.422          68.61       1.750       1.995
    sosr
    20000       100      77.280         24.731          52.549          74.765      1.576       1.512
    
    101.0938
    50.5637
    50.5301
    100.0
    3.3221752959352897
    4.701233370588478
    
    101.6531
    50.6456
    51.0075
    98.91
    2.5591626933218317
    3.349355183462787
    """