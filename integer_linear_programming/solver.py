from __future__ import annotations

import logging
import numpy as np
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
    # service_active: dict[LightpathKey, object]
    # security_active: dict[LightpathKey, object]
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
        solver: str | None = None,
        time_limit_seconds: int | None = None,
        solver_message: bool = False,
    ) -> None:
        self.instance = instance
        self.time_limit_seconds = time_limit_seconds
        self.solver_message = solver_message

        self._requests = {
            request.request_id: request for request in self.instance.requests
        }
        self._request_ids = tuple(self._requests)
        self._lightpaths = 0
        self._max_lps = 8
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
        logger.info(f"{"=" * 20} Start Solving ILP {"=" * 20}")
        logger.info(f"Available solvers: {pulp.listSolvers(onlyAvailable=True)}")

        phase_one = self._build_model(maximize_admitted=True)
        logger.info("Phase 1 model built, maximizing admitted requests")
        self._solve_problem(phase_one.problem, pulp)
        # phase_one_status = pulp.LpStatus[phase_one.problem.status]
        # logger.info("Phase 1 solve finished with status=%s", phase_one_status)
        # if phase_one_status != "Optimal":
        #     raise RuntimeError(f"Phase 1 did not solve optimally: {phase_one_status}")
        #
        # admitted_target = int(round(pulp.value(pulp.lpSum(phase_one.mu.values())) or 0))
        # phase_one_objective = float(pulp.value(phase_one.problem.objective) or 0.0)
        # logger.info(
        #     "Phase 1 accepted %s requests with objective %.4f",
        #     admitted_target,
        #     phase_one_objective,
        # )
        #
        # phase_two = self._build_model(
        #     maximize_admitted=False,
        #     fixed_admitted_requests=admitted_target,
        # )
        # logger.info(
        #     "Phase 2 model built, minimizing cost with admitted_target=%s",
        #     admitted_target,
        # )
        # self._solve_problem(phase_two.problem, pulp)
        # phase_two_status = pulp.LpStatus[phase_two.problem.status]
        # logger.info("Phase 2 solve finished with status=%s", phase_two_status)
        # if phase_two_status != "Optimal":
        #     raise RuntimeError(f"Phase 2 did not solve optimally: {phase_two_status}")
        #
        # solution = self._extract_solution(
        #     artifacts=phase_two,
        #     pulp=pulp,
        #     phase_one_objective=phase_one_objective,
        # )
        # logger.info(
        #     "Solution extracted: admitted=%s/%s, phase2_objective=%.4f",
        #     solution.admitted_count,
        #     solution.total_requests,
        #     solution.phase_two_objective or 0.0,
        # )
        # return solution

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
        # 1. data transmission channel
        mu = pulp.LpVariable.dicts(
            "mu",
            [
                (req.source, req.target, req.sequence)
                for req in self._requests.values()
            ],
            cat='Binary'
        )

        lambda_ = pulp.LpVariable.dicts(
            "lambda",
            [
                (req.source, req.target, req.sequence, m, n, k)
                for req in self._requests.values()
                for m in self.instance.nodes
                for n in self.instance.nodes
                for k in range(self._max_lps * self.instance.wavelengths)
            ],
            cat='Binary'
        )

        iota = pulp.LpVariable.dicts(
            "iota",
            [
                (m, n, k, i, j, w)
                for m in self.instance.nodes
                for n in self.instance.nodes
                for k in range(self._max_lps * self.instance.wavelengths)
                for i in self.instance.nodes
                for j in self.instance.nodes
                for w in range(self.instance.wavelengths)
            ],
            cat='Binary'
        )

        # 2. security channel
        gamma = pulp.LpVariable.dicts(
            "gamma",
            [
                (req.source, req.target, req.sequence)
                for req in self._requests.values()
            ],
            cat='Binary'
        )

        kappa = pulp.LpVariable.dicts(
            "kappa",
            [
                (req.source, req.target, req.sequence, m, n, k)
                for req in self._requests.values()
                for m in self.instance.nodes
                for n in self.instance.nodes
                for k in range(self._max_lps * self.instance.wavelengths)
            ],
            cat='Binary'
        )

        chi = pulp.LpVariable.dicts(
            "chi",
            [
                (m, n, k, i, j, w)
                for m in self.instance.nodes
                for n in self.instance.nodes
                for k in range(self._max_lps * self.instance.wavelengths)
                for i in self.instance.nodes
                for j in self.instance.nodes
                for w in range(self.instance.wavelengths)
            ],
            cat='Binary'
        )

        # 3.

        request_count = max(1, len(self._request_ids))

        # Objective
        # if maximize_admitted:
        problem += pulp.lpSum(mu[(req.source, req.target, req.sequence)] for req in self._requests.values()), "Objective"
        # else:
        #     # 很小的打破平局项用于抑制等价环路解，让导出的路径更易读。
        #     problem += (
        #         security_wavelength_cost
        #         # + security_distance_cost
        #         # + key_rate_cost
        #         # + security_port_cost
        #         # + logical_hop_tiebreak
        #         # + physical_hop_tiebreak
        #     )

        # Constraints
        # 1. connection
        for req in self._requests.values():
            problem += (
                pulp.lpSum(
                    lambda_[(req.source, req.target, req.sequence, req.source, n, k)]
                    for n in self.instance.nodes
                    for k in range(self._max_lps * self.instance.wavelengths)
                ) == mu[(req.source, req.target, req.sequence)]
            )

            problem += (
                pulp.lpSum(
                    lambda_[(req.source, req.target, req.sequence, m, req.source, k)]
                    for m in self.instance.nodes
                    for k in range(self._max_lps * self.instance.wavelengths)
                ) == mu[(req.source, req.target, req.sequence)]
            )

            problem += (
                pulp.lpSum(
                    lambda_[(req.source, req.target, req.sequence, m, req.source, k)]
                    for m in self.instance.nodes
                    for k in range(self._max_lps * self.instance.wavelengths)
                ) == 0
            )

            problem += (
                pulp.lpSum(
                    lambda_[(req.source, req.target, req.sequence, req.target, n, k)]
                    for n in self.instance.nodes
                    for k in range(self._max_lps * self.instance.wavelengths)
                ) == 0
            )

            for u in self.instance.nodes:
                problem += (
                    pulp.lpSum(
                        lambda_[(req.source, req.target, req.sequence, m, u, k)]
                        for m in self.instance.nodes
                        for k in range(self._max_lps * self.instance.wavelengths)
                    ) == pulp.lpSum(
                        lambda_[(req.source, req.target, req.sequence, u, n, k)]
                        for n in self.instance.nodes
                        for k in range(self._max_lps * self.instance.wavelengths)
                    )
                )

        for m in self.instance.nodes:
            for n in self.instance.nodes:
                for k in range(self._max_lps * self.instance.wavelengths):
                    problem += (
                        pulp.lpSum(
                            lambda_[(req.source, req.target, req.sequence, m, n, k)] * req.bandwidth
                            for req in self._requests.values()
                        ) <= self.instance.bandwidth_max
                    )

                    problem += (
                        pulp.lpSum(
                            lambda_[(req.source, req.target, req.sequence, m, n, k)] + kappa[(req.source, req.target, req.sequence, m, n, k)]
                            for req in self._requests.values()
                        ) <= 1
                    )

        # 2. security
        # for req in self._requests.values():
        #     problem += (
        #         gamma[(req.source, req.target, req.sequence)] ==
        #         mu[(req.source, req.target, req.sequence)] * self._custom_calculation(req.security_level)
        #     )
        #
        #     problem += (
        #         pulp.lpSum(
        #             kappa[(req.source, req.target, req.sequence, req.source, n, k)]
        #             for n in self.instance.nodes
        #             for k in range(self._max_lps * self.instance.wavelengths)
        #         ) == gamma[(req.source, req.target, req.sequence)]
        #     )
        #
        #     problem += (
        #         pulp.lpSum(
        #             kappa[(req.source, req.target, req.sequence, m, req.source, k)]
        #             for m in self.instance.nodes
        #             for k in range(self._max_lps * self.instance.wavelengths)
        #         ) == gamma[(req.source, req.target, req.sequence)]
        #     )
        #
        #     problem += (
        #         pulp.lpSum(
        #             kappa[(req.source, req.target, req.sequence, m, req.source, k)]
        #             for m in self.instance.nodes
        #             for k in range(self._max_lps * self.instance.wavelengths)
        #         ) == 0
        #     )
        #
        #     problem += (
        #         pulp.lpSum(
        #             kappa[(req.source, req.target, req.sequence, req.target, n, k)]
        #             for n in self.instance.nodes
        #             for k in range(self._max_lps * self.instance.wavelengths)
        #         ) == 0
        #     )
        #
        #     for u in self.instance.nodes:
        #         problem += (
        #             pulp.lpSum(
        #                 kappa[(req.source, req.target, req.sequence, m, u, k)]
        #                 for m in self.instance.nodes
        #                 for k in range(self._max_lps * self.instance.wavelengths)
        #             ) == pulp.lpSum(
        #                 kappa[(req.source, req.target, req.sequence, u, n, k)]
        #                 for n in self.instance.nodes
        #                 for k in range(self._max_lps * self.instance.wavelengths)
        #             )
        #         )
        #
        #     for m in self.instance.nodes:
        #         for n in self.instance.nodes:
        #             problem += (
        #                 pulp.lpSum(
        #                     lambda_[(req.source, req.target, req.sequence, m, n, k)]
        #                     for k in range(self._max_lps * self.instance.wavelengths)
        #                 ) == pulp.lpSum(
        #                     kappa[(req.source, req.target, req.sequence, m, n, k)]
        #                     for k in range(self._max_lps * self.instance.wavelengths)
        #                 )
        #             )
        #
        # for m in self.instance.nodes:
        #     for n in self.instance.nodes:
        #         for k in range(self._max_lps * self.instance.wavelengths):
        #             problem += (
        #                     pulp.lpSum(
        #                         kappa[(req.source, req.target, req.sequence, m, n, k)] * req.key_rate
        #                         for req in self._requests.values()
        #                     ) <= self.instance.key_rate_max
        #             )



        if fixed_admitted_requests is not None:
            problem += (
                pulp.lpSum(mu[request_id] for request_id in self._request_ids)
                == fixed_admitted_requests
            )

        security_wavelength_cost = self.instance.costs.wavelength_cost * pulp.lpSum(
            chi.values()
        )
        # security_distance_cost = self.instance.costs.distance_cost * pulp.lpSum(
        #     self.instance.distance_lookup[edge] * chi[(key, edge, wavelength)]
        #     for key in self._lightpaths
        #     for edge in self._edges
        #     for wavelength in self._wavelengths
        # )
        # key_rate_cost = self.instance.costs.key_rate_cost * pulp.lpSum(
        #     self._requests[request_id].security_level * gamma[request_id]
        #     for request_id in self._request_ids
        # )
        # security_port_cost = (
        #     2
        #     * self.instance.costs.security_port_cost
        #     * pulp.lpSum(security_active.values())
        # )
        # logical_hop_tiebreak = self.instance.costs.logical_hop_tiebreak * (
        #     pulp.lpSum(lambda_.values()) + pulp.lpSum(kappa.values())
        # )
        # physical_hop_tiebreak = self.instance.costs.physical_hop_tiebreak * (
        #     pulp.lpSum(iota.values()) + pulp.lpSum(chi.values())
        # )



        return _ModelArtifacts(
            problem=problem,
            mu=mu,
            gamma=gamma,
            lambda_vars=lambda_,
            kappa_vars=kappa,
            # service_active=service_active,
            # security_active=security_active,
            iota_vars=iota,
            chi_vars=chi,
            cost_expressions={
                "security_wavelength_cost": security_wavelength_cost,
                # "security_distance_cost": security_distance_cost,
                # "key_rate_cost": key_rate_cost,
                # "security_port_cost": security_port_cost,
                # "logical_hop_tiebreak": logical_hop_tiebreak,
                # "physical_hop_tiebreak": physical_hop_tiebreak,
            },
        )

    def _solve_problem(self, problem, pulp, *, solver: str = "") -> None:
        """优先使用 CBC 运行 PuLP，否则退回默认求解器。"""
        if hasattr(pulp, solver):
            solver = getattr(pulp, solver)(
                msg=self.solver_message,
                timeLimit=self.time_limit_seconds,
            )
        else:
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
            request = self._requests[request_id]
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
                    self._requests[request_id].bandwidth for request_id in request_ids
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
                    self._requests[request_id].security_level
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

    def _custom_calculation(self, x):
        infinity = 1e5
        return np.ceil(x / infinity)
