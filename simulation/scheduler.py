from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field

from models.events import Event


@dataclass
class EventScheduler:
    _heap: list[tuple[float, int, Event]] = field(default_factory=list)
    _sequence: itertools.count = field(default_factory=itertools.count)

    def add_event(self, event: Event) -> None:
        if event.time < 0:
            raise ValueError(f"simulation time must be non-negative, got {event.time}")
        heapq.heappush(self._heap, (event.time, next(self._sequence), event))

    def pop_event(self) -> Event:
        if not self._heap:
            raise IndexError("cannot pop from an empty simulation scheduler")
        return heapq.heappop(self._heap)[2]

    def __len__(self) -> int:
        return len(self._heap)

