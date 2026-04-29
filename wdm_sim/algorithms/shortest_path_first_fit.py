from __future__ import annotations

from dataclasses import dataclass

from wdm_sim.event.control_plane import ControlPlane
from wdm_sim.event.flow import Flow
from wdm_sim.graph_algorithms import dijkstra_shortest_path

from .common import FirstFitAllocator


@dataclass
class ShortestPathFirstFitRWA(FirstFitAllocator):
    cp: ControlPlane | None = None

    def simulation_interface(self, cp: ControlPlane) -> None:
        self.cp = cp

    def flow_arrival(self, flow: Flow) -> None:
        assert self.cp is not None
        physical = self.cp.get_physical_topology()
        node_path = dijkstra_shortest_path(
            physical.num_nodes, physical.weighted_adjacency(), flow.src, flow.dst
        )
        if self.try_first_fit_on_node_path(flow, node_path):
            return
        self.cp.block_flow(flow.id)

    def flow_departure(self, flow_id: int) -> None:
        return None

    def simulation_end(self) -> None:
        return None
