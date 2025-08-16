import logging
import pandas as pd
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

from utl.event import Event
from network.generator import TopoGen, CallsGen

# todo change the way of calculate sec deviation
class MeanList:
    def __init__(self):
        self.real_time_list = []

    def add(self, value: float):
        self.real_time_list.append(value)

    def get(self):
        return np.mean(self.real_time_list)


class MultiMeanList:
    def __init__(self, num: int):
        self.real_time_list = [[] for _ in range(num)]

    def add(self, index: int, value: any):
        self.real_time_list[index].append(value)

    def get(self):
        mean_for_all_list = np.mean([value for _list in self.real_time_list for value in _list])
        mean_for_each_list = [np.mean(_list) for _list in self.real_time_list]

        return mean_for_all_list, *mean_for_each_list


class Statistic:
    def __init__(self):
        self.time_stamp = [0.0]  # 时间戳

        self.num_total_calls = 0  # 总业务数量
        self.num_carried_calls = 0  # 成功路由业务总数
        self.num_blocked_calls = 0  # 阻塞业务总数

        self.success_rate = []  # 业务成功率
        self.block_rate = []  # 业务阻塞率

        self.mean_hop = 0.0  # 平均路径跳数

        self.realtime_num_carried_calls = [0]  # 实时承载业务数量
        self.realtime_num_blocked_calls = [0]  # 实时阻塞业务数量
        self.realtime_link_utilization = [0.0]

        self.mean_link_utilization = 0.0  # 平均链路利用率

        self.mean_security_deviation = MultiMeanList(3)  # 平均值 - 路径安全性与业务需求的偏差值
        self.mean_exposure_ratio = MultiMeanList(3)  # 平均值 - 路径安全风险暴露比率
        self.overused_bandwidth = 0  # 被超额使用的带宽

        self.content_displayable_results = [
            "block_rate",
            "mean_hop",
            "mean_link_utilization",
            "overused_bandwidth",
            "mean_security_deviation",
            "mean_exposure_ratio"
        ]

    def snapshot(self, event: Event, topo_gen: TopoGen, tfk_gen: CallsGen):
        calls = tfk_gen.calls
        G = topo_gen.G

        if event.type == "simEnd":
            self._update_block_rate(tfk_gen)
            self._update_overused_bw(topo_gen, tfk_gen)
            self._update_hop(calls)
        else:
            self.time_stamp.append(event.time)

            # 基础网络参数
            self._update_num_calls(calls, event)
            self._update_link_utilization(G)

            # 自定义性能参数
            self._update_security(G, event, tfk_gen.cfg_call_security[-1], topo_gen.cfg_link_security[-1])

    def show(self):
        results = []
        for attr in self.content_displayable_results:
            if isinstance(getattr(self, attr), MeanList):
                results.append(getattr(self, attr).get())
            else:
                results.append(getattr(self, attr))
        ser = pd.Series(results, index=self.content_displayable_results)
        print(ser)

    def get(self):
        results = []
        for attr in self.content_displayable_results:
            if isinstance(getattr(self, attr), MeanList):
                results.append(getattr(self, attr).get())
            elif isinstance(getattr(self, attr), MultiMeanList):
                data = getattr(self, attr).get()
                for x in data:
                    results.append(x)
            elif isinstance(getattr(self, attr), list):
                results = results + getattr(self, attr)
            else:
                results.append(getattr(self, attr))
        return results

    def plot_real_time_carried_service(self):
        self._plot_single_line(self.time_stamp, self.realtime_num_carried_calls,
                               xylabel=["time", "real time carried services"])

    def plot_real_time_blocked_service(self):
        self._plot_single_line(self.time_stamp, self.realtime_num_blocked_calls,
                               xylabel=["time", "real time blocked services"])

    def plot_real_time_link_utilization(self):
        self._plot_single_line(self.time_stamp, self.realtime_link_utilization,
                               xylabel=["time", "real time link utilization"])

    def _plot_single_line(self, x, y, xylabel: list):
        plt.plot(x, y, ls='solid', lw=1, color="#73C0DE")
        plt.xlabel(xylabel[0])
        plt.ylabel(xylabel[1])
        plt.show()

    def _update_num_calls(self, calls: list, event: Event):
        if self.num_total_calls == 0:
            self.num_total_calls = len(calls)
        if self.num_total_calls != 0 and self.num_total_calls != len(calls):
            raise ValueError
        call = event.event
        # 查询当前业务状态
        if event.type == "eventArrive":
            if call.is_routed:
                self.num_carried_calls += 1
                self.realtime_num_carried_calls.append(self.realtime_num_carried_calls[-1] + 1)
                self.realtime_num_blocked_calls.append(self.realtime_num_blocked_calls[-1])
            else:
                self.num_blocked_calls += 1
                self.realtime_num_carried_calls.append(self.realtime_num_carried_calls[-1])
                self.realtime_num_blocked_calls.append(self.realtime_num_blocked_calls[-1] + 1)
        elif event.type == "eventDeparture":
            if call.is_routed:
                self.realtime_num_carried_calls.append(self.realtime_num_carried_calls[-1] - 1)
                self.realtime_num_blocked_calls.append(self.realtime_num_blocked_calls[-1])
            else:
                self.realtime_num_carried_calls.append(self.realtime_num_carried_calls[-1])
                self.realtime_num_blocked_calls.append(self.realtime_num_blocked_calls[-1])

        logging.debug(
            f"The number of blocked calls {self.num_blocked_calls} + carried calls {self.num_carried_calls} -> total calls {self.num_total_calls}")

    def _update_block_rate(self, tfk_gen: CallsGen):
        if not self.num_total_calls:
            return
        # self.success_rate.add(self.num_carried_calls / self.num_total_calls * 100)
        self.block_rate = [0 for _ in range(tfk_gen.cfg_call_security[-1] + 1)]
        self.success_rate = [0 for _ in range(tfk_gen.cfg_call_security[-1] + 1)]
        for call in tfk_gen.calls:
            if not call.is_routed:
                self.block_rate[call.security] += 1
            else:
                self.success_rate[call.security] += 1
        self.block_rate = [sum(self.block_rate) / self.num_total_calls * 100] + [x / self.num_total_calls * 100 for x in
                                                                                 self.block_rate]
        self.success_rate = [sum(self.success_rate) / self.num_total_calls * 100] + [x / self.num_total_calls * 100 for
                                                                                     x in self.success_rate]

    def _update_hop(self, calls: list):
        hops = []
        for call in calls:
            if call.path and call.is_routed:
                hops.append(len(call.path) - 1)
            elif call.path == [] and call.is_routed == False:
                continue
            else:
                logging.error(
                    f"When update hop for call {call.id}, it is routed {call.is_routed} but with path {call.path}.")
        self.mean_hop = np.mean(hops)

    def _update_link_utilization(self, G: nx.Graph):
        each_link_utilization = []
        for u_node, v_node in G.edges:
            each_link_utilization.append(
                (1 - G[u_node][v_node]["link_available_bandwidth"] / G[u_node][v_node]["link_bandwidth"]) * 100)
        self.realtime_link_utilization.append(np.mean(each_link_utilization))

        len_list = len(self.realtime_link_utilization)
        self.mean_link_utilization = np.mean(
            self.realtime_link_utilization[int(len_list / 3): int(2 * len_list / 3)])  # 抽样中间1/3个点的平均值
        logging.debug(f"Mean link utilization is {self.mean_link_utilization}.")
        # 校验
        if 100 < self.mean_link_utilization < 0:
            raise Exception("The value of the average of link utilization {} is invalidation."
                            .format(self.mean_link_utilization))

    def _update_overused_bw(self, topo_gen: TopoGen, tfk_gen: CallsGen):
        for call in tfk_gen.calls:
            if not call.is_routed:
                continue
            for u_node, v_node in zip(call.path[:-1], call.path[1:]):
                # 若链路加密，但业务不需要安全性，则视为超用
                if topo_gen.G[u_node][v_node]["link_security"] == 1 and call.security == 0:
                    self.overused_bandwidth += call.rate

    def _update_security(self, G: nx.Graph, event: Event, num_req_security: int, num_link_security: int):
        # 更新安全性偏差与不同业务的暴露率
        call = event.event
        if event.type == "eventArrive":
            # 1 安全偏差 \sqrt{\frac{\sum_{(i,j)\in p}{(sec_{req}-sec_{(i,j)})^2}}{|p|}}
            if call.path:
                logging.debug(f"===== STATISTIC SEC INFO =====")
                div_value = 0.0
                for (u, v) in zip(call.path[:-1], call.path[1:]):
                    div_value += (G[u][v]['link_security'] - (
                            num_link_security * call.security / num_req_security)) ** 2
                    logging.debug(
                        f"Service {call.id} has security: {call.security}, link {u}-{v} sec: {G[u][v]['link_security']}")
                div_value = (div_value / (len(call.path) - 1)) ** 0.5
                self.mean_security_deviation.add(call.security, div_value)
                logging.debug(f"Service {call.id} has security deviation {div_value}.")

                # 2 暴露率 \frac{\sum_{(i,j)\in p}{dist_{insec}(i,j)}}{\sum_{(i,j)\in p}{dist(i,j)}}
                expo_value = [0.0, 0.0]
                for (u, v) in zip(call.path[:-1], call.path[1:]):
                    distance = ((G.nodes[u]["Latitude"] - G.nodes[v]["Latitude"]) ** 2 +
                                (G.nodes[u]["Longitude"] - G.nodes[v]["Longitude"]) ** 2) ** 0.5
                    if G[u][v]["link_security"] == 0:
                        expo_value[0] += distance  # 记录非安全路径长度
                    expo_value[1] += distance  # 记录总路径长度
                    logging.debug(
                        f"Service {call.id} through link {u}-{v} with {G[u][v]["link_security"]}, distance {distance}, "
                        f"risk link {expo_value[0]}, total link {expo_value[1]}.")
                self.mean_exposure_ratio.add(call.security, expo_value[0] / expo_value[1] * 100)
                logging.debug(f"Service {call.id} has exposure ratio {expo_value[0] / expo_value[1] * 100}.")
