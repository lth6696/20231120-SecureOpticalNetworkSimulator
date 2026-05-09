import networkx as nx
from collections import defaultdict
from dataclasses import dataclass


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
    def __init__(self):
        self.aux_graph = nx.DiGraph()

    def get_aux_graph(
            self,
            phy_graph: nx.DiGraph,
            vir_graph: nx.MultiDiGraph,
            *,
            name_aws: str = "aws",
            name_wavelength: str = "wavelength",
            physical_route_attr: str = "physical_route",
            allow_wavelength_conversion: bool = False,
            weights: dict | None = None,
    ) -> nx.DiGraph:
        # 1. Add access / physical nodes
        for v, data in phy_graph.nodes(data=True):
            self.aux_graph.add_node(
                v,
                physical_node=v,
                **data,
            )

        # 2. Build wavelength layer from available wavelengths
        aws_by_node = defaultdict(set)
        for u, v, data in phy_graph.edges(data=True):
            aws = data.get(name_aws, [])
            for w in aws:
                self.aux_graph.add_node(
                    WavelengthNode(u, w),
                    layer="wavelength",
                    physical_node=u,
                )

                self.aux_graph.add_node(
                    WavelengthNode(v, w),
                    layer="wavelength",
                    physical_node=v,
                )

                aws_by_node[u].add(w)
                aws_by_node[v].add(w)

                self.aux_graph.add_edge(
                    WavelengthNode(u, w),
                    WavelengthNode(v, w),
                    layer="wavelength",
                    wavelength=w,
                    physical_route=[(u, v)],
                    **data
                )

        # 3. Mapping edges between access layer and wavelength layer
        for v, wavelengths in aws_by_node.items():
            for w in wavelengths:
                self.aux_graph.add_edge(
                    v,
                    WavelengthNode(v, w),
                    layer="mapping",
                    wavelength=-1,
                    physical_route=[]
                )

                self.aux_graph.add_edge(
                    WavelengthNode(v, w),
                    v,
                    layer="mapping",
                    wavelength=-1,
                    physical_route=[]
                )

        # 5. Build lightpath layer from existing lightpaths
        for u, v, key, data in vir_graph.edges(keys=True, data=True):
            w = data.get(name_wavelength)

            lightpath_id = data.get("lightpath_id", key)

            self.aux_graph.add_node(
                VirtualNode(u, key),
                layer="lightpath",
                physical_node=u
            )

            self.aux_graph.add_node(
                VirtualNode(v, key),
                layer="lightpath",
                physical_node=v
            )

            self.aux_graph.add_edge(
                u,
                VirtualNode(u, key),
                layer="mapping",
                wavelength=-1,
                physical_route=[],
                **data
            )

            self.aux_graph.add_edge(
                VirtualNode(v, key),
                v,
                layer="mapping",
                wavelength=-1,
                physical_route=[]
            )

            self.aux_graph.add_edge(
                VirtualNode(u, key),
                VirtualNode(v, key),
                layer="lightpath",
                wavelength=w,
                physical_route=[]
            )

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
                return False
            for key, value in blocked_edges_attr.items():
                if key == "max_key_rate":
                    if self.aux_graph.edges[u, v]["layer"] == "wavelength" or \
                        self.aux_graph.edges[u, v]["layer"] == "lightpath":
                        return self.aux_graph.edges[u, v][key] > value
                elif self.aux_graph.edges[u, v][key] == value:
                    return False
            return True

        sub_graph = nx.subgraph_view(
            self.aux_graph,
            filter_node=filter_node,
            filter_edge=filter_edge
        )

        return sub_graph
