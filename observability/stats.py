from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable
from collections import Counter, defaultdict

from models.events import Event, FlowArrivalEvent
from models.flow import Flow
from models.config import SimulationConfig


logger = logging.getLogger(__name__)

class StatsCollector:
    
    def __init__(self, config: SimulationConfig = None):
        # 当前优先统计阻塞率、成本、安全性
        self.arrivals: int = 0
        self.accepted: int = 0
        self.blocked: int = 0
    
        self.arrivals_secure: int = 0
        self.accepted_secure: int = 0
        self.blocked_secure: int = 0
    
        self.arrivals_unsecure: int = 0
        self.accepted_unsecure: int = 0
        self.blocked_unsecure: int = 0
    
        # self.grooming_count: int = 0
    
        # Security metrics
        self.num_inband_transmission: dict[tuple[int, int], int] = {}
        self.num_recip_channel_per_edge: dict[tuple[int, int], list] = defaultdict(list)
        self.physical_edges: set[tuple[int, int]] = set()
    
        # Cost metric
        self.cost_recip_channel: int = 0
        self.cost_recip_port: int = 0
        self.c_h = config.attrs["costs"]["channel"]
        self.c_p = config.attrs["costs"]["port"]

    def observe_event(self, event: Event) -> None:
        if isinstance(event, FlowArrivalEvent):
            self.arrivals += 1

            # 增加安全业务统计项
            if event.flow.attrs["sec"] > 0:
                self.arrivals_secure += 1
            else:
                self.arrivals_unsecure += 1

    def accept_flow(
        self,
        flow: Flow,
        lightpaths: dict[str, list[Any]],
        physical_edges: Iterable[tuple[int, int]] | None = None,
    ) -> None:
        if physical_edges is not None:
            self.physical_edges.update((int(u), int(v)) for u, v in physical_edges)

        logger.debug(f"Flow {flow}")
        logger.debug(f"Paths have {lightpaths.keys()}.")
        logger.debug(f"Already accepted {self.accepted}, including security {self.accepted_secure} and normal {self.accepted_unsecure}")
        # 统计阻塞率
        self.accepted += 1
        if flow.attrs["sec"] > 0:
            self.accepted_secure += 1
        else:
            self.accepted_unsecure += 1
        logger.debug(f"Now accept {self.accepted}, including security {self.accepted_secure} and normal {self.accepted_unsecure}")

        # 统计安全性
        self._update_security_metrics(lightpaths)
        # 统计成本
        self._update_cost_metrics(lightpaths)

        # self.physical_hops_accepted += physical_hops
        # self.virtual_hops_accepted += virtual_hops
        # if groomed:
        #     self.grooming_count += 1
        # else:
        #     self.new_lightpath_count += 1

    def block_flow(self, flow: Flow) -> None:
        self.blocked += 1

        if flow.attrs["sec"] > 0:
            self.blocked_secure += 1
        else:
            self.blocked_unsecure += 1

    def remove_flow(self, flow: Flow, lightpaths: dict[str, list[Any]]):

        for lightpath in lightpaths:
            if lightpath.usage == "data":
                continue
            for edge in self._route_physical_edges(lightpath.route):
                self.num_recip_channel_per_edge[edge].append(
                        self.num_recip_channel_per_edge.get(edge, [0])[-1] - 1
                )
                logger.debug(f"The number of recip channels carried by {edge} link is {self.num_recip_channel_per_edge[edge]}.")

    def summary(self) -> dict[str, Any]:
        edge_count = len(self.physical_edges)
        total_security_exposure = sum(self.num_inband_transmission.values())
        total_security_cost = (self.c_h * self.cost_recip_channel + 2.0 * self.c_p * self.cost_recip_port)

        return {
            "arrivals": self.arrivals,
            "accepted": self.accepted,
            "blocked": self.blocked,
            "blocking_rate": self.blocked / self.arrivals if self.arrivals else 0.0,

            "arrivals_secure": self.arrivals_secure,
            "accepted_secure": self.accepted_secure,
            "blocked_secure": self.blocked_secure,
            "secure_blocking_rate": (
                self.blocked_secure / self.arrivals_secure if self.arrivals_secure else 0.0
            ),

            "arrivals_unsecure": self.arrivals_unsecure,
            "accepted_unsecure": self.accepted_unsecure,
            "blocked_unsecure": self.blocked_unsecure,
            "unsecure_blocking_rate": (
                self.blocked_unsecure / self.arrivals_unsecure if self.arrivals_unsecure else 0.0
            ),

            # Uploaded security metrics.
            "total_security_exposure": total_security_exposure,
            "average_security_exposure": (
                total_security_exposure / edge_count if edge_count else 0.0
            ),
            "average_num_recip_channels": self._mean_dictlist(self.num_recip_channel_per_edge),

            # Uploaded cost metric C_bar.
            "total_security_cost": total_security_cost,
            "average_security_cost": total_security_cost / self.accepted_secure,

        }

    def _update_security_metrics(self, lightpaths: dict[str, list[Any]]) -> None:
        data_edge_counts: Counter[tuple[int, int]] = Counter()
        recip_edge_counts: Counter[tuple[int, int]] = Counter()

        for lightpath in lightpaths.get("data", []) or []:
            for edge in self._route_physical_edges(lightpath.route):
                data_edge_counts[edge] += 1
                self.physical_edges.add(edge)

        for lightpath in lightpaths.get("recip", []) or []:
            for edge in self._route_physical_edges(lightpath.route):
                recip_edge_counts[edge] += 1
                self.physical_edges.add(edge)

                val = self.num_recip_channel_per_edge.get(edge, [0])[-1] + 1
                self.num_recip_channel_per_edge[edge].append(val)
                logger.debug(f"The number of recip channels carried by {edge} link is {self.num_recip_channel_per_edge[edge]}.")

        # S_eij for this request is (#recip wavelengths on eij) *
        # (#data wavelengths on eij). Accumulate it over accepted requests.
        for edge in set(data_edge_counts) & set(recip_edge_counts):
            self.num_inband_transmission[edge] = (
                    self.num_inband_transmission.get(edge, 0) + 1
            )
            logger.debug(f"The number of in-band transmission is {edge}: {self.num_inband_transmission[edge]}.")

    def _update_cost_metrics(self, lightpaths: dict[str, list[Any]]) -> None:
        """Update the cost units in the uploaded C_bar formula.

        The formula counts reciprocal-channel wavelength-link usage with kappa
        and reciprocal lightpath usage with gamma. Therefore each accepted
        secure request contributes the physical hops of its reciprocal paths
        and the number of reciprocal lightpaths it uses.
        """
        for lightpath in lightpaths.get("recip", []) or []:
            self.cost_recip_port += 1
            self.cost_recip_channel += len(lightpath.route)

    @staticmethod
    def _route_physical_edges(route: list[Any]) -> list[tuple[int, int]]:
        if not route:
            return []

        # Some helper functions store route as [(u, v), ...].
        if all(isinstance(item, tuple) and len(item) == 2 for item in route):
            return [(int(u), int(v)) for u, v in route]

        edges: list[tuple[int, int]] = []
        for u, v in zip(route[:-1], route[1:]):
            if hasattr(u, "node") and hasattr(v, "node"):
                edges.append((int(u.node), int(v.node)))
            elif isinstance(u, int) and isinstance(v, int):
                edges.append((u, v))
        return edges

    @staticmethod
    def _stringify_edge_dict(values: dict[tuple[int, int], int]) -> dict[str, int]:
        return {f"{u}->{v}": value for (u, v), value in sorted(values.items())}

    @staticmethod
    def _mean_dictlist(data: dict[Any, list]):
        all_values = [
            value
            for values in data.values()
            for value in values
        ]

        return sum(all_values) / len(all_values) if all_values else 0.0
