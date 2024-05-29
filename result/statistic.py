from event.event import Event

import networkx as nx
import numpy as np


class Statistic:
    def __init__(self):
        self.callsNum = 0               # 业务需求总数
        self.totalCarriedCallsNum = 0   # 成功承载的业务总数
        self.pathHop = None             # 平均路径跳数
        self.securityPathHop = None     # 平均安全路径跳数
        self.carriedCallsList = []      # 成功承载业务列表
        self.timeStamp = []                     # 时间戳
        self.currentCallsCarriedNum = 0         # 某时间点承载业务数量
        self.currentSecurityCallsCarriedNum = 0 # 某时间点承载安全业务数量
        self.currentCallsBlockNum = 0           # 某时间点阻塞业务数量
        self.currentSecurityCallsBlockNum = 0   # 某时间点安全业务阻塞数量
        self.realTimeCallsCarried = []          # 实时承载的业务数量
        self.realTimeCallsBlocked = []          # 实时拒绝业务数量
        self.realTimeSecurityCallsCarried = []  # 实时安全业务承载数量
        self.realTimeSecurityCallsBlocked = []  # 实时安全业务拒绝数量
        self.realTimeLinkUtilization = []       # 实时平均链路利用率

    def snapshot(self, event: Event, status: bool, G: nx.MultiDiGraph, routeTable: dict):
        self.timeStamp.append(event.time)
        if event.type == "callArrive":
            self.callsNum += 1
            if status:
                # 若业务成功开通
                self.totalCarriedCallsNum += 1
                self.pathHop = np.mean([self.pathHop, len(routeTable[event.call.id]["workingPath"])]) if self.pathHop else len(routeTable[event.call.id]["workingPath"])
                self.carriedCallsList.append(event.call)
                self.currentCallsCarriedNum += 1
                if event.call.requestSecurity:
                    self.currentSecurityCallsCarriedNum += 1
                    if self.securityPathHop:
                        self.securityPathHop = np.mean([self.securityPathHop, len(routeTable[event.call.id]["workingPath"]), len(routeTable[event.call.id]["backupPath"])])
                    else:
                        self.securityPathHop = np.mean([len(routeTable[event.call.id]["workingPath"]), len(routeTable[event.call.id]["backupPath"])])
                self.realTimeSecurityCallsCarried.append(self.currentSecurityCallsCarriedNum)
                self.realTimeCallsCarried.append(self.currentCallsCarriedNum)
                self.realTimeCallsBlocked.append(self.currentCallsBlockNum)
                self.realTimeSecurityCallsBlocked.append(self.currentSecurityCallsBlockNum)
                self.realTimeLinkUtilization.append(self._calLinkUtilization(G))
            else:
                # 若业阻塞
                self.currentCallsBlockNum += 1
                self.currentSecurityCallsBlockNum += 1 if event.call.requestSecurity else 0
                self.realTimeCallsCarried.append(self.currentCallsCarriedNum)
                self.realTimeCallsBlocked.append(self.currentCallsBlockNum)
                self.realTimeSecurityCallsCarried.append(self.currentSecurityCallsCarriedNum)
                self.realTimeSecurityCallsBlocked.append(self.currentSecurityCallsBlockNum)
                self.realTimeLinkUtilization.append(self._calLinkUtilization(G))
        elif event.type == "callDeparture":
            if status:
                # 若开通的业务离去
                self.currentCallsCarriedNum -= 1
                self.currentSecurityCallsCarriedNum -= 1 if event.call.requestSecurity else 0
                self.realTimeCallsCarried.append(self.currentCallsCarriedNum)
                self.realTimeCallsBlocked.append(self.currentCallsBlockNum)
                self.realTimeSecurityCallsCarried.append(self.currentSecurityCallsCarriedNum)
                self.realTimeSecurityCallsBlocked.append(self.currentSecurityCallsBlockNum)
                self.realTimeLinkUtilization.append(self._calLinkUtilization(G))
            else:
                # 若阻塞业务离去
                self.realTimeCallsCarried.append(self.currentCallsCarriedNum)
                self.realTimeCallsBlocked.append(self.currentCallsBlockNum)
                self.realTimeSecurityCallsCarried.append(self.currentSecurityCallsCarriedNum)
                self.realTimeSecurityCallsBlocked.append(self.currentSecurityCallsBlockNum)
                self.realTimeLinkUtilization.append(self._calLinkUtilization(G))

    def _calLinkUtilization(self, G: nx.MultiDiGraph):
        linkUtilization = 0
        for (start, end, index) in G.edges:
            linkUtilization += 1 - G[start][end][index]["bandwidth"] / G[start][end][index]["max-bandwidth"]
        return linkUtilization / len(G.edges)
