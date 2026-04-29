from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TypeVar

from .events import FlowArrivalEvent, FlowDepartureEvent
from .flow import Flow
from .scheduler import EventScheduler
from wdm_sim.config import CallTypeConfig, PairWeightConfig, TrafficConfig

T = TypeVar("T")


@dataclass
class TrafficGenerator:
    config: TrafficConfig
    node_ids: list[int]

    def generate(self, scheduler: EventScheduler) -> None:
        rng = random.Random(self.config.seed)
        mean_rate = _weighted_mean_rate(self.config.call_types)
        mean_arrival_time = (
            self.config.mean_holding_time * (mean_rate / self.config.max_rate)
        ) / self.config.load

        pairs = self.config.pairs or [
            PairWeightConfig(src=src, dst=dst, weight=1.0)
            for src in self.node_ids
            for dst in self.node_ids
            if src != dst
        ]
        if not pairs:
            raise ValueError("traffic generation requires at least two nodes")

        time = 0.0
        for flow_id in range(self.config.calls):
            call_type = _weighted_choice(rng, self.config.call_types)
            pair = _weighted_choice(rng, pairs)
            inter_arrival = rng.expovariate(1.0 / mean_arrival_time)
            duration = rng.expovariate(1.0 / self.config.mean_holding_time)
            time += inter_arrival
            flow = Flow(
                id=flow_id,
                src=pair.src,
                dst=pair.dst,
                rate=call_type.rate,
                duration=duration,
                cos=call_type.cos,
                security_required=call_type.security_required,
                key_rate=call_type.key_rate,
            )
            scheduler.add_event(FlowArrivalEvent(time=time, flow=flow))
            scheduler.add_event(FlowDepartureEvent(time=time + duration, flow_id=flow_id))


def _weighted_mean_rate(call_types: list[CallTypeConfig]) -> float:
    total_weight = sum(item.weight for item in call_types)
    if total_weight <= 0:
        raise ValueError("call type weights must sum to a positive value")
    return sum(item.rate * item.weight for item in call_types) / total_weight


def _weighted_choice(rng: random.Random, items: list[T]) -> T:
    total = sum(float(getattr(item, "weight")) for item in items)
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    threshold = rng.uniform(0.0, total)
    cumulative = 0.0
    for item in items:
        cumulative += float(getattr(item, "weight"))
        if threshold <= cumulative:
            return item
    return items[-1]
