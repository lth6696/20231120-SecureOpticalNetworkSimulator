"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import os.path

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
    # 生成离散事件器
    scheduler = event.scheduler.Scheduler()
    # 生成攻击事件
    logging.info("{} - {} - Generate the attack events.".format(__file__, __name__))
    atks = network.generator.Generator()
    atks.generate(configFile, scheduler)
    logging.info("{} - {} - Done.".format(__file__, __name__))
    # 生成流量
    tfc_gen = network.traffic.TrafficGenerator(configFile)
    tfc_gen.set_static_traffic()
    physicalTopology.route(tfc_gen.calls)
    # 加载数据统计模块
    logging.info("{} - {} - Load the statistic module.".format(__file__, __name__))
    statistic = result.statistic.Statistic()
    # 启动管控平台
    logging.info("{} - {} - Start the control plane.".format(__file__, __name__))
    controller = network.controller.ControlPlane(configFile)
    controller.run(scheduler, physicalTopology, statistic)
    logging.info("{} - {} - Done.".format(__file__, __name__))
    # # 返回仿真结果
    # try:
    #     # print(sum([len(controller.algorithm.secAvailableSymbiosisPaths[key]) for key in controller.algorithm.secAvailableSymbiosisPaths]))
    #     # print(sum([len(controller.algorithm.nomAvailableSymbiosisPaths[key]) for key in controller.algorithm.nomAvailableSymbiosisPaths]))
    #     result.curve.PlotCurve.plotRealTime(statistic.time_stamp, statistic.realtime_num_carried_calls)
    #     result.curve.PlotCurve.plotRealTime(statistic.time_stamp, statistic.realtime_link_utilization)
    # except:
    #     pass
    # return statistic.content_displayable_results, statistic.get()
    pass

if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')

    # 仿真配置文件
    configFile = "./topology/NSFNet.xml"
    ResultFile = "results.xlsx"
    isSimulate = True
    collector = {"title": [], "results": []}

    # 开始仿真
    if isSimulate:
        simulator(configFile)
        # df = pd.Series(result, index=title)
        # print(df)
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
        col = 12
        x = [100 * (i + 1) for i in range(9)]
        y = [list(data.iloc[0+i*9 : 9+i*9, col])[::-1] for i in range(3)]
        legend = ["SOSR-U", "SOSR-S", "Benchmark"]
        pc = result.curve.PlotCurve()
        pc.plotMultiRealTime(x, *y, legend=legend, label=["load (in Erlang)", title[col]])
