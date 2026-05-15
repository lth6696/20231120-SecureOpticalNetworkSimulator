import logging
import itertools
import networkx as nx
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class WavelengthNode:
    node: int
    wavelength: int


@dataclass(slots=True, frozen=True)
class VirtualNode:
    node: int
    wavelength: int
    key: int


class AuxiliaryGraph:
    """
    节点属性应包括：
     - id
     - Latitude, Longitude
     - layer: {physical, wavelength, lightpath}
    链路属性应包括：
     - layer: {mapping, physical, wavelength, lightpath}
     - wavelength_used: [index] | int
     - max_bandwidth: int
     - avl_bandwidth: int
     - max_key_rate: int
     - avl_key_rate: int
     - route: []
    """

    REQUIRED_NODE_ATTRS = (
        "id",
        "Latitude",
        "Longitude",
        "layer"
    )

    REQUIRED_EDGE_ATTRS_PHY = (
        "layer",
        "wavelength_used",
        "wavelength_available",
        "max_bandwidth",
        "max_key_rate",
        "route",
    )

    REQUIRED_EDGE_ATTRS_VIR = (
        "layer",
        "wavelength_used",
        "max_bandwidth",
        "max_key_rate",
        "avl_bandwidth",
        "avl_key_rate",
        "route",
        "usage",
        "dedicate"
    )

    REQUIRED_EDGE_ATTRS_AUX = (
        "layer",
        "wavelength_used",
        "max_bandwidth",
        "max_key_rate",
        "avl_bandwidth",
        "avl_key_rate",
        "route",
        "usage",
        "dedicate"
    )

    def __init__(self):
        self.aux_graph = nx.DiGraph()
        self._counter = itertools.count(0)

    def get_aux_graph(
            self,
            phy_graph: nx.DiGraph,
            vir_graph: nx.MultiDiGraph,
    ) -> nx.DiGraph:
        self._validate_graph_with_attrs(phy_graph)
        self._validate_graph_with_attrs(vir_graph)

        # 1. Add access / physical nodes
        for v, data in phy_graph.nodes(data=True):
            filter_attrs = {key: data[key] for key in self.REQUIRED_NODE_ATTRS}
            self.aux_graph.add_node(v, **filter_attrs)
            logger.debug(f"AuxG adds {v} node with {filter_attrs}.")

        # 2. Build wavelength layer from available wavelengths
        aws_by_node = defaultdict(set)
        for u, v, data in phy_graph.edges(data=True):
            for w in data.get("wavelength_available", []):
                self.aux_graph.add_node(
                    WavelengthNode(u, w),
                    layer="wavelength",
                )
                logger.debug(f"AuxG adds {WavelengthNode(u, w)} node in wavelength layer.")

                self.aux_graph.add_node(
                    WavelengthNode(v, w),
                    layer="wavelength",
                )
                logger.debug(f"AuxG adds {WavelengthNode(v, w)} node in wavelength layer.")

                aws_by_node[u].add(w)
                aws_by_node[v].add(w)

                self.aux_graph.add_edge(
                    WavelengthNode(u, w),
                    WavelengthNode(v, w),
                    layer="wavelength",
                    wavelength=w,
                    max_bandwidth=data["max_bandwidth"],
                    max_key_rate=data["max_key_rate"],
                    avl_bandwidth=data["max_bandwidth"],
                    avl_key_rate=data["max_key_rate"],
                    route=[(u, v)],
                    usage=None,
                    dedicate=None
                )
                logger.debug(f"AuxG adds edge {WavelengthNode(u, w)} - {WavelengthNode(v, w)} with {self.aux_graph.edges[WavelengthNode(u, w), WavelengthNode(v, w)]}.")

        # 3. Mapping edges between access layer and wavelength layer
        for node, wavelengths in aws_by_node.items():
            for w in wavelengths:
                self.aux_graph.add_edge(
                    node,
                    WavelengthNode(node, w),
                    layer="mapping",
                    wavelength=None,
                    max_bandwidth=None,
                    max_key_rate=None,
                    avl_bandwidth=None,
                    avl_key_rate=None,
                    route=[],
                    usage=None,
                    dedicate=None
                )
                logger.debug(f"AuxG adds edge {node} - {WavelengthNode(node, w)} with {self.aux_graph.edges[node, WavelengthNode(node, w)]}.")

                self.aux_graph.add_edge(
                    WavelengthNode(node, w),
                    node,
                    layer="mapping",
                    wavelength=None,
                    max_bandwidth=None,
                    max_key_rate=None,
                    avl_bandwidth=None,
                    avl_key_rate=None,
                    route=[],
                    usage=None,
                    dedicate=None
                )
                logger.debug(f"AuxG adds edge {WavelengthNode(node, w)} - {node} with {self.aux_graph.edges[WavelengthNode(node, w), node]}.")

        # 5. Build lightpath layer from existing lightpaths
        for u, v, key, data in vir_graph.edges(keys=True, data=True):
            w = data.get("wavelength_used")
            u_id = self._get_node_id()
            v_id = self._get_node_id()

            self.aux_graph.add_node(
                VirtualNode(u, w, u_id),
                layer="lightpath"
            )
            logger.debug(f"AuxG adds {VirtualNode(u, w, u_id)} node in lightpath layer.")

            self.aux_graph.add_node(
                VirtualNode(v, w, v_id),
                layer="lightpath"
            )
            logger.debug(f"AuxG adds {VirtualNode(v, w, v_id)} node in lightpath layer.")

            self.aux_graph.add_edge(
                u,
                VirtualNode(u, w, u_id),
                layer="mapping",
                wavelength=None,
                max_bandwidth=None,
                max_key_rate=None,
                avl_bandwidth=None,
                avl_key_rate=None,
                route=[],
                usage=None,
                dedicate=None
            )
            logger.debug(
                f"AuxG adds edge {u} - {VirtualNode(u, w, u_id)} with {self.aux_graph.edges[u, VirtualNode(u, w, u_id)]}.")

            self.aux_graph.add_edge(
                VirtualNode(v, w, v_id),
                v,
                layer="mapping",
                wavelength=None,
                max_bandwidth=None,
                max_key_rate=None,
                avl_bandwidth=None,
                avl_key_rate=None,
                route=[],
                usage=None,
                dedicate=None
            )
            logger.debug(
                f"AuxG adds edge {VirtualNode(v, w, v_id)} - {v} with {self.aux_graph.edges[VirtualNode(v, w, v_id), v]}.")

            self.aux_graph.add_edge(
                VirtualNode(u, w, u_id),
                VirtualNode(v, w, v_id),
                layer="lightpath",
                wavelength=w,
                max_bandwidth=data["max_bandwidth"],
                max_key_rate=data["max_key_rate"],
                avl_bandwidth=data["avl_bandwidth"],
                avl_key_rate=data["avl_key_rate"],
                route=data["route"],
                usage=data["usage"],
                dedicate=data["dedicate"]
            )
            logger.debug(
                f"AuxG adds edge {VirtualNode(u, w, u_id)} - {VirtualNode(v, w, v_id)} with {self.aux_graph.edges[VirtualNode(u, w, u_id), VirtualNode(v, w, v_id)]}.")

        return self.aux_graph

    def get_sub_aux_graph(
            self,
            blocked_nodes: list = [],
            blocked_edges: [tuple] = [],
            blocked_nodes_attr: dict = {},
            blocked_edges_attr: dict = {}
    ):
        def filter_node(n):
            if n in blocked_nodes:
                return False
            return True

        def filter_edge(u, v):
            # 依赖两种方式，其一是指定节点，其二是指定属性
            if (u, v) in blocked_edges:
                logging.debug(f"Filter edge {u} - {v}")
                return False
            for key, value in blocked_edges_attr.items():
                if self.aux_graph.edges[u, v]["layer"] in {"wavelength", "lightpath"}:
                    if key in {"avl_key_rate", "avl_bandwidth"} and self.aux_graph.edges[u, v][key] < value:
                        logging.debug(f"Filter edge {u} - {v}")
                        return False
                elif self.aux_graph.edges[u, v][key] == value:
                    logging.debug(f"Filter edge {u} - {v}")
                    return False
            return True

        sub_graph = nx.subgraph_view(
            self.aux_graph,
            filter_node=filter_node,
            filter_edge=filter_edge
        )

        return sub_graph

    def _validate_graph_with_attrs(self, graph: nx.DiGraph | nx.MultiDiGraph):
        # 校验节点
        for node, data in graph.nodes(data=True):
            for attr in self.REQUIRED_NODE_ATTRS:
                if attr not in data:
                    logger.error(f"Node {node} has no attr {attr}.")
                    raise AttributeError

        # 校验边
        if graph.is_multigraph():
            for u, v, key, data in graph.edges(keys=True, data=True):
                for attr in self.REQUIRED_EDGE_ATTRS_VIR:
                    if attr not in data:
                        logger.error(f"Edge {key}th from {u} to {v} has no attr {attr}.")
                        raise AttributeError
        else:
            for u, v, data in graph.edges(data=True):
                for attr in self.REQUIRED_EDGE_ATTRS_PHY:
                    if attr not in data:
                        logger.error(f"Edge from {u} to {v} has no attr {attr}.")
                        raise AttributeError

    def _get_node_id(self):
        return next(self._counter)
