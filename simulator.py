"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import os.path

import numpy as np
import pandas as pd

import event
import network
import result
import utl

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)


def simulator(config_file: str):
    # 检查输入
    if not os.path.exists(config_file):
        raise Exception("Config file does not exist.")
    configer = utl.config.Config()
    configer.read(config_file)
    # # 生成流量
    # tfc_gen = network.traffic.TrafficGenerator(config_file)
    # tfc_gen.set_static_traffic()
    # # 生成物理拓扑
    # logging.info("{} - {} - Construct the physical topology.".format(__file__, __name__))
    # physicalTopology = network.topology.PhysicalTopology()
    # physicalTopology.constructGraph(config_file)
    # physicalTopology.route(tfc_gen.calls, weight="weight")
    # logging.info("{} - {} - Done.".format(__file__, __name__))
    # # 生成离散事件器
    # scheduler = event.scheduler.Scheduler()
    # # 生成攻击事件
    # logging.info("{} - {} - Generate the attack events.".format(__file__, __name__))
    # ai = network.info.AreaInfo(config_file)
    # area_info = ai.get(physicalTopology)
    # atks = network.generator.Generator()
    # atks.generate(config_file, scheduler, ai, "random")
    # logging.info("{} - {} - Done.".format(__file__, __name__))
    # # 加载数据统计模块
    # logging.info("{} - {} - Load the statistic module.".format(__file__, __name__))
    # statistic = result.statistic.Statistic()
    # # 启动管控平台
    # logging.info("{} - {} - Start the control plane.".format(__file__, __name__))
    # controller = network.controller.ControlPlane(config_file)
    # controller.run(scheduler, physicalTopology, ai, statistic)
    # logging.info("{} - {} - Done.".format(__file__, __name__))
    # # 返回仿真结果
    # # result.curve.PlotCurve.plotRealTime(statistic.time_stamp, statistic.realtime_num_carried_calls)
    # # result.curve.PlotCurve.plotRealTime(statistic.time_stamp, statistic.realtime_attacks)
    # return statistic.content_displayable_results, statistic.get()


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
        all_res = []
        title = None
        for i in range(1):
            try:
                title, res = simulator(configFile)
                all_res.append(res)
                print(res)
            except:
                continue
        # data = np.array(all_res).mean(axis=0)
        # df = pd.Series(data, index=title)
        # print(df)
    else:
        if not os.path.exists(ResultFile):
            raise Exception("File does not exist.")
        data = pd.read_excel(ResultFile)
        title = {
            5: "BR (%)",
            6: "RT",
            7: "PAH (%)"
        }
        col = 7
        x = [5, 10, 15, 20, 25]
        y = [list(data.iloc[i*len(x): len(x)*(1+i), col]) for i in [0, 1, 2, 3, 4]]
        legend = ["Benchmark", "PRACA k=1", "PRACA k=2", "PRACA k=3", "PRACA k=4"]
        # legend = ["Benchmark", "PRACA-degree", "PRACA-service", "PRACA-random"]
        pc = result.curve.PlotCurve()
        pc.plotMultiRealTime(x, *y, legend=legend, label=["the number of attacks", title[col]])
