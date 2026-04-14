from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from .models import ActiveLightpath, NetworkInstance, SolverSolution

logger = logging.getLogger(__name__)


def _require_visual_libraries():
    """仅在需要可视化时导入绘图库。

    ``matplotlib.use("Agg")`` 会选择非交互式后端，这在服务器环境或
    只有终端、没有图形界面的环境里尤其有用。
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Visualization requires matplotlib and networkx. "
            "Run `python -m pip install -r requirements.txt`."
        ) from exc
    return plt, nx


def visualize_solution(
    instance: NetworkInstance,
    solution: SolverSolution,
    output_dir: str | Path,
) -> dict[str, Path]:
    """生成逻辑层和物理层的可视化文件。

    输入：
        instance: 网络输入数据。
        solution: ILP 求解结果。
        output_dir: PNG 文件输出目录。

    输出：
        图名到输出文件路径的映射。
    """
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    logger.info("Writing visualization outputs to %s", output_root)

    logical_path = output_root / "lightpaths_mnk.png"
    physical_path = output_root / "links_ijw.png"

    _draw_logical_lightpaths(instance, solution, logical_path)
    _draw_physical_links(instance, solution, physical_path)

    return {
        "lightpaths_mnk": logical_path,
        "links_ijw": physical_path,
    }


def _draw_logical_lightpaths(
    instance: NetworkInstance,
    solution: SolverSolution,
    output_path: Path,
) -> None:
    """把业务层/安全层逻辑光路 ``(m,n,k)`` 绘制到一张 PNG 中。"""
    plt, nx = _require_visual_libraries()
    positions = _resolve_positions(instance, nx)
    logger.info(
        "Rendering logical lightpath figure with service=%s and security=%s paths",
        len(solution.service_lightpaths),
        len(solution.security_lightpaths),
    )

    figure, axes = plt.subplots(1, 2, figsize=(14, 6))
    _draw_single_logical_layer(
        ax=axes[0],
        instance=instance,
        positions=positions,
        lightpaths=solution.service_lightpaths,
        title="Service Lightpaths (mnk)",
        edge_color="#2563eb",
        nx=nx,
    )
    _draw_single_logical_layer(
        ax=axes[1],
        instance=instance,
        positions=positions,
        lightpaths=solution.security_lightpaths,
        title="Security Lightpaths (mnk)",
        edge_color="#dc2626",
        nx=nx,
    )
    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)
    logger.info("Saved logical lightpath visualization to %s", output_path)


def _draw_single_logical_layer(
    *,
    ax,
    instance: NetworkInstance,
    positions: dict[str, tuple[float, float]],
    lightpaths: tuple[ActiveLightpath, ...],
    title: str,
    edge_color: str,
    nx,
) -> None:
    """在共享坐标轴上绘制单层逻辑光路图。"""
    graph = nx.DiGraph()
    graph.add_nodes_from(instance.nodes)

    edge_labels: dict[tuple[str, str], str] = {}
    grouped_labels: dict[tuple[str, str], list[str]] = defaultdict(list)
    for lightpath in lightpaths:
        key = (lightpath.key.source, lightpath.key.target)
        requests = ",".join(lightpath.request_ids) or "-"
        grouped_labels[key].append(
            f"k={lightpath.key.index} load={lightpath.carried_load:g} req={requests}"
        )
        graph.add_edge(*key)

    for key, parts in grouped_labels.items():
        edge_labels[key] = "\n".join(parts)

    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color="#f8fafc",
        edgecolors="#1f2937",
        node_size=1800,
        ax=ax,
    )
    nx.draw_networkx_labels(graph, positions, font_size=10, ax=ax)

    if graph.number_of_edges() > 0:
        nx.draw_networkx_edges(
            graph,
            positions,
            edge_color=edge_color,
            width=2.2,
            arrows=True,
            arrowstyle="-|>",
            ax=ax,
        )
        nx.draw_networkx_edge_labels(
            graph,
            positions,
            edge_labels=edge_labels,
            font_size=8,
            ax=ax,
        )

    ax.set_title(title)
    ax.axis("off")


def _draw_physical_links(
    instance: NetworkInstance,
    solution: SolverSolution,
    output_path: Path,
) -> None:
    """把物理链路-波长使用情况 ``(i,j,w)`` 绘制成 PNG。"""
    plt, nx = _require_visual_libraries()
    positions = _resolve_positions(instance, nx)
    logger.info("Rendering physical link usage figure")

    graph = nx.DiGraph()
    graph.add_nodes_from(instance.nodes)
    graph.add_edges_from(instance.directed_edges)

    usage_labels: dict[tuple[str, str], str] = {}
    grouped_labels: dict[tuple[str, str], list[str]] = defaultdict(list)
    active_edges = set()

    for layer_name, lightpaths in (
        ("svc", solution.service_lightpaths),
        ("sec", solution.security_lightpaths),
    ):
        for lightpath in lightpaths:
            lightpath_label = (
                f"{layer_name}:{lightpath.key.source}{lightpath.key.target}{lightpath.key.index}"
            )
            for assignment in lightpath.physical_assignments:
                edge = (assignment.source, assignment.target)
                active_edges.add(edge)
                grouped_labels[edge].append(
                    f"w{assignment.wavelength} {lightpath_label}"
                )

    for edge, parts in grouped_labels.items():
        usage_labels[edge] = "\n".join(parts)

    figure, ax = plt.subplots(figsize=(8, 6))
    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color="#f8fafc",
        edgecolors="#1f2937",
        node_size=1800,
        ax=ax,
    )
    nx.draw_networkx_labels(graph, positions, font_size=10, ax=ax)
    nx.draw_networkx_edges(
        graph,
        positions,
        edge_color="#cbd5e1",
        width=1.2,
        arrows=True,
        arrowstyle="-|>",
        ax=ax,
    )

    if active_edges:
        nx.draw_networkx_edges(
            graph,
            positions,
            edgelist=list(active_edges),
            edge_color="#0f766e",
            width=2.4,
            arrows=True,
            arrowstyle="-|>",
            ax=ax,
        )
        nx.draw_networkx_edge_labels(
            graph,
            positions,
            edge_labels=usage_labels,
            font_size=8,
            ax=ax,
        )

    ax.set_title("Physical Link / Wavelength Usage (ijw)")
    ax.axis("off")
    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)
    logger.info("Saved physical link visualization to %s", output_path)


def _resolve_positions(instance: NetworkInstance, nx) -> dict[str, tuple[float, float]]:
    """返回节点绘图坐标。

    如果 GraphML 中已经给出了节点坐标，就直接复用；否则用
    ``spring_layout`` 自动生成一个较易读的布局。
    """
    if instance.node_positions and set(instance.node_positions) == set(instance.nodes):
        return instance.node_positions

    graph = nx.DiGraph()
    graph.add_nodes_from(instance.nodes)
    graph.add_edges_from(instance.directed_edges)
    return nx.spring_layout(graph, seed=7)
