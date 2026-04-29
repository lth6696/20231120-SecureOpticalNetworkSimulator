from __future__ import annotations

from dataclasses import dataclass

from wdm_sim.event.control_plane import ControlPlane
from wdm_sim.event.flow import Flow
from wdm_sim.graph_algorithms import dijkstra_shortest_path, yen_k_shortest_paths
from wdm_sim.topology.virtual import WDMLightPath

from .common import FirstFitAllocator


@dataclass(frozen=True, slots=True)
class _PairSolution:
    cost: float
    working_links: list[int]
    working_wavelength: int
    backup_links: list[int]
    backup_wavelength: int
    existing_working_lightpath: WDMLightPath | None = None


@dataclass
class JointKPathPairGroomingRWA(FirstFitAllocator):
    """KSP working path plus link-disjoint backup path with grooming support.

    This implements the uploaded pseudocode in the current WDM model:
    AG is a capacity-aware physical graph; temporarily applying the working path
    is modeled by excluding its physical fiber edges from the backup graph.
    """

    k: int = 3
    cp: ControlPlane | None = None

    def simulation_interface(self, cp: ControlPlane) -> None:
        self.cp = cp

    def flow_arrival(self, flow: Flow) -> None:
        assert self.cp is not None
        if not flow.security_required:
            if self._try_unprotected_grooming_or_ksp(flow):
                return
            self.cp.block_flow(flow.id)
            return

        solution = self._select_best_protected_pair(flow)
        if solution is None:
            self.cp.block_flow(flow.id)
            return
        if not self._allocate_solution(flow, solution):
            self.cp.block_flow(flow.id)

    def flow_departure(self, flow_id: int) -> None:
        return None

    def simulation_end(self) -> None:
        return None

    def _try_unprotected_grooming_or_ksp(self, flow: Flow) -> bool:
        assert self.cp is not None
        virtual = self.cp.get_virtual_topology()
        candidates = virtual.get_available_lightpaths(flow.src, flow.dst, flow.rate)
        if candidates:
            lightpath = max(
                candidates,
                key=lambda item: virtual.get_lightpath_bw_available(item.id),
            )
            if self.cp.accept_flow(flow.id, [lightpath]):
                return True

        physical = self.cp.get_physical_topology()
        for node_path in yen_k_shortest_paths(
            physical.num_nodes,
            physical.weighted_adjacency(),
            flow.src,
            flow.dst,
            self.k,
        ):
            if self.try_first_fit_on_node_path(flow, node_path):
                return True
        return False

    def _select_best_protected_pair(self, flow: Flow) -> _PairSolution | None:
        assert self.cp is not None
        best_solution: _PairSolution | None = None

        for solution in self._existing_working_solutions(flow):
            if best_solution is None or solution.cost < best_solution.cost:
                best_solution = solution

        physical = self.cp.get_physical_topology()
        working_allowed = self._links_with_first_fit_wavelength(flow.rate)
        working_paths = yen_k_shortest_paths(
            physical.num_nodes,
            physical.filtered_weighted_adjacency(working_allowed),
            flow.src,
            flow.dst,
            self.k,
        )
        for working_node_path in working_paths:
            working_links = physical.nodes_to_links(working_node_path)
            working_wavelength = self._first_fit_wavelength(working_links, flow.rate)
            if working_wavelength is None:
                continue
            backup = self._find_backup_path(flow, working_links)
            if backup is None:
                continue
            backup_links, backup_wavelength = backup
            cost = self._path_cost(working_links) + self._path_cost(backup_links)
            solution = _PairSolution(
                cost=cost,
                working_links=working_links,
                working_wavelength=working_wavelength,
                backup_links=backup_links,
                backup_wavelength=backup_wavelength,
            )
            if best_solution is None or solution.cost < best_solution.cost:
                best_solution = solution

        return best_solution

    def _existing_working_solutions(self, flow: Flow) -> list[_PairSolution]:
        assert self.cp is not None
        virtual = self.cp.get_virtual_topology()
        solutions: list[_PairSolution] = []
        for lightpath in virtual.get_available_lightpaths(flow.src, flow.dst, flow.rate):
            backup = self._find_backup_path(flow, lightpath.links)
            if backup is None:
                continue
            backup_links, backup_wavelength = backup
            solutions.append(
                _PairSolution(
                    cost=self._path_cost(backup_links),
                    working_links=list(lightpath.links),
                    working_wavelength=lightpath.wavelengths[0],
                    backup_links=backup_links,
                    backup_wavelength=backup_wavelength,
                    existing_working_lightpath=lightpath,
                )
            )
        return solutions

    def _find_backup_path(
        self, flow: Flow, working_links: list[int]
    ) -> tuple[list[int], int] | None:
        assert self.cp is not None
        physical = self.cp.get_physical_topology()
        excluded_links: set[int] = set()
        for link_id in working_links:
            excluded_links.update(physical.shared_physical_edge_link_ids(link_id))

        allowed = self._links_with_first_fit_wavelength(flow.rate) - excluded_links
        backup_node_path = dijkstra_shortest_path(
            physical.num_nodes,
            physical.filtered_weighted_adjacency(allowed),
            flow.src,
            flow.dst,
        )
        if not backup_node_path:
            return None
        backup_links = physical.nodes_to_links(backup_node_path)
        backup_wavelength = self._first_fit_wavelength(backup_links, flow.rate)
        if backup_wavelength is None:
            return None
        return backup_links, backup_wavelength

    def _allocate_solution(self, flow: Flow, solution: _PairSolution) -> bool:
        assert self.cp is not None
        virtual = self.cp.get_virtual_topology()
        created: list[WDMLightPath] = []
        try:
            backup = virtual.create_lightpath(
                self.cp.create_candidate_wdm_lightpath(
                    flow.src,
                    flow.dst,
                    solution.backup_links,
                    [solution.backup_wavelength] * len(solution.backup_links),
                    reserved=True,
                    backup=True,
                )
            )
            created.append(backup)

            if solution.existing_working_lightpath is None:
                working = virtual.create_lightpath(
                    self.cp.create_candidate_wdm_lightpath(
                        flow.src,
                        flow.dst,
                        solution.working_links,
                        [solution.working_wavelength] * len(solution.working_links),
                    )
                )
                created.append(working)
            else:
                working = solution.existing_working_lightpath

            if not self.cp.accept_flow(flow.id, [working]):
                raise RuntimeError("selected working lightpath could not accept flow")
            self.cp.reserve_backup_lightpaths(flow.id, [backup])
            return True
        except Exception:
            for lightpath in reversed(created):
                if lightpath.id in virtual.lightpaths and virtual.is_lightpath_idle(lightpath.id):
                    virtual.remove_lightpath(lightpath.id)
            return False

    def _links_with_first_fit_wavelength(self, rate: int) -> set[int]:
        assert self.cp is not None
        physical = self.cp.get_physical_topology()
        return {
            link.id
            for link in physical.links.values()
            if any(
                link.free_wavelengths[wavelength]
                and link.available_bandwidth[wavelength] >= rate
                for wavelength in range(link.num_wavelengths)
            )
        }

    def _first_fit_wavelength(self, link_ids: list[int], rate: int) -> int | None:
        assert self.cp is not None
        physical = self.cp.get_physical_topology()
        for wavelength in range(physical.max_num_wavelengths):
            if self._path_can_host(link_ids, wavelength, rate):
                return wavelength
        return None

    def _path_cost(self, link_ids: list[int]) -> float:
        assert self.cp is not None
        physical = self.cp.get_physical_topology()
        return sum(physical.get_link(link_id).weight for link_id in link_ids)

