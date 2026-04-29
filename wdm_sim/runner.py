from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from algorithms import (
    GroomingShortestPathRWA,
    JointKPathPairGroomingRWA,
    KShortestPathFirstFitRWA,
    RoutingAlgorithm,
    ShortestPathFirstFitRWA,
)
from config import SimulationConfig
from event.control_plane import ControlPlane
from event.events import Event
from event.scheduler import EventScheduler
from event.traffic import TrafficGenerator
from exceptions import ConfigurationError
from stats import StatsCollector
from topology import VirtualTopology, load_physical_topology
from tracer import Tracer


@dataclass
class SimulationRunner:
    scheduler: EventScheduler
    control_plane: ControlPlane
    stats: StatsCollector
    routing_algorithm: RoutingAlgorithm

    def run(self) -> dict[str, Any]:
        while len(self.scheduler) > 0:
            event: Event = self.scheduler.pop_event()
            self.stats.observe_event(event)
            self.control_plane.new_event(event)
        self.routing_algorithm.simulation_end()
        self.control_plane.tracer.close()
        return self.stats.summary()


def build_runner(config: SimulationConfig) -> SimulationRunner:
    stats = StatsCollector()
    physical = load_physical_topology(config.topology_path)
    virtual = VirtualTopology(physical_topology=physical, stats=stats)
    tracer = Tracer(path=config.trace_path)
    control_plane = ControlPlane(
        physical_topology=physical,
        virtual_topology=virtual,
        stats=stats,
        tracer=tracer,
    )
    routing_algorithm = _create_algorithm(config)
    routing_algorithm.simulation_interface(control_plane)
    control_plane.set_routing_algorithm(routing_algorithm)

    scheduler = EventScheduler()
    TrafficGenerator(config.traffic, sorted(physical.nodes)).generate(scheduler)
    return SimulationRunner(
        scheduler=scheduler,
        control_plane=control_plane,
        stats=stats,
        routing_algorithm=routing_algorithm,
    )


def _create_algorithm(config: SimulationConfig) -> RoutingAlgorithm:
    name = config.algorithm.strip().lower()
    if name in {"shortest_path_first_fit", "spff", "shortestpathfirstfitrwa"}:
        return ShortestPathFirstFitRWA()
    if name in {"grooming_shortest_path", "grooming", "groomingshortestpathrwa"}:
        return GroomingShortestPathRWA()
    if name in {"k_shortest_path_first_fit", "ksp_first_fit", "ksp"}:
        return KShortestPathFirstFitRWA(k=config.k_paths)
    if name in {
        "joint_kpath_pair_grooming",
        "joint_k_path_pair_grooming",
        "jkpg",
        "protected_pair_grooming",
    }:
        return JointKPathPairGroomingRWA(k=config.k_paths)
    raise ConfigurationError(f"unknown routing algorithm: {config.algorithm}")
