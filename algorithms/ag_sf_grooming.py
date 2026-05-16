from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import islice
from typing import Any

import networkx as nx

from models.flow import Flow
from topology import Lightpath

from .auxiliary_graph import AuxiliaryGraph
from .ag_jdr_grooming import AuxGJointDataRecipGrooming
from .base import AlgInput, AlgOutput

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Segment:
    """一段可被 accept_flow 消耗/复用的光路资源。"""

    src: Any
    dst: Any
    kind: str  # "new" or "exist"
    wavelength: int
    route: list[Any]


class AuxGSecurityFirstGrooming(AuxGJointDataRecipGrooming):
    """
    Auxiliary-Graph-Based Security-First Grooming Algorithm.

    flow.sec 的语义：
      - 0：普通业务，只建立/复用数据光路；
      - 1：中安全业务，先尝试每个数据 hop 配一条与数据资源隔离的协商光路；
           若失败，则退化为 s-d 端到端协商路径，并按 NSe 权重选择较少占用的协商资源；
      - 2 及以上：高安全业务，只接受每个数据 hop 都有隔离协商光路的方案。
    """
    def __init__(self, k: int = 8):
        super().__init__(k)
        self.k = k

        logger.info(f"Auxiliary-Graph-Based Security First Grooming Algorithm initialized with k=%s", self.k)

    def flow_arrival(self, alg_input: AlgInput) -> AlgOutput:
        pt = alg_input.pt
        vt = alg_input.vt
        flow = alg_input.flow
        logger.info(f"Algorithm handling flow {flow}")

        # 1. 构建当前时刻的辅助图。
        ag = AuxiliaryGraph()
        G_aux = ag.get_aux_graph(pt.graph, vt.graph)

        # 2. 数据路径不能走协商光路，并且必须满足带宽约束。
        G_sub = ag.get_sub_aux_graph(
            blocked_edges_attr={
                "usage": "recip",
                "avl_bandwidth": flow.rate
            }
        )

        paths = self._get_kpaths(G_sub, flow.src, flow.dst, self.k)
        if not paths:
            return AlgOutput()

        # 3. Security-first：对每条候选数据路径，优先寻找满足安全约束的协商路径。
        for path in paths:
            logger.debug("Candidate data node path: %s", path)

            lightpaths_data = self._find_lightpaths(path, G_aux, "data")

            # 普通业务：数据路径可行即可接受。
            if flow.attrs["sec"] == 0:
                return AlgOutput(status=True, routes={"data": lightpaths_data})

            # 高/中安全业务：先找逐 hop 隔离协商路径。
            lightpaths_recip = self._find_reciprocal_lightpath_for_secure(
                ag=ag,
                lightpaths=lightpaths_data,
                flow=flow,
                is_loose=False
            )

            # 中安全业务：若逐离失败，允许退化共路传输。
            if (not lightpaths_recip) and (flow.attrs["sec"] == 1):
                lightpaths_recip = self._find_reciprocal_lightpath_for_secure(
                    ag=ag,
                    lightpaths=lightpaths_data,
                    flow=flow,
                    is_loose=True
                )

            if lightpaths_recip and lightpaths_data:
                logger.info("Accepted data lightpaths: %s", lightpaths_data)
                logger.info("Accepted recip lightpaths: %s", lightpaths_recip)
                return AlgOutput(status=True, routes={"data": lightpaths_data, "recip": lightpaths_recip})

        return AlgOutput()

    def _find_reciprocal_lightpath_for_secure(
        self,
        ag: AuxiliaryGraph,
        lightpaths: [Lightpath],
        flow: Flow,
        is_loose: False
    ) -> [Lightpath]:
        """
        为数据路径中的每个 lightpath 寻找一条 同端点的协商路径。

        约束：
         - 异路传输
         - 协商路径分散承载
        """
        blocked_edges = []
        for lightpath in lightpaths:
            blocked_edges.append((lightpath.src, lightpath.dst))
            for u, v in self._get_node_pairs(lightpath.route):
                blocked_edges.append((u, v))

        if not is_loose:
            logger.debug(f"Disable In-band Transmission with req {flow.attrs["sec"]}.")
            # 协商路径不能经过本业务数据路径占用的任何波长链路，即异路传输。
            forbidden_data_phy_edges = self._data_occupied_physical_edges(ag.aux_graph)
            for seg in lightpaths:
                forbidden_data_phy_edges.update(self._segment_physical_edges(seg))
            blocked_edges += self._aux_edges_intersecting_physical_edges(ag.aux_graph, forbidden_data_phy_edges)

        ns_by_phy_edge = self._recip_channel_count_by_physical_edge(ag.aux_graph)
        selected_recip_segments: list[Lightpath] = []

        for data_hop in lightpaths:
            src = self._physical_endpoint(data_hop.src)
            dst = self._physical_endpoint(data_hop.dst)

            sub_graph = ag.get_sub_aux_graph(
                blocked_edges=list(blocked_edges),
                blocked_edges_attr={"usage": "data", "avl_key_rate": flow.attrs["kgr"]},
            )

            try:
                sp_node_path = nx.shortest_path(
                    sub_graph,
                    src,
                    dst,
                    weight=lambda u, v, data: self._security_edge_weight(data, ns_by_phy_edge),
                )
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                logger.debug("No isolated recip path for data hop %s -> %s", src, dst)
                return []

            sp_segments = self._find_lightpaths(sp_node_path, ag.aux_graph, "recip")
            logger.debug("Isolated recip path for hop %s -> %s: %s", src, dst, sp_segments)

            # 协商路径必须是一跳，即不经过中间 OEO/业务汇聚节点。
            if len(sp_segments) != 1:
                return []

            selected_recip_segments.extend(sp_segments)

            # 避免同一业务内重复占用同一条新建波长资源；也避免重复扣减同一条已有协商光路。
            blocked_edges.extend(self._resource_edges_from_segments(sp_segments))

        return selected_recip_segments

    def _turn_path_to_hops(self, path: list[Any], aux_graph: nx.DiGraph) -> list[Segment]:
        """将辅助图节点路径转换成 accept_flow 可消费的 Segment 列表。"""
        if not path:
            return []

        hops: list[Segment] = []
        route: list[Any] = []

        for u, v in zip(path[:-1], path[1:]):
            edge_data = aux_graph.edges[u, v]
            layer = edge_data["layer"]

            if layer == "mapping":
                if aux_graph.nodes[v]["layer"] == "wavelength":
                    route = [v]
                elif aux_graph.nodes[u]["layer"] == "wavelength":
                    if not route:
                        raise ValueError(f"Invalid auxiliary path, empty wavelength route before edge {u}->{v}")
                    hops.append(
                        Segment(
                            src=route[0],
                            dst=u,
                            kind="new",
                            route=route,
                            wavelength=u.wavelength,
                        )
                    )
                    route = []

            elif layer == "wavelength":
                route.append(v)

            elif layer == "lightpath":
                hops.append(
                    Segment(
                        src=u,
                        dst=v,
                        kind="exist",
                        route=edge_data["route"],
                        wavelength=edge_data.get("wavelength", edge_data.get("wavelength_used")),
                    )
                )
            else:
                raise ValueError(f"Unknown auxiliary edge layer: {layer}")

        return hops

    def _get_lightpath(self, aux_graph: nx.DiGraph, path: list[Segment], usage: str, is_dedicate="False") -> list[Lightpath]:
        lightpaths: list[Lightpath] = []
        for seg in path:
            if seg.kind == "exist":
                edge_data = aux_graph.edges[seg.src, seg.dst]
                lightpaths.append(
                    Lightpath(
                        src=self._physical_endpoint(seg.src),
                        dst=self._physical_endpoint(seg.dst),
                        wavelength_used=seg.wavelength,
                        max_bandwidth=edge_data["max_bandwidth"],
                        max_key_rate=edge_data["max_key_rate"],
                        avl_bandwidth=edge_data["avl_bandwidth"],
                        avl_key_rate=edge_data["avl_key_rate"],
                        route=edge_data["route"],
                        usage=edge_data["usage"],
                        kind="exist",
                        layer="lightpath",
                        dedicate=edge_data["dedicate"]
                    )
                )
            elif seg.kind == "new":
                first_edge_data = aux_graph.edges[seg.route[0], seg.route[1]]
                lightpaths.append(
                    Lightpath(
                        src=self._physical_endpoint(seg.src),
                        dst=self._physical_endpoint(seg.dst),
                        wavelength_used=seg.wavelength,
                        max_bandwidth=first_edge_data["max_bandwidth"] if usage == "data" else 0,
                        max_key_rate=first_edge_data["max_key_rate"] if usage == "recip" else 0,
                        avl_bandwidth=first_edge_data["max_bandwidth"] if usage == "data" else 0,
                        avl_key_rate=first_edge_data["max_key_rate"] if usage == "recip" else 0,
                        route=seg.route,
                        usage=usage,
                        kind="new",
                        layer="lightpath",
                        dedicate=is_dedicate
                    )
                )
            else:
                raise ValueError(f"Unknown segment kind: {seg.kind}")
        return lightpaths

    @staticmethod
    def _physical_endpoint(node: Any) -> int:
        return node if isinstance(node, int) else node.node

    def _resource_edges_from_segments(self, segments: list[Lightpath]) -> list[tuple[Any, Any]]:
        resource_edges: list[tuple[Any, Any]] = []
        for seg in segments:
            if seg.kind == "new":
                resource_edges.extend(zip(seg.route[:-1], seg.route[1:]))
            elif seg.kind == "exist":
                resource_edges.append((seg.src, seg.dst))
        return resource_edges

    def _data_occupied_physical_edges(self, aux_graph: nx.DiGraph) -> set[tuple[int, int]]:
        occupied: set[tuple[int, int]] = set()
        for _u, _v, data in aux_graph.edges(data=True):
            if data.get("layer") == "lightpath" and data.get("usage") == "data":
                occupied.update(self._route_physical_edges(data.get("route", [])))
        return occupied

    def _recip_channel_count_by_physical_edge(self, aux_graph: nx.DiGraph) -> dict[tuple[int, int], int]:
        counts: dict[tuple[int, int], int] = {}
        for _u, _v, data in aux_graph.edges(data=True):
            if data.get("layer") == "lightpath" and data.get("usage") == "recip":
                for phy_edge in self._route_physical_edges(data.get("route", [])):
                    counts[phy_edge] = counts.get(phy_edge, 0) + 1
        return counts

    def _aux_edges_intersecting_physical_edges(
        self,
        aux_graph: nx.DiGraph,
        forbidden_phy_edges: set[tuple[int, int]],
    ) -> list[tuple[Any, Any]]:
        blocked: list[tuple[Any, Any]] = []
        if not forbidden_phy_edges:
            return blocked

        for u, v, data in aux_graph.edges(data=True):
            if data.get("layer") not in {"wavelength", "lightpath"}:
                continue
            if self._route_physical_edges(data.get("route", [])) & forbidden_phy_edges:
                blocked.append((u, v))
        return blocked

    def _segment_physical_edges(self, seg: Segment) -> set[tuple[int, int]]:
        return self._route_physical_edges(seg.route)

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

    def _security_edge_weight(self, edge_data: dict[str, Any], ns_by_phy_edge: dict[tuple[int, int], int]) -> float:
        """SPF 的 NSe 权重：优先选择已有协商信道数量更少的物理链路。"""
        if edge_data.get("layer") == "mapping":
            return 0.0

        phy_edges = self._route_physical_edges(edge_data.get("route", []))
        if not phy_edges:
            return 1.0

        # +1 是物理跳数项，避免所有无协商占用链路权重都为 0；
        # sum(NSe) 是安全优先项。
        return float(len(phy_edges) + sum(ns_by_phy_edge.get(edge, 0) for edge in phy_edges))
