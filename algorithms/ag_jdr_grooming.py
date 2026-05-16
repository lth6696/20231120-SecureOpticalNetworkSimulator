from __future__ import annotations

import logging
import networkx as nx

from models.flow import Flow
from topology import Lightpath

from .auxiliary_graph import AuxiliaryGraph
from .base import HeuristicAlgorithm, AlgInput, AlgOutput

logger = logging.getLogger(__name__)


class AuxGJointDataRecipGrooming(HeuristicAlgorithm):

    def __init__(self, k: int = 8):
        super().__init__()
        self.k = k

        logger.info(f"Auxiliary-Graph-Based Joint Data-and-Key Path Grooming Algorithm initialized with k={self.k}")

    def flow_arrival(self, alg_input: AlgInput) -> AlgOutput:
        pt = alg_input.pt
        vt = alg_input.vt
        flow = alg_input.flow
        logger.info(f"Algorithm handling flow {flow}")

        # 1. 构建当前时刻的辅助图。
        ag = AuxiliaryGraph()
        G_aux = ag.get_aux_graph(pt.graph, vt.graph)

        # 2. 数据路径不能走协商光路，并且必须满足带宽约束。
        G_sub = ag.get_sub_aux_graph(
            blocked_edges_attr={
                "usage": "recip",
                "avl_bandwidth": flow.rate
            }
        )

        paths = self._get_kpaths(G_sub, flow.src, flow.dst, self.k)
        if not paths:
            return AlgOutput()

        # 3. 对每条候选数据路径，找协商路径。
        for path in paths:
            logger.debug("Candidate data path: %s", path)

            lightpaths_data = self._find_lightpaths(path, G_aux, "data")

            # 普通业务：数据路径可行即可接受。
            if flow.attrs["sec"] == 0:
                return AlgOutput(status=True, routes={"data": lightpaths_data})

            # 如果 flow 需要安全
            # 寻找协商路径，要求协商路径与数据路径同端点
            lightpaths_recip = self._find_reciprocal_lightpath(ag, lightpaths_data, flow)
            logger.debug(f"Candidate recip path: {lightpaths_recip}")

            # 如果所有数据跳都有密钥路径，则接受该数据路径
            if lightpaths_recip and lightpaths_data:
                logger.info("Accepted data lightpaths: %s", lightpaths_data)
                logger.info("Accepted recip lightpaths: %s", lightpaths_recip)
                return AlgOutput(status=True, routes={"data": lightpaths_data, "recip": lightpaths_recip})

        return AlgOutput()

    def _find_lightpaths(self, path: list, aux_graph: nx.DiGraph, usage: str) -> list[Lightpath]:
        lightpaths: list[Lightpath] = []
        route: list = []
        bandwidths = []
        key_rates = []

        for u, v in self._get_node_pairs(path):
            edge_data = aux_graph.edges[u, v]
            layer = edge_data["layer"]

            if layer == "mapping":
                if aux_graph.nodes[v]["layer"] == "wavelength":
                    route.append(v)
                elif aux_graph.nodes[u]["layer"] == "wavelength":
                    src = route[0]
                    dst = u
                    max_bandwidth = min(bandwidths)
                    max_key_rate = min(key_rates)
                    lightpaths.append(
                        Lightpath(
                            src=src.node,
                            dst=dst.node,
                            wavelength_used=u.wavelength,
                            max_bandwidth=max_bandwidth if usage == "data" else 0,
                            max_key_rate=max_key_rate if usage == "recip" else 0,
                            avl_bandwidth=max_bandwidth if usage == "data" else 0,
                            avl_key_rate=max_key_rate if usage == "recip" else 0,
                            route=route,
                            usage=usage,
                            kind="new",
                            layer="lightpath",
                            dedicate="False"
                        )
                    )
                    route = []
            elif layer == "wavelength":
                bandwidths.append(edge_data["max_bandwidth"])
                key_rates.append(edge_data["max_key_rate"])
                route.append(v)
            elif layer == "lightpath":
                lightpaths.append(
                    Lightpath(
                        src=u.node,
                        dst=v.node,
                        wavelength_used=edge_data["wavelength"],
                        max_bandwidth=edge_data["max_bandwidth"],
                        max_key_rate=edge_data["max_key_rate"],
                        avl_bandwidth=edge_data["avl_bandwidth"],
                        avl_key_rate=edge_data["avl_key_rate"],
                        route=edge_data["route"],
                        usage=edge_data["usage"],
                        kind="exist",
                        layer="lightpath",
                        dedicate=edge_data["dedicate"]
                    )
                )
            else:
                raise ValueError

        return lightpaths

    def _find_reciprocal_lightpath(
            self,
            aux_graph: AuxiliaryGraph,
            lightpaths: [Lightpath],
            flow: Flow
    ) -> [Lightpath]:
        blocked_edges = []
        for lightpath in lightpaths:
            blocked_edges.append((lightpath.src, lightpath.dst))
            for u, v in self._get_node_pairs(lightpath.route):
                blocked_edges.append((u, v))

        lightpaths_recip = []
        for lightpath in lightpaths:
            # 约束：扣除所有数据路径, 满足密钥速率要求
            sub_graph = aux_graph.get_sub_aux_graph(
                blocked_edges=blocked_edges,
                blocked_edges_attr={"usage": "data", "avl_key_rate": flow.attrs["kgr"]}
            )
            try:
                path = nx.shortest_path(sub_graph, lightpath.src, lightpath.dst)
            except:
                path = []

            lp = self._find_lightpaths(path, sub_graph, usage="recip")
            logger.debug(f"{lp}")
            if len(lp) != 1:
                # 若协商信道不是一跳联通的
                return []

            lightpaths_recip.append(*lp)

            for lightpath in lp:
                blocked_edges.append((lightpath.src, lightpath.dst))
                for u, v in self._get_node_pairs(lightpath.route):
                    blocked_edges.append((u, v))
        return lightpaths_recip
