from __future__ import annotations

import argparse
import logging
from pathlib import Path

from secure_optical_ilp import (
    AppConfig,
    SecureOpticalILPSolver,
    build_requests,
    build_network,
    load_app_config,
    load_topology_graphml,
    setup_logging,
    visualize_solution,
)

logger = logging.getLogger(__name__)


def build_instance(config: AppConfig):
    """Read the configured topology and convert it into an ILP input instance."""
    topology_path = config.topology.path
    request_config = config.request_generation
    resource_config = config.network_resources

    logger.info("Loading topology from %s", topology_path)
    graph = load_topology_graphml(topology_path)
    requests = build_requests(
        graph,
        request_count=request_config.count,
        seed=request_config.seed,
        bandwidth_min=request_config.bandwidth_min,
        bandwidth_max=request_config.bandwidth_max,
        security_level_min=request_config.security_level_min,
        security_level_max=request_config.security_level_max,
    )
    logger.info(
        "Generated %s uniformly distributed demo requests from topology graph with |V|=%s, |E|=%s",
        len(requests),
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )

    instance = build_network(
        graph,
        requests=requests,
        wavelengths=resource_config.wavelengths,
        lightpaths_per_pair=resource_config.lightpaths_per_pair,
        logical_bandwidth_capacity=resource_config.logical_bandwidth_capacity,
        logical_key_capacity=resource_config.logical_key_capacity,
        costs=config.costs,
    )
    logger.info(
        "Built NetworkInstance with %s directed links and %s requests",
        len(instance.links),
        len(instance.requests),
    )
    return graph, instance


def parse_args() -> argparse.Namespace:
    """Parse only the config path; experiment inputs live in the TOML file."""
    parser = argparse.ArgumentParser(
        description="Solve the secure optical network ILP from a TOML config file."
    )
    parser.add_argument(
        "--config",
        default="config.toml",
        help="TOML config file containing topology, demand, cost, solver, and output parameters.",
    )
    return parser.parse_args()


def print_solution(solution) -> None:
    """Print a compact summary of the final solution to standard output."""
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
    """Program entry point."""
    args = parse_args()
    config = load_app_config(Path(args.config))
    logging_config_path = setup_logging(config.logging.config_path)
    logger.info("Program started with app config %s", Path(args.config).resolve())
    logger.info("Logging config loaded from %s", logging_config_path)

    try:
        graph, instance = build_instance(config)
        solver = SecureOpticalILPSolver(
            instance,
            time_limit_seconds=config.solver.time_limit_seconds,
            solver_message=config.solver.solver_message,
        )
        solution = solver.solve()

        output_dir = config.outputs.directory
        output_dir.mkdir(parents=True, exist_ok=True)

        solution_path = output_dir / config.outputs.solution_filename
        solution.write_json(solution_path)
        images = {}
        if config.outputs.enable_visualization:
            images = visualize_solution(instance, solution, output_dir)
        logger.info("Solution written to %s", solution_path)
        logger.info("Visualization outputs: %s", images)

        print_solution(solution)
        print()
        print(f"config={Path(args.config).resolve()}")
        print(f"topology={config.topology.path}")
        print(f"G(V,E)=({graph.number_of_nodes()},{graph.number_of_edges()})")
        print(f"requests={config.request_generation.count}")
        print(f"seed={config.request_generation.seed}")
        print(f"solution_json={solution_path}")
        for name, path in images.items():
            print(f"{name}={path}")
        logger.info("Program finished successfully")
    except Exception:
        logger.exception("Program execution failed")
        raise


if __name__ == "__main__":
    main()
