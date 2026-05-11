from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from exceptions import ConfigurationError, ResourceUnavailableError, TopologyError

logger = logging.getLogger(__name__)


@dataclass
class WDMPhysicalTopology:
    """
    节点属性应包括：
     - id
     - Latitude, Longitude
     - layer: {physical, wavelength, lightpath}
    链路属性应包括：
     - layer: {mapping, physical, wavelength, lightpath}
     - wavelength_used: [index]
     - wavelength_available: [index]
     - max_bandwidth: int
     - max_key_rate: int
     - route: []
    """
    graph: nx.DiGraph = field(init=False, repr=False)

    def __post_init__(self):
        self.graph = nx.DiGraph()

    @property
    def num_nodes(self) -> int:
        return len(self.graph.nodes)

    @property
    def num_edges(self) -> int:
        return len(self.graph.edges)


def load_physical_topology(path: str | Path, **kwargs) -> WDMPhysicalTopology:
    # JSON/XML can describe WDM resources explicitly; GraphML is treated as a
    # topology skeleton and filled with simulator defaults where needed.
    logger.info(f"{'='*25} Loading Physical Topology {'='*25}")
    topology_path = Path(path)
    if not topology_path.exists():
        raise ConfigurationError(f"topology file does not exist: {topology_path}")
    logger.info(f"Topology file: {topology_path}")
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
            layer="physical",
            **attrs
        )

    for src, dst in raw_graph.edges():
        directions = [(src, dst)] if raw_graph.is_directed() else [(src, dst), (dst, src)]
        for directed_src, directed_dst in directions:
            topology.graph.add_edge(
                int(directed_src), int(directed_dst),
                layer="physical",
                wavelength_used=[],
                wavelength_available=list(range(kwargs.get("wavelengths", 0))),
                max_bandwidth=int(kwargs.get("max_bandwidth", 0)),
                max_key_rate=int(kwargs.get("max_key_rate", 0)),
                route=[]
            )
    logger.info(f"GraphML topology loaded: nodes={topology.num_nodes} directed_links={topology.num_edges}.")
    return topology
