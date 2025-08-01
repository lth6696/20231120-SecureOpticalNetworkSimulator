import logging

import pandas as pd

from utl.event import Event

import networkx as nx
import numpy as np
import matplotlib.pyplot as plt


class MeanList:
    def __init__(self):
        self.real_time_list = []

    def add(self, value: float):
        self.real_time_list.append(value)

    def get(self):
        return np.mean(self.real_time_list)


class Statistic:
    def __init__(self):
        self.time_stamp = [0.0]                   # 时间戳

        self.num_total_calls = 0                # 总业务数量
        self.num_carried_calls = 0              # 成功路由业务总数
        self.num_blocked_calls = 0              # 阻塞业务总数

        self.success_rate = MeanList()          # 业务成功率
        self.block_rate = MeanList()            # 业务阻塞率

        self.mean_hop = 0.0                     # 平均路径跳数

        self.realtime_num_carried_calls = [0]    # 实时承载业务数量
        self.realtime_num_blocked_calls = [0]    # 实时阻塞业务数量
        self.realtime_link_utilization = [0.0]

        self.mean_link_utilization = 0.0        # 平均链路利用率

        self.content_displayable_results = [
            "success_rate",
            "block_rate",
            "mean_hop",
            "mean_link_utilization"
        ]

    def snapshot(self, event: Event, G: nx.DiGraph, calls: list):
        self.time_stamp.append(event.time)
        self._update_num_calls(calls, event)
        self._update_block_rate()
        self._update_hop(calls)
        self._update_link_utilization(G)

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
            else:
                results.append(getattr(self, attr))
        return results

    def plot_real_time_carried_service(self):
        self._plot_single_line(self.time_stamp, self.realtime_num_carried_calls, xylabel=["time", "real time carried services"])

    def plot_real_time_blocked_service(self):
        self._plot_single_line(self.time_stamp, self.realtime_num_blocked_calls, xylabel=["time", "real time blocked services"])

    def plot_real_time_link_utilization(self):
        self._plot_single_line(self.time_stamp, self.realtime_link_utilization, xylabel=["time", "real time link utilization"])

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

        logging.debug(f"The number of blocked calls {self.num_blocked_calls} + carried calls {self.num_carried_calls} -> total calls {self.num_total_calls}")

    def _update_block_rate(self):
        if not self.num_total_calls:
            return
        self.success_rate.add(self.num_carried_calls / self.num_total_calls * 100)
        self.block_rate.add(self.num_blocked_calls / self.num_total_calls * 100)

    def _update_hop(self, calls: list):
        hops = []
        for call in calls:
            if call.path is None:
                continue
            hops.append(len(call.path)-1)
        self.mean_hop = np.mean(hops)

    def _update_link_utilization(self, G: nx.Graph):
        each_link_utilization = []
        for u_node, v_node in G.edges:
            each_link_utilization.append((1 - G[u_node][v_node]["link_available_bandwidth"] / G[u_node][v_node]["link_bandwidth"]) * 100)
        self.realtime_link_utilization.append(np.mean(each_link_utilization))

        len_list = len(self.realtime_link_utilization)
        self.mean_link_utilization = np.mean(self.realtime_link_utilization[int(len_list/3): int(2*len_list/3)])    # 抽样中间1/3个点的平均值
        logging.debug(f"Mean link utilization is {self.mean_link_utilization}.")
        # 校验
        if 100 < self.mean_link_utilization < 0:
            raise Exception("The value of the average of link utilization {} is invalidation."
                            .format(self.mean_link_utilization))
