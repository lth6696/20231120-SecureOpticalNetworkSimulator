from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from event.events import Event, FlowArrivalEvent
from event.flow import Flow


@dataclass
class StatsCollector:
    arrivals: int = 0
    accepted: int = 0
    blocked: int = 0
    required_bandwidth: int = 0
    blocked_bandwidth: int = 0
    num_lightpaths_created: int = 0
    num_lightpaths_removed: int = 0
    grooming_count: int = 0
    new_lightpath_count: int = 0
    physical_hops_accepted: int = 0
    virtual_hops_accepted: int = 0

    def observe_event(self, event: Event) -> None:
        if isinstance(event, FlowArrivalEvent):
            self.arrivals += 1
            self.required_bandwidth += event.flow.rate

    def accept_flow(
        self,
        flow: Flow,
        physical_hops: int,
        virtual_hops: int,
        groomed: bool,
    ) -> None:
        self.accepted += 1
        self.physical_hops_accepted += physical_hops
        self.virtual_hops_accepted += virtual_hops
        if groomed:
            self.grooming_count += 1
        else:
            self.new_lightpath_count += 1

    def block_flow(self, flow: Flow) -> None:
        self.blocked += 1
        self.blocked_bandwidth += flow.rate

    def lightpath_created(self) -> None:
        self.num_lightpaths_created += 1

    def lightpath_removed(self) -> None:
        self.num_lightpaths_removed += 1

    def summary(self) -> dict[str, Any]:
        return {
            "arrivals": self.arrivals,
            "accepted": self.accepted,
            "blocked": self.blocked,
            "blocking_rate": self.blocked / self.arrivals if self.arrivals else 0.0,
            "required_bandwidth": self.required_bandwidth,
            "blocked_bandwidth": self.blocked_bandwidth,
            "bandwidth_blocking_rate": (
                self.blocked_bandwidth / self.required_bandwidth
                if self.required_bandwidth
                else 0.0
            ),
            "num_lightpaths_created": self.num_lightpaths_created,
            "num_lightpaths_removed": self.num_lightpaths_removed,
            "grooming_count": self.grooming_count,
            "new_lightpath_count": self.new_lightpath_count,
            "average_physical_hops_per_accepted_flow": (
                self.physical_hops_accepted / self.accepted if self.accepted else 0.0
            ),
            "average_virtual_hops_per_accepted_flow": (
                self.virtual_hops_accepted / self.accepted if self.accepted else 0.0
            ),
        }
