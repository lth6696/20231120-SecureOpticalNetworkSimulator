from __future__ import annotations

import argparse
import json
import logging
import logging.config
from pathlib import Path

from config import load_simulation_config
from runner import build_runner

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse only the config path; experiment inputs live in the TOML file."""
    parser = argparse.ArgumentParser(
        description="Read setup from a TOML config file."
    )
    parser.add_argument(
        "--config",
        default="config.toml",
        help="TOML config file containing topology, demand, cost, solver, and output parameters.",
    )
    return parser.parse_args()


def main() -> int:
    # Keep the CLI thin so experiment behavior is driven by configuration and
    # the runner, not by ad hoc argument handling here.
    args = parse_args()
    config = load_simulation_config(args.config)
    _configure_logging(config)
    logger.info("Starting simulation with config=%s", args.config)
    runner = build_runner(config)
    summary = runner.run()
    logger.info("Simulation completed with summary=%s", summary)
    if args.pretty:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(json.dumps(summary, sort_keys=True))
    return 0


def _configure_logging(config) -> None:
    logconfig_path = Path(config.logging.path)
    if not logconfig_path.is_absolute():
        candidates = [
            Path.cwd() / logconfig_path,
            Path(__file__).resolve().parent / logconfig_path,
        ]
        for candidate in candidates:
            if candidate.exists():
                logconfig_path = candidate
                break
    if logconfig_path.exists():
        logging.config.fileConfig(logconfig_path, disable_existing_loggers=False)
    logging.getLogger().setLevel(config.logging.level.upper())


if __name__ == "__main__":
    raise SystemExit(main())
