from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
from collections import Counter

from event.events import Event, FlowArrivalEvent
from event.flow import Flow


@dataclass
class StatsCollector:
    # 当前优先统计阻塞率、成本、安全性
    arrivals: int = 0
    accepted: int = 0
    blocked: int = 0

    arrivals_secure: int = 0
    accepted_secure: int = 0
    blocked_secure: int = 0

    arrivals_unsecure: int = 0
    accepted_unsecure: int = 0
    blocked_unsecure: int = 0

    required_bandwidth: int = 0
    blocked_bandwidth: int = 0

    num_lightpaths_created: int = 0
    num_lightpaths_removed: int = 0
    grooming_count: int = 0
    new_lightpath_count: int = 0
    physical_hops_accepted: int = 0
    virtual_hops_accepted: int = 0

    # Security metrics in the uploaded formula.
    # security_exposure_by_edge[e_ij] = S_eij
    # recip_channel_count_by_edge[e_ij] = NSe_eij
    security_exposure_by_edge: dict[tuple[int, int], int] = field(default_factory=dict)
    recip_channel_count_by_edge: dict[tuple[int, int], int] = field(default_factory=dict)
    physical_edges: set[tuple[int, int]] = field(default_factory=set)

    # Cost metric units in C_bar:
    #   sum kappa = reciprocal-channel physical wavelength-link usage,
    #   sum gamma = reciprocal lightpath usage.
    cost_recip_wavelength_link_units: int = 0
    cost_recip_lightpath_units: int = 0
    c_h: float = 1.0
    c_p: float = 1.0

    def observe_event(self, event: Event) -> None:
        if isinstance(event, FlowArrivalEvent):
            self.arrivals += 1
            self.required_bandwidth += event.flow.rate
            if event.flow.sec > 0:
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

        # 统计阻塞率
        self.accepted += 1
        if lightpaths.get("recip"):
            self.accepted_secure += 1
        else:
            self.accepted_unsecure += 1

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
        self.blocked_bandwidth += flow.rate
        if flow.sec > 0:
            self.blocked_secure += 1
        else:
            self.blocked_unsecure += 1

    def lightpath_created(self) -> None:
        self.num_lightpaths_created += 1

    def lightpath_removed(self) -> None:
        self.num_lightpaths_removed += 1

    def summary(self) -> dict[str, Any]:
        edge_count = len(self.physical_edges)
        total_security_exposure = sum(self.security_exposure_by_edge.values())
        total_recip_channels = sum(self.recip_channel_count_by_edge.values())

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
            "security_exposure_total": total_security_exposure,
            # "security_exposure_by_edge": self._stringify_edge_dict(
            #     self.security_exposure_by_edge
            # ),
            "expected_security_exposure": (
                total_security_exposure / edge_count if edge_count else 0.0
            ),
            "recip_channel_count_total": total_recip_channels,
            # "recip_channel_count_by_edge": self._stringify_edge_dict(
            #     self.recip_channel_count_by_edge
            # ),
            "average_recip_channel_count_per_edge": (
                total_recip_channels / edge_count if edge_count else 0.0
            ),

            # Uploaded cost metric C_bar.
            "cost": {
                # "c_h": self.c_h,
                # "c_p": self.c_p,
                # "recip_wavelength_link_units": self.cost_recip_wavelength_link_units,
                # "recip_lightpath_units": self.cost_recip_lightpath_units,
                "total_security_cost": (self.c_h * self.cost_recip_wavelength_link_units + 2.0 * self.c_p * self.cost_recip_lightpath_units) / self.accepted_secure,
                # "secure_service_count": self.accepted_secure,
                # "average_secure_service_cost": average_secure_service_cost,
                # "c_bar": average_secure_service_cost,
            },
            # Backward-compatible / easy-to-plot aliases.
            # "total_security_cost": total_cost,
            # "average_secure_service_cost": average_secure_service_cost,
            # "c_bar": average_secure_service_cost,
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
                self.recip_channel_count_by_edge[edge] = (
                        self.recip_channel_count_by_edge.get(edge, 0) + 1
                )

        # S_eij for this request is (#recip wavelengths on eij) *
        # (#data wavelengths on eij). Accumulate it over accepted requests.
        for edge in set(data_edge_counts) & set(recip_edge_counts):
            self.security_exposure_by_edge[edge] = (
                    self.security_exposure_by_edge.get(edge, 0)
                    + data_edge_counts[edge] * recip_edge_counts[edge]
            )

    def _update_cost_metrics(self, lightpaths: dict[str, list[Any]]) -> None:
        """Update the cost units in the uploaded C_bar formula.

        The formula counts reciprocal-channel wavelength-link usage with kappa
        and reciprocal lightpath usage with gamma. Therefore each accepted
        secure request contributes the physical hops of its reciprocal paths
        and the number of reciprocal lightpaths it uses.
        """
        for lightpath in lightpaths.get("recip", []) or []:
            self.cost_recip_lightpath_units += 1
            self.cost_recip_wavelength_link_units += len(lightpath.route)

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