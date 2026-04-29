from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_simulation_config
from runner import build_runner


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
    args = parse_args()
    config = load_simulation_config(args.config)
    runner = build_runner(config)
    summary = runner.run()
    if args.pretty:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
