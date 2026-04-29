from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_simulation_config
from .runner import build_runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wdm-sim",
        description="Run a WDM optical network discrete-event simulation.",
    )
    parser.add_argument("config", type=Path, help="Path to JSON, TOML, or XML config")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON statistics",
    )
    args = parser.parse_args(argv)

    config = load_simulation_config(args.config)
    runner = build_runner(config)
    summary = runner.run()
    if args.pretty:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(json.dumps(summary, sort_keys=True))
    return 0

