from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from .models import (
    ActiveLightpath,
    LightpathKey,
    NetworkInstance,
    PhysicalAssignment,
    RequestRouting,
    SolverSolution,
)

logger = logging.getLogger(__name__)


def _require_pulp():
    """延迟导入 PuLP，并给出更直接的依赖报错信息。"""
    try:
        import pulp
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PuLP is not installed. Run `python -m pip install -r requirements.txt`."
        ) from exc
    return pulp


@dataclass(slots=True)
class _ModelArtifacts:
    """PuLP 变量和表达式的内部容器。

    这个对象不属于公开 API。它把某一阶段的模型、决策变量和成本表达式
    放在一起，方便 ``solve()`` 统一构建、求解和提取结果。
    """

    problem: object
    mu: dict[str, object]
    gamma: dict[str, object]
    lambda_vars: dict[tuple[str, LightpathKey], object]
    kappa_vars: dict[tuple[str, LightpathKey], object]
    service_active: dict[LightpathKey, object]
    security_active: dict[LightpathKey, object]
    iota_vars: dict[tuple[LightpathKey, tuple[str, str], int], object]
    chi_vars: dict[tuple[LightpathKey, tuple[str, str], int], object]
    cost_expressions: dict[str, object]


class SecureOpticalILPSolver:
    """构建并求解安全感知光网络 ILP 模型。

    输入：
        instance: 已经完成校验的 ``NetworkInstance``。
        time_limit_seconds: CBC 求解器的可选时间限制。
        solver_message: 是否输出 CBC 原始求解日志。

    输出：
        ``SolverSolution``，其中包含被接纳的业务、激活的逻辑光路以及
        物理链路-波长资源分配结果。
    """

    def __init__(
        self,
        instance: NetworkInstance,
        *,
        time_limit_seconds: int | None = None,
        solver_message: bool = False,
    ) -> None:
        self.instance = instance
        self.time_limit_seconds = time_limit_seconds
        self.solver_message = solver_message

        self._requests_by_id = {
            request.request_id: request for request in self.instance.requests
        }
        self._request_ids = tuple(self._requests_by_id)
        self._lightpaths = self.instance.candidate_lightpaths
        self._edges = self.instance.directed_edges
        self._wavelengths = self.instance.wavelength_indices

        self._out_edges = defaultdict(list)
        self._in_edges = defaultdict(list)
        for edge in self._edges:
            self._out_edges[edge[0]].append(edge)
            self._in_edges[edge[1]].append(edge)

    def solve(self) -> SolverSolution:
        """分两阶段求解模型。

        第一阶段最大化被接纳的业务数，因为原始目标里含有 ``1 / sum(mu)``这样的非线性项。
        第二阶段固定第一阶段得到的接纳数，再最小化线性化后的成本。
        """
        pulp = _require_pulp()
        logger.info(
            "Starting ILP solve: requests=%s, candidate_lightpaths=%s, edges=%s, wavelengths=%s",
            len(self._request_ids),
            len(self._lightpaths),
            len(self._edges),
            len(self._wavelengths),
        )

        phase_one = self._build_model(maximize_admitted=True)
        logger.info("Phase 1 model built, maximizing admitted requests")
        self._solve_problem(phase_one.problem, pulp)
        phase_one_status = pulp.LpStatus[phase_one.problem.status]
        logger.info("Phase 1 solve finished with status=%s", phase_one_status)
        if phase_one_status != "Optimal":
            raise RuntimeError(f"Phase 1 did not solve optimally: {phase_one_status}")

        admitted_target = int(round(pulp.value(pulp.lpSum(phase_one.mu.values())) or 0))
        phase_one_objective = float(pulp.value(phase_one.problem.objective) or 0.0)
        logger.info(
            "Phase 1 accepted %s requests with objective %.4f",
            admitted_target,
            phase_one_objective,
        )

        phase_two = self._build_model(
            maximize_admitted=False,
            fixed_admitted_requests=admitted_target,
        )
        logger.info(
            "Phase 2 model built, minimizing cost with admitted_target=%s",
            admitted_target,
        )
        self._solve_problem(phase_two.problem, pulp)
        phase_two_status = pulp.LpStatus[phase_two.problem.status]
        logger.info("Phase 2 solve finished with status=%s", phase_two_status)
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
        """为某个求解阶段创建一个 PuLP 模型。

        输入：
            maximize_admitted: 第一阶段取 ``True``，第二阶段取 ``False``。
            fixed_admitted_requests: 第二阶段固定的接纳请求数。

        输出：
            ``_ModelArtifacts``，其中包含 PuLP 模型和全部决策变量。
        """
        pulp = _require_pulp()

        sense = pulp.LpMaximize if maximize_admitted else pulp.LpMinimize
        problem = pulp.LpProblem("secure_optical_network_ilp", sense)

        # Variables
        # 1. whether $R^{sd,l}$ is successfully routed.
        mu = {
            request_id: pulp.LpVariable(f"mu_{request_id}", cat="Binary")
            for request_id in self._request_ids
        }
        # 2. whether $R^{sd,l}$ is provisioned.
        gamma = {
            request_id: pulp.LpVariable(f"gamma_{request_id}", cat="Binary")
            for request_id in self._request_ids
        }
        service_active = {
            key: pulp.LpVariable(
                f"service_lp_{key.source}_{key.target}_{key.index}",
                cat="Binary",
            )
            for key in self._lightpaths
        }
        security_active = {
            key: pulp.LpVariable(
                f"security_lp_{key.source}_{key.target}_{key.index}",
                cat="Binary",
            )
            for key in self._lightpaths
        }
        # 3. $R^{sd,l}$ passed through the $k^{th}$ lightpath from $m$ to $n$.
        lambda_vars = {
            (request_id, key): pulp.LpVariable(
                f"lambda_{request_id}_{key.source}_{key.target}_{key.index}",
                cat="Binary",
            )
            for request_id in self._request_ids
            for key in self._lightpaths
        }
        # 4. the usage of the secret channel of the $R^{sd,l}$
        kappa_vars = {
            (request_id, key): pulp.LpVariable(
                f"kappa_{request_id}_{key.source}_{key.target}_{key.index}",
                cat="Binary",
            )
            for request_id in self._request_ids
            for key in self._lightpaths
        }
        # 5. the lightpath use the link $e_{ij}$ with the usage of the wavelength $w$.
        iota_vars = {
            (key, edge, wavelength): pulp.LpVariable(
                f"iota_{key.source}_{key.target}_{key.index}_{edge[0]}_{edge[1]}_{wavelength}",
                cat="Binary",
            )
            for key in self._lightpaths
            for edge in self._edges
            for wavelength in self._wavelengths
        }
        # 6. whether the secret channel deployed in the $e_{ij,w}$
        chi_vars = {
            (key, edge, wavelength): pulp.LpVariable(
                f"chi_{key.source}_{key.target}_{key.index}_{edge[0]}_{edge[1]}_{wavelength}",
                cat="Binary",
            )
            for key in self._lightpaths
            for edge in self._edges
            for wavelength in self._wavelengths
        }

        request_count = max(1, len(self._request_ids))

        # Constraints
        for request_id in self._request_ids:
            request = self._requests_by_id[request_id]
            security_required = 1 if request.security_level > 0 else 0

            problem += gamma[request_id] == security_required * mu[request_id]

            self._add_logical_flow_constraints(
                problem=problem,
                demand_variable=mu[request_id],
                request_id=request_id,
                source=request.source,
                target=request.target,
                layer_vars=lambda_vars,
                pulp=pulp,
            )
            self._add_logical_flow_constraints(
                problem=problem,
                demand_variable=gamma[request_id],
                request_id=request_id,
                source=request.source,
                target=request.target,
                layer_vars=kappa_vars,
                pulp=pulp,
            )

            for key in self._lightpaths:
                problem += lambda_vars[(request_id, key)] <= mu[request_id]
                problem += lambda_vars[(request_id, key)] <= service_active[key]
                problem += kappa_vars[(request_id, key)] <= gamma[request_id]
                problem += kappa_vars[(request_id, key)] <= security_active[key]

        for key in self._lightpaths:
            service_usage = pulp.lpSum(
                lambda_vars[(request_id, key)] for request_id in self._request_ids
            )
            security_usage = pulp.lpSum(
                kappa_vars[(request_id, key)] for request_id in self._request_ids
            )

            problem += service_usage <= request_count * service_active[key]
            problem += security_usage <= request_count * security_active[key]
            problem += service_active[key] <= service_usage
            problem += security_active[key] <= security_usage
            # 业务光路和安全光路不能共享同一个逻辑槽位 ``(m,n,k)``。
            problem += service_active[key] + security_active[key] <= 1

            problem += (
                pulp.lpSum(
                    self._requests_by_id[request_id].bandwidth
                    * lambda_vars[(request_id, key)]
                    for request_id in self._request_ids
                )
                <= self.instance.logical_bandwidth_capacity
            )
            problem += (
                pulp.lpSum(
                    self._requests_by_id[request_id].security_level
                    * kappa_vars[(request_id, key)]
                    for request_id in self._request_ids
                )
                <= self.instance.logical_key_capacity
            )

            self._add_physical_flow_constraints(
                problem=problem,
                key=key,
                active_var=service_active[key],
                edge_vars=iota_vars,
                pulp=pulp,
            )
            self._add_physical_flow_constraints(
                problem=problem,
                key=key,
                active_var=security_active[key],
                edge_vars=chi_vars,
                pulp=pulp,
            )

            for edge in self._edges:
                for wavelength in self._wavelengths:
                    problem += iota_vars[(key, edge, wavelength)] <= service_active[key]
                    problem += chi_vars[(key, edge, wavelength)] <= security_active[key]

        for edge in self._edges:
            for wavelength in self._wavelengths:
                problem += (
                    pulp.lpSum(
                        iota_vars[(key, edge, wavelength)] for key in self._lightpaths
                    )
                    + pulp.lpSum(
                        chi_vars[(key, edge, wavelength)] for key in self._lightpaths
                    )
                    <= 1
                )

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
            self._requests_by_id[request_id].security_level * gamma[request_id]
            for request_id in self._request_ids
        )
        security_port_cost = (
            2
            * self.instance.costs.security_port_cost
            * pulp.lpSum(security_active.values())
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
            # 很小的打破平局项用于抑制等价环路解，让导出的路径更易读。
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
        demand_variable,
        request_id: str,
        source: str,
        target: str,
        layer_vars: dict[tuple[str, LightpathKey], object],
        pulp,
    ) -> None:
        """为逻辑光路层添加请求级流守恒约束。

        输入：
            demand_variable: 业务层对应 ``mu``，安全层对应 ``gamma``。
            layer_vars: 以 ``(request_id, mnk)`` 为下标的 ``lambda`` 或 ``kappa``。

        输出：
            无。约束会直接追加到 PuLP 模型中。
        """
        outgoing_source = pulp.lpSum(
            layer_vars[(request_id, key)]
            for key in self._lightpaths
            if key.source == source
        )
        incoming_target = pulp.lpSum(
            layer_vars[(request_id, key)]
            for key in self._lightpaths
            if key.target == target
        )
        incoming_source = pulp.lpSum(
            layer_vars[(request_id, key)]
            for key in self._lightpaths
            if key.target == source
        )
        outgoing_target = pulp.lpSum(
            layer_vars[(request_id, key)]
            for key in self._lightpaths
            if key.source == target
        )

        problem += outgoing_source == demand_variable
        problem += incoming_target == demand_variable
        problem += incoming_source == 0
        problem += outgoing_target == 0

        for node in self.instance.nodes:
            if node in {source, target}:
                continue
            incoming = pulp.lpSum(
                layer_vars[(request_id, key)]
                for key in self._lightpaths
                if key.target == node
            )
            outgoing = pulp.lpSum(
                layer_vars[(request_id, key)]
                for key in self._lightpaths
                if key.source == node
            )
            problem += incoming == outgoing

    def _add_physical_flow_constraints(
        self,
        *,
        problem,
        key: LightpathKey,
        active_var,
        edge_vars: dict[tuple[LightpathKey, tuple[str, str], int], object],
        pulp,
    ) -> None:
        """把一条逻辑光路映射到物理 ``(i, j, w)`` 路径上。

        输入：
            key: 逻辑光路 ``(m,n,k)``。
            active_var: 该逻辑光路的激活二元变量。
            edge_vars: 以 ``(mnk, ij, w)`` 为下标的 ``iota`` 或 ``chi``。
        """
        outgoing_source = pulp.lpSum(
            edge_vars[(key, edge, wavelength)]
            for edge in self._out_edges[key.source]
            for wavelength in self._wavelengths
        )
        incoming_target = pulp.lpSum(
            edge_vars[(key, edge, wavelength)]
            for edge in self._in_edges[key.target]
            for wavelength in self._wavelengths
        )
        incoming_source = pulp.lpSum(
            edge_vars[(key, edge, wavelength)]
            for edge in self._in_edges[key.source]
            for wavelength in self._wavelengths
        )
        outgoing_target = pulp.lpSum(
            edge_vars[(key, edge, wavelength)]
            for edge in self._out_edges[key.target]
            for wavelength in self._wavelengths
        )

        problem += outgoing_source == active_var
        problem += incoming_target == active_var
        problem += incoming_source == 0
        problem += outgoing_target == 0

        for node in self.instance.nodes:
            if node in {key.source, key.target}:
                continue
            incoming = pulp.lpSum(
                edge_vars[(key, edge, wavelength)]
                for edge in self._in_edges[node]
                for wavelength in self._wavelengths
            )
            outgoing = pulp.lpSum(
                edge_vars[(key, edge, wavelength)]
                for edge in self._out_edges[node]
                for wavelength in self._wavelengths
            )
            problem += incoming == outgoing

    def _solve_problem(self, problem, pulp) -> None:
        """优先使用 CBC 运行 PuLP，否则退回默认求解器。"""
        solver = None
        if hasattr(pulp, "PULP_CBC_CMD"):
            solver = pulp.PULP_CBC_CMD(
                msg=self.solver_message,
                timeLimit=self.time_limit_seconds,
            )
        if solver is None:
            problem.solve()
            return
        problem.solve(solver)

    def _extract_solution(
        self,
        *,
        artifacts: _ModelArtifacts,
        pulp,
        phase_one_objective: float,
    ) -> SolverSolution:
        """把求解后的 PuLP 变量转换为可序列化的 Python 对象。"""
        def is_one(variable) -> bool:
            return (pulp.value(variable) or 0.0) > 0.5

        request_routes = []
        for request_id in self._request_ids:
            raw_service_lightpaths = tuple(
                key
                for key in self._lightpaths
                if is_one(artifacts.lambda_vars[(request_id, key)])
            )
            raw_security_lightpaths = tuple(
                key
                for key in self._lightpaths
                if is_one(artifacts.kappa_vars[(request_id, key)])
            )
            request = self._requests_by_id[request_id]
            request_routes.append(
                RequestRouting(
                    request_id=request_id,
                    admitted=is_one(artifacts.mu[request_id]),
                    security_enabled=is_one(artifacts.gamma[request_id]),
                    service_lightpaths=self._order_lightpaths(
                        raw_service_lightpaths,
                        source=request.source,
                        target=request.target,
                    ),
                    security_lightpaths=self._order_lightpaths(
                        raw_security_lightpaths,
                        source=request.source,
                        target=request.target,
                    ),
                )
            )

        service_lightpaths = []
        security_lightpaths = []
        for key in self._lightpaths:
            if is_one(artifacts.service_active[key]):
                request_ids = tuple(
                    request_id
                    for request_id in self._request_ids
                    if is_one(artifacts.lambda_vars[(request_id, key)])
                )
                carried_load = sum(
                    self._requests_by_id[request_id].bandwidth for request_id in request_ids
                )
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
                        request_ids=request_ids,
                        carried_load=carried_load,
                        physical_assignments=self._order_physical_assignments(
                            assignments,
                            source=key.source,
                            target=key.target,
                        ),
                    )
                )

            if is_one(artifacts.security_active[key]):
                request_ids = tuple(
                    request_id
                    for request_id in self._request_ids
                    if is_one(artifacts.kappa_vars[(request_id, key)])
                )
                carried_load = sum(
                    self._requests_by_id[request_id].security_level
                    for request_id in request_ids
                )
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
                        request_ids=request_ids,
                        carried_load=carried_load,
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
        """把选中的逻辑边排序成从源到宿的可读路径。"""
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
            candidates.sort(key=lambda key: (key.index, key.target))
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
        """把 ``(i,j,w)`` 分配结果按物理路径顺序排列，便于输出。"""
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
