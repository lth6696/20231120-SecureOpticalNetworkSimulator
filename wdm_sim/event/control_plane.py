from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .events import Event, FlowArrivalEvent, FlowDepartureEvent
from .flow import Flow
from wdm_sim.exceptions import SimulationError, TopologyError
from wdm_sim.stats import StatsCollector
from wdm_sim.topology.physical import WDMPhysicalTopology
from wdm_sim.topology.virtual import VirtualTopology, WDMLightPath
from wdm_sim.tracer import Tracer

logger = logging.getLogger(__name__)


@dataclass
class ControlPlane:
    # The control plane coordinates event handling, routing decisions, flow
    # lifecycle, and topology/resource bookkeeping.
    physical_topology: WDMPhysicalTopology
    virtual_topology: VirtualTopology
    stats: StatsCollector
    tracer: Tracer
    active_flows: dict[int, Flow] = field(default_factory=dict)
    mapped_flows_single_path: dict[int, list[int]] = field(default_factory=dict)
    mapped_backup_lightpaths: dict[int, list[int]] = field(default_factory=dict)
    routing_algorithm: object | None = None
    current_time: float = 0.0

    def set_routing_algorithm(self, routing_algorithm: object) -> None:
        self.routing_algorithm = routing_algorithm
        logger.info("Control plane bound to routing algorithm=%s", type(routing_algorithm).__name__)

    def new_event(self, event: Event) -> None:
        # Arrivals are made visible to the algorithm before admission; departures
        # reclaim any working or backup resources still tied to the flow.
        self.current_time = event.time
        logger.debug("Processing event type=%s time=%.6f", type(event).__name__, event.time)
        if isinstance(event, FlowArrivalEvent):
            self.active_flows[event.flow.id] = event.flow
            logger.info(
                "Flow arrival id=%d src=%d dst=%d rate=%d",
                event.flow.id,
                event.flow.src,
                event.flow.dst,
                event.flow.rate,
            )
            self._require_algorithm().flow_arrival(event.flow)
        elif isinstance(event, FlowDepartureEvent):
            if event.flow_id in self.active_flows:
                logger.info("Flow departure id=%d", event.flow_id)
                self._require_algorithm().flow_departure(event.flow_id)
                self.remove_flow(event.flow_id)
        else:
            raise SimulationError(f"unsupported event type: {type(event).__name__}")

    def accept_flow(self, flow_id: int, lightpaths: list[WDMLightPath]) -> bool:
        flow = self.active_flows.get(flow_id)
        if flow is None:
            logger.warning("Ignoring accept for missing flow id=%d", flow_id)
            return False
        if not lightpaths:
            raise TopologyError("accept_flow requires at least one lightpath")

        # Wavelength occupation is checked when lightpaths are created. At flow
        # admission time we only need to verify residual groomable bandwidth.
        self._validate_virtual_continuity(flow, lightpaths)
        for lightpath in lightpaths:
            if lightpath.backup:
                raise TopologyError(
                    f"backup lightpath {lightpath.id} cannot carry primary traffic"
                )
            available = self.virtual_topology.get_lightpath_bw_available(lightpath.id)
            if available < flow.rate:
                logger.warning(
                    "Insufficient bandwidth for flow id=%d on lightpath id=%d available=%d required=%d",
                    flow.id,
                    lightpath.id,
                    available,
                    flow.rate,
                )
                return False

        groomed = any(lightpath.active_flow_ids for lightpath in lightpaths)
        for lightpath in lightpaths:
            for link_id, wavelength in zip(lightpath.links, lightpath.wavelengths):
                self.physical_topology.get_link(link_id).allocate_bandwidth(
                    wavelength, flow.rate
                )
            lightpath.active_flow_ids.add(flow.id)

        self.mapped_flows_single_path[flow.id] = [lightpath.id for lightpath in lightpaths]
        self.stats.accept_flow(
            flow=flow,
            physical_hops=sum(len(lightpath.links) for lightpath in lightpaths),
            virtual_hops=len(lightpaths),
            groomed=groomed,
        )
        self.tracer.record(
            "flow-accepted",
            self.current_time,
            flow,
            lightpaths=[lightpath.id for lightpath in lightpaths],
            groomed=groomed,
        )
        logger.info(
            "Flow accepted id=%d lightpaths=%s groomed=%s",
            flow.id,
            [lightpath.id for lightpath in lightpaths],
            groomed,
        )
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
            lightpath = self.virtual_topology.lightpaths.get(lightpath_id)
            if lightpath is None:
                continue
            for link_id, wavelength in zip(lightpath.links, lightpath.wavelengths):
                self.physical_topology.get_link(link_id).release_bandwidth(
                    wavelength, flow.rate
                )
            lightpath.active_flow_ids.discard(flow_id)
            if self.virtual_topology.is_lightpath_idle(lightpath.id) and not lightpath.reserved:
                self.virtual_topology.remove_lightpath(lightpath.id)
        for backup_id in self.mapped_backup_lightpaths.pop(flow_id, []):
            backup = self.virtual_topology.lightpaths.get(backup_id)
            if backup is not None and self.virtual_topology.is_lightpath_idle(backup_id):
                self.virtual_topology.remove_lightpath(backup_id)
        del self.active_flows[flow_id]
        logger.info("Flow removed id=%d", flow_id)
        return True

    def reserve_backup_lightpaths(
        self, flow_id: int, lightpaths: list[WDMLightPath]
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
        return self.physical_topology

    def get_virtual_topology(self) -> VirtualTopology:
        return self.virtual_topology

    def create_candidate_wdm_lightpath(
        self,
        src: int,
        dst: int,
        links: list[int],
        wavelengths: list[int],
        *,
        reserved: bool = False,
        backup: bool = False,
    ) -> WDMLightPath:
        return WDMLightPath(
            id=-1,
            src=src,
            dst=dst,
            links=list(links),
            wavelengths=list(wavelengths),
            reserved=reserved,
            backup=backup,
        )

    def _validate_virtual_continuity(
        self, flow: Flow, lightpaths: list[WDMLightPath]
    ) -> None:
        # A multi-segment virtual route must form one continuous src->dst chain.
        current = flow.src
        for lightpath in lightpaths:
            if lightpath.id not in self.virtual_topology.lightpaths:
                raise TopologyError(f"lightpath {lightpath.id} is not registered")
            if lightpath.src != current:
                raise TopologyError(
                    f"virtual path is discontinuous: expected src {current}, "
                    f"got lightpath {lightpath.id} src {lightpath.src}"
                )
            current = lightpath.dst
        if current != flow.dst:
            raise TopologyError(f"virtual path ends at {current}, expected {flow.dst}")

    def _require_algorithm(self):
        if self.routing_algorithm is None:
            raise SimulationError("routing algorithm has not been installed")
        return self.routing_algorithm
