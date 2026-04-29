from __future__ import annotations

from dataclasses import dataclass, field

from wdm_sim.exceptions import ResourceUnavailableError, TopologyError
from wdm_sim.stats import StatsCollector
from wdm_sim.topology.physical import WDMPhysicalTopology


@dataclass(slots=True)
class WDMLightPath:
    id: int
    src: int
    dst: int
    links: list[int]
    wavelengths: list[int]
    tx: int = -1
    rx: int = -1
    reserved: bool = False
    backup: bool = False
    active_flow_ids: set[int] = field(default_factory=set)


@dataclass
class VirtualTopology:
    physical_topology: WDMPhysicalTopology
    stats: StatsCollector | None = None
    lightpaths: dict[int, WDMLightPath] = field(default_factory=dict)
    _next_lightpath_id: int = 0

    def create_lightpath(self, candidate: WDMLightPath) -> WDMLightPath:
        self._validate_candidate(candidate)

        src_node = self.physical_topology.get_node(candidate.src)
        dst_node = self.physical_topology.get_node(candidate.dst)
        if not src_node.has_free_input_port():
            raise ResourceUnavailableError(
                f"source node {candidate.src} has no free grooming input port"
            )
        if not dst_node.has_free_output_port():
            raise ResourceUnavailableError(
                f"destination node {candidate.dst} has no free grooming output port"
            )

        reserved: list[tuple[int, int]] = []
        tx = -1
        rx = -1
        try:
            for link_id, wavelength in zip(candidate.links, candidate.wavelengths):
                link = self.physical_topology.get_link(link_id)
                link.reserve_wavelength(wavelength)
                reserved.append((link_id, wavelength))
            tx = src_node.allocate_input_port()
            rx = dst_node.allocate_output_port()
        except Exception:
            for link_id, wavelength in reserved:
                self.physical_topology.get_link(link_id).release_wavelength(wavelength)
            if tx >= 0:
                src_node.release_input_port(tx)
            if rx >= 0:
                dst_node.release_output_port(rx)
            raise

        lightpath = WDMLightPath(
            id=self._next_lightpath_id,
            src=candidate.src,
            dst=candidate.dst,
            links=list(candidate.links),
            wavelengths=list(candidate.wavelengths),
            tx=tx,
            rx=rx,
            reserved=candidate.reserved,
            backup=candidate.backup,
        )
        self._next_lightpath_id += 1
        self.lightpaths[lightpath.id] = lightpath
        if self.stats is not None:
            self.stats.lightpath_created()
        return lightpath

    def remove_lightpath(self, lightpath_id: int) -> None:
        try:
            lightpath = self.lightpaths[lightpath_id]
        except KeyError as exc:
            raise TopologyError(f"unknown lightpath id {lightpath_id}") from exc
        if lightpath.active_flow_ids:
            raise ResourceUnavailableError(
                f"cannot remove lightpath {lightpath_id}; it still carries flows"
            )

        for link_id, wavelength in zip(lightpath.links, lightpath.wavelengths):
            self.physical_topology.get_link(link_id).release_wavelength(wavelength)
        self.physical_topology.get_node(lightpath.src).release_input_port(lightpath.tx)
        self.physical_topology.get_node(lightpath.dst).release_output_port(lightpath.rx)
        del self.lightpaths[lightpath_id]
        if self.stats is not None:
            self.stats.lightpath_removed()

    def deallocate_lightpaths(self, lightpaths: list[WDMLightPath]) -> None:
        for lightpath in lightpaths:
            self.remove_lightpath(lightpath.id)

    def get_available_lightpaths(
        self, src: int, dst: int, required_bw: int
    ) -> list[WDMLightPath]:
        return [
            lightpath
            for lightpath in self.lightpaths.values()
            if lightpath.src == src
            and lightpath.dst == dst
            and not lightpath.backup
            and self.get_lightpath_bw_available(lightpath.id) >= required_bw
        ]

    def get_lightpath_bw_available(self, lightpath_id: int) -> int:
        lightpath = self.lightpaths[lightpath_id]
        values = [
            self.physical_topology.get_link(link_id).available_bandwidth[wavelength]
            for link_id, wavelength in zip(lightpath.links, lightpath.wavelengths)
        ]
        return min(values) if values else 0

    def is_lightpath_idle(self, lightpath_id: int) -> bool:
        return not self.lightpaths[lightpath_id].active_flow_ids

    def _validate_candidate(self, candidate: WDMLightPath) -> None:
        if len(candidate.links) != len(candidate.wavelengths):
            raise TopologyError(
                "lightpath candidate must have the same number of links and wavelengths"
            )
        if not candidate.links:
            raise TopologyError("lightpath candidate must contain at least one link")
        self.physical_topology.validate_link_path(
            candidate.src, candidate.dst, candidate.links
        )
        first_wavelength = candidate.wavelengths[0]
        if any(wavelength != first_wavelength for wavelength in candidate.wavelengths):
            raise TopologyError(
                "wavelength conversion is not implemented; all hops must use one wavelength"
            )
        for link_id, wavelength in zip(candidate.links, candidate.wavelengths):
            link = self.physical_topology.get_link(link_id)
            link.check_wavelength_index(wavelength)
            if not link.free_wavelengths[wavelength]:
                raise ResourceUnavailableError(
                    f"link {link_id} wavelength {wavelength} is not free"
                )
