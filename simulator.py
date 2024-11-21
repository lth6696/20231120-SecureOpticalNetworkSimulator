"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import os.path

import multiprocessing
import pandas as pd

import event
import network
import result

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)


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
    logging.info("{} - {} - Load the statistic module.".format(__file__, __name__))
    statistic = result.statistic.Statistic()
    # 启动管控平台
    logging.info("{} - {} - Start the control plane.".format(__file__, __name__))
    controller = network.controller.ControlPlane(configFile)
    controller.run(scheduler, physicalTopology, statistic)
    logging.info("{} - {} - Done.".format(__file__, __name__))
    # 返回仿真结果
    try:
        df = pd.Series(statistic.get(), index=statistic.content_displayable_results)
        print(df)
    #     # print(sum([len(controller.algorithm.secAvailableSymbiosisPaths[key]) for key in controller.algorithm.secAvailableSymbiosisPaths]))
    #     # print(sum([len(controller.algorithm.nomAvailableSymbiosisPaths[key]) for key in controller.algorithm.nomAvailableSymbiosisPaths]))
        result.curve.PlotCurve.plotRealTime(statistic.time_stamp, statistic.realtime_num_carried_calls)
    #     result.curve.PlotCurve.plotRealTime(statistic.time_stamp, statistic.realtime_link_utilization)
    except:
        pass
    return statistic.content_displayable_results, statistic.get()


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')

    # 仿真配置文件
    configFile = "./topology/NSFNet.xml"
    ResultFile = "results.xlsx"
    isSimulate = False
    collector = {"title": [], "results": []}

    # 开始仿真
    if isSimulate:
        title, result = simulator(configFile)
        # df = pd.Series(result, index=title)
    else:
        if not os.path.exists(ResultFile):
            raise Exception("File does not exist.")
        data = pd.read_excel(ResultFile)
        title = {
            3: "blocking rate (%)",
            4: "blocking rate of security calls (%)",
            5: "blocking rate of normal calls (%)",
            6: "the number of hops",
            7: "the number of hops of security calls",
            8: "the number of hops of normal calls",
            9: "link utilization (%)",
            10: "path risk level (%)",
            11: "the number of path risk",
            12: "joint risk level (%)"
        }
        col = 10
        # x = [100 * (i + 1) for i in range(9)]
        # y = [list(data.iloc[0+i*9 : 9+i*9, col])[::-1] for i in range(3)]
        legend = ["SOSR-U", "SOSR-S", "Benchmark"]
        x = [10 * i for i in [0, 2, 4, 6, 8, 10]]
        y = [list(data.iloc[54+i*6: 60+i*6, col]) for i in range(3)]
        y = [[0.0, 31.517135, 32.672424, 33.71738, 34.732917, 35.576042], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 40.395266, 40.309858, 40.374467, 39.780241, 40.038564]]
        # y = [list(data.iloc[0 + i * 9: 9 + i * 9, col])[::-1] for i in [0, 1, 3, 4]]
        # legend = ["NSFNet SOSR-U", "NSFNet SOSR-S", "AttMpls SOSR-U", "AttMpls SOSR-S"]
        pc = result.curve.PlotCurve()
        # pc.plotMultiRealTime(x, *y, legend=legend, label=["load (in Erlang)", title[col]])
        pc.plotMultiRealTime(x, *y, legend=legend, label=["proportion of security services to total services (%)", title[col]])
