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
    nodes: dict[int, WDMNode]
    links: dict[int, WDMLink]
    adjacency: dict[int, list[int]] = field(init=False)

    def __post_init__(self) -> None:
        self.adjacency = {node_id: [] for node_id in self.nodes}
        seen_edges: set[tuple[int, int]] = set()
        for link in self.links.values():
            if link.src not in self.nodes or link.dst not in self.nodes:
                raise TopologyError(f"link {link.id} references an unknown node")
            edge = (link.src, link.dst)
            if edge in seen_edges:
                raise TopologyError(
                    f"parallel directed edge {link.src}->{link.dst} is not supported"
                )
            seen_edges.add(edge)
            self.adjacency.setdefault(link.src, []).append(link.id)

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def max_num_wavelengths(self) -> int:
        return max((link.num_wavelengths for link in self.links.values()), default=0)

    def get_node(self, node_id: int) -> WDMNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise TopologyError(f"unknown node id {node_id}") from exc

    def get_link(self, link_id: int) -> WDMLink:
        try:
            return self.links[link_id]
        except KeyError as exc:
            raise TopologyError(f"unknown link id {link_id}") from exc

    def find_link(self, src: int, dst: int) -> int | None:
        for link_id in self.adjacency.get(src, []):
            if self.links[link_id].dst == dst:
                return link_id
        return None

    def shared_physical_edge_link_ids(self, link_id: int) -> set[int]:
        # Undirected source topologies are expanded into two directed arcs; both
        # arcs represent the same fiber and should be excluded together.
        link = self.get_link(link_id)
        endpoints = {link.src, link.dst}
        return {
            candidate.id
            for candidate in self.links.values()
            if {candidate.src, candidate.dst} == endpoints
        }

    def nodes_to_links(self, node_path: list[int]) -> list[int]:
        if len(node_path) < 2:
            return []
        link_ids: list[int] = []
        for src, dst in zip(node_path, node_path[1:]):
            link_id = self.find_link(src, dst)
            if link_id is None:
                raise TopologyError(f"no directed link exists for hop {src}->{dst}")
            link_ids.append(link_id)
        return link_ids

    def weighted_adjacency(self) -> dict[int, list[tuple[int, float]]]:
        result: dict[int, list[tuple[int, float]]] = {node_id: [] for node_id in self.nodes}
        for link in self.links.values():
            result.setdefault(link.src, []).append((link.dst, link.weight))
        return result

    def filtered_weighted_adjacency(
        self, allowed_link_ids: set[int] | None = None
    ) -> dict[int, list[tuple[int, float]]]:
        result: dict[int, list[tuple[int, float]]] = {node_id: [] for node_id in self.nodes}
        for link in self.links.values():
            if allowed_link_ids is not None and link.id not in allowed_link_ids:
                continue
            result.setdefault(link.src, []).append((link.dst, link.weight))
        return result

    def validate_link_path(self, src: int, dst: int, link_ids: list[int]) -> None:
        if not link_ids:
            raise TopologyError("a lightpath must contain at least one physical link")
        current = src
        for link_id in link_ids:
            link = self.get_link(link_id)
            if link.src != current:
                raise TopologyError(
                    f"link path is discontinuous at link {link_id}: "
                    f"expected src {current}, got {link.src}"
                )
            current = link.dst
        if current != dst:
            raise TopologyError(f"link path ends at {current}, expected {dst}")


def load_physical_topology(path: str | Path) -> WDMPhysicalTopology:
    # JSON/XML can describe WDM resources explicitly; GraphML is treated as a
    # topology skeleton and filled with simulator defaults where needed.
    topology_path = Path(path)
    if not topology_path.exists():
        raise ConfigurationError(f"topology file does not exist: {topology_path}")
    logger.info("Loading physical topology from %s", topology_path)
    if topology_path.suffix.lower() == ".json":
        data = json.loads(topology_path.read_text(encoding="utf-8"))
    elif topology_path.suffix.lower() == ".xml":
        data = _load_topology_xml(topology_path)
    elif topology_path.suffix.lower() == ".graphml":
        return _load_topology_graphml(topology_path)
    else:
        raise ConfigurationError(
            f"unsupported topology format {topology_path.suffix!r}; use JSON, XML, or GraphML"
        )
    topology = _topology_from_mapping(data)
    logger.info(
        "Physical topology loaded from structured file: nodes=%d links=%d",
        topology.num_nodes,
        len(topology.links),
    )
    return topology


def _topology_from_mapping(data: dict[str, Any]) -> WDMPhysicalTopology:
    raw_nodes = data.get("nodes", [])
    raw_links = data.get("links", [])
    if not raw_nodes or not raw_links:
        raise ConfigurationError("topology must contain non-empty nodes and links")

    nodes = {
        int(item["id"]): WDMNode(
            id=int(item["id"]),
            name=str(item.get("name", item["id"])),
            grooming_input_ports=int(item.get("grooming_input_ports", item.get("inputPorts", 0))),
            grooming_output_ports=int(
                item.get("grooming_output_ports", item.get("outputPorts", 0))
            ),
        )
        for item in raw_nodes
    }
    links = {
        int(item["id"]): WDMLink(
            id=int(item["id"]),
            src=int(item["src"]),
            dst=int(item["dst"]),
            weight=float(item.get("weight", 1.0)),
            num_wavelengths=int(item.get("wavelengths", item.get("num_wavelengths", 0))),
            wavelength_bandwidth=int(item.get("bandwidth", item.get("wavelength_bandwidth", 0))),
        )
        for item in raw_links
    }
    return WDMPhysicalTopology(nodes=nodes, links=links)


def _load_topology_xml(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    nodes_parent = root.find("nodes")
    links_parent = root.find("links")
    if nodes_parent is None or links_parent is None:
        raise ConfigurationError("XML topology must contain <nodes> and <links>")
    nodes = [dict(node.attrib) for node in nodes_parent.findall("node")]
    links = [dict(link.attrib) for link in links_parent.findall("link")]
    return {"nodes": nodes, "links": links}


def _load_topology_graphml(path: Path) -> WDMPhysicalTopology:
    # Many GraphML datasets describe an undirected IP topology, so we normalize
    # node ids and synthesize directed WDM links during import.
    graph = nx.read_graphml(path)
    node_mapping = _graphml_node_mapping(graph.nodes)
    nodes: dict[int, WDMNode] = {}
    for raw_id, attrs in graph.nodes(data=True):
        node_id = node_mapping[str(raw_id)]
        nodes[node_id] = WDMNode(
            id=node_id,
            name=str(attrs.get("label", attrs.get("name", raw_id))),
            grooming_input_ports=_get_int(
                attrs,
                "grooming_input_ports",
                "inputPorts",
                "groomingInputPorts",
                default=DEFAULT_GROOMING_INPUT_PORTS,
            ),
            grooming_output_ports=_get_int(
                attrs,
                "grooming_output_ports",
                "outputPorts",
                "groomingOutputPorts",
                default=DEFAULT_GROOMING_OUTPUT_PORTS,
            ),
        )

    links: dict[int, WDMLink] = {}
    next_link_id = 0
    for raw_src, raw_dst, attrs in graph.edges(data=True):
        src = node_mapping[str(raw_src)]
        dst = node_mapping[str(raw_dst)]
        weight = _graphml_edge_weight(graph, raw_src, raw_dst, attrs)
        num_wavelengths = _get_int(
            attrs,
            "wavelengths",
            "num_wavelengths",
            "numWavelengths",
            default=DEFAULT_WAVELENGTHS,
        )
        bandwidth = _get_int(
            attrs,
            "bandwidth",
            "wavelength_bandwidth",
            "wavelengthBandwidth",
            default=DEFAULT_WAVELENGTH_BANDWIDTH,
        )
        directions = [(src, dst)] if graph.is_directed() else [(src, dst), (dst, src)]
        for directed_src, directed_dst in directions:
            links[next_link_id] = WDMLink(
                id=next_link_id,
                src=directed_src,
                dst=directed_dst,
                weight=weight,
                num_wavelengths=num_wavelengths,
                wavelength_bandwidth=bandwidth,
            )
            next_link_id += 1

    if not nodes or not links:
        raise ConfigurationError(f"GraphML topology is empty: {path}")
    topology = WDMPhysicalTopology(nodes=nodes, links=links)
    logger.info(
        "GraphML topology loaded: nodes=%d directed_links=%d source=%s",
        topology.num_nodes,
        len(topology.links),
        path,
    )
    return topology


def _graphml_node_mapping(raw_node_ids: Any) -> dict[str, int]:
    raw_ids = [str(raw_id) for raw_id in raw_node_ids]
    try:
        parsed = {raw_id: int(raw_id) for raw_id in raw_ids}
    except ValueError:
        return {raw_id: index for index, raw_id in enumerate(raw_ids)}
    if len(set(parsed.values())) != len(parsed):
        return {raw_id: index for index, raw_id in enumerate(raw_ids)}
    return parsed


def _graphml_edge_weight(
    graph: nx.Graph, raw_src: Any, raw_dst: Any, attrs: dict[str, Any]
) -> float:
    # Prefer explicit edge cost; if only coordinates exist, use geographic
    # distance so shortest-path algorithms still have meaningful weights.
    explicit = _get_float(attrs, "weight", "distance", "cost", default=None)
    if explicit is not None and explicit > 0:
        return explicit

    src_attrs = graph.nodes[raw_src]
    dst_attrs = graph.nodes[raw_dst]
    src_lat = _get_float(src_attrs, "Latitude", "latitude", "lat", default=None)
    src_lon = _get_float(src_attrs, "Longitude", "longitude", "lon", default=None)
    dst_lat = _get_float(dst_attrs, "Latitude", "latitude", "lat", default=None)
    dst_lon = _get_float(dst_attrs, "Longitude", "longitude", "lon", default=None)
    if None not in {src_lat, src_lon, dst_lat, dst_lon}:
        return max(
            _haversine_km(
                float(src_lat), float(src_lon), float(dst_lat), float(dst_lon)
            ),
            1.0,
        )
    return 1.0


def _get_int(attrs: dict[str, Any], *names: str, default: int) -> int:
    for name in names:
        if name in attrs and attrs[name] not in {None, ""}:
            return int(float(attrs[name]))
    return default


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
