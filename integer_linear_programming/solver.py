from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from .data_model import (
    ActiveLightpath,
    LightpathKey,
    NetworkInstance,
    PhysicalAssignment,
    RequestRouting,
    SolverSolution,
)

logger = logging.getLogger(__name__)


def _require_pulp():
    """Import PuLP lazily so dependency errors point at the solver boundary."""
    try:
        import pulp
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PuLP is not installed. Run `python -m pip install -r requirements.txt`."
        ) from exc
    return pulp


@dataclass(slots=True)
class _ModelArtifacts:
    problem: object
    mu: dict[str, object]
    gamma: dict[str, object]
    lambda_vars: dict[tuple[str, LightpathKey], object]
    kappa_vars: dict[tuple[str, LightpathKey], object]
    service_active: dict[LightpathKey, object]
    security_active: dict[LightpathKey, object]
    iota_vars: dict[tuple[LightpathKey, tuple[str, str], int], object]
    chi_vars: dict[tuple[LightpathKey, tuple[str, str], int], object]
    rho_vars: dict[tuple[str, LightpathKey, tuple[str, str], int], object]
    varphi_vars: dict[tuple[str, LightpathKey, tuple[str, str], int], object]
    cost_expressions: dict[str, object]


class SecureOpticalILPSolver:
    """Build and solve the revised security-aware optical network ILP."""

    def __init__(
        self,
        instance: NetworkInstance,
        *,
        solver: str | None = None,
        candidate_lightpaths_per_pair: int | None = None,
        time_limit_seconds: int | None = None,
        solver_message: bool = False,
    ) -> None:
        self.instance = instance
        self.solver_name = solver
        self.time_limit_seconds = time_limit_seconds
        self.solver_message = solver_message
        self.lightpaths_per_pair = (
            candidate_lightpaths_per_pair or self.instance.wavelengths
        )

        self._requests = {
            request.request_id: request for request in self.instance.requests
        }
        self._request_ids = tuple(self._requests)
        self._edges = self.instance.directed_edges
        self._wavelengths = self.instance.wavelength_indices
        self._lightpaths = tuple(
            LightpathKey(source, target, index)
            for source in self.instance.nodes
            for target in self.instance.nodes
            if source != target
            for index in range(self.lightpaths_per_pair)
        )

        self._out_edges = defaultdict(list)
        self._in_edges = defaultdict(list)
        for edge in self._edges:
            self._out_edges[edge[0]].append(edge)
            self._in_edges[edge[1]].append(edge)

    def solve(self) -> SolverSolution:
        """Solve in two stages: maximize admitted requests, then minimize cost."""
        pulp = _require_pulp()
        logger.info("%s Start Solving ILP %s", "=" * 20, "=" * 20)
        logger.info("Available PuLP solvers: %s", pulp.listSolvers(onlyAvailable=True))
        logger.info(
            "ILP size input: requests=%s, lightpaths=%s, directed_edges=%s, wavelengths=%s",
            len(self._request_ids),
            len(self._lightpaths),
            len(self._edges),
            len(self._wavelengths),
        )

        phase_one = self._build_model(maximize_admitted=True)
        self._solve_problem(phase_one.problem, pulp)
        phase_one_status = pulp.LpStatus[phase_one.problem.status]
        logger.info("Phase 1 status=%s", phase_one_status)
        if phase_one_status != "Optimal":
            raise RuntimeError(f"Phase 1 did not solve optimally: {phase_one_status}")

        admitted_target = int(round(pulp.value(phase_one.problem.objective) or 0.0))
        phase_one_objective = float(pulp.value(phase_one.problem.objective) or 0.0)
        logger.info("Phase 1 accepted %s requests", admitted_target)

        phase_two = self._build_model(
            maximize_admitted=False,
            fixed_admitted_requests=admitted_target,
        )
        self._solve_problem(phase_two.problem, pulp)
        phase_two_status = pulp.LpStatus[phase_two.problem.status]
        logger.info("Phase 2 status=%s", phase_two_status)
        if phase_two_status != "Optimal":
            raise RuntimeError(f"Phase 2 did not solve optimally: {phase_two_status}")

        solution = self._extract_solution(
            artifacts=phase_two,
            pulp=pulp,
            phase_one_objective=phase_one_objective,
        )
        logger.info(
            "Solution extracted: admitted=%s/%s, phase2_objective=%.4f",
            solution.admitted_count,
            solution.total_requests,
            solution.phase_two_objective or 0.0,
        )
        return solution

    def _build_model(
        self,
        *,
        maximize_admitted: bool,
        fixed_admitted_requests: int | None = None,
    ) -> _ModelArtifacts:
        pulp = _require_pulp()
        sense = pulp.LpMaximize if maximize_admitted else pulp.LpMinimize
        problem = pulp.LpProblem("secure_optical_network_ilp", sense)

        mu = {
            request_id: pulp.LpVariable(f"mu_{request_id}", cat="Binary")
            for request_id in self._request_ids
        }
        gamma = {
            request_id: pulp.LpVariable(f"gamma_{request_id}", cat="Binary")
            for request_id in self._request_ids
        }
        lambda_vars = {
            (request_id, key): pulp.LpVariable(
                f"lambda_{request_id}_{key.source}_{key.target}_{key.index}",
                cat="Binary",
            )
            for request_id in self._request_ids
            for key in self._lightpaths
        }
        kappa_vars = {
            (request_id, key): pulp.LpVariable(
                f"kappa_{request_id}_{key.source}_{key.target}_{key.index}",
                cat="Binary",
            )
            for request_id in self._request_ids
            for key in self._lightpaths
        }
        service_active = {
            key: pulp.LpVariable(
                f"service_active_{key.source}_{key.target}_{key.index}",
                cat="Binary",
            )
            for key in self._lightpaths
        }
        security_active = {
            key: pulp.LpVariable(
                f"security_active_{key.source}_{key.target}_{key.index}",
                cat="Binary",
            )
            for key in self._lightpaths
        }
        iota_vars = {
            (key, edge, wavelength): pulp.LpVariable(
                f"iota_{key.source}_{key.target}_{key.index}_{edge[0]}_{edge[1]}_{wavelength}",
                cat="Binary",
            )
            for key in self._lightpaths
            for edge in self._edges
            for wavelength in self._wavelengths
        }
        chi_vars = {
            (key, edge, wavelength): pulp.LpVariable(
                f"chi_{key.source}_{key.target}_{key.index}_{edge[0]}_{edge[1]}_{wavelength}",
                cat="Binary",
            )
            for key in self._lightpaths
            for edge in self._edges
            for wavelength in self._wavelengths
        }
        rho_vars = {
            (request_id, key, edge, wavelength): pulp.LpVariable(
                f"rho_{request_id}_{key.source}_{key.target}_{key.index}_{edge[0]}_{edge[1]}_{wavelength}",
                lowBound=0,
                upBound=1,
                cat="Continuous",
            )
            for request_id in self._request_ids
            for key in self._lightpaths
            for edge in self._edges
            for wavelength in self._wavelengths
        }
        varphi_vars = {
            (request_id, key, edge, wavelength): pulp.LpVariable(
                f"varphi_{request_id}_{key.source}_{key.target}_{key.index}_{edge[0]}_{edge[1]}_{wavelength}",
                lowBound=0,
                upBound=1,
                cat="Continuous",
            )
            for request_id in self._request_ids
            for key in self._lightpaths
            for edge in self._edges
            for wavelength in self._wavelengths
        }

        for request_id in self._request_ids:
            request = self._requests[request_id]
            security_required = self._delta_key_rate(request.key_rate)
            problem += gamma[request_id] == security_required * mu[request_id]

            self._add_logical_flow_constraints(
                problem=problem,
                request_id=request_id,
                source=request.source,
                target=request.target,
                demand_variable=mu[request_id],
                layer_vars=lambda_vars,
                pulp=pulp,
            )
            self._add_logical_flow_constraints(
                problem=problem,
                request_id=request_id,
                source=request.source,
                target=request.target,
                demand_variable=gamma[request_id],
                layer_vars=kappa_vars,
                pulp=pulp,
            )

            if security_required:
                for source in self.instance.nodes:
                    for target in self.instance.nodes:
                        if source == target:
                            continue
                        problem += (
                            pulp.lpSum(
                                lambda_vars[(request_id, key)]
                                for key in self._lightpaths
                                if key.source == source and key.target == target
                            )
                            == pulp.lpSum(
                                kappa_vars[(request_id, key)]
                                for key in self._lightpaths
                                if key.source == source and key.target == target
                            )
                        )
            else:
                problem += (
                    pulp.lpSum(
                        kappa_vars[(request_id, key)] for key in self._lightpaths
                    )
                    == 0
                )

            for edge in self._edges:
                problem += (
                    pulp.lpSum(
                        rho_vars[(request_id, key, edge, wavelength)]
                        + varphi_vars[(request_id, key, edge, wavelength)]
                        for key in self._lightpaths
                        for wavelength in self._wavelengths
                    )
                    <= 1
                )

        for key in self._lightpaths:
            service_usage = pulp.lpSum(
                lambda_vars[(request_id, key)] for request_id in self._request_ids
            )
            security_usage = pulp.lpSum(
                kappa_vars[(request_id, key)] for request_id in self._request_ids
            )

            problem += service_usage <= len(self._request_ids) * service_active[key]
            problem += security_usage <= len(self._request_ids) * security_active[key]
            problem += service_active[key] <= service_usage
            problem += security_active[key] <= security_usage
            problem += service_active[key] + security_active[key] <= 1

            problem += (
                pulp.lpSum(
                    self._requests[request_id].bandwidth
                    * lambda_vars[(request_id, key)]
                    for request_id in self._request_ids
                )
                <= self.instance.bandwidth_max
            )
            problem += (
                pulp.lpSum(
                    self._requests[request_id].key_rate
                    * kappa_vars[(request_id, key)]
                    for request_id in self._request_ids
                )
                <= self.instance.key_rate_max
            )

            self._add_physical_flow_constraints(
                problem=problem,
                key=key,
                demand_expression=service_active[key],
                edge_vars=iota_vars,
                pulp=pulp,
            )
            self._add_physical_flow_constraints(
                problem=problem,
                key=key,
                demand_expression=security_active[key],
                edge_vars=chi_vars,
                pulp=pulp,
            )

            for edge in self._edges:
                for wavelength in self._wavelengths:
                    problem += iota_vars[(key, edge, wavelength)] <= service_active[key]
                    problem += chi_vars[(key, edge, wavelength)] <= security_active[key]

        for edge in self._edges:
            problem += (
                pulp.lpSum(
                    iota_vars[(key, edge, wavelength)]
                    + chi_vars[(key, edge, wavelength)]
                    for key in self._lightpaths
                    for wavelength in self._wavelengths
                )
                <= self.instance.wavelengths
            )
            for wavelength in self._wavelengths:
                problem += (
                    pulp.lpSum(
                        iota_vars[(key, edge, wavelength)]
                        + chi_vars[(key, edge, wavelength)]
                        for key in self._lightpaths
                    )
                    <= 1
                )

        for request_id in self._request_ids:
            for key in self._lightpaths:
                for edge in self._edges:
                    for wavelength in self._wavelengths:
                        rho = rho_vars[(request_id, key, edge, wavelength)]
                        varphi = varphi_vars[(request_id, key, edge, wavelength)]
                        lambda_var = lambda_vars[(request_id, key)]
                        kappa_var = kappa_vars[(request_id, key)]
                        iota_var = iota_vars[(key, edge, wavelength)]
                        chi_var = chi_vars[(key, edge, wavelength)]

                        problem += rho <= lambda_var
                        problem += rho <= iota_var
                        problem += rho >= lambda_var + iota_var - 1
                        problem += varphi <= kappa_var
                        problem += varphi <= chi_var
                        problem += varphi >= kappa_var + chi_var - 1

        if fixed_admitted_requests is not None:
            problem += (
                pulp.lpSum(mu[request_id] for request_id in self._request_ids)
                == fixed_admitted_requests
            )

        security_wavelength_cost = self.instance.costs.wavelength_cost * pulp.lpSum(
            chi_vars.values()
        )
        security_distance_cost = self.instance.costs.distance_cost * pulp.lpSum(
            self.instance.distance_lookup[edge] * chi_vars[(key, edge, wavelength)]
            for key in self._lightpaths
            for edge in self._edges
            for wavelength in self._wavelengths
        )
        key_rate_cost = self.instance.costs.key_rate_cost * pulp.lpSum(
            gamma[request_id] * self._requests[request_id].key_rate
            for request_id in self._request_ids
        )
        security_port_cost = 2 * self.instance.costs.security_port_cost * pulp.lpSum(
            kappa_vars.values()
        )
        logical_hop_tiebreak = self.instance.costs.logical_hop_tiebreak * (
            pulp.lpSum(lambda_vars.values()) + pulp.lpSum(kappa_vars.values())
        )
        physical_hop_tiebreak = self.instance.costs.physical_hop_tiebreak * (
            pulp.lpSum(iota_vars.values()) + pulp.lpSum(chi_vars.values())
        )

        if maximize_admitted:
            problem += pulp.lpSum(mu.values())
        else:
            problem += (
                security_wavelength_cost
                + security_distance_cost
                + key_rate_cost
                + security_port_cost
                + logical_hop_tiebreak
                + physical_hop_tiebreak
            )

        return _ModelArtifacts(
            problem=problem,
            mu=mu,
            gamma=gamma,
            lambda_vars=lambda_vars,
            kappa_vars=kappa_vars,
            service_active=service_active,
            security_active=security_active,
            iota_vars=iota_vars,
            chi_vars=chi_vars,
            rho_vars=rho_vars,
            varphi_vars=varphi_vars,
            cost_expressions={
                "security_wavelength_cost": security_wavelength_cost,
                "security_distance_cost": security_distance_cost,
                "key_rate_cost": key_rate_cost,
                "security_port_cost": security_port_cost,
                "logical_hop_tiebreak": logical_hop_tiebreak,
                "physical_hop_tiebreak": physical_hop_tiebreak,
            },
        )

    def _add_logical_flow_constraints(
        self,
        *,
        problem,
        request_id: str,
        source: str,
        target: str,
        demand_variable,
        layer_vars: dict[tuple[str, LightpathKey], object],
        pulp,
    ) -> None:
        problem += (
            pulp.lpSum(
                layer_vars[(request_id, key)]
                for key in self._lightpaths
                if key.source == source
            )
            == demand_variable
        )
        problem += (
            pulp.lpSum(
                layer_vars[(request_id, key)]
                for key in self._lightpaths
                if key.target == target
            )
            == demand_variable
        )
        problem += (
            pulp.lpSum(
                layer_vars[(request_id, key)]
                for key in self._lightpaths
                if key.target == source
            )
            == 0
        )
        problem += (
            pulp.lpSum(
                layer_vars[(request_id, key)]
                for key in self._lightpaths
                if key.source == target
            )
            == 0
        )

        for node in self.instance.nodes:
            if node in {source, target}:
                continue
            problem += (
                pulp.lpSum(
                    layer_vars[(request_id, key)]
                    for key in self._lightpaths
                    if key.target == node
                )
                == pulp.lpSum(
                    layer_vars[(request_id, key)]
                    for key in self._lightpaths
                    if key.source == node
                )
            )

    def _add_physical_flow_constraints(
        self,
        *,
        problem,
        key: LightpathKey,
        demand_expression,
        edge_vars: dict[tuple[LightpathKey, tuple[str, str], int], object],
        pulp,
    ) -> None:
        problem += (
            pulp.lpSum(
                edge_vars[(key, edge, wavelength)]
                for edge in self._out_edges[key.source]
                for wavelength in self._wavelengths
            )
            == demand_expression
        )
        problem += (
            pulp.lpSum(
                edge_vars[(key, edge, wavelength)]
                for edge in self._in_edges[key.target]
                for wavelength in self._wavelengths
            )
            == demand_expression
        )
        problem += (
            pulp.lpSum(
                edge_vars[(key, edge, wavelength)]
                for edge in self._in_edges[key.source]
                for wavelength in self._wavelengths
            )
            == 0
        )
        problem += (
            pulp.lpSum(
                edge_vars[(key, edge, wavelength)]
                for edge in self._out_edges[key.target]
                for wavelength in self._wavelengths
            )
            == 0
        )

        for node in self.instance.nodes:
            if node in {key.source, key.target}:
                continue
            for wavelength in self._wavelengths:
                problem += (
                    pulp.lpSum(
                        edge_vars[(key, edge, wavelength)]
                        for edge in self._in_edges[node]
                    )
                    == pulp.lpSum(
                        edge_vars[(key, edge, wavelength)]
                        for edge in self._out_edges[node]
                    )
                )

    def _solve_problem(self, problem, pulp) -> None:
        solver = self._select_solver(pulp)
        if solver is None:
            problem.solve()
            return
        try:
            problem.solve(solver)
        except Exception as exc:
            if self.solver_name == "PULP_CBC_CMD":
                raise
            logger.warning(
                "Configured solver %s failed (%s); falling back to PULP_CBC_CMD",
                self.solver_name,
                exc,
            )
            fallback = self._make_solver(pulp, "PULP_CBC_CMD")
            if fallback is None:
                raise
            problem.solve(fallback)

    def _select_solver(self, pulp):
        for solver_name in (self.solver_name, "PULP_CBC_CMD"):
            if not solver_name:
                continue
            solver = self._make_solver(pulp, solver_name)
            if solver is not None:
                return solver
        return None

    def _make_solver(self, pulp, solver_name: str):
        solver_class = getattr(pulp, solver_name, None)
        if solver_class is None:
            logger.warning("PuLP solver %s is not known; falling back", solver_name)
            return None
        try:
            solver = solver_class(
                msg=self.solver_message,
                timeLimit=self.time_limit_seconds,
            )
        except TypeError:
            solver = solver_class(msg=self.solver_message)
        try:
            if solver.available():
                return solver
        except Exception:  # pragma: no cover - solver-specific behavior
            logger.warning("Could not check availability for solver %s", solver_name)
            return solver
        logger.warning("PuLP solver %s is not available; falling back", solver_name)
        return None

    @staticmethod
    def _delta_key_rate(key_rate: float) -> int:
        """Linear counterpart of delta(S): 1 if a key-rate demand exists."""
        return 1 if key_rate > 0 else 0

    def _extract_solution(
        self,
        *,
        artifacts: _ModelArtifacts,
        pulp,
        phase_one_objective: float,
    ) -> SolverSolution:
        def is_one(variable) -> bool:
            return (pulp.value(variable) or 0.0) > 0.5

        request_routes = []
        for request_id in self._request_ids:
            request = self._requests[request_id]
            service_lightpaths = tuple(
                key
                for key in self._lightpaths
                if is_one(artifacts.lambda_vars[(request_id, key)])
            )
            security_lightpaths = tuple(
                key
                for key in self._lightpaths
                if is_one(artifacts.kappa_vars[(request_id, key)])
            )
            request_routes.append(
                RequestRouting(
                    request_id=request_id,
                    admitted=is_one(artifacts.mu[request_id]),
                    security_enabled=is_one(artifacts.gamma[request_id]),
                    service_lightpaths=self._order_lightpaths(
                        service_lightpaths,
                        source=request.source,
                        target=request.target,
                    ),
                    security_lightpaths=self._order_lightpaths(
                        security_lightpaths,
                        source=request.source,
                        target=request.target,
                    ),
                )
            )

        service_lightpaths = []
        security_lightpaths = []
        for key in self._lightpaths:
            service_request_ids = tuple(
                request_id
                for request_id in self._request_ids
                if is_one(artifacts.lambda_vars[(request_id, key)])
            )
            if service_request_ids:
                assignments = tuple(
                    PhysicalAssignment(
                        source=edge[0],
                        target=edge[1],
                        wavelength=wavelength,
                        distance=self.instance.distance_lookup[edge],
                    )
                    for edge in self._edges
                    for wavelength in self._wavelengths
                    if is_one(artifacts.iota_vars[(key, edge, wavelength)])
                )
                service_lightpaths.append(
                    ActiveLightpath(
                        key=key,
                        layer="service",
                        request_ids=service_request_ids,
                        carried_load=sum(
                            self._requests[request_id].bandwidth
                            for request_id in service_request_ids
                        ),
                        physical_assignments=self._order_physical_assignments(
                            assignments,
                            source=key.source,
                            target=key.target,
                        ),
                    )
                )

            security_request_ids = tuple(
                request_id
                for request_id in self._request_ids
                if is_one(artifacts.kappa_vars[(request_id, key)])
            )
            if security_request_ids:
                assignments = tuple(
                    PhysicalAssignment(
                        source=edge[0],
                        target=edge[1],
                        wavelength=wavelength,
                        distance=self.instance.distance_lookup[edge],
                    )
                    for edge in self._edges
                    for wavelength in self._wavelengths
                    if is_one(artifacts.chi_vars[(key, edge, wavelength)])
                )
                security_lightpaths.append(
                    ActiveLightpath(
                        key=key,
                        layer="security",
                        request_ids=security_request_ids,
                        carried_load=sum(
                            self._requests[request_id].key_rate
                            for request_id in security_request_ids
                        ),
                        physical_assignments=self._order_physical_assignments(
                            assignments,
                            source=key.source,
                            target=key.target,
                        ),
                    )
                )

        total_cost_breakdown = {
            name: float(pulp.value(expression) or 0.0)
            for name, expression in artifacts.cost_expressions.items()
        }
        admitted_count = sum(route.admitted for route in request_routes)
        return SolverSolution(
            status=pulp.LpStatus[artifacts.problem.status],
            admitted_count=int(admitted_count),
            total_requests=len(request_routes),
            phase_one_objective=phase_one_objective,
            phase_two_objective=float(pulp.value(artifacts.problem.objective) or 0.0),
            total_cost_breakdown=total_cost_breakdown,
            request_routes=tuple(request_routes),
            service_lightpaths=tuple(service_lightpaths),
            security_lightpaths=tuple(security_lightpaths),
        )

    def _order_lightpaths(
        self,
        lightpaths: tuple[LightpathKey, ...],
        *,
        source: str,
        target: str,
    ) -> tuple[LightpathKey, ...]:
        if len(lightpaths) <= 1:
            return lightpaths

        outgoing = defaultdict(list)
        for key in lightpaths:
            outgoing[key.source].append(key)

        ordered = []
        used = set()
        current = source
        while current != target:
            candidates = [key for key in outgoing[current] if key not in used]
            if not candidates:
                break
            candidates.sort(key=lambda item: (item.index, item.target))
            selected = candidates[0]
            ordered.append(selected)
            used.add(selected)
            current = selected.target
            if len(ordered) > len(lightpaths):
                break

        for key in lightpaths:
            if key not in used:
                ordered.append(key)
        return tuple(ordered)

    def _order_physical_assignments(
        self,
        assignments: tuple[PhysicalAssignment, ...],
        *,
        source: str,
        target: str,
    ) -> tuple[PhysicalAssignment, ...]:
        if len(assignments) <= 1:
            return assignments

        outgoing = defaultdict(list)
        for assignment in assignments:
            outgoing[assignment.source].append(assignment)

        ordered = []
        used = set()
        current = source
        while current != target:
            candidates = [
                assignment for assignment in outgoing[current] if assignment not in used
            ]
            if not candidates:
                break
            candidates.sort(key=lambda item: (item.wavelength, item.target))
            selected = candidates[0]
            ordered.append(selected)
            used.add(selected)
            current = selected.target
            if len(ordered) > len(assignments):
                break

        for assignment in assignments:
            if assignment not in used:
                ordered.append(assignment)
        return tuple(ordered)
