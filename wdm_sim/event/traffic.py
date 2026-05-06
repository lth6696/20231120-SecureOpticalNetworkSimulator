from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import TypeVar

from .events import FlowArrivalEvent, FlowDepartureEvent
from .flow import Flow
from .scheduler import EventScheduler
from wdm_sim.config import CallTypeConfig, TrafficConfig

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass
class TrafficGenerator:
    config: TrafficConfig
    node_ids: list[int]

    def generate(self, scheduler: EventScheduler) -> None:
        # Each generated flow immediately schedules both its arrival and its
        # future departure so teardown ordering stays deterministic.
        rng = random.Random(self.config.seed)
        mean_rate = _weighted_mean_rate(self.config.call_types)
        mean_arrival_time = (
            self.config.mean_holding_time * (mean_rate / self.config.max_bandwidth)
        ) / self.config.load

        pairs = [
            (src, dst)
            for src in self.node_ids
            for dst in self.node_ids
            if src != dst
        ]
        if not pairs:
            raise ValueError("traffic generation requires at least two nodes")

        time = 0.0
        for flow_id in range(self.config.calls):
            call_type = _weighted_choice(rng, self.config.call_types)
            pair = rng.choice(pairs)
            inter_arrival = rng.expovariate(1.0 / mean_arrival_time)
            duration = rng.expovariate(1.0 / self.config.mean_holding_time)
            time += inter_arrival
            flow = Flow(
                id=flow_id,
                src=pair[0],
                dst=pair[1],
                # rate=call_type.rate,
                rate=rng.randint(self.config.min_bandwidth, self.config.max_bandwidth),
                duration=duration,
                cos=call_type.cos,
                security_required=rng.randint(self.config.min_security_level, self.config.max_security_level),
                key_rate=rng.randint(self.config.min_key_rate, self.config.max_key_rate),
            )
            scheduler.add_event(FlowArrivalEvent(time=time, flow=flow))
            scheduler.add_event(FlowDepartureEvent(time=time + duration, flow_id=flow_id))
            logger.debug(FlowArrivalEvent(time=time, flow=flow))
            logger.debug(FlowDepartureEvent(time=time + duration, flow_id=flow_id))
        logger.info(
            "Traffic generated: flows=%d mean_arrival_time=%.6f seed=%s",
            self.config.calls,
            mean_arrival_time,
            self.config.seed,
        )


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
