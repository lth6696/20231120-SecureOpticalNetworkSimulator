from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any

from algorithms import *
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
    routing_algorithm: HeuristicAlgorithm

    def run(self) -> dict[str, Any]:
        # Core discrete-event loop: process the earliest event, observe it in
        # statistics, then let the control plane mutate network state.
        logger.info(f"{"=" * 30} Start Simulation {"=" * 30}")
        logger.info("Simulation loop started with %d scheduled events", len(self.scheduler))
        while len(self.scheduler) > 0:
            event: Event = self.scheduler.pop_event()
            logger.debug("Dispatching event type=%s time=%.6f", type(event).__name__, event.time)
            self.stats.observe_event(event)
            self.control_plane.process_event(event)
        self.routing_algorithm.simulation_end()
        self.control_plane.tracer.close()
        summary = self.stats.summary()
        logger.info("Simulation loop finished with summary=%s", summary)
        return summary


def build_runner(config: SimulationConfig) -> SimulationRunner:
    # 创建统计模块，用于记录业务到达、接受、阻塞、释放、资源利用率等仿真过程中的统计信息。
    stats = StatsCollector()
    # 创建事件追踪器
    tracer = Tracer(path=config.trace_path)

    # 加载物理拓扑
    pt = load_physical_topology(config.topology.path, **asdict(config.topology.resource))
    # 创建虚拟拓扑
    vt = VirtualTopology()
    vt.init(pt.graph)

    # 创建控制平面
    logger.info(f"{'='*25} Initialize Control Plane {'='*25}")
    control_plane = ControlPlane(
        pt=pt,
        vt=vt,
        stats=stats,
        tracer=tracer,
    )
    routing_algorithm = _create_algorithm(config)
    routing_algorithm.simulation_interface(control_plane)
    control_plane.set_algorithm(routing_algorithm)
    logger.info("Algorithm selected: %s", type(routing_algorithm).__name__)

    # 创建事件调度器
    logger.info(f"{'=' * 25} Initialize Scheduler {'=' * 25}")
    scheduler = EventScheduler()
    TrafficGenerator(config.traffic, sorted(pt.graph.nodes())).generate(scheduler)
    logger.info("Traffic generation completed with %d scheduled events", len(scheduler))
    return SimulationRunner(
        scheduler=scheduler,
        control_plane=control_plane,
        stats=stats,
        routing_algorithm=routing_algorithm,
    )


def _create_algorithm(config: SimulationConfig) -> HeuristicAlgorithm:
    # Accept a few aliases so config files can stay readable while still mapping
    # cleanly onto concrete algorithm classes.
    name = config.algorithm.name.strip().lower()
    if name == "jdrg":
        return AuxGJointDataRecipGrooming(k=config.algorithm.k)
    elif name == "sfg":
        return AuxGSecurityFirstGrooming(k=config.algorithm.k)
    raise ConfigurationError(f"unknown routing algorithm: {config.algorithm}")
