from __future__ import annotations

from typing import Protocol
from dataclasses import dataclass

from models.flow import Flow
from topology.physical import PhysicalTopology
from topology.virtual import VirtualTopology


@dataclass
class AlgInput:

    flow: Flow
    pt: PhysicalTopology
    vt: VirtualTopology


@dataclass
class AlgOutput:

    status: bool = False
    routes: dict = None


class HeuristicAlgorithm(Protocol):
    def flow_arrival(self, alg_input: AlgInput) -> AlgOutput: ...

    def flow_departure(self, flow_id: int) -> AlgOutput: ...

    def simulation_end(self) -> None: ...

    @staticmethod
    def _get_kpaths(graph, src: int, dst: int, k: int) -> list:
        import networkx as nx
        from itertools import islice

        # 寻找K条路径
        try:
            paths = nx.shortest_simple_paths(graph, src, dst)
            k_paths = [list(path) for path in islice(paths, k)]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            k_paths = []
        return k_paths

    @staticmethod
    def _get_node_pairs(path: list):
        return zip(path[:-1], path[1:])