from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


"""
dataclass 是 Python 3.7+ 内置标准库的装饰器，专门用来创建数据类
frozen=True：让配置不可修改，安全可靠；
slots=True：让配置类省内存、速度快、禁止乱加属性，更严谨。
"""


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    config_path: Path = Path("logconfig.ini")


@dataclass(frozen=True, slots=True)
class TopologyConfig:
    path: Path = Path("topology/SixNode.graphml")


@dataclass(frozen=True, slots=True)
class RequestGenerationConfig:
    count: int = 0
    seed: int = 0
    bandwidth_min: int = 0
    bandwidth_max: int = 0
    key_rate_min: int = 0
    key_rate_max: int = 0
    security_level_min: int = 0
    security_level_max: int = 0


@dataclass(frozen=True, slots=True)
class NetworkResourceConfig:
    wavelengths: int = 0
    bandwidth_max: int = 10
    key_rate_max: int = 10


@dataclass(frozen=True, slots=True)
class SolverConfig:
    solver: str = None
    time_limit_seconds: int | None = None
    solver_message: bool = False


@dataclass(frozen=True, slots=True)
class OutputConfig:
    directory: Path = Path("outputs")
    solution_filename: str = "solution.json"
    report_filename: str = "solution_report.md"
    enable_visualization: bool = True


@dataclass(frozen=True, slots=True)
class PhysicalLink:
    """有向物理光纤链路。

    输入字段：
        source: 起点节点编号。
        target: 终点节点编号。
        distance: 链路距离，通常以 km 为单位。
    """

    source: str
    target: str
    distance: float


@dataclass(frozen=True, slots=True)
class ServiceRequest:
    """ILP 模型中的业务请求。

    输入字段：
        request_id: 业务请求唯一标识。
        source: 源节点。
        target: 宿节点。
        bandwidth: 业务光路承载的带宽需求。
        key_rate: 密钥速率.
        security_level: 安全等级需求，0 表示不需要安全通道; 1 表示共享安全通道; 2 表示专用安全通道。
    """

    request_id: str
    source: str
    target: str
    sequence: int
    bandwidth: float
    key_rate: float
    security_level: int


@dataclass(frozen=True, slots=True)
class CostParameters:
    """目标函数中的成本系数。"""

    wavelength_cost: float = 0.0
    distance_cost: float = 0.0
    key_rate_cost: float = 0.0
    security_port_cost: float = 0.0
    logical_hop_tiebreak: float = 1e-3
    physical_hop_tiebreak: float = 1e-3


# todo to be deleted
@dataclass(frozen=True, slots=True)
class LightpathKey:
    """逻辑光路 ``(m, n, k)`` 的标识。"""

    source: str
    target: str
    index: int

    def label(self) -> str:
        return f"({self.source},{self.target},{self.index})"


# todo to be deleted
@dataclass(frozen=True, slots=True)
class PhysicalAssignment:
    """某条逻辑光路选中的物理链路-波长资源 ``(i, j, w)``。"""

    source: str
    target: str
    wavelength: int
    distance: float


# todo to be deleted
@dataclass(frozen=True, slots=True)
class RequestRouting:
    """单个业务在业务层/安全层上的最终路由结果。"""

    request_id: str
    admitted: bool
    security_enabled: bool
    service_lightpaths: tuple[LightpathKey, ...]
    security_lightpaths: tuple[LightpathKey, ...]


# todo to be deleted
@dataclass(frozen=True, slots=True)
class ActiveLightpath:
    """被激活的逻辑光路及其映射到的物理资源。"""

    key: LightpathKey
    layer: str
    request_ids: tuple[str, ...]
    carried_load: float
    physical_assignments: tuple[PhysicalAssignment, ...]


@dataclass(slots=True)
class SolverSolution:
    """可序列化的 ILP 求解结果对象。

    输出字段：
        status: 求解器终止状态。
        admitted_count: 被接纳的业务请求数量。
        total_requests: 输入业务总数。
        phase_one_objective: 第一阶段目标值。
        phase_two_objective: 第二阶段目标值。
        total_cost_breakdown: 最终目标函数中的各项成本。
        request_routes: 每个请求对应的逻辑层路由结果。
        service_lightpaths/security_lightpaths: 激活的逻辑光路以及它们
            对应的物理 ``(i, j, w)`` 资源分配。
    """

    status: str
    admitted_count: int
    total_requests: int
    phase_one_objective: float | None
    phase_two_objective: float | None
    total_cost_breakdown: dict[str, float]
    request_routes: tuple[RequestRouting, ...]
    service_lightpaths: tuple[ActiveLightpath, ...]
    security_lightpaths: tuple[ActiveLightpath, ...]

    def to_dict(self) -> dict:
        """将嵌套数据类转换成普通字典，便于导出 JSON。"""
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        """把求解结果写入 UTF-8 编码的 JSON 文件。"""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def summary_text(self) -> str:
        """返回简洁的人类可读摘要，供 ``main.py`` 直接打印。"""
        lines = [
            f"status={self.status}",
            f"accepted={self.admitted_count}/{self.total_requests}",
        ]
        if self.phase_one_objective is not None:
            lines.append(f"phase1_max_accept={self.phase_one_objective:.0f}")
        if self.phase_two_objective is not None:
            lines.append(f"phase2_min_cost={self.phase_two_objective:.4f}")
        for name, value in sorted(self.total_cost_breakdown.items()):
            lines.append(f"{name}={value:.4f}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AppConfig:
    logging: LoggingConfig = LoggingConfig()
    topology: TopologyConfig = TopologyConfig()
    request_generation: RequestGenerationConfig = RequestGenerationConfig()
    network_resources: NetworkResourceConfig = NetworkResourceConfig()
    costs: CostParameters = CostParameters()
    solver: SolverConfig = SolverConfig()
    outputs: OutputConfig = OutputConfig()


@dataclass(slots=True)
class NetworkInstance:
    """完整的 ILP 输入实例。

    输入字段：
        nodes: 节点集合 ``V``。
        links: 有向链路集合 ``E``。
        wavelengths: 每条有向物理链路可用的波长数。
        bandwidth_max: 单条业务逻辑光路的带宽容量。
        key_rate_max: 单条安全逻辑光路的密钥容量。
        requests: 业务请求集合。
        costs: 目标函数中的成本系数。
        node_positions: ``networkx`` 可视化时使用的可选节点坐标。
    """

    nodes: tuple[str, ...]
    links: tuple[PhysicalLink, ...]
    wavelengths: int
    bandwidth_max: float
    key_rate_max: float
    requests: tuple[ServiceRequest, ...]
    costs: CostParameters = field(default_factory=CostParameters)
    node_positions: dict[str, tuple[float, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """对象构建完成后立即做输入合法性检查。"""
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("Node identifiers must be unique.")
        if self.wavelengths <= 0:
            raise ValueError("wavelengths must be positive.")
        if self.bandwidth_max <= 0:
            raise ValueError("logical_bandwidth_capacity must be positive.")
        if self.key_rate_max <= 0:
            raise ValueError("logical_key_capacity must be positive.")

        known_nodes = set(self.nodes)
        for link in self.links:
            if link.source not in known_nodes or link.target not in known_nodes:
                raise ValueError(f"Unknown node in link {link}.")
            if link.source == link.target:
                raise ValueError(f"Self-loop link is not allowed: {link}.")
        for request in self.requests:
            if request.source not in known_nodes or request.target not in known_nodes:
                raise ValueError(f"Unknown node in request {request}.")
            if request.source == request.target:
                raise ValueError(f"Request source and target must differ: {request}.")
            if request.bandwidth <= 0:
                raise ValueError(f"Request bandwidth must be positive: {request}.")
            if request.security_level < 0:
                raise ValueError(f"Security level cannot be negative: {request}.")

    @property
    def directed_edges(self) -> tuple[tuple[str, str], ...]:
        """以二元组形式输出边集合，便于作为 PuLP 下标。"""
        return tuple((link.source, link.target) for link in self.links)

    @property
    def distance_lookup(self) -> dict[tuple[str, str], float]:
        """建立 ``(i, j) -> distance`` 的映射，供目标函数和结果导出使用。"""
        return {(link.source, link.target): link.distance for link in self.links}

    # @property
    # def candidate_lightpaths(self) -> tuple[LightpathKey, ...]:
    #     """枚举所有候选逻辑光路 ``(m, n, k)``。"""
    #     return tuple(
    #         LightpathKey(source, target, index)
    #         for source in self.nodes
    #         for target in self.nodes
    #         if source != target
    #         for index in range(self.lightpaths_per_pair)
    #     )

    @property
    def wavelength_indices(self) -> tuple[int, ...]:
        """返回波长下标 ``0..W-1``，用于构造变量。"""
        return tuple(range(self.wavelengths))
