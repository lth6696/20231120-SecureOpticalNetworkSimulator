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
        self.time_stamp = []                    # 时间戳

        self.num_total_calls = 0                # 总业务数量
        self.num_carried_calls = 0              # 成功路由业务总数
        self.num_blocked_calls = 0              # 阻塞业务总数

        self.success_rate = MeanList()          # 业务成功率
        self.block_rate = MeanList()            # 业务阻塞率

        self.mean_hop = MeanList()              # 平均路径跳数

        self.realtime_num_carried_calls = [0]    # 实时承载业务数量
        self.realtime_num_blocked_calls = [0]    # 实时阻塞业务数量
        self.realtime_link_utilization = [0]
        self.realtime_attacks = []  #todo delete this attr

        self.mean_link_utilization = 0.0        # 平均链路利用率

        self.content_displayable_results = [
            "success_rate",
            "block_rate",
            "mean_hop",
            "mean_link_utilization"
        ]

    def snapshot(self, event: Event, G: nx.DiGraph, calls: list):
        self.time_stamp.append(event.time)
        self._update_real_time_events(event)
        self._update_num_calls(calls, event)
        self._update_block_rate()
        self._update_hop(calls)

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
        plt.plot(self.realtime_num_carried_calls)
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
            else:
                self.num_blocked_calls += 1
                self.realtime_num_blocked_calls.append(self.realtime_num_blocked_calls[-1] + 1)
        elif event.type == "eventDeparture":
            if call.is_routed:
                self.realtime_num_carried_calls.append(self.realtime_num_carried_calls[-1] - 1)

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
        self.mean_hop.add(np.mean(hops))

    def _update_link_utilization(self, G: nx.MultiDiGraph):
        lu = 0.0
        for (start, end, index) in G.edges:
            lu += (1 - G[start][end][index]["bandwidth"] / G[start][end][index]["max-bandwidth"]) * 100
        lu = lu / len(G.edges)
        self.realtime_link_utilization.append(lu)
        self.mean_link_utilization = np.mean(self.realtime_link_utilization)
        # 校验
        if 100 < self.mean_link_utilization < 0:
            raise Exception("The value of the average of link utilization {} is invalidation."
                            .format(self.mean_link_utilization))

    def _update_real_time_events(self, event: Event):
        if event.type == "eventArrive":
            n_atks = self.realtime_attacks[-1] + 1 if self.realtime_attacks else 1
            self.realtime_attacks.append(n_atks)
        elif event.type == "eventDeparture":
            n_atks = self.realtime_attacks[-1] - 1
            self.realtime_attacks.append(n_atks)

