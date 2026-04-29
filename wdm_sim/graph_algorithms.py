from __future__ import annotations

from itertools import islice

import networkx as nx


WeightedAdjacency = dict[int, list[tuple[int, float]]]


def _build_graph(num_nodes: int, adjacency: WeightedAdjacency) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_nodes_from(range(num_nodes))
    for src, edges in adjacency.items():
        for dst, weight in edges:
            graph.add_edge(src, dst, weight=weight)
    return graph


def dijkstra_shortest_path(
    num_nodes: int, adjacency: WeightedAdjacency, src: int, dst: int
) -> list[int]:
    graph = _build_graph(num_nodes, adjacency)
    try:
        return list(nx.dijkstra_path(graph, src, dst, weight="weight"))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def yen_k_shortest_paths(
    num_nodes: int, adjacency: WeightedAdjacency, src: int, dst: int, k: int
) -> list[list[int]]:
    if k <= 0:
        return []
    graph = _build_graph(num_nodes, adjacency)
    try:
        return [list(path) for path in islice(nx.shortest_simple_paths(graph, src, dst, weight="weight"), k)]
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []

