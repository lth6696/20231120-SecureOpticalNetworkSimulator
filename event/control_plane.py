from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, Any

from .events import Event, FlowArrivalEvent, FlowDepartureEvent
from .flow import Flow
from exceptions import SimulationError, TopologyError
from stats import StatsCollector
from topology.physical import WDMPhysicalTopology
from topology.virtual import VirtualTopology, Lightpath
from tracer import Tracer

logger = logging.getLogger(__name__)


@dataclass
class FlowLightpathRef:
    usage: Literal["data", "recip"]
    src: int
    dst: int
    key: int
    wavelength_used: int
    route: list[Any]
    created_by_this_flow: bool


@dataclass
class ControlPlane:
    pt: WDMPhysicalTopology
    vt: VirtualTopology
    stats: StatsCollector
    tracer: Tracer
    active_flows: dict[int, Flow] = field(default_factory=dict)
    mapped_flow_lightpaths: dict[int, list[FlowLightpathRef]] = field(default_factory=dict)
    algorithm: object | None = None
    current_time: float = 0.0

    def set_algorithm(self, algorithm: object) -> None:
        self.algorithm = algorithm
        logger.info(f"Control plane bound to routing algorithm=%s", type(algorithm).__name__)

    def process_event(self, event: Event) -> None:
        # Arrivals are made visible to the algorithm before admission; departures
        # reclaim any working or backup resources still tied to the flow.
        self.current_time = event.time
        logger.debug("Processing event type=%s time=%.6f", type(event).__name__, event.time)
        if isinstance(event, FlowArrivalEvent):
            self.active_flows[event.flow.id] = event.flow
            logger.info(f"Flow arrival id={event.flow.id} src={event.flow.src} dst={event.flow.dst}")
            self.get_algorithm().flow_arrival(event.flow)
        elif isinstance(event, FlowDepartureEvent):
            if event.flow.id in self.active_flows:
                logger.info(f"Flow departure id={event.flow.id} src={event.flow.src} dst={event.flow.dst}")
                # self.get_algorithm().flow_departure(event.flow.id)
                self.remove_flow(event.flow.id)
        else:
            raise SimulationError(f"unsupported event type: {type(event).__name__}")

    def accept_flow(self, flow_id: int, lightpaths: dict) -> bool:
        flow = self.active_flows.get(flow_id)
        if flow is None:
            logger.warning("Ignoring accept for missing flow id=%d", flow_id)
            return False
        if not lightpaths:
            raise TopologyError("accept_flow requires at least one lightpath")

        physical_hops = 0
        virtual_hops = 0
        groomed = False
        # 分数据和协商路径，若占用波长，则新建光路，扣除数据速率和密钥速率
        # 若复用光路，则扣除数据速率和密钥速率
        # 为数据光路打上标记，为协商光路打上标记
        for usage, value in lightpaths.items():
            if usage == "data":
                for lightpath in value:
                    if lightpath.kind == "new":
                        # 新建光路
                        edge_key = self.vt.graph.add_edge(
                            lightpath.src,
                            lightpath.dst,
                            layer="lightpath",
                            wavelength_used=lightpath.wavelength_used,
                            max_bandwidth=lightpath.max_bandwidth,
                            max_key_rate=0,
                            avl_bandwidth=lightpath.avl_bandwidth - flow.rate,
                            avl_key_rate=0,
                            route=lightpath.route,
                            usage="data",
                            kind="exist",
                            active_flows={flow.id}
                        )
                        self.mapped_flow_lightpaths.setdefault(flow.id, []).append(
                            FlowLightpathRef(
                                usage="data",
                                src=lightpath.src,
                                dst=lightpath.dst,
                                key=edge_key,
                                wavelength_used=lightpath.wavelength_used,
                                route=lightpath.route,
                                created_by_this_flow=True,
                            )
                        )
                        virtual_hops += 1
                        # 删除波长
                        for u, v in zip(lightpath.route[:-1], lightpath.route[1:]):
                            self.pt.graph.edges[u.node, v.node]["wavelength_available"].remove(lightpath.wavelength_used)
                            self.pt.graph.edges[u.node, v.node]["wavelength_used"].append(lightpath.wavelength_used)
                            physical_hops += 1
                    elif lightpath.kind == "exist":
                        for key, attr in self.vt.graph[lightpath.src][lightpath.dst].items():
                            if attr["route"] == lightpath.route and attr["usage"] == "data":
                                attr["avl_bandwidth"] -= flow.rate
                                attr.setdefault("active_flows", set()).add(flow.id)

                                self.mapped_flow_lightpaths.setdefault(flow.id, []).append(
                                    FlowLightpathRef(
                                        usage="data",
                                        src=lightpath.src,
                                        dst=lightpath.dst,
                                        key=key,
                                        wavelength_used=lightpath.wavelength_used,
                                        route=lightpath.route,
                                        created_by_this_flow=False,
                                    )
                                )
                                break
                        virtual_hops += 1
                        groomed = True
            elif usage == "recip":
                for lightpath in value:
                    if lightpath.kind == "new":
                        edge_key = self.vt.graph.add_edge(
                            lightpath.src,
                            lightpath.dst,
                            layer="lightpath",
                            wavelength_used=lightpath.wavelength_used,
                            max_bandwidth=0,
                            max_key_rate=lightpath.max_key_rate,
                            avl_bandwidth=0,
                            avl_key_rate=lightpath.avl_key_rate - flow.kgr,
                            route=lightpath.route,
                            usage="recip",
                            kind="exist",
                            active_flows={flow.id}
                        )
                        self.mapped_flow_lightpaths.setdefault(flow.id, []).append(
                            FlowLightpathRef(
                                usage="recip",
                                src=lightpath.src,
                                dst=lightpath.dst,
                                key=edge_key,
                                wavelength_used=lightpath.wavelength_used,
                                route=lightpath.route,
                                created_by_this_flow=True,
                            )
                        )
                        virtual_hops += 1
                        # 删除波长
                        for u, v in zip(lightpath.route[:-1], lightpath.route[1:]):
                            self.pt.graph.edges[u.node, v.node]["wavelength_available"].remove(lightpath.wavelength_used)
                            self.pt.graph.edges[u.node, v.node]["wavelength_used"].append(lightpath.wavelength_used)
                            physical_hops += 1
                    elif lightpath.kind == "exist":
                        for key, attr in self.vt.graph[lightpath.src][lightpath.dst].items():
                            if attr["route"] == lightpath.route and attr["usage"] == "recip":
                                attr["avl_key_rate"] -= flow.kgr
                                attr.setdefault("active_flows", set()).add(flow.id)

                                self.mapped_flow_lightpaths.setdefault(flow.id, []).append(
                                    FlowLightpathRef(
                                        usage="recip",
                                        src=lightpath.src,
                                        dst=lightpath.dst,
                                        key=key,
                                        wavelength_used=lightpath.wavelength_used,
                                        route=lightpath.route,
                                        created_by_this_flow=False,
                                    )
                                )
                                break
                        virtual_hops += 1
                        groomed = True

        self.stats.accept_flow(
            flow=flow,
            physical_hops=int(physical_hops/2),
            virtual_hops=int(virtual_hops/2),
            groomed=groomed,
        )
        # self.tracer.record(
        #     "flow-accepted",
        #     self.current_time,
        #     flow,
        #     lightpaths=[lightpath.id for lightpath in lightpaths],
        #     groomed=groomed,
        # )
        logger.info(f"Flow {flow.id} accepted.")
        return True

    def block_flow(self, flow_id: int) -> bool:
        flow = self.active_flows.pop(flow_id, None)
        if flow is None:
            logger.warning("Ignoring block for missing flow id=%d", flow_id)
            return False
        self.stats.block_flow(flow)
        self.tracer.record("flow-blocked", self.current_time, flow)
        logger.info(
            "Flow blocked id=%d src=%d dst=%d rate=%d",
            flow.id,
            flow.src,
            flow.dst,
            flow.rate,
        )
        return True

    def remove_flow(self, flow_id: int) -> bool:
        """
        1. 根据 flow_id 找到 active flow
        2. 找到该 flow 占用的 lightpath id
        3. 释放这些 lightpath 上占用的带宽
        4. 如果 lightpath 已经空闲，则删除 lightpath
        5. 从 active_flows 中删除该 flow
        """
        flow = self.active_flows.get(flow_id)

        if flow is None:
            logger.warning("Ignoring removal for missing flow id=%d", flow_id)
            return False

        lightpath_refs = self.mapped_flow_lightpaths.pop(flow_id, [])

        for ref in lightpath_refs:
            try:
                edge_data = self.vt.graph[ref.src][ref.dst][ref.key]
            except KeyError:
                logger.warning(
                    "Virtual lightpath edge missing during flow removal: "
                    "flow_id=%d src=%s dst=%s key=%s",
                    flow_id,
                    ref.src,
                    ref.dst,
                    ref.key,
                )
                continue

            # 1. 释放虚拟光路上的业务资源
            if ref.usage == "data":
                edge_data["avl_bandwidth"] += flow.rate

            elif ref.usage == "recip":
                edge_data["avl_key_rate"] += flow.kgr

            else:
                raise TopologyError(f"unknown lightpath usage: {ref.usage}")

            # 2. 从 active_flow_ids 中删除该 flow
            active_flow_ids = edge_data.setdefault("active_flows", set())
            active_flow_ids.discard(flow_id)

            # 3. 如果该 lightpath 已经空闲，并且是动态新建的，则拆除
            if not active_flow_ids:
                for u, v in zip(edge_data["route"][:-1], edge_data["route"][1:]):
                    self.pt.graph[u.node][v.node]["wavelength_available"].append(edge_data["wavelength_used"])
                    self.pt.graph[u.node][v.node]["wavelength_used"].remove(edge_data["wavelength_used"])
                    logger.debug(f"Release resource on edge {u.node} - {v.node}: {self.pt.graph[u.node][v.node]}")

                self.vt.graph.remove_edge(
                    ref.src,
                    ref.dst,
                    key=ref.key,
                )
                logger.debug(f"Tear down lightpath {ref.src} - {ref.dst} - {ref.key}.")

                self.stats.lightpath_removed()

        del self.active_flows[flow_id]

        self.tracer.record(
            "flow-removed",
            self.current_time,
            flow,
        )

        logger.info("Flow removed id=%d", flow_id)
        return True

    def get_physical_topology(self) -> WDMPhysicalTopology:
        return self.pt

    def get_virtual_topology(self) -> VirtualTopology:
        return self.vt

    def get_algorithm(self):
        if self.algorithm is None:
            raise SimulationError("routing algorithm has not been installed")
        return self.algorithm
