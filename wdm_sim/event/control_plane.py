from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .events import Event, FlowArrivalEvent, FlowDepartureEvent
from .flow import Flow
from wdm_sim.exceptions import SimulationError, TopologyError
from wdm_sim.stats import StatsCollector
from wdm_sim.topology.physical import WDMPhysicalTopology
from wdm_sim.topology.virtual import VirtualTopology, Lightpath
from wdm_sim.tracer import Tracer

logger = logging.getLogger(__name__)


@dataclass
class ControlPlane:
    pt: WDMPhysicalTopology
    vt: VirtualTopology
    stats: StatsCollector
    tracer: Tracer
    active_flows: dict[int, Flow] = field(default_factory=dict)
    mapped_flows_single_path: dict[int, list[int]] = field(default_factory=dict)
    mapped_backup_lightpaths: dict[int, list[int]] = field(default_factory=dict)
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
                self.get_algorithm().flow_departure(event.flow.id)
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
                        self.vt.graph.add_edge(
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
                            kind="exist"
                        )
                        virtual_hops += 1
                        # 删除波长
                        for u, v in zip(lightpath.route[:-1], lightpath.route[1:]):
                            self.pt.graph.edges[u.node, v.node]["wavelength_available"].remove(lightpath.wavelength_used)
                            self.pt.graph.edges[u.node, v.node]["wavelength_used"].append(lightpath.wavelength_used)
                            physical_hops += 1
                    elif lightpath.kind == "exist":
                        for key, attr in self.vt.graph[lightpath.src][lightpath.dst].items():
                            if self.vt.graph[lightpath.src][lightpath.dst][key]["route"] == lightpath.route:
                                self.vt.graph[lightpath.src][lightpath.dst][key]["avl_bandwidth"] -= flow.rate
                                break
                        virtual_hops += 1
                        groomed = True
            elif usage == "recip":
                for lightpath in value:
                    if lightpath.kind == "new":
                        self.vt.graph.add_edge(
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
                            kind="exist"
                        )
                        virtual_hops += 1
                        # 删除波长
                        for u, v in zip(lightpath.route[:-1], lightpath.route[1:]):
                            self.pt.graph.edges[u.node, v.node]["wavelength_available"].remove(lightpath.wavelength_used)
                            self.pt.graph.edges[u.node, v.node]["wavelength_used"].append(lightpath.wavelength_used)
                            physical_hops += 1
                    elif lightpath.kind == "exist":
                        for key, attr in self.vt.graph[lightpath.src][lightpath.dst].items():
                            if self.vt.graph[lightpath.src][lightpath.dst][key]["route"] == lightpath.route:
                                self.vt.graph[lightpath.src][lightpath.dst][key]["avl_key_rate"] -= flow.kgr
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
        # Removing a flow releases bandwidth first, then tears down any idle
        # working or reserved backup lightpaths that were created for it.
        flow = self.active_flows.get(flow_id)
        if flow is None:
            logger.warning("Ignoring removal for missing flow id=%d", flow_id)
            return False
        lightpath_ids = self.mapped_flows_single_path.pop(flow_id, [])
        for lightpath_id in lightpath_ids:
            lightpath = self.vt.lightpaths.get(lightpath_id)
            if lightpath is None:
                continue
            for link_id, wavelength in zip(lightpath.links, lightpath.wavelengths):
                self.pt.get_link(link_id).release_bandwidth(
                    wavelength, flow.rate
                )
            lightpath.active_flow_ids.discard(flow_id)
            if self.vt.is_lightpath_idle(lightpath.id) and not lightpath.reserved:
                self.vt.remove_lightpath(lightpath.id)
        for backup_id in self.mapped_backup_lightpaths.pop(flow_id, []):
            backup = self.vt.lightpaths.get(backup_id)
            if backup is not None and self.vt.is_lightpath_idle(backup_id):
                self.vt.remove_lightpath(backup_id)
        del self.active_flows[flow_id]
        logger.info("Flow removed id=%d", flow_id)
        return True

    def reserve_backup_lightpaths(
        self, flow_id: int, lightpaths: list
    ) -> None:
        # Backup resources are tracked separately because they reserve optical
        # capacity without carrying the flow's bandwidth directly.
        if flow_id not in self.active_flows:
            raise SimulationError(f"cannot reserve backup for inactive flow {flow_id}")
        self.mapped_backup_lightpaths[flow_id] = [
            lightpath.id for lightpath in lightpaths
        ]
        logger.info(
            "Reserved backup lightpaths for flow id=%d lightpaths=%s",
            flow_id,
            [lightpath.id for lightpath in lightpaths],
        )

    def get_physical_topology(self) -> WDMPhysicalTopology:
        return self.pt

    def get_virtual_topology(self) -> VirtualTopology:
        return self.vt

    # def create_candidate_wdm_lightpath(
    #     self,
    #     src: int,
    #     dst: int,
    #     links: list[int],
    #     wavelengths: list[int],
    #     *,
    #     reserved: bool = False,
    #     backup: bool = False,
    # ):
    #     return WDMLightPath(
    #         id=-1,
    #         src=src,
    #         dst=dst,
    #         links=list(links),
    #         wavelengths=list(wavelengths),
    #         reserved=reserved,
    #         backup=backup,
    #     )

    def get_algorithm(self):
        if self.algorithm is None:
            raise SimulationError("routing algorithm has not been installed")
        return self.algorithm
