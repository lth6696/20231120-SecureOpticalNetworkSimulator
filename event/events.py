from __future__ import annotations

from dataclasses import dataclass

from .flow import Flow


@dataclass(slots=True)
class Event:
    time: float


@dataclass(slots=True)
class FlowArrivalEvent(Event):
    flow: Flow

    def __repr__(self):
        return f"{self.flow.id} FlowArrival from node {self.flow.src} to node {self.flow.dst} with {self.flow.rate} rate, {self.flow.kgr} kgr and {self.flow.sec} security level."


@dataclass(slots=True)
class FlowDepartureEvent(Event):
    flow: Flow

    def __repr__(self):
        return f"{self.flow.id} FlowDeparture."

