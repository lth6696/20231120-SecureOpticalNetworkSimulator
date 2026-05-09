from __future__ import annotations

import logging
import networkx as nx
from itertools import islice
from dataclasses import dataclass
from typing import Any

from wdm_sim.event.control_plane import ControlPlane
from wdm_sim.event.flow import Flow

from .auxiliary_graph import AuxiliaryGraph, VirtualNode
from .base import HeuristicAlgorithm

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Segment:
    src: Any
    dst: Any
    kind: str # new_ltp or exist_ltp
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
        logger.info(f"Algorithm handling flow id={flow.id} src={flow.src} dst={flow.dst} rate={flow.rate} security={flow.sec}")
        pt = self.cp.get_physical_topology()
        vt = self.cp.get_virtual_topology()

        # 构建光路波长辅助图
        ag = AuxiliaryGraph()
        G_aux = ag.get_aux_graph(pt.graph, vt.graph)
        sub_graph = ag.get_sub_aux_graph(blocked_edges={"usage": "recip"})

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
                feasible = True
                hops_recip = []
                hops = self._turn_path_to_hops(path, G_aux)

                for hop in hops:
                    sp = self._find_reciprocal_path_for_hop(ag, hops, hop, flow)
                    if sp is None:
                        feasible = False
                        break
                    hops_recip.append(sp)

                # 如果所有数据跳都有密钥路径，则接受该数据路径
                if feasible:
                    path_data = path
                    path_recip = hops_recip
                    logger.debug(f"Data path is {path_data}.")
                    logger.debug(f"Recip path is {path_recip}.")
                    break

            if not path_data or not path_recip:
                self.cp.block_flow(flow.id)
            else:
                self._allocate_resource(flow, G_aux, path_data, path_recip)
        # 如果 flow 不需要安全
        else:
            # 选择第一条满足速率要求的路径
            return

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
    ) -> list:
        # 约束一：扣除源宿节点
        # 约束二：扣除源宿链路
        # todo 约束三：扣除所有数据路径
        # 约束四：满足密钥速率要求
        sub_graph = aux_graph.get_sub_aux_graph(
            blocked_nodes=[hop.src for hop in hops] + [hop.dst for hop in hops],
            blocked_edges=[(hop.src, hop.dst) for hop in hops],
            blocked_edges_attr={"max_key_rate": flow.kgr}
        )
        try:
            path = nx.shortest_path(sub_graph, current_hop.src.node, current_hop.dst.node)
        except:
            path = []
        return path

    def _turn_path_to_hops(self, path: list, aux_graph: nx.DiGraph) -> list[tuple]:
        hops: list[Segment] = []
        route = []
        for u, v in zip(path[:-1], path[1:]):
            # logger.debug(f"{u}, {v}")
            if aux_graph.edges[u, v]["layer"] == "mapping":
                if aux_graph.nodes[v]["layer"] == "wavelength":
                    route.append(v)
                elif aux_graph.nodes[u]["layer"] == "wavelength":
                    hops.append(
                        Segment(
                            src=route[0],
                            dst=u,
                            kind="new_lightpath",
                            route=route,
                            wavelength=u.wavelength
                        )
                    )
                    route = []
            elif aux_graph.edges[u, v]["layer"] == "wavelength":
                # hops.append(
                #     Segment(
                #         src=u,
                #         dst=v,
                #         kind="new_lightpath",
                #         route=aux_graph.edges[u, v]["physical_route"],
                #         wavelength=aux_graph.edges[u, v]["wavelength"]
                #     )
                # )
                route.append(v)
            elif aux_graph.edges[u, v]["layer"] == "lightpath":
                hops.append(
                    Segment(
                        src=u,
                        dst=v,
                        kind="exist_lightpath",
                        route=aux_graph.edges[u, v]["physical_route"],
                        wavelength=aux_graph.edges[u, v]["wavelength"]
                    )
                )
            else:
                raise ValueError
            # logger.debug(f"{route}")

        return hops

    def _allocate_resource(
            self,
            flow: Flow,
            aux_graph: nx.DiGraph,
            path_data: list,
            path_recip: list = None
    ):
        # 修改辅助图，若占用波长，则新建光路，扣除数据速率和密钥速率
        # 若复用光路，则扣除数据速率和密钥速率
        # 为数据光路打上标记，为协商光路打上标记
        hops: [Segment] = self._turn_path_to_hops(path_data, aux_graph)
        for hop in hops:
            build_lightpath = False
            logger.debug(f"{hop.route}")
            for u, v in zip(hop.route[:-1], hop.route[1:]):
                if aux_graph.edges[u, v]["layer"] == "lightpath":
                    aux_graph.edges[u, v]["ava_bandwidth"] -= flow.rate
                    logger.debug(f"Lightpath {u} to {v} changes bandwidth to {aux_graph.edges[u, v]["ava_bandwidth"]}")

                # 若占用波长，则新建光路, 需要检查光路是否由多个链路构成
                elif aux_graph.edges[u, v]["layer"] == "wavelength":
                    build_lightpath = True
                    max_bandwidth = aux_graph.edges[u, v]["max_bandwidth"]
                    ava_bandwidth = aux_graph.edges[u, v]["max_bandwidth"] - flow.rate
                    aux_graph.remove_edge(u, v)
                    logger.debug(f"Aux graph's edge {u} to {v} has been removed.")

            if build_lightpath:
                aux_graph.add_edge(
                    VirtualNode(hop.src.node, hop.wavelength, 0),
                    VirtualNode(hop.dst.node, hop.wavelength, 0),
                    layer="lightpath",
                    wavelength=hop.wavelength,
                    physical_route=hop.route,
                    max_bandwidth=max_bandwidth,
                    ava_bandwidth=ava_bandwidth,
                    max_key_rate=0,
                    ava_key_rate=0,
                    usage="data"
                )
                logger.debug(f"Aux graph's lightpath from {VirtualNode(hop.src.node, hop.wavelength, 0)} to {VirtualNode(hop.dst.node, hop.wavelength, 0)} has been built.")

        hops: [Segment] = self._turn_path_to_hops(path_recip, aux_graph)
        for hop in hops:
            build_lightpath = False
            for u, v in zip(hop.route[:-1], hop.route[1:]):
                # 若占用波长，则新建光路, 需要检查光路是否由多个链路构成
                if aux_graph.edges[u, v]["layer"] == "wavelength":
                    build_lightpath = True
                    max_key_rate = aux_graph.edges[u, v]["max_key_rate"]
                    ava_key_rate = aux_graph.edges[u, v]["max_key_rate"] - flow.kgr
                    aux_graph.remove_edge(u, v)
                    logger.debug(f"Aux graph's edge {u} to {v} has been removed.")
                elif aux_graph.edges[u, v]["layer"] == "lightpath":
                    aux_graph.edges[u, v]["ava_key_rate"] -= flow.kgr
                    logger.debug(
                        f"Lightpath {u} to {v} changes bandwidth to {aux_graph.edges[u, v]["ava_bandwidth"]}")
            if build_lightpath:
                aux_graph.add_edge(
                    VirtualNode(hop.src.node, hop.wavelength, 0),
                    VirtualNode(hop.dst.node, hop.wavelength, 0),
                    layer="lightpath",
                    wavelength=hop.wavelength,
                    physical_route=hop.route,
                    max_bandwidth=0,
                    ava_bandwidth=0,
                    max_key_rate=max_key_rate,
                    ava_key_rate=ava_key_rate,
                    usage="recip"
                )
                logger.debug(f"Aux graph's lightpath from {VirtualNode(hop.src.node, hop.wavelength, 0)} to {VirtualNode(hop.dst.node, hop.wavelength, 0)} has been built.")


