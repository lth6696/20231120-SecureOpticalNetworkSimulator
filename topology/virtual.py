from __future__ import annotations

import logging
from dataclasses import dataclass, field

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class Lightpath:
    src: int
    dst: int
    wavelength_used: int
    max_bandwidth: int
    max_key_rate: int
    avl_bandwidth: int
    avl_key_rate: int
    route: []
    usage: str
    kind: str       # new, exist

    layer: str = "lightpath"


@dataclass
class VirtualTopology:
    """
    节点属性应包括：
     - id
     - Latitude, Longitude
     - layer: {physical, wavelength, lightpath}
    链路属性应包括：
     - layer: {mapping, physical, wavelength, lightpath}
     - wavelength_used: int
     - max_bandwidth: int
     - max_key_rate: int
     - avl_bandwidth: int
     - avl_key_rate: int
     - route: []
     - usage: {data, recip}
     - kind: exist
     - active_flows: {}
    """
    graph: nx.MultiDiGraph = field(init=False)

    def __post_init__(self):
        self.graph = nx.MultiDiGraph()

    def init(self, phy_graph: nx.DiGraph):
        logger.info(f"{'='*25} Loading Virtual Topology {'='*25}")
        self.graph.add_nodes_from(phy_graph.nodes(data=True))

        for node in self.graph.nodes:
            self.graph.nodes[node]["layer"] = "lightpath"
