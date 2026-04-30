from __future__ import annotations

import logging
from dataclasses import dataclass

from wdm_sim.event.control_plane import ControlPlane
from wdm_sim.event.flow import Flow
from wdm_sim.graph_algorithms import dijkstra_shortest_path

from .common import FirstFitAllocator

logger = logging.getLogger(__name__)


@dataclass
class GroomingShortestPathRWA(FirstFitAllocator):
    cp: ControlPlane | None = None

    def simulation_interface(self, cp: ControlPlane) -> None:
        self.cp = cp

    def flow_arrival(self, flow: Flow) -> None:
        assert self.cp is not None
        virtual = self.cp.get_virtual_topology()
        candidates = virtual.get_available_lightpaths(flow.src, flow.dst, flow.rate)
        logger.info(
            "Grooming-SP handling flow id=%d candidate_lightpaths=%d",
            flow.id,
            len(candidates),
        )
        if candidates:
            lightpath = max(
                candidates,
                key=lambda item: virtual.get_lightpath_bw_available(item.id),
            )
            if self.cp.accept_flow(flow.id, [lightpath]):
                logger.info(
                    "Flow id=%d groomed onto existing lightpath id=%d",
                    flow.id,
                    lightpath.id,
                )
                return

        physical = self.cp.get_physical_topology()
        node_path = dijkstra_shortest_path(
            physical.num_nodes, physical.weighted_adjacency(), flow.src, flow.dst
        )
        logger.debug("Grooming-SP new lightpath attempt for flow id=%d path=%s", flow.id, node_path)
        if self.try_first_fit_on_node_path(flow, node_path):
            return
        self.cp.block_flow(flow.id)

    def flow_departure(self, flow_id: int) -> None:
        return None

    def simulation_end(self) -> None:
        return None
