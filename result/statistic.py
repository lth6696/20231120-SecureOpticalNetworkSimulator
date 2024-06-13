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

        self.mean_link_utilization = []         # 平均链路利用率

    def snapshot(self, event: Event, status: bool, G: nx.MultiDiGraph, routeTable: dict):
        self.time_stamp.append(event.time)
        if event.type == "callArrive":
            self._update_num_calls(event, status)
            self._update_block_rate()
            self._update_hop(event, status, routeTable)
            self._update_tapping_risk(event, status, routeTable, G)

            if status:
                # 若业务成功开通
                self.realtime_num_carried_calls += 1
                if event.call.requestSecurity:
                    self.realtime_num_carried_sec_calls += 1
                    if self.mean_num_high_tapping_risk:
                        self.mean_num_high_tapping_risk = np.mean([self.mean_num_high_tapping_risk, self._calLinkRisky(G, routeTable[event.call.id]["workingPath"]), self._calLinkRisky(G, routeTable[event.call.id]["backupPath"])])
                    else:
                        self.mean_num_high_tapping_risk = np.mean([self._calLinkRisky(G, routeTable[event.call.id]["workingPath"]), self._calLinkRisky(G, routeTable[event.call.id]["backupPath"])])
                    if self.mean_num_joint_tapping_risk:
                        self.mean_num_joint_tapping_risk = np.mean([self.mean_num_joint_tapping_risk, self._calJointRisk(G, routeTable[event.call.id]["workingPath"], routeTable[event.call.id]["backupPath"])])
                    else:
                        self.mean_num_joint_tapping_risk = np.mean([self._calJointRisk(G, routeTable[event.call.id]["workingPath"], routeTable[event.call.id]["backupPath"])])
                    if self.mean_hop_sec_req_calls:
                        self.mean_hop_sec_req_calls = np.mean([self.mean_hop_sec_req_calls, len(routeTable[event.call.id]["workingPath"]), len(routeTable[event.call.id]["backupPath"])])
                    else:
                        self.mean_hop_sec_req_calls = np.mean([len(routeTable[event.call.id]["workingPath"]), len(routeTable[event.call.id]["backupPath"])])
                else:
                    self.realtime_num_carried_norm_calls += 1
            else:
                # 若业阻塞
                self.currentCallsBlockNum += 1
                self.currentSecurityCallsBlockNum += 1 if event.call.requestSecurity else 0
                self.currentNormalCallsBlockNum += 1 if not event.call.requestSecurity else 0
        elif event.type == "callDeparture":
            if status:
                # 若开通的业务离去
                self.realtime_num_carried_calls -= 1
                self.realtime_num_carried_sec_calls -= 1 if event.call.requestSecurity else 0
                self.realtime_num_carried_norm_calls -= 1 if not event.call.requestSecurity else 0
            else:
                # 若阻塞业务离去
                pass

        self.mean_link_utilization.append(self._calLinkUtilization(G))

    def show(self):
        """
        np.divide(statistic.totalCarriedCallsNum, statistic.callsNum) * 100,
        np.divide(statistic.totalCarriedSecCallsNum, statistic.secCallsNum) * 100,
        np.divide(statistic.totalCarriedNomCallsNum, statistic.nomCallsNum) * 100,
        statistic.pathHop,
        statistic.securityPathHop,
        np.mean(statistic.realTimeLinkUtilization[int(len(statistic.realTimeLinkUtilization)/3): int(len(statistic.realTimeLinkUtilization)*2/3)]),
        statistic.meanRiskLevel,
        statistic.meanJointRiskLevel
        """
        pass

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
        if self.num_sec_req_calls != 0:
            self.success_rate_sec_req_calls = self.num_carried_sec_req_calls / self.num_sec_req_calls * 100
            self.block_rate_sec_req_calls = self.num_blocked_sec_req_calls / self.num_sec_req_calls * 100
        if self.num_norm_req_calls != 0:
            self.success_rate_norm_req_calls = self.num_carried_norm_req_calls / self.num_norm_req_calls * 100
            self.block_rate_norm_req_calls = self.num_blocked_norm_req_calls / self.num_norm_req_calls * 100
        # 校验
        if self.success_rate_total_calls + self.block_rate_total_calls != 100:
            raise Exception("The sum of the success rate {} and the blocking rate {} is not 100%."
                            .format(self.success_rate_total_calls, self.block_rate_total_calls))
        if self.success_rate_sec_req_calls + self.block_rate_sec_req_calls != 100:
            raise Exception("The sum of sec calls of the success rate {} and the blocking rate {} is not 100%."
                            .format(self.success_rate_sec_req_calls, self.block_rate_sec_req_calls))
        if self.success_rate_norm_req_calls + self.block_rate_norm_req_calls != 100:
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
        """
        self.mean_num_high_tapping_risk = 0.0       # 平均高窃听风险数量
        self.mean_num_joint_tapping_risk = 0.0      # 平均共享窃听风险数量
        self.mean_level_high_tapping_risk = 0.0     # 平均高窃听风险度（%）
        self.mean_level_joint_taping_risk = 0.0     # 平均共享窃听度(%)
        """
        def calLinkRisky(self, G: nx.MultiDiGraph, path: list):
            riskLinkNum = 0
            for (start, end, index) in path:
                for risk in G[start][end][index]["risk"]:
                    if "H" in risk:
                        riskLinkNum += 1
            return riskLinkNum / len(path) * 100
        if status:
            if event.call.requestSecurity:
                pass
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
        if self.mean_link_utilization > 100 and self.mean_link_utilization < 0:
            raise Exception("")

    def _calJointRisk(self, G: nx.MultiDiGraph, workingPath: list, backupPath: list):
        workingPathRisk = [G[s][d][i]["risk"] for (s, d, i) in workingPath]
        backupPathRisk = [G[s][d][i]["risk"] for (s, d, i) in backupPath]
        jointRiskNum = len([risk for risk in workingPathRisk if risk in backupPathRisk])
        return jointRiskNum

    def _mean(self, a, b):
        if a * b == 0:
            return a + b
        else:
            return np.mean([a, b])