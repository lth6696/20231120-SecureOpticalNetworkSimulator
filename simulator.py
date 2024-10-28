"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import logging
import logging.config
import sys

import numpy as np
import pandas as pd

import algorithm.static_spf
import utl
import network
import result

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)


def simulator(config_file: str):
    # 读取配置
    configer = utl.config.Config().read(config_file)

    algo_set = {}
    topo_gen = network.generator.TopoGen()
    tfc_gen = network.generator.CallsGen()
    atk_gen = network.generator.EventGen()
    net_state = network.state.NetState()
    scheduler = network.scheduler.Scheduler()
    res = result.statistic.Statistic()
    # 生成配置
    for section in configer.sections():
        kargs = {key: utl.config.convert(configer[section][key]) for key in configer[section]}
        if section == "topology":
            # 生成物理拓扑
            topo_gen.generate(**kargs)
        elif section == "link" or section == "node":
            # 设置节点或链路属性
            topo_gen.set(section, **kargs)
        elif section == "call":
            # 生成业务
            nodes = list(topo_gen.G.nodes.keys())
            tfc_gen.generate(nodes, **kargs)
            algorithm.static_spf.StaticSPF.route(topo_gen.G, tfc_gen.calls)
        elif section == "states":
            # 获取网络状态
            net_state.get(topo_gen.G, tfc_gen.calls, **kargs)
        elif section == "algorithm":
            algo_set = kargs
        elif section == "events":
            # 生成离散事件
            atk_gen.generate(scheduler, net_state, **kargs)
            net_state.update(topo_gen.G, tfc_gen.calls, atk_gen.attacked_regions)
        elif section == "result":
            pass
        else:
            pass

    # 启动管控平台
    logging.info("{} - {} - Start the control plane.".format(__file__, __name__))
    controller = network.controller.ControlPlane()
    controller.run(scheduler, topo_gen, tfc_gen, net_state, res, **algo_set)
    logging.info(f"{__file__} - {__name__} - Done.")


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
