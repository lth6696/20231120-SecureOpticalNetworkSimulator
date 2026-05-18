from __future__ import annotations

import csv
import math
import os
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Any

# --- one-time project preparation ---
PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / 'config.toml'
OUT_DIR = PROJECT_DIR / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)


LOADS = [x*10 for x in range(1, 11)]
NUM_REPEATS = 1  # 如需每个 load 重复 10 次，改为 10
SEED_RANGE = range(1, 100)
ALGORITHMS = {
    'ag_cf_grooming': 'CFG',
    'ag_sf_grooming': 'SFG',
    'ag_jdr_grooming': 'JDRG',
}

# None 表示自动使用 CPU 核心数；也可以手动指定，例如 MAX_WORKERS = 8
MAX_WORKERS: int | None = 8


def _build_config(load: float, seed: int, algorithm_name: str):
    """Load config.toml and override only the parameters for one experiment."""
    # 子进程在 Windows/PyCharm 下不会继承工作目录，显式切到项目根目录，
    # 确保 graphml/Nsfnet.graphml 等相对路径能够被正确读取。
    os.chdir(PROJECT_DIR)

    from models.config import SimulationConfig

    config = SimulationConfig()
    config.load_config(path=str(CONFIG_PATH))

    return replace(
        config,
        traffic=replace(config.traffic, load=float(load), seed=int(seed)),
        algorithm=replace(config.algorithm, name=algorithm_name),
    )


def run_one(task: tuple[float, int, str, str]) -> dict[str, Any]:
    """Run one independent simulation task in a worker process."""
    load, seed, alg_label, alg_name = task

    cfg = _build_config(load=load, seed=seed, algorithm_name=alg_name)

    from simulation.runner import SimulationRunner

    runner = SimulationRunner()
    runner.build(cfg)
    summary = runner.run()

    return {
        "topology": cfg.topology.path,
        "algorithm": alg_label,
        "algorithm_config_name": alg_name,
        "calls": cfg.traffic.calls,
        "load": float(load),
        "seed": int(seed),
        "blocking_rate": summary["blocking_rate"],
        "average_security_exposure": summary["average_security_exposure"],
        "average_num_recip_channels": summary["average_num_recip_channels"],
        "average_security_cost": summary["average_security_cost"],
    }


def aggregate_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate raw results into mean/std/sem grouped by load and algorithm."""
    metrics = ["blocking_rate", "average_security_exposure", "average_security_cost"]
    agg_rows: list[dict[str, Any]] = []

    loads = sorted({float(r["load"]) for r in rows})
    algorithms = sorted({r["algorithm"] for r in rows})

    for load in loads:
        for alg_label in algorithms:
            group = [
                r
                for r in rows
                if float(r["load"]) == float(load) and r["algorithm"] == alg_label
            ]

            if not group:
                continue

            agg: dict[str, Any] = {
                "load": float(load),
                "algorithm": alg_label,
                "repeat": len(group),
            }

            for metric in metrics:
                vals = [float(r[metric]) for r in group]
                agg[f"{metric}_mean"] = mean(vals)
                agg[f"{metric}_std"] = stdev(vals) if len(vals) > 1 else 0.0
                agg[f"{metric}_sem"] = (
                    stdev(vals) / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
                )

            agg_rows.append(agg)

    return agg_rows


def save_raw_results(rows: list[dict[str, Any]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    raw_csv = OUT_DIR / f"{timestamp}-results.csv"
    fieldnames = [
        "topology",
        "algorithm",
        "algorithm_config_name",
        "calls",
        "load",
        "seed",
        "blocking_rate",
        "average_security_exposure",
        "average_num_recip_channels",
        "average_security_cost",
    ]

    with raw_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return raw_csv


def save_summary(agg_rows: list[dict[str, Any]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = ["blocking_rate", "average_security_exposure", "average_security_cost"]
    summary_csv = OUT_DIR / "summary_mean_std_sem.csv"
    summary_fields = ["load", "algorithm", "repeat"]
    for metric in metrics:
        summary_fields += [f"{metric}_mean", f"{metric}_std", f"{metric}_sem"]

    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(agg_rows)

    return summary_csv


def plot_results(agg_rows: list[dict[str, Any]]) -> None:
    """Draw error-bar figures. Matplotlib is imported only in the main process."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    loads = sorted({float(r["load"]) for r in agg_rows})
    algorithms = sorted({r["algorithm"] for r in agg_rows})

    for metric, ylabel, filename in [
        ("blocking_rate", "Blocking Rate", "blocking_rate_errorbar.png"),
        (
            "average_security_exposure",
            "Average Security Exposure",
            "average_security_exposure_errorbar.png",
        ),
        (
            "average_security_cost",
            "Average Security Cost",
            "average_security_cost_errorbar.png",
        ),
    ]:
        fig, ax = plt.subplots(figsize=(8.2, 5), dpi=180)

        for alg_label in algorithms:
            data = [r for r in agg_rows if r["algorithm"] == alg_label]
            data.sort(key=lambda x: float(x["load"]))

            x = [float(r["load"]) for r in data]
            y = [float(r[f"{metric}_mean"]) for r in data]
            yerr = [float(r[f"{metric}_std"]) for r in data]

            ax.errorbar(
                x,
                y,
                yerr=yerr,
                marker="o",
                linewidth=1.6,
                capsize=3,
                label=alg_label,
            )

        ax.set_xlabel("Load")
        ax.set_ylabel(ylabel)
        ax.set_xticks(loads)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.65)
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT_DIR / filename)
        plt.close(fig)


def read_raw_results(csv_path: Path) -> None:
    rows = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append({
                "topology": row["topology"],
                "algorithm": row["algorithm"],
                "algorithm_config_name": row["algorithm_config_name"],
                "calls": int(row["calls"]),
                "load": float(row["load"]),
                "seed": int(row["seed"]),
                "blocking_rate": float(row["blocking_rate"]),
                "average_security_exposure": float(row["average_security_exposure"]),
                "average_num_recip_channels": float(row["average_num_recip_channels"]),
                "average_security_cost": float(row["average_security_cost"]),
            })

    if not rows:
        raise ValueError(f"No data found in {csv_path}")

    agg_rows = aggregate_results(rows)
    plot_results(agg_rows)


def main() -> None:
    os.chdir(PROJECT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    seeds = random.sample(SEED_RANGE, NUM_REPEATS)
    tasks = [
        (float(load), int(seed), alg_label, alg_name)
        for load in LOADS
        for seed in seeds
        for alg_label, alg_name in ALGORITHMS.items()
    ]

    if not tasks:
        print("No simulation tasks to run.", flush=True)
        return

    worker_count = MAX_WORKERS or min(os.cpu_count() or 1, len(tasks))
    print(f"LOADS: {LOADS}", flush=True)
    print(f"SEEDS: {seeds}", flush=True)
    print(f"Total tasks: {len(tasks)}, workers: {worker_count}", flush=True)

    rows: list[dict[str, Any]] = []
    completed = 0

    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(run_one, task): task for task in tasks}
        for future in as_completed(futures):
            task = futures[future]
            load, seed, alg_label, _ = task
            try:
                row = future.result()
            except Exception as exc:
                print(
                    f"FAILED load={load}, seed={seed}, algorithm={alg_label}: {exc}",
                    flush=True,
                )
                raise

            rows.append(row)
            completed += 1
            print(
                f"DONE {completed}/{len(tasks)}: "
                f"load={load}, seed={seed}, algorithm={alg_label}",
                flush=True,
            )

    rows.sort(key=lambda r: (r["load"], r["seed"], r["algorithm"]))
    agg_rows = aggregate_results(rows)

    raw_csv = save_raw_results(rows)
    summary_csv = save_summary(agg_rows)
    plot_results(agg_rows)

    print(f"Raw results saved to: {raw_csv}", flush=True)
    print(f"Summary saved to: {summary_csv}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    # main()
    read_raw_results(Path("data/20260518-1138-results.csv"))
