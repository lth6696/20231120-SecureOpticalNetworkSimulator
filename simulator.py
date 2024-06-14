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
    return statistic.content_displayable_results, statistic.get()


if __name__ == '__main__':
    # 配置日志文件
    logging.config.fileConfig('logconfig.ini')

    # 仿真配置文件
    configFile = "./topology/NSFNet.xml"
    ResultFile = "results.xlsx"
    iterRound = 20
    isSimulate = False
    collector = {"title": [], "results": []}

    # 开始仿真
    if isSimulate:
        with multiprocessing.Pool(processes=iterRound) as pool:
            for _ in range(iterRound):
                title, result = pool.apply_async(simulator, (configFile, )).get()
                if not collector["title"]:
                    collector["title"] = title
                collector["results"].append(result)
            pool.close()
            pool.join()
        df = pd.DataFrame(collector["results"], columns=collector["title"])
        print(df.mean())
    else:
        if not os.path.exists(ResultFile):
            raise Exception("File does not exist.")
        data = pd.read_excel(ResultFile)
        title = {
            3: "success rate (%)",
            4: "success rate of security calls (%)",
            5: "success rate of normal calls (%)",
            6: "the number of hops",
            7: "the number of hops of security calls",
            8: "the number of hops of normal calls",
            9: "link utilization (%)",
            10: "path risk level (%)",
            11: "the number of path risk",
            12: "the number of joint risk"
        }
        col = 12
        x = [100 * (i + 1) for i in range(6)]
        y = [list(data.iloc[0+i*6 : 6+i*6, col])[::-1] for i in range(3)]
        label = ["SOSR-U", "SOSR-S", "Benchmark"]
        pc = result.curve.PlotCurve()
        pc.plotMultiRealTime(x, *y, label=label, axis_name=["load (in Erlang)", title[col]])
