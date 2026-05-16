from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from models.flow import Flow
from topology import Lightpath
from .ag_jdr_grooming import AuxGJointDataRecipGrooming
from .auxiliary_graph import AuxiliaryGraph
from .base import AlgOutput, AlgInput

logger = logging.getLogger(__name__)


class AuxGCostFirstGrooming(AuxGJointDataRecipGrooming):
    """
    Auxiliary-Graph-Based Cost-First2 Grooming Algorithm.

    伪代码对应关系：
      1. 先在辅助图中寻找 K 条满足数据带宽约束、且不复用协商光路的候选数据路径 P_w；
      2. 普通业务直接接受第一条可行 P_w；
      3. 安全业务为 P_w 中的每个 lightpath hop 寻找一条 one-hop 协商路径 P_s；
      4. l == 2 时按专有成本 c_2 计算 P_s 成本；l == 1 时按共享成本 c_1 计算 P_s 成本；
      5. 在 K 条候选数据路径中选择协商路径成本最低的可行方案。
    """

    def __init__(self, k: int = 8, c_p: int = 0, c_h: int = 0):
        super().__init__()
        self.k = k

        self.c_p = c_p
        self.c_h = c_h

        self.max_key_rate: float | None = None

        logger.info(f"Auxiliary-Graph-Based Cost First Grooming Algorithm initialized with k={self.k}")

    def flow_arrival(self, alg_input: AlgInput) -> AlgOutput:
        pt = alg_input.pt
        vt = alg_input.vt
        flow = alg_input.flow
        logger.info(f"Algorithm handling flow {flow}")

        # 1. 构建当前时刻的辅助图。
        ag = AuxiliaryGraph()
        G_aux = ag.get_aux_graph(pt.graph, vt.graph)

        # 数据路径不能走协商光路，并且必须满足带宽约束。
        G_sub = ag.get_sub_aux_graph(
            blocked_edges_attr={
                "usage": "recip",
                "avl_bandwidth": flow.rate
            }
        )

        paths = self._get_kpaths(G_sub, flow.src, flow.dst, self.k)
        if not paths:
            return AlgOutput()

        best_cost: float | None = None
        best_data_segments: list[Lightpath] = []
        best_recip_segments: list[Lightpath] = []

        for path in paths:
            logger.debug("Candidate data path: %s", path)

            lightpaths_data = self._find_lightpaths(path, G_aux, "data")

            # 普通业务不需要协商路径，直接接受第一条可行数据路径。
            if flow.attrs["sec"] == 0:
                return AlgOutput(status=True, routes={"data": lightpaths_data})

            recip_segments = self._find_reciprocal_lightpath(
                ag=ag,
                lightpaths=lightpaths_data,
                flow=flow,
            )
            if not recip_segments:
                continue
            logger.debug(f"Candidate recip path is {recip_segments}")

            current_cost = self._calculate_recip_path_cost(G_aux, recip_segments, flow)
            logger.debug(
                "Candidate CF solution cost=%s",
                current_cost
            )

            if best_cost is None or current_cost < best_cost:
                best_cost = current_cost
                best_data_segments = lightpaths_data
                best_recip_segments = recip_segments

        if best_data_segments and best_recip_segments:
            logger.info("Accepted data lightpaths: %s", best_data_segments)
            logger.info("Accepted recip lightpaths: %s", best_recip_segments)
            return AlgOutput(status=True, routes={"data": best_data_segments, "recip": best_recip_segments})

        return AlgOutput()

    def _find_reciprocal_lightpath(
        self,
        ag: AuxiliaryGraph,
        lightpaths: list[Lightpath],
        flow: Flow,
    ) -> list[Lightpath]:
        blocked_edges = []
        for lightpath in lightpaths:
            blocked_edges.append((lightpath.src, lightpath.dst))
            for u, v in self._get_node_pairs(lightpath.route):
                blocked_edges.append((u, v))

        selected_recip_segments: list[Lightpath] = []
        for lightpath in lightpaths:
            src = lightpath.src
            dst = lightpath.dst

            sub_graph = ag.get_sub_aux_graph(
                blocked_edges=list(blocked_edges),
                blocked_edges_attr={"usage": "data", "avl_key_rate": flow.attrs["kgr"], "dedicate": "True"},
            )

            try:
                sp_node_path = nx.shortest_path(
                    sub_graph,
                    src,
                    dst,
                    weight=lambda u, v, data: self._recip_edge_cost_weight(data),
                )
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                logger.debug("No cost-first recip path for data hop %s -> %s", src, dst)
                return []

            sp_segments = self._find_lightpaths(sp_node_path, sub_graph, "recip")
            logger.debug("Cost-first recip path for hop %s -> %s: %s", src, dst, sp_segments)

            # 协商路径必须是一跳，即不能由多段 lightpath 经中间业务节点拼接。
            if len(sp_segments) != 1:
                return []

            selected_recip_segments.extend(sp_segments)

            # 避免同一业务内重复占用同一条新建波长链路或重复扣减同一条已有协商光路。
            blocked_edges.extend(self._resource_edges_from_segments(sp_segments))

        return selected_recip_segments

    def _calculate_recip_path_cost(
        self,
        aux_graph: nx.DiGraph,
        recip_segments: list[Lightpath],
        flow: Flow,
    ) -> float:
        """按照文档中的 c_2/c_1 思路计算候选协商路径成本。"""
        total_dedicated_cost = 0.0
        max_key_rate = []
        for seg in recip_segments:
            physical_hops = len(self._segment_physical_edges(seg))
            # 对应一条协商 lightpath 的专有成本：2*c_p + c_h * 物理波长链路数。
            total_dedicated_cost += 2.0 * self.c_p + self.c_h * physical_hops
            max_key_rate.append(seg.max_key_rate)
        max_key_rate = min(max_key_rate)

        if flow.attrs["sec"] == 1:
            factor = flow.attrs["kgr"] / max_key_rate if max_key_rate > 0 else flow.attrs["kgr"]
            return total_dedicated_cost * factor

        # flow.sec >= 2：高安全业务按专有成本计算。
        return total_dedicated_cost

    def _recip_edge_cost_weight(self, edge_data: dict[str, Any]) -> float:
        """协商路径 SPF 权重：优先选择物理波长链路成本更低的路径。"""
        if edge_data.get("layer") == "mapping":
            return 0.0
        return max(1.0, self.c_h * len(self._route_physical_edges(edge_data.get("route", []))))

    @staticmethod
    def _route_physical_edges(route: list[Any]) -> set[tuple[int, int]]:
        """兼容 [(u, v)] 形式和 [WavelengthNode(...), ...] 形式的 route。"""
        if not route:
            return set()

        # AuxiliaryGraph 中 wavelength edge 的 route 是 [(u, v)]。
        if all(isinstance(item, tuple) and len(item) == 2 for item in route):
            return {(int(u), int(v)) for u, v in route}

        # VirtualTopology 中 lightpath 的 route 是 WavelengthNode 列表。
        physical_edges: set[tuple[int, int]] = set()
        for u, v in zip(route[:-1], route[1:]):
            if hasattr(u, "node") and hasattr(v, "node"):
                physical_edges.add((u.node, v.node))
        return physical_edges

    def _resource_edges_from_segments(self, segments: list[Lightpath]) -> list[tuple[Any, Any]]:
        resource_edges: list[tuple[Any, Any]] = []
        for seg in segments:
            if seg.kind == "new":
                resource_edges.extend(zip(seg.route[:-1], seg.route[1:]))
            elif seg.kind == "exist":
                resource_edges.append((seg.src, seg.dst))
        return resource_edges

    def _segment_physical_edges(self, seg: Lightpath) -> set[tuple[int, int]]:
        return self._route_physical_edges(seg.route)
