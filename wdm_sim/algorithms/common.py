from __future__ import annotations

from wdm_sim.event.control_plane import ControlPlane
from wdm_sim.event.flow import Flow
from wdm_sim.exceptions import ResourceUnavailableError, TopologyError


class FirstFitAllocator:
    cp: ControlPlane

    def try_first_fit_on_node_path(self, flow: Flow, node_path: list[int]) -> bool:
        if not node_path:
            return False
        physical = self.cp.get_physical_topology()
        virtual = self.cp.get_virtual_topology()
        link_ids = physical.nodes_to_links(node_path)
        for wavelength in range(physical.max_num_wavelengths):
            if not self._path_can_host(link_ids, wavelength, flow.rate):
                continue
            candidate = self.cp.create_candidate_wdm_lightpath(
                flow.src,
                flow.dst,
                link_ids,
                [wavelength] * len(link_ids),
            )
            try:
                lightpath = virtual.create_lightpath(candidate)
            except (ResourceUnavailableError, TopologyError):
                continue
            if self.cp.accept_flow(flow.id, [lightpath]):
                return True
            if virtual.is_lightpath_idle(lightpath.id):
                virtual.remove_lightpath(lightpath.id)
        return False

    def _path_can_host(self, link_ids: list[int], wavelength: int, rate: int) -> bool:
        physical = self.cp.get_physical_topology()
        for link_id in link_ids:
            link = physical.get_link(link_id)
            if wavelength >= link.num_wavelengths:
                return False
            if not link.free_wavelengths[wavelength]:
                return False
            if link.available_bandwidth[wavelength] < rate:
                return False
        return True
