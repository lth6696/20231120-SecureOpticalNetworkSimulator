from __future__ import annotations

import logging
import networkx as nx
from itertools import islice
from dataclasses import dataclass
from typing import Any

from event.control_plane import ControlPlane
from event.flow import Flow
from topology import Lightpath

from .auxiliary_graph import AuxiliaryGraph, VirtualNode
from .base import HeuristicAlgorithm

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Segment:
    src: Any
    dst: Any
    kind: str # new or exist
    wavelength: int
    route: list | None


@dataclass
class AuxGJointDataRecipGrooming(HeuristicAlgorithm):
    k: int = 3
    cp: ControlPlane | None = None

    def simulation_interface(self, cp: ControlPlane) -> None:
        self.cp = cp
        logger.info(f"Auxiliary-Graph-Based Joint Data-and-Key Path Grooming Algorithm initialized with k={self.k}")

    def flow_arrival(self, flow: Flow) -> None:
        assert self.cp is not None
        logger.info(f"{"="*80}")
        logger.info(f"Algorithm handling flow id={flow.id} src={flow.src} dst={flow.dst} rate={flow.rate} security={flow.sec} kgr={flow.kgr}")
        pt = self.cp.get_physical_topology()
        vt = self.cp.get_virtual_topology()

        # 构建光路波长辅助图
        ag = AuxiliaryGraph()
        G_aux = ag.get_aux_graph(pt.graph, vt.graph)
        sub_graph = ag.get_sub_aux_graph(blocked_edges_attr={"usage": "recip", "avl_bandwidth": flow.rate})

        # 寻找K条路径
        try:
            k_paths = [list(path) for path in islice(nx.shortest_simple_paths(sub_graph, flow.src, flow.dst), self.k)]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            k_paths = []

        if not k_paths:
            self.cp.block_flow(flow.id)
            return

        # 如果 flow 需要安全
        if flow.sec:
            # 寻找数据路径和协商路径，要求协商路径与数据路径同端点
            path_data = []
            path_recip = []
            for path in k_paths:
                logger.debug(f"Data path: {path}")
                feasible = True
                hops_recip = []
                hops = self._turn_path_to_hops(path, G_aux)

                for hop in hops:
                    logger.debug(f"Hop: {hop}")
                    sp = self._find_reciprocal_path_for_hop(ag, hops, hop, flow)
                    logger.debug(f"Recip hop: {sp}")
                    if sp is None:
                        feasible = False
                        break
                    hops_recip.append(*sp)

                # 如果所有数据跳都有密钥路径，则接受该数据路径
                if feasible:
                    path_data = hops
                    path_recip = hops_recip
                    logger.debug(f"Data path is {path_data}.")
                    logger.debug(f"Recip path is {path_recip}.")
                    break

            if not path_data or not path_recip:
                self.cp.block_flow(flow.id)
            else:
                # self._allocate_resource(flow, G_aux, path_data, path_recip)
                lightpaths_path_data = self._get_lightpath(G_aux, path_data, "data")
                lightpaths_path_recip = self._get_lightpath(G_aux, path_recip, "recip")
                logger.debug(f"Data Lightpath: {lightpaths_path_data}")
                logger.debug(f"Recip Lightpath: {lightpaths_path_recip}")
                self.cp.accept_flow(flow.id, lightpaths={"data": lightpaths_path_data, "recip": lightpaths_path_recip})
        # 如果 flow 不需要安全
        else:
            # 选择第一条满足速率要求的路径
            path_data = self._turn_path_to_hops(k_paths[0], G_aux)
            lightpaths_path_data = self._get_lightpath(G_aux, path_data, "data")
            self.cp.accept_flow(flow.id, lightpaths={"data": lightpaths_path_data})


    def flow_departure(self, flow_id: int) -> None:
        return None

    def simulation_end(self) -> None:
        return None

    def _find_reciprocal_path_for_hop(
            self,
            aux_graph: AuxiliaryGraph,
            hops: [Segment],
            current_hop: Segment,
            flow: Flow
    ):
        blocked_edges = []
        for seg in hops:
            # 若将用波长链路构成新的光路：将波长链路滤除
            for u, v in zip(seg.route[:-1], seg.route[1:]):
                blocked_edges.append((u, v))
            # 若复用已有光路：将光路滤除
            blocked_edges.append((seg.src, seg.dst))
        # 约束：扣除所有数据路径, 满足密钥速率要求
        sub_graph = aux_graph.get_sub_aux_graph(
            blocked_edges=blocked_edges,
            blocked_edges_attr={"usage": "data", "avl_key_rate": flow.kgr}
        )
        try:
            path = nx.shortest_path(sub_graph, current_hop.src.node, current_hop.dst.node)
        except:
            path = []

        hop = self._turn_path_to_hops(path, sub_graph)
        if len(hop) == 1:
            # 若协商信道是一跳联通的
            return hop
        else:
            # 若需要OEO 则无法构成测量信道
            return None

    def _turn_path_to_hops(self, path: list, aux_graph: nx.DiGraph) -> list[tuple]:
        hops: list[Segment] = []
        route = []
        for u, v in zip(path[:-1], path[1:]):
            if aux_graph.edges[u, v]["layer"] == "mapping":
                if aux_graph.nodes[v]["layer"] == "wavelength":
                    route.append(v)
                elif aux_graph.nodes[u]["layer"] == "wavelength":
                    hops.append(
                        Segment(
                            src=route[0],
                            dst=u,
                            kind="new",
                            route=route,
                            wavelength=u.wavelength
                        )
                    )
                    route = []
            elif aux_graph.edges[u, v]["layer"] == "wavelength":
                route.append(v)
            elif aux_graph.edges[u, v]["layer"] == "lightpath":
                hops.append(
                    Segment(
                        src=u,
                        dst=v,
                        kind="exist",
                        route=aux_graph.edges[u, v]["route"],
                        wavelength=aux_graph.edges[u, v]["wavelength"]
                    )
                )
            else:
                raise ValueError

        return hops

    def _get_lightpath(self, aux_graph: nx.DiGraph, path: list[Segment], usage: str) -> list[Lightpath]:
        lightpaths = []
        for seg in path:
            if seg.kind == "exist":
                lp = Lightpath(
                    src=seg.src.node,
                    dst=seg.dst.node,
                    wavelength_used=seg.wavelength,
                    max_bandwidth=aux_graph.edges[seg.src, seg.dst]["max_bandwidth"],
                    max_key_rate=aux_graph.edges[seg.src, seg.dst]["max_key_rate"],
                    avl_bandwidth=aux_graph.edges[seg.src, seg.dst]["avl_bandwidth"],
                    avl_key_rate=aux_graph.edges[seg.src, seg.dst]["avl_key_rate"],
                    route=aux_graph.edges[seg.src, seg.dst]["route"],
                    usage=aux_graph.edges[seg.src, seg.dst]["usage"],
                    kind="exist",
                    layer="lightpath"
                )
                lightpaths.append(lp)
            else:
                lp = Lightpath(
                    src=seg.src.node,
                    dst=seg.dst.node,
                    wavelength_used=seg.wavelength,
                    max_bandwidth=aux_graph.edges[seg.route[0], seg.route[1]]["max_bandwidth"] if usage == "data" else 0,
                    max_key_rate=aux_graph.edges[seg.route[0], seg.route[1]]["max_key_rate"] if usage == "recip" else 0,
                    avl_bandwidth=aux_graph.edges[seg.route[0], seg.route[1]]["max_bandwidth"] if usage == "data" else 0,
                    avl_key_rate=aux_graph.edges[seg.route[0], seg.route[1]]["max_key_rate"] if usage == "recip" else 0,
                    route=seg.route,
                    usage=usage,
                    kind="new",
                    layer="lightpath"
                )
                lightpaths.append(lp)
        return lightpaths

