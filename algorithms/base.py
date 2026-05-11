from __future__ import annotations

from typing import Protocol

from event.control_plane import ControlPlane
from event.flow import Flow


class HeuristicAlgorithm(Protocol):
    def simulation_interface(self, cp: ControlPlane) -> None: ...

    def flow_arrival(self, flow: Flow) -> None: ...

    def flow_departure(self, flow_id: int) -> None: ...

    def simulation_end(self) -> None: ...
