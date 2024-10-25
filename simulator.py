"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import sys

import numpy as np
import pandas as pd

import utl
import network
import result

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)


def simulator(config_file: str):
    # 读取配置
    configer = utl.config.Config().read(config_file)

    algorithm_name = ""
    topo_gen = network.generator.TopoGen()
    tfc_gen = network.generator.CallsGen()
    atk_gen = network.generator.EventGen()
    # 生成配置
    for section in configer.sections():
        if section == "topology":
            kargs = dict(configer[section])
            topo_gen.generate(**kargs)
        elif section == "call":
            nodes = list(topo_gen.G.nodes.keys())
            kargs = dict(configer[section])
            tfc_gen.generate(nodes, **kargs)
        elif section == "algorithm":
            algorithm_name = configer[section]["name"]
        elif section == "markov":
            pass
        elif section == "events":
            kargs = dict(configer[section])
            atk_gen.generate(**kargs)
        elif section == "result":
            pass
        else:
            pass

    # # 生成物理拓扑
    # physicalTopology.route(tfc_gen.calls, weight="weight")
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
    configFile = "simconfig.ini"
    # 开始仿真
    if input("Do you want to start simulation?") == "":
        simulator(configFile)

        # data = np.array(all_res).mean(axis=0)
        # df = pd.Series(data, index=title)
        # print(df)
    elif input("Do you want to show results?") == "":
        # if not os.path.exists(ResultFile):
        #     raise Exception("File does not exist.")
        # data = pd.read_excel(ResultFile)
        # title = {
        #     5: "BR (%)",
        #     6: "RT",
        #     7: "PAH (%)"
        # }
        # col = 7
        # x = [5, 10, 15, 20, 25]
        # y = [list(data.iloc[i*len(x): len(x)*(1+i), col]) for i in [0, 1, 2, 3, 4]]
        # legend = ["Benchmark", "PRACA k=1", "PRACA k=2", "PRACA k=3", "PRACA k=4"]
        # # legend = ["Benchmark", "PRACA-degree", "PRACA-service", "PRACA-random"]
        # pc = result.curve.PlotCurve()
        # pc.plotMultiRealTime(x, *y, legend=legend, label=["the number of attacks", title[col]])
        print("no")
    else:
        sys.exit()
