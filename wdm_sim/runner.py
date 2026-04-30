from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


@dataclass
class SimulationRunner:
    scheduler: EventScheduler
    control_plane: ControlPlane
    stats: StatsCollector
    routing_algorithm: RoutingAlgorithm

    def run(self) -> dict[str, Any]:
        # Core discrete-event loop: process the earliest event, observe it in
        # statistics, then let the control plane mutate network state.
        logger.info("Simulation loop started with %d scheduled events", len(self.scheduler))
        while len(self.scheduler) > 0:
            event: Event = self.scheduler.pop_event()
            logger.debug("Dispatching event type=%s time=%.6f", type(event).__name__, event.time)
            self.stats.observe_event(event)
            self.control_plane.new_event(event)
        self.routing_algorithm.simulation_end()
        self.control_plane.tracer.close()
        summary = self.stats.summary()
        logger.info("Simulation loop finished with summary=%s", summary)
        return summary


def build_runner(config: SimulationConfig) -> SimulationRunner:
    # Build all stateful simulation components once and connect them through the
    # control plane so algorithms work against a single shared state model.
    stats = StatsCollector()
    physical = load_physical_topology(config.topology.path)
    logger.info(
        "Physical topology loaded: nodes=%d links=%d",
        physical.num_nodes,
        len(physical.links),
    )
    virtual = VirtualTopology(physical_topology=physical, stats=stats)
    tracer = Tracer(path=config.trace_path)
    control_plane = ControlPlane(
        physical_topology=physical,
        virtual_topology=virtual,
        stats=stats,
        tracer=tracer,
    )
    routing_algorithm = _create_algorithm(config)
    logger.info("Routing algorithm selected: %s", type(routing_algorithm).__name__)
    routing_algorithm.simulation_interface(control_plane)
    control_plane.set_routing_algorithm(routing_algorithm)

    scheduler = EventScheduler()
    TrafficGenerator(config.traffic, sorted(physical.nodes)).generate(scheduler)
    logger.info("Traffic generation completed with %d scheduled events", len(scheduler))
    return SimulationRunner(
        scheduler=scheduler,
        control_plane=control_plane,
        stats=stats,
        routing_algorithm=routing_algorithm,
    )


def _create_algorithm(config: SimulationConfig) -> RoutingAlgorithm:
    # Accept a few aliases so config files can stay readable while still mapping
    # cleanly onto concrete algorithm classes.
    name = config.algorithm.name.strip().lower()
    if name in {"shortest_path_first_fit", "spff", "shortestpathfirstfitrwa"}:
        return ShortestPathFirstFitRWA()
    if name in {"grooming_shortest_path", "grooming", "groomingshortestpathrwa"}:
        return GroomingShortestPathRWA()
    if name in {"k_shortest_path_first_fit", "ksp_first_fit", "ksp"}:
        return KShortestPathFirstFitRWA(k=config.algorithm.k_paths)
    if name in {
        "joint_kpath_pair_grooming",
        "joint_k_path_pair_grooming",
        "jkpg",
        "protected_pair_grooming",
    }:
        return JointKPathPairGroomingRWA(k=config.algorithm.k_paths)
    raise ConfigurationError(f"unknown routing algorithm: {config.algorithm}")
