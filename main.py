from __future__ import annotations

import argparse
import logging.config

from simulation.runner import SimulationRunner
from models.config import SimulationConfig

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse only the config path; experiment inputs live in the TOML file."""
    parser = argparse.ArgumentParser(
        description="Read setup from a TOML config file."
    )
    parser.add_argument(
        "--config_path",
        default="config.toml",
        help="TOML config file containing topology, demand, cost, solver, and output parameters.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = SimulationConfig()
    config.load_config(path=args.config_path)
    config.load_logging()

    logger.info(f"{'='*25} Start Running {'='*25}")
    runner = SimulationRunner()
    runner.build(config)
    summary = runner.run()
    logger.info("Simulation completed with summary=%s", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
