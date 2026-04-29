from __future__ import annotations

import unittest
from pathlib import Path

from wdm_sim.config import load_simulation_config
from wdm_sim.event.control_plane import ControlPlane
from wdm_sim.event.events import Event
from wdm_sim.event.flow import Flow
from wdm_sim.event.scheduler import EventScheduler
from wdm_sim.runner import build_runner
from wdm_sim.stats import StatsCollector
from wdm_sim.topology.physical import (
    WDMLink,
    WDMNode,
    WDMPhysicalTopology,
    load_physical_topology,
)
from wdm_sim.topology.virtual import VirtualTopology
from wdm_sim.tracer import Tracer

ROOT = Path(__file__).resolve().parents[1]


class EventSchedulerTests(unittest.TestCase):
    def test_same_time_events_keep_insertion_order(self) -> None:
        scheduler = EventScheduler()
        first = Event(time=1.0)
        second = Event(time=1.0)
        scheduler.add_event(first)
        scheduler.add_event(second)

        self.assertIs(scheduler.pop_event(), first)
        self.assertIs(scheduler.pop_event(), second)


class GroomingResourceTests(unittest.TestCase):
    def test_two_flows_share_lightpath_and_release_when_idle(self) -> None:
        physical = WDMPhysicalTopology(
            nodes={
                0: WDMNode(0, grooming_input_ports=2, grooming_output_ports=2),
                1: WDMNode(1, grooming_input_ports=2, grooming_output_ports=2),
            },
            links={
                0: WDMLink(
                    id=0,
                    src=0,
                    dst=1,
                    weight=1.0,
                    num_wavelengths=1,
                    wavelength_bandwidth=100,
                )
            },
        )
        stats = StatsCollector()
        virtual = VirtualTopology(physical_topology=physical, stats=stats)
        cp = ControlPlane(
            physical_topology=physical,
            virtual_topology=virtual,
            stats=stats,
            tracer=Tracer(),
        )
        lp = virtual.create_lightpath(
            cp.create_candidate_wdm_lightpath(0, 1, [0], [0])
        )
        flow_a = Flow(id=1, src=0, dst=1, rate=40, duration=1.0, cos=0)
        flow_b = Flow(id=2, src=0, dst=1, rate=30, duration=1.0, cos=0)
        cp.active_flows[1] = flow_a
        cp.active_flows[2] = flow_b

        self.assertTrue(cp.accept_flow(1, [lp]))
        self.assertTrue(cp.accept_flow(2, [lp]))
        self.assertEqual(physical.get_link(0).available_bandwidth[0], 30)
        self.assertEqual(stats.grooming_count, 1)

        cp.remove_flow(1)
        self.assertIn(lp.id, virtual.lightpaths)
        cp.remove_flow(2)
        self.assertNotIn(lp.id, virtual.lightpaths)
        self.assertTrue(physical.get_link(0).free_wavelengths[0])
        self.assertEqual(physical.get_link(0).available_bandwidth[0], 100)


class GraphMLTopologyTests(unittest.TestCase):
    def test_undirected_graphml_is_loaded_as_directed_wdm_links(self) -> None:
        topology = load_physical_topology(ROOT / "wdm_sim/graphml/SixNode.graphml")

        self.assertEqual(topology.num_nodes, 6)
        self.assertEqual(len(topology.links), 16)
        self.assertIsNotNone(topology.find_link(1, 2))
        self.assertIsNotNone(topology.find_link(2, 1))


class ProtectedPairGroomingTests(unittest.TestCase):
    def test_protected_pair_grooming_releases_reserved_backups(self) -> None:
        config = load_simulation_config(ROOT / "examples/protected_config.json")
        runner = build_runner(config)
        summary = runner.run()

        self.assertGreater(summary["accepted"], 0)
        self.assertEqual(
            summary["num_lightpaths_created"], summary["num_lightpaths_removed"]
        )
        self.assertEqual(len(runner.control_plane.virtual_topology.lightpaths), 0)


if __name__ == "__main__":
    unittest.main()
