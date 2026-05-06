from __future__ import annotations

import json
import logging
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

from wdm_sim.exceptions import ConfigurationError, ResourceUnavailableError, TopologyError

logger = logging.getLogger(__name__)

DEFAULT_GROOMING_INPUT_PORTS = 8
DEFAULT_GROOMING_OUTPUT_PORTS = 8
DEFAULT_WAVELENGTHS = 4
DEFAULT_WAVELENGTH_BANDWIDTH = 100


@dataclass(slots=True)
class WDMNode:
    # In this simplified WDM model, grooming ports bound how many lightpaths
    # can originate from or terminate at the node simultaneously.
    id: int
    name: str = ""
    grooming_input_ports: int = 0
    grooming_output_ports: int = 0
    used_grooming_input_ports: set[int] = field(default_factory=set)
    used_grooming_output_ports: set[int] = field(default_factory=set)

    def allocate_input_port(self) -> int:
        for port in range(self.grooming_input_ports):
            if port not in self.used_grooming_input_ports:
                self.used_grooming_input_ports.add(port)
                return port
        raise ResourceUnavailableError(f"node {self.id} has no free grooming input port")

    def allocate_output_port(self) -> int:
        for port in range(self.grooming_output_ports):
            if port not in self.used_grooming_output_ports:
                self.used_grooming_output_ports.add(port)
                return port
        raise ResourceUnavailableError(f"node {self.id} has no free grooming output port")

    def release_input_port(self, port: int) -> None:
        self.used_grooming_input_ports.discard(port)

    def release_output_port(self, port: int) -> None:
        self.used_grooming_output_ports.discard(port)

    def has_free_input_port(self) -> bool:
        return len(self.used_grooming_input_ports) < self.grooming_input_ports

    def has_free_output_port(self) -> bool:
        return len(self.used_grooming_output_ports) < self.grooming_output_ports


@dataclass(slots=True)
class WDMLink:
    # Each wavelength tracks both binary occupancy and remaining bandwidth for
    # flows groomed onto the lightpath that owns that wavelength.
    id: int
    src: int
    dst: int
    weight: float
    num_wavelengths: int
    wavelength_bandwidth: int
    free_wavelengths: list[bool] = field(init=False)
    available_bandwidth: list[int] = field(init=False)

    def __post_init__(self) -> None:
        if self.num_wavelengths <= 0:
            raise TopologyError(f"link {self.id} must have at least one wavelength")
        if self.wavelength_bandwidth <= 0:
            raise TopologyError(f"link {self.id} must have positive wavelength bandwidth")
        self.free_wavelengths = [True] * self.num_wavelengths
        self.available_bandwidth = [self.wavelength_bandwidth] * self.num_wavelengths

    def check_wavelength_index(self, wavelength: int) -> None:
        if wavelength < 0 or wavelength >= self.num_wavelengths:
            raise TopologyError(
                f"wavelength {wavelength} is out of range for link {self.id}"
            )

    def reserve_wavelength(self, wavelength: int) -> None:
        self.check_wavelength_index(wavelength)
        if not self.free_wavelengths[wavelength]:
            raise ResourceUnavailableError(
                f"wavelength {wavelength} on link {self.id} is already reserved"
            )
        self.free_wavelengths[wavelength] = False

    def release_wavelength(self, wavelength: int) -> None:
        self.check_wavelength_index(wavelength)
        self.free_wavelengths[wavelength] = True
        self.available_bandwidth[wavelength] = self.wavelength_bandwidth

    def allocate_bandwidth(self, wavelength: int, amount: int) -> None:
        self.check_wavelength_index(wavelength)
        if self.available_bandwidth[wavelength] < amount:
            raise ResourceUnavailableError(
                f"link {self.id} wavelength {wavelength} has "
                f"{self.available_bandwidth[wavelength]} bandwidth, needs {amount}"
            )
        self.available_bandwidth[wavelength] -= amount

    def release_bandwidth(self, wavelength: int, amount: int) -> None:
        self.check_wavelength_index(wavelength)
        self.available_bandwidth[wavelength] = min(
            self.wavelength_bandwidth, self.available_bandwidth[wavelength] + amount
        )


@dataclass
class WDMPhysicalTopology:
    # The physical topology keeps a directed graph view so routing and resource
    # accounting can be expressed in terms of concrete link identifiers.
    # nodes: dict[int, WDMNode]
    # links: dict[int, WDMLink]
    # adjacency: dict[int, list[int]] = field(init=False)
    graph: nx.DiGraph = field(init=False, repr=False)

    def __post_init__(self):
        self.graph = nx.DiGraph()

    @property
    def num_nodes(self) -> int:
        return len(self.graph.nodes)

    @property
    def num_edges(self) -> int:
        return len(self.graph.edges)

    #
    # @property
    # def max_num_wavelengths(self) -> int:
    #     return max((link.num_wavelengths for link in self.links.values()), default=0)
    #
    # def get_node(self, node_id: int) -> WDMNode:
    #     try:
    #         return self.nodes[node_id]
    #     except KeyError as exc:
    #         raise TopologyError(f"unknown node id {node_id}") from exc
    #
    # def get_link(self, link_id: int) -> WDMLink:
    #     try:
    #         return self.links[link_id]
    #     except KeyError as exc:
    #         raise TopologyError(f"unknown link id {link_id}") from exc
    #
    # def shared_physical_edge_link_ids(self, link_id: int) -> set[int]:
    #     # Undirected source topologies are expanded into two directed arcs; both
    #     # arcs represent the same fiber and should be excluded together.
    #     link = self.get_link(link_id)
    #     endpoints = {link.src, link.dst}
    #     return {
    #         candidate.id
    #         for candidate in self.links.values()
    #         if {candidate.src, candidate.dst} == endpoints
    #     }
    #
    # def nodes_to_links(self, node_path: list[int]) -> list[int]:
    #     if len(node_path) < 2:
    #         return []
    #     link_ids: list[int] = []
    #     for src, dst in zip(node_path, node_path[1:]):
    #         link_id = self.find_link(src, dst)
    #         if link_id is None:
    #             raise TopologyError(f"no directed link exists for hop {src}->{dst}")
    #         link_ids.append(link_id)
    #     return link_ids
    #
    # def weighted_adjacency(self) -> dict[int, list[tuple[int, float]]]:
    #     result: dict[int, list[tuple[int, float]]] = {node_id: [] for node_id in self.nodes}
    #     for link in self.links.values():
    #         result.setdefault(link.src, []).append((link.dst, link.weight))
    #     return result
    #
    # def filtered_weighted_adjacency(
    #     self, allowed_link_ids: set[int] | None = None
    # ) -> dict[int, list[tuple[int, float]]]:
    #     result: dict[int, list[tuple[int, float]]] = {node_id: [] for node_id in self.nodes}
    #     for link in self.links.values():
    #         if allowed_link_ids is not None and link.id not in allowed_link_ids:
    #             continue
    #         result.setdefault(link.src, []).append((link.dst, link.weight))
    #     return result
    #
    # def validate_link_path(self, src: int, dst: int, link_ids: list[int]) -> None:
    #     if not link_ids:
    #         raise TopologyError("a lightpath must contain at least one physical link")
    #     current = src
    #     for link_id in link_ids:
    #         link = self.get_link(link_id)
    #         if link.src != current:
    #             raise TopologyError(
    #                 f"link path is discontinuous at link {link_id}: "
    #                 f"expected src {current}, got {link.src}"
    #             )
    #         current = link.dst
    #     if current != dst:
    #         raise TopologyError(f"link path ends at {current}, expected {dst}")


def load_physical_topology(path: str | Path, **kwargs) -> WDMPhysicalTopology:
    # JSON/XML can describe WDM resources explicitly; GraphML is treated as a
    # topology skeleton and filled with simulator defaults where needed.
    topology_path = Path(path)
    if not topology_path.exists():
        raise ConfigurationError(f"topology file does not exist: {topology_path}")
    logger.info("Loading physical topology from %s", topology_path)
    if topology_path.suffix.lower() == ".graphml":
        return _load_topology_from_graphml(topology_path, **kwargs)
    else:
        raise ConfigurationError(
            f"unsupported topology format {topology_path.suffix!r}, use GraphML"
        )


def _load_topology_from_graphml(path: Path, **kwargs) -> WDMPhysicalTopology:
    # Many GraphML datasets describe an undirected IP topology, so we normalize
    # node ids and synthesize directed WDM links during import.
    raw_graph = nx.read_graphml(path)
    topology = WDMPhysicalTopology()
    for node_id, attrs in raw_graph.nodes(data=True):
        topology.graph.add_node(
            int(node_id),
            grooming_input_ports=DEFAULT_GROOMING_INPUT_PORTS,
            grooming_output_ports=DEFAULT_GROOMING_OUTPUT_PORTS,
            **attrs
        )

    for src, dst, attrs in raw_graph.edges(data=True):
        # todo add config attr (resource)
        directions = [(src, dst)] if raw_graph.is_directed() else [(src, dst), (dst, src)]
        for directed_src, directed_dst in directions:
            topology.graph.add_edge(
                int(directed_src), int(directed_dst),
                **attrs,
                **kwargs
            )

    logger.info(f"GraphML topology loaded: nodes={topology.num_nodes} directed_links={topology.num_edges} source={path}")
    return topology


def _get_float(
    attrs: dict[str, Any], *names: str, default: float | None
) -> float | None:
    for name in names:
        if name in attrs and attrs[name] not in {None, ""}:
            return float(attrs[name])
    return default


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
