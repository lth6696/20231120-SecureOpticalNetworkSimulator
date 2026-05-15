from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from algorithms import *
from models.config import SimulationConfig
from simulation.control_plane import ControlPlane
from models.events import Event
from simulation.scheduler import EventScheduler
from simulation.traffic import TrafficGenerator
from models.exceptions import ConfigurationError
from observability.stats import StatsCollector
from topology import VirtualTopology, PhysicalTopology
from observability.tracer import Tracer

logger = logging.getLogger(__name__)


class SimulationRunner:
    def __init__(self):
        self.scheduler: EventScheduler | None = None
        self.control_plane: ControlPlane | None = None
        self.stats: StatsCollector | None = None
        self.routing_algorithm: HeuristicAlgorithm | None = None

    def run(self) -> dict[str, Any]:
        # Core discrete-simulation loop: process the earliest simulation, observe it in
        # statistics, then let the control plane mutate network state.
        logger.info(f"{"=" * 30} Start Simulation {"=" * 30}")
        logger.info("Simulation loop started with %d scheduled events", len(self.scheduler))
        while len(self.scheduler) > 0:
            event: Event = self.scheduler.pop_event()
            logger.debug("Dispatching simulation type=%s time=%.6f", type(event).__name__, event.time)
            self.stats.observe_event(event)
            self.control_plane.process_event(event)
        # self.routing_algorithm.simulation_end()
        return self.stats.summary()

    def build(self, config: SimulationConfig):
        # 创建统计模块，用于记录业务到达、接受、阻塞、释放、资源利用率等仿真过程中的统计信息。
        self.stats = StatsCollector(config)
        # 创建事件追踪器
        # tracer = Tracer(path=config.trace_path)

        # 加载物理拓扑
        pt = PhysicalTopology()
        pt.load(config.topology.path, **asdict(config.topology.resource))

        # 创建虚拟拓扑
        vt = VirtualTopology()
        vt.init(pt.graph)

        # 创建控制平面
        logger.info(f"{'='*25} Initialize Control Plane {'='*25}")
        routing_algorithm = self._create_algorithm(config)
        self.control_plane = ControlPlane(
            pt=pt,
            vt=vt,
            stats=self.stats,
        )
        self.control_plane.set_algorithm(routing_algorithm)
        logger.info("Algorithm selected: %s", type(routing_algorithm).__name__)

        # 创建事件调度器
        logger.info(f"{'=' * 25} Initialize Scheduler {'=' * 25}")
        self.scheduler = EventScheduler()
        TrafficGenerator(config.traffic, sorted(pt.graph.nodes())).generate(self.scheduler)
        logger.info("Traffic generation completed with %d scheduled events", len(self.scheduler))

    @staticmethod
    def _create_algorithm(config: SimulationConfig) -> HeuristicAlgorithm:
        # Accept a few aliases so config files can stay readable while still mapping
        # cleanly onto concrete algorithm classes.
        name = config.algorithm.name.strip().lower()
        if name == "jdrg":
            return AuxGJointDataRecipGrooming(k=config.algorithm.k)
        elif name == "sfg":
            return AuxGSecurityFirstGrooming(k=config.algorithm.k)
        elif name == "cfg":
            return AuxGCostFirstGrooming(k=config.algorithm.k, c_h=config.attrs["costs"]["channel"], c_p=config.attrs["costs"]["port"])
        raise ConfigurationError(f"unknown routing algorithm: {config.algorithm}")
