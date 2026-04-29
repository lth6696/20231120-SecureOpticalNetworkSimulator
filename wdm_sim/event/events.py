from __future__ import annotations

from dataclasses import dataclass

from .flow import Flow


@dataclass(slots=True)
class Event:
    time: float


@dataclass(slots=True)
class FlowArrivalEvent(Event):
    flow: Flow


@dataclass(slots=True)
class FlowDepartureEvent(Event):
    flow_id: int

