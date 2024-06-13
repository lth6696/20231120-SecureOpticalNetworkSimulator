import pandas as pd

from event.event import Event

import networkx as nx
import numpy as np


class Statistic:
    def __init__(self):
        self.time_stamp = []                    # 时间戳

        self.num_total_calls = 0                # 总业务数量
        self.num_sec_req_calls = 0              # 安全需求业务数量
        self.num_norm_req_calls = 0             # 普通需求业务数量
        self.num_carried_calls = 0              # 成功路由业务总数
        self.num_carried_sec_req_calls = 0      # 成功路由安全需求业务数
        self.num_carried_norm_req_calls = 0     # 成功路由普通需求业务数
        self.num_blocked_calls = 0              # 阻塞业务总数
        self.num_blocked_sec_req_calls = 0      # 阻塞安全需求业务数
        self.num_blocked_norm_req_calls = 0     # 阻塞普通需求业务数

        self.success_rate_total_calls = 0.0     # 业务成功率
        self.success_rate_sec_req_calls = 0.0   # 安全需求业务成功率
        self.success_rate_norm_req_calls = 0.0  # 普通需求业务成功率
        self.block_rate_total_calls = 0.0       # 业务阻塞率
        self.block_rate_sec_req_calls = 0.0     # 安全需求业务阻塞率
        self.block_rate_norm_req_calls = 0.0    # 普通需求业务阻塞率

        self.mean_hop = 0.0                         # 平均路径跳数
        self.mean_hop_sec_req_calls = 0.0           # 平均安全业务跳数
        self.mean_hop_norm_req_calls = 0.0          # 平均普通业务跳数
        self.mean_hop_working_path = 0.0            # 平均工作路径跳数
        self.mean_hop_backup_path = 0.0             # 平均保护路径跳数
        self.mean_hop_working_path_sec_req = 0.0    # 平均安全业务工作路径跳数
        self.mean_hop_backup_path_sec_req = 0.0     # 平均安全业务保护路径跳数
        self.mean_hop_working_path_norm_req = 0.0   # 平均普通业务工作路径跳数
        self.mean_hop_backup_path_norm_req = 0.0    # 平均普通业务保护路径跳数

        self.mean_num_high_tapping_risk = 0.0       # 平均高窃听风险数量
        self.mean_num_joint_tapping_risk = 0.0      # 平均共享窃听风险数量
        self.mean_level_high_tapping_risk = 0.0     # 平均高窃听风险度（%）
        self.mean_level_joint_taping_risk = 0.0     # 平均共享窃听度(%)

        self.realtime_num_carried_calls = []        # 实时承载的业务数量
        self.realtime_num_carried_sec_calls = []    # 实时安全业务承载数量
        self.realtime_num_carried_norm_calls = []   # 实时普通业务承载数量

        self.mean_link_utilization = 0.0            # 平均链路利用率

        self.content_displayable_results = [
            "success_rate_total_calls", "success_rate_sec_req_calls", "success_rate_norm_req_calls",
            "block_rate_total_calls", "block_rate_sec_req_calls", "block_rate_norm_req_calls",
            "mean_hop", "mean_hop_sec_req_calls", "mean_hop_norm_req_calls", "mean_hop_working_path", "mean_hop_backup_path",
            "mean_num_high_tapping_risk", "mean_num_joint_tapping_risk", "mean_level_high_tapping_risk", "mean_level_joint_taping_risk",
            "mean_link_utilization"
        ]

    def snapshot(self, event: Event, status: bool, G: nx.MultiDiGraph, routeTable: dict):
        self.time_stamp.append(event.time)
        self._update_real_time_calls(event, status)
        self._update_link_utilization(G)

        if event.type == "callArrive":
            self._update_num_calls(event, status)
            self._update_block_rate()
            self._update_hop(event, status, routeTable)
            self._update_tapping_risk(event, status, routeTable, G)
        elif event.type == "callDeparture":
            pass

    def show(self):
        results = []
        for attr in self.content_displayable_results:
            results.append(getattr(self, attr))
        ser = pd.Series(results, index=self.content_displayable_results)
        print(ser)

    def _update_num_calls(self, event: Event, status: bool):
        self.num_total_calls += 1
        if status:
            self.num_carried_calls += 1
            if event.call.requestSecurity:
                self.num_sec_req_calls += 1
                self.num_carried_sec_req_calls += 1
            else:
                self.num_norm_req_calls += 1
                self.num_carried_norm_req_calls += 1
        else:
            self.num_blocked_calls += 1
            if event.call.requestSecurity:
                self.num_sec_req_calls += 1
                self.num_blocked_sec_req_calls += 1
            else:
                self.num_norm_req_calls += 1
                self.num_blocked_norm_req_calls += 1
        # 校验
        if self.num_total_calls != self.num_carried_calls + self.num_blocked_calls:
            raise Exception("The sum of blocking calls {} and carried calls {} "
                            "is not equal to the total number of calls {}."
                            .format(self.num_blocked_calls, self.num_carried_calls, self.num_total_calls))
        if self.num_total_calls != self.num_sec_req_calls + self.num_norm_req_calls:
            raise Exception("The sum of sec-required calls {} and norm-required calls {} "
                            "is not equal to the total number of calls {}."
                            .format(self.num_sec_req_calls, self.num_norm_req_calls, self.num_total_calls))
        if self.num_carried_calls != self.num_carried_sec_req_calls + self.num_carried_norm_req_calls:
            raise Exception("The number of sec-required carried calls {} and norm-required carried calls {} "
                            "does not match the number of carried calls {}."
                            .format(self.num_carried_sec_req_calls, self.num_carried_norm_req_calls,
                                    self.num_carried_calls))
        if self.num_blocked_calls != self.num_blocked_sec_req_calls + self.num_blocked_norm_req_calls:
            raise Exception("The number of sec-required blocked calls {} and norm-required blocked calls {} "
                            "does not match the number of blocked calls {}."
                            .format(self.num_blocked_sec_req_calls, self.num_blocked_norm_req_calls,
                                    self.num_blocked_calls))

    def _update_block_rate(self):
        if self.num_total_calls != 0:
            self.success_rate_total_calls = self.num_carried_calls / self.num_total_calls * 100
            self.block_rate_total_calls = self.num_blocked_calls / self.num_total_calls * 100
            if round(self.success_rate_total_calls + self.block_rate_total_calls) != 100:
                raise Exception("The sum of the success rate {} and the blocking rate {} is not 100%."
                                .format(self.success_rate_total_calls, self.block_rate_total_calls))
        if self.num_sec_req_calls != 0:
            self.success_rate_sec_req_calls = self.num_carried_sec_req_calls / self.num_sec_req_calls * 100
            self.block_rate_sec_req_calls = self.num_blocked_sec_req_calls / self.num_sec_req_calls * 100
            if round(self.success_rate_sec_req_calls + self.block_rate_sec_req_calls) != 100:
                raise Exception("The sum of sec calls of the success rate {} and the blocking rate {} is not 100%."
                                .format(self.success_rate_sec_req_calls, self.block_rate_sec_req_calls))
        if self.num_norm_req_calls != 0:
            self.success_rate_norm_req_calls = self.num_carried_norm_req_calls / self.num_norm_req_calls * 100
            self.block_rate_norm_req_calls = self.num_blocked_norm_req_calls / self.num_norm_req_calls * 100
            if round(self.success_rate_norm_req_calls + self.block_rate_norm_req_calls) != 100:
                raise Exception("The sum of norm calls of the success rate {} and the blocking rate {} is not 100%."
                                .format(self.success_rate_norm_req_calls, self.block_rate_norm_req_calls))

    def _update_hop(self, event: Event, status: bool, routing_table: dict):
        if status:
            hop_working_path = len(routing_table[event.call.id]["workingPath"])
            hop_backup_path = len(routing_table[event.call.id]['backupPath'])
            mean_hop_call = self._mean(hop_working_path, hop_backup_path)
            self.mean_hop = self._mean(self.mean_hop, mean_hop_call)
            self.mean_hop_working_path = self._mean(self.mean_hop_working_path, hop_working_path)
            self.mean_hop_backup_path = self._mean(self.mean_hop_backup_path, hop_backup_path)
            if event.call.requestSecurity:
                self.mean_hop_sec_req_calls = self._mean(self.mean_hop_sec_req_calls, mean_hop_call)
                self.mean_hop_working_path_sec_req = self._mean(self.mean_hop_working_path_sec_req, hop_working_path)
                self.mean_hop_backup_path_sec_req = self._mean(self.mean_hop_backup_path_sec_req, hop_backup_path)
            else:
                self.mean_hop_norm_req_calls = self._mean(self.mean_hop_norm_req_calls, mean_hop_call)
                self.mean_hop_working_path_norm_req = self._mean(self.mean_hop_working_path_norm_req, hop_working_path)
                self.mean_hop_backup_path_norm_req = self._mean(self.mean_hop_backup_path_norm_req, hop_backup_path)
        else:
            pass

    def _update_tapping_risk(self, event: Event, status: bool, routing_table: dict, G: nx.MultiDiGraph):
        def num_link_tapping_risk(G: nx.MultiDiGraph, path: list):
            num = 0
            for (s, e, i) in path:
                for risk in G[s][e][i]["risk"]:
                    if "H" in risk:
                        num += 1
            return num

        def num_joint_tapping_risk(G: nx.MultiDiGraph, workingPath: list, backupPath: list):
            workingPathRisk = [G[s][d][i]["risk"] for (s, d, i) in workingPath]
            backupPathRisk = [G[s][d][i]["risk"] for (s, d, i) in backupPath]
            jointRiskNum = len([risk for risk in workingPathRisk if risk in backupPathRisk])
            return jointRiskNum

        if status:
            working_path = routing_table[event.call.id]["workingPath"]
            backup_path = routing_table[event.call.id]["backupPath"]
            if event.call.requestSecurity:
                joint_tapping_risk = num_joint_tapping_risk(G, working_path, backup_path)
                tapping_risk_working_path = num_link_tapping_risk(G, working_path)
                tapping_risk_backup_path = num_link_tapping_risk(G, backup_path)
                mean_tapping_risk = self._mean(tapping_risk_working_path, tapping_risk_backup_path)
                mean_tapping_risk_level = self._mean(tapping_risk_working_path / len(working_path) * 100,
                                                     tapping_risk_backup_path / len(backup_path) * 100)

                self.mean_num_high_tapping_risk = self._mean(self.mean_num_high_tapping_risk, mean_tapping_risk)
                self.mean_level_high_tapping_risk = self._mean(self.mean_level_high_tapping_risk, mean_tapping_risk_level)
                self.mean_num_joint_tapping_risk = self._mean(self.mean_num_joint_tapping_risk, joint_tapping_risk)
                self.mean_level_joint_taping_risk = self._mean(self.mean_level_joint_taping_risk,
                                                               joint_tapping_risk / (len(working_path) + len(backup_path)) * 100)
            else:
                pass
        else:
            pass

    def _update_link_utilization(self, G: nx.MultiDiGraph):
        lu = 0.0
        for (start, end, index) in G.edges:
            lu += (1 - G[start][end][index]["bandwidth"] / G[start][end][index]["max-bandwidth"]) * 100
        lu = lu / len(G.edges)
        self.mean_link_utilization = self._mean(self.mean_link_utilization, lu)
        # 校验
        if 100 < self.mean_link_utilization < 0:
            raise Exception("The value of the average of link utilization {} is invalidation."
                            .format(self.mean_link_utilization))

    def _update_real_time_calls(self, event: Event, status: bool):
        def calls(a: list):
            if not a:
                return 0
            else:
                return a[-1]

        if event.type == "callArrive":
            if status:
                self.realtime_num_carried_calls.append(calls(self.realtime_num_carried_calls) + 1)
                if event.call.requestSecurity:
                    self.realtime_num_carried_sec_calls.append(calls(self.realtime_num_carried_sec_calls) + 1)
                else:
                    self.realtime_num_carried_norm_calls.append(calls(self.realtime_num_carried_norm_calls) + 1)
            else:
                self.realtime_num_carried_calls.append(calls(self.realtime_num_carried_calls))
                self.realtime_num_carried_sec_calls.append(calls(self.realtime_num_carried_sec_calls))
                self.realtime_num_carried_norm_calls.append(calls(self.realtime_num_carried_norm_calls))
        elif event.type == "callDeparture":
            if status:
                self.realtime_num_carried_calls.append(calls(self.realtime_num_carried_calls) - 1)
                if event.call.requestSecurity:
                    self.realtime_num_carried_sec_calls.append(calls(self.realtime_num_carried_sec_calls) - 1)
                else:
                    self.realtime_num_carried_norm_calls.append(calls(self.realtime_num_carried_norm_calls) - 1)
            else:
                self.realtime_num_carried_calls.append(calls(self.realtime_num_carried_calls))
                self.realtime_num_carried_sec_calls.append(calls(self.realtime_num_carried_sec_calls))
                self.realtime_num_carried_norm_calls.append(calls(self.realtime_num_carried_norm_calls))

    def _mean(self, a, b):
        if a * b == 0:
            return a + b
        else:
            return np.mean([a, b])