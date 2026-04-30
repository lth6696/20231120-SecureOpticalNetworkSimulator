from __future__ import annotations

import logging
from dataclasses import dataclass

from wdm_sim.event.control_plane import ControlPlane
from wdm_sim.event.flow import Flow
from wdm_sim.graph_algorithms import yen_k_shortest_paths

from .common import FirstFitAllocator

logger = logging.getLogger(__name__)


@dataclass
class KShortestPathFirstFitRWA(FirstFitAllocator):
    k: int = 3
    cp: ControlPlane | None = None

    def simulation_interface(self, cp: ControlPlane) -> None:
        self.cp = cp

    def flow_arrival(self, flow: Flow) -> None:
        assert self.cp is not None
        physical = self.cp.get_physical_topology()
        paths = yen_k_shortest_paths(
            physical.num_nodes,
            physical.weighted_adjacency(),
            flow.src,
            flow.dst,
            self.k,
        )
        logger.info(
            "KSP-FF handling flow id=%d k=%d candidate_paths=%d",
            flow.id,
            self.k,
            len(paths),
        )
        for node_path in paths:
            if self.try_first_fit_on_node_path(flow, node_path):
                return
        self.cp.block_flow(flow.id)

    def flow_departure(self, flow_id: int) -> None:
        return None

    def simulation_end(self) -> None:
        return None
