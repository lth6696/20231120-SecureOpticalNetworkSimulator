from __future__ import annotations

import argparse
import logging
from pathlib import Path

from secure_optical_ilp import (
    CostParameters,
    SecureOpticalILPSolver,
    build_demo_requests_from_graph,
    build_instance_from_graph,
    load_topology_graphml,
    setup_logging,
    visualize_solution,
)

logger = logging.getLogger(__name__)


def build_instance_from_topology(
    topology_path: Path,
    request_count: int,
    *,
    seed: int,
):
    """读取拓扑文件并转换成 ILP 输入实例。

    输入：
        topology_path: GraphML 拓扑文件路径。

    输出：
        二元组 (graph, instance):
        - graph 是 NetworkX 拓扑 G(V,E)
        - instance 是转换后的 ILP 输入对象
    """
    logger.info("Loading topology from %s", topology_path)
    graph = load_topology_graphml(topology_path)
    requests = build_demo_requests_from_graph(
        graph,
        request_count=request_count,
        seed=seed,
    )
    logger.info(
        "Generated %s uniformly distributed demo requests from topology graph with |V|=%s, |E|=%s",
        len(requests),
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )
    costs = CostParameters(
        wavelength_cost=2.0,
        distance_cost=0.03,
        key_rate_cost=1.2,
        security_port_cost=3.0,
        logical_hop_tiebreak=1e-3,
        physical_hop_tiebreak=1e-3,
    )

    instance = build_instance_from_graph(
        graph,
        requests=requests,
        wavelengths=2,
        lightpaths_per_pair=2,
        logical_bandwidth_capacity=10,
        logical_key_capacity=6,
        costs=costs,
    )
    logger.info(
        "Built NetworkInstance with %s directed links and %s requests",
        len(instance.links),
        len(instance.requests),
    )
    return graph, instance


def parse_args() -> argparse.Namespace:
    """解析命令行参数。

    输出：
        至少包含 ``topology`` 字段的 ``Namespace`` 对象。
    """
    parser = argparse.ArgumentParser(
        description="Solve the secure optical network ILP from a topology file."
    )
    # 添加命令行参数（核心步骤）
    parser.add_argument(
        "--topology",
        default="topology/SixNode.graphml",
        help="GraphML topology file under the topology folder.",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=4,
        help="生成的业务数量 N。",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子，用于复现均匀分布业务。",
    )
    return parser.parse_args()


def print_solution(solution) -> None:
    """将最终求解结果的简要摘要打印到标准输出。"""
    print(solution.summary_text())
    print()
    for route in solution.request_routes:
        service_path = [lightpath.label() for lightpath in route.service_lightpaths]
        security_path = [lightpath.label() for lightpath in route.security_lightpaths]
        print(
            f"{route.request_id}: admitted={route.admitted}, "
            f"security={route.security_enabled}, "
            f"lambda={service_path}, kappa={security_path}"
        )


def main() -> None:
    """程序入口函数。

    流程：
        1. 从 ``logconfig.ini`` 初始化日志
        2. 读取 GraphML 拓扑并构建 ``G(V,E)``
        3. 将图转换为 ILP 输入数据
        4. 执行模型求解
        5. 导出 JSON 和 PNG 结果
    """
    config_path = setup_logging()
    args = parse_args()
    topology_path = Path(args.topology)
    logger.info("Program started with logging config %s", config_path)
    try:
        graph, instance = build_instance_from_topology(
            topology_path,
            args.requests,
            seed=args.seed,
        )
        solver = SecureOpticalILPSolver(instance)
        solution = solver.solve()

        output_dir = Path("outputs")
        output_dir.mkdir(parents=True, exist_ok=True)

        solution_path = output_dir / "solution.json"
        solution.write_json(solution_path)
        images = visualize_solution(instance, solution, output_dir)
        logger.info("Solution written to %s", solution_path)
        logger.info("Visualization outputs: %s", images)

        print_solution(solution)
        print()
        print(f"topology={topology_path}")
        print(f"G(V,E)=({graph.number_of_nodes()},{graph.number_of_edges()})")
        print(f"requests={args.requests}")
        print(f"seed={args.seed}")
        print(f"solution_json={solution_path}")
        for name, path in images.items():
            print(f"{name}={path}")
        logger.info("Program finished successfully")
    except Exception:
        logger.exception("Program execution failed")
        raise


if __name__ == "__main__":
    main()
