from __future__ import annotations

import logging
import math
import random
from pathlib import Path

from .models import CostParameters, NetworkInstance, PhysicalLink, ServiceRequest

logger = logging.getLogger(__name__)


def _require_networkx():
    """延迟导入 NetworkX，让依赖报错更贴近实际调用位置。"""
    try:
        import networkx as nx
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "NetworkX is not installed. Run `python -m pip install -r requirements.txt`."
        ) from exc
    return nx


def load_topology_graphml(path: str | Path):
    """读取拓扑文件并构建 ``networkx`` 图 ``G(V, E)``。

    输入：
        path: ``topology`` 文件夹下的 GraphML 文件路径。

    输出：
        保留节点和边属性的 ``networkx.Graph`` 或 ``networkx.DiGraph``。
    """
    nx = _require_networkx()
    graph_path = Path(path)
    if not graph_path.exists():
        raise FileNotFoundError(f"Topology file not found: {graph_path}")

    logger.info("Reading GraphML topology from %s", graph_path)
    graph = nx.read_graphml(graph_path)
    if graph.is_directed():
        topology = nx.DiGraph()
        topology.add_nodes_from(graph.nodes(data=True))
        topology.add_edges_from(graph.edges(data=True))
    else:
        topology = nx.Graph()
        topology.add_nodes_from(graph.nodes(data=True))
        topology.add_edges_from(graph.edges(data=True))
    logger.info(
        "Loaded topology graph: directed=%s, |V|=%s, |E|=%s",
        topology.is_directed(),
        topology.number_of_nodes(),
        topology.number_of_edges(),
    )
    return topology


def build_instance_from_graph(
    graph,
    *,
    requests: tuple[ServiceRequest, ...],
    wavelengths: int,
    lightpaths_per_pair: int,
    logical_bandwidth_capacity: float,
    logical_key_capacity: float,
    costs: CostParameters | None = None,
) -> NetworkInstance:
    """将 ``networkx`` 拓扑转换为 ILP 的输入实例。

    输入：
        graph: 由 NetworkX 构建的拓扑 ``G(V,E)``。
        requests: 由 ``ServiceRequest`` 定义的业务请求集合。
        wavelengths/lightpaths_per_pair/logical_*: ILP 资源参数。
        costs: 目标函数成本系数。

    输出：
        供 ``SecureOpticalILPSolver`` 使用的 ``NetworkInstance``。
    """
    nodes = tuple(str(node) for node in graph.nodes)
    links = tuple(_graph_to_links(graph))
    node_positions = {
        str(node): _extract_position(attributes)
        for node, attributes in graph.nodes(data=True)
        if _extract_position(attributes) is not None
    }
    logger.info(
        "Converting graph to NetworkInstance: nodes=%s, directed_links=%s, positioned_nodes=%s",
        len(nodes),
        len(links),
        len(node_positions),
    )

    return NetworkInstance(
        nodes=nodes,
        links=links,
        wavelengths=wavelengths,
        lightpaths_per_pair=lightpaths_per_pair,
        logical_bandwidth_capacity=logical_bandwidth_capacity,
        logical_key_capacity=logical_key_capacity,
        requests=requests,
        costs=costs or CostParameters(),
        node_positions=node_positions,
    )


def build_demo_requests_from_graph(
    graph,
    request_count: int = 4,
    *,
    seed: int = 42,
) -> tuple[ServiceRequest, ...]:
    """根据拓扑自动生成一组示例业务请求。

    输入：
        graph: NetworkX 拓扑图。

    输出：
        ``ServiceRequest`` 对象元组。

    说明：
        这里只是为了演示和测试而自动生成请求。后续如果改成从独立
        流量文件读取业务，只需要替换这个函数，不需要改求解器。
    """
    if request_count <= 0:
        raise ValueError("request_count 必须为正整数。")

    nodes = [str(node) for node in graph.nodes]
    if len(nodes) < 2:
        raise ValueError("Topology must contain at least two nodes.")

    candidate_pairs = [
        (source, target)
        for source in nodes
        for target in nodes
        if source != target
    ]
    rng = random.Random(seed)

    requests = []
    for index in range(1, request_count + 1):
        source, target = rng.choice(candidate_pairs)
        request = ServiceRequest(
                request_id=f"r{index}",
                source=source,
                target=target,
                bandwidth=rng.randint(1, 4),
                security_level=rng.randint(0, 3),
        )
        requests.append(request)
        logger.info(request)
    logger.info(
        "Built %s uniformly distributed demo requests from topology with seed=%s",
        len(requests),
        seed,
    )
    return tuple(requests)


def _graph_to_links(graph):
    """从 NetworkX 图中生成有向 ``PhysicalLink`` 对象。

    对于无向 GraphML 拓扑，会把每条物理边扩展成两条有向链路，
    因为 ILP 中的边是按有序对 ``(i, j)`` 建模的。
    """
    for source, target, attributes in graph.edges(data=True):
        source_id = str(source)
        target_id = str(target)
        distance = _extract_distance(graph, source, target, attributes)
        yield PhysicalLink(source_id, target_id, distance)
        if not graph.is_directed():
            yield PhysicalLink(target_id, source_id, distance)


def _extract_distance(graph, source, target, attributes: dict) -> float:
    """返回一条边的物理距离。

    优先级：
        1. 边属性中的显式字段，例如 ``distance`` 或 ``weight``
        2. 根据节点经纬度估算的大圆距离
        3. 回退值 ``1.0``
    """
    for field_name in ("distance", "Distance", "length", "Length", "weight"):
        value = attributes.get(field_name)
        numeric = _safe_float(value)
        if numeric is not None and numeric > 0:
            return numeric

    source_position = _extract_position(graph.nodes[source])
    target_position = _extract_position(graph.nodes[target])
    if source_position is not None and target_position is not None:
        lon1, lat1 = source_position
        lon2, lat2 = target_position
        return max(_haversine_km(lon1, lat1, lon2, lat2), 1.0)

    return 1.0


def _extract_position(attributes: dict) -> tuple[float, float] | None:
    """读取节点坐标 ``(longitude, latitude)``，供绘图使用。"""
    longitude = _safe_float(attributes.get("Longitude"))
    latitude = _safe_float(attributes.get("Latitude"))
    if longitude is None or latitude is None:
        return None
    return (longitude, latitude)


def _safe_float(value) -> float | None:
    """安全地把 GraphML 属性值转换成浮点数。"""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """计算以千米为单位的大圆距离。

    这个公式不像欧氏距离那样常见，但当 GraphML 节点保存的是地理经纬度时，
    用它来估算链路长度更合适。
    """
    earth_radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c
