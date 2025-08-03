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
    evnt_gen = network.generator.EventGen()
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
            # algorithm.static_spf.StaticSPF.route(topo_gen.G, tfc_gen.calls)
        elif section == "algorithm":
            algo_set = kargs
        elif section == "events":
            # 生成离散事件
            evnt_gen.generate(scheduler, tfc_gen.calls, **kargs)
            # net_state.update(topo_gen.G, tfc_gen.calls, evnt_gen.attacked_regions)
        elif section == "result":
            pass
        else:
            pass

    # 启动管控平台
    logging.info("Start the control plane.".format(__file__, __name__))
    controller = network.controller.ControlPlane()
    controller.run(scheduler, topo_gen, tfc_gen, res, **algo_set)
    # res.plot_real_time_carried_service()
    # res.plot_real_time_blocked_service()
    # res.plot_real_time_link_utilization()
    logging.info(f"Done.")
    return res.get()


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')
    # 仿真配置文件
    config_file = "simconfig.ini"
    configer = utl.config.Config().read(config_file)
    # 开始仿真
    if input("Do you want to start simulation?[Y/n]") == "Y":
        res = simulator(configer)
        prefix = [0.4, 10000, 20, 1]
        formatted = [f"{num:8.3f}" for num in prefix+res]
        print(", ".join(formatted))
    elif input("Do you want to show results?[Y/n]") == "Y":
        for iter in range(int(configer["result"]["iter_round"])):
            res = simulator(configer)
    else:
        sys.exit()
