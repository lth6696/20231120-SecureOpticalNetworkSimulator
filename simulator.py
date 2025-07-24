"""
离散事件仿真入口：
输入：仿真配置文件（拓扑、流量、算法）
"""
import configparser
import logging
import logging.config
import sys

import numpy as np
import pandas as pd
import scipy.stats as st

import algorithm.static_spf
import utl
import network
import result

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)


def simulator(configer: configparser.ConfigParser):
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
    # print(res.show())
    logging.info(f"{__file__} - {__name__} - Done.")
    return res.get()


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')
    # 仿真配置文件
    config_file = "simconfig.ini"
    configer = utl.config.Config().read(config_file)
    # 开始仿真
    if input("Do you want to start simulation?") == "":
        simulator(configer)
        # data = np.array(all_res).mean(axis=0)
        # df = pd.Series(data, index=title)
        # print(df)
    elif input("Do you want to show results?") == "":
        a = []
        for _ in range(int(configer["result"]["iter_round"])):
            res = simulator(configer)
            a.append(res[-1])
        confidence_level = 0.99
        b = st.t.interval(confidence_level, df=len(a)-1, loc=np.mean(a), scale=st.sem(a))
        print(np.mean(a), b)

        # node
        # 1 1.54305 (1.467573225752915, 1.618526774247085)
        # 2 1.48225 (1.4272658613839426, 1.5372341386160575)
        # 3 1.4943 (1.430776569913386, 1.5578234300866138)
        # 4 1.48345 (1.4221433530150465, 1.5447566469849534)
        # random
        # 1 0.8745499999999999 (0.7429207459364495, 1.0061792540635504)
        # 2 0.9243500000000001 (0.7549721574100385, 1.0937278425899617)
        # link
        # 1 1.67175 (1.5580507694846828, 1.7854492305153173)
        # 2 1.63679 (1.5369389944660492, 1.7366610055339504)
        # 3 1.67595 (1.603390805334344, 1.7485091946656557)
        # 4 1.57645 (1.508901619660383, 1.6439983803396168)

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
    else:
        sys.exit()
