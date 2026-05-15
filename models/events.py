from dataclasses import dataclass

from .flow import Flow


@dataclass(slots=True, frozen=True)
class Event:
    time: float


@dataclass(slots=True, frozen=True)
class FlowArrivalEvent(Event):
    flow: Flow

    def __repr__(self):
        return f"Arrive: {self.flow}."


@dataclass(slots=True, frozen=True)
class FlowDepartureEvent(Event):
    flow: Flow

    def __repr__(self):
        return f"Departure: {self.flow}."

