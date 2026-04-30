from __future__ import annotations

import logging

from wdm_sim.event.control_plane import ControlPlane
from wdm_sim.event.flow import Flow
from wdm_sim.exceptions import ResourceUnavailableError, TopologyError

logger = logging.getLogger(__name__)


class FirstFitAllocator:
    cp: ControlPlane

    def try_first_fit_on_node_path(self, flow: Flow, node_path: list[int]) -> bool:
        # Map a node route to physical links, then scan wavelengths in ascending
        # order until one can host a fresh end-to-end lightpath.
        if not node_path:
            logger.debug("No node path available for flow id=%d", flow.id)
            return False
        physical = self.cp.get_physical_topology()
        virtual = self.cp.get_virtual_topology()
        link_ids = physical.nodes_to_links(node_path)
        logger.debug(
            "Trying first-fit allocation for flow id=%d node_path=%s link_ids=%s",
            flow.id,
            node_path,
            link_ids,
        )
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
                logger.debug(
                    "First-fit candidate failed during lightpath creation flow id=%d wavelength=%d",
                    flow.id,
                    wavelength,
                )
                continue
            if self.cp.accept_flow(flow.id, [lightpath]):
                logger.info(
                    "First-fit allocation succeeded for flow id=%d lightpath id=%d wavelength=%d",
                    flow.id,
                    lightpath.id,
                    wavelength,
                )
                return True
            if virtual.is_lightpath_idle(lightpath.id):
                virtual.remove_lightpath(lightpath.id)
        logger.info("First-fit allocation failed for flow id=%d", flow.id)
        return False

    def _path_can_host(self, link_ids: list[int], wavelength: int, rate: int) -> bool:
        # A first-fit candidate is feasible only if every hop exposes the same
        # wavelength with enough residual bandwidth for the flow.
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
