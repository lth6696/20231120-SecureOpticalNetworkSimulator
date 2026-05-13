from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import islice
from typing import Any

import networkx as nx

from event.control_plane import ControlPlane
from event.flow import Flow

from .ag_sf_grooming import Segment, AuxGSecurityFirstGrooming
from .base import HeuristicAlgorithm
from .auxiliary_graph import AuxiliaryGraph

logger = logging.getLogger(__name__)


@dataclass
class AuxGCostFirstGrooming(AuxGSecurityFirstGrooming):
    """
    Auxiliary-Graph-Based Cost-First2 Grooming Algorithm.

    伪代码对应关系：
      1. 先在辅助图中寻找 K 条满足数据带宽约束、且不复用协商光路的候选数据路径 P_w；
      2. 普通业务直接接受第一条可行 P_w；
      3. 安全业务为 P_w 中的每个 lightpath hop 寻找一条 one-hop 协商路径 P_s；
      4. l == 2 时按专有成本 c_2 计算 P_s 成本；l == 1 时按共享成本 c_1 计算 P_s 成本；
      5. 在 K 条候选数据路径中选择协商路径成本最低的可行方案。
    """

    k: int
    c_p: float = 0
    c_h: float = 0

    cp: ControlPlane | None = None
    max_key_rate: float | None = None

    def simulation_interface(self, cp: ControlPlane) -> None:
        self.cp = cp
        logger.info(
            "Auxiliary-Graph-Based Cost First2 Grooming Algorithm initialized "
            "with k=%s c_p=%s c_h=%s max_key_rate=%s",
            self.k,
            self.c_p,
            self.c_h,
            self.max_key_rate,
        )

    def flow_arrival(self, flow: Flow) -> None:
        assert self.cp is not None
        logger.info("%s", "=" * 80)
        logger.info(
            "Algorithm handling flow id=%s src=%s dst=%s rate=%s security=%s kgr=%s",
            flow.id,
            flow.src,
            flow.dst,
            flow.rate,
            flow.sec,
            flow.kgr,
        )

        pt = self.cp.get_physical_topology()
        vt = self.cp.get_virtual_topology()

        ag = AuxiliaryGraph()
        G_aux = ag.get_aux_graph(pt.graph, vt.graph)

        # 数据路径不能走协商光路，并且必须满足带宽约束。
        work_graph = ag.get_sub_aux_graph(
            blocked_edges_attr={"usage": "recip", "avl_bandwidth": flow.rate}
        )

        try:
            k_paths = [
                list(path)
                for path in islice(
                    nx.shortest_simple_paths(work_graph, flow.src, flow.dst),
                    self.k,
                )
            ]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            k_paths = []

        if not k_paths:
            self.cp.block_flow(flow.id)
            return

        best_cost: float | None = None
        best_data_segments: list[Segment] = []
        best_recip_segments: list[Segment] = []

        for node_path in k_paths:
            logger.debug("Candidate data node path: %s", node_path)
            data_segments = self._turn_path_to_hops(node_path, G_aux)
            if not data_segments:
                continue

            # 普通业务不需要协商路径，直接接受第一条可行数据路径。
            if flow.sec <= 0:
                lightpaths_path_data = self._get_lightpath(G_aux, data_segments, "data")
                self.cp.accept_flow(flow.id, lightpaths={"data": lightpaths_path_data})
                return

            recip_segments = self._find_recip_paths_for_each_hop(
                ag=ag,
                data_segments=data_segments,
                flow=flow,
            )
            if not recip_segments:
                continue

            current_cost = self._calculate_recip_path_cost(G_aux, recip_segments, flow)
            logger.debug(
                "Candidate cost-first2 solution cost=%s data=%s recip=%s",
                current_cost,
                data_segments,
                recip_segments,
            )

            # todo add whether recip path is dedicate or shared
            if best_cost is None or current_cost < best_cost:
                best_cost = current_cost
                best_data_segments = data_segments
                best_recip_segments = recip_segments

        if best_data_segments and best_recip_segments:
            lightpaths_path_data = self._get_lightpath(G_aux, best_data_segments, "data")
            lightpaths_path_recip = self._get_lightpath(G_aux, best_recip_segments, "recip", "False" if flow.sec < 2 else "True")
            self.cp.accept_flow(
                flow.id,
                lightpaths={"data": lightpaths_path_data, "recip": lightpaths_path_recip},
            )
            return

        self.cp.block_flow(flow.id)

    def _find_recip_paths_for_each_hop(
        self,
        ag: AuxiliaryGraph,
        data_segments: list[Segment],
        flow: Flow,
    ) -> list[Segment]:
        """
        为数据路径中的每个 lightpath hop 寻找一条 one-hop 协商路径。

        cost_first2 与 security_first 的区别是：这里不强制 Se_ij = 0，
        只过滤本业务数据路径已经占用的辅助图边、已有数据光路，以及密钥速率不足的边。
        """
        blocked_edges = set(self._resource_edges_from_segments(data_segments))
        selected_recip_segments: list[Segment] = []

        for data_hop in data_segments:
            src = data_hop.src.node
            dst = data_hop.dst.node

            sub_graph = ag.get_sub_aux_graph(
                blocked_edges=list(blocked_edges),
                blocked_edges_attr={"usage": "data", "avl_key_rate": flow.kgr, "dedicate": "True"},
            )

            try:
                sp_node_path = nx.shortest_path(
                    sub_graph,
                    src,
                    dst,
                    # weight=lambda u, v, data: self._recip_edge_cost_weight(data),
                )
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                logger.debug("No cost-first recip path for data hop %s -> %s", src, dst)
                return []

            sp_segments = self._turn_path_to_hops(sp_node_path, sub_graph)
            logger.debug("Cost-first recip path for hop %s -> %s: %s", src, dst, sp_segments)

            # 协商路径必须是一跳，即不能由多段 lightpath 经中间业务节点拼接。
            if len(sp_segments) != 1:
                return []

            selected_recip_segments.extend(sp_segments)
            # 避免同一业务内重复占用同一条新建波长链路或重复扣减同一条已有协商光路。
            blocked_edges.update(self._resource_edges_from_segments(sp_segments))

        return selected_recip_segments

    def _calculate_recip_path_cost(
        self,
        aux_graph: nx.DiGraph,
        recip_segments: list[Segment],
        flow: Flow,
    ) -> float:
        """按照文档中的 c_2/c_1 思路计算候选协商路径成本。"""
        total_dedicated_cost = 0.0
        for seg in recip_segments:
            physical_hops = len(self._segment_physical_edges(seg))
            # 对应一条协商 lightpath 的专有成本：2*c_p + c_h * 物理波长链路数。
            total_dedicated_cost += 2.0 * self.c_p + self.c_h * physical_hops

        if flow.sec == 1:
            key_rate_capacity = self._get_max_key_rate(aux_graph)
            factor = (flow.kgr / key_rate_capacity) if key_rate_capacity > 0 else flow.kgr
            return total_dedicated_cost * factor

        # flow.sec >= 2：高安全业务按专有成本计算。
        return total_dedicated_cost

    def _recip_edge_cost_weight(self, edge_data: dict[str, Any]) -> float:
        """协商路径 SPF 权重：优先选择物理波长链路成本更低的路径。"""
        if edge_data.get("layer") == "mapping":
            return 0.0
        return max(1.0, self.c_h * len(self._route_physical_edges(edge_data.get("route", []))))

    def _get_max_key_rate(self, aux_graph: nx.DiGraph) -> float:
        capacities = [
            int(data.get("max_key_rate", 0) or 0)
            for _u, _v, data in aux_graph.edges(data=True)
        ]
        return max(capacities)

    def _physical_hops(self, segments: list[Segment]) -> int:
        return sum(len(self._segment_physical_edges(seg)) for seg in segments)
