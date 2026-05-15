from __future__ import annotations

import csv
import math
import os
import shutil
from dataclasses import replace
from pathlib import Path
from statistics import mean, stdev

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- one-time project preparation ---
PROJECT_DIR = Path(__file__).resolve().parent
UPLOADED_CONFIG = Path('config.toml')
CONFIG_PATH = PROJECT_DIR / 'config.toml'


def patch_source_for_speed(project_dir: Path) -> None:
    # minimal JDRG correctness fix used in prior runs
    jdr = project_dir / 'algorithms' / 'ag_jdr_grooming.py'
    text = jdr.read_text(encoding='utf-8')
    old = 'sp = self._find_reciprocal_path_for_hop(ag, hops, hop, flow)'
    new = 'sp = self._find_reciprocal_path_for_hop(ag, [*hops, *hops_recip], hop, flow)'
    if old in text:
        text = text.replace(old, new)
        jdr.write_text(text, encoding='utf-8')


patch_source_for_speed(PROJECT_DIR)

# delayed imports after patching
os.chdir(PROJECT_DIR)
from models.config import load_simulation_config
from simulation.runner import build_runner
import random

OUT_DIR = Path('data/')
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOADS = [x for x in range(1, 11)]  # 10 points: 1..10
SEEDS = random.sample(range(1, 100), 10)  # 10 runs per load
ALGORITHMS = {
    'ag_cf_grooming': 'CFG',
    'ag_sf_grooming': 'SFG',
    'ag_jdr_grooming': 'JDRG',
}

base = load_simulation_config(str(CONFIG_PATH))
rows = []

for load in LOADS:
    print(f'LOAD {load} start', flush=True)
    for seed in SEEDS:
        for alg_label, alg_name in ALGORITHMS.items():
            cfg = replace(
                base,
                traffic=replace(base.traffic, load=float(load), seed=int(seed)),
                algorithm=replace(base.algorithm, name=alg_name),
            )
            summary = build_runner(cfg).run()
            rows.append({
                'topology': cfg.topology.path,
                'algorithm': alg_label,
                'algorithm_config_name': alg_name,
                'calls': cfg.traffic.calls,
                'load': float(load),
                'seed': int(seed),
                'blocking_rate': summary['blocking_rate'],
                'expected_security_exposure': summary['expected_security_exposure'],
                'total_security_cost': summary['cost']['total_security_cost'],
                'accepted': summary['accepted'],
                'blocked': summary['blocked'],
                'accepted_secure': summary.get('accepted_secure'),
                'blocked_secure': summary.get('blocked_secure'),
            })
    print(f'LOAD {load} done', flush=True)

raw_csv = OUT_DIR / 'raw_results_10loads_10seeds.csv'
fieldnames = [
    'topology', 'algorithm', 'algorithm_config_name', 'calls', 'load', 'seed',
    'blocking_rate', 'expected_security_exposure', 'total_security_cost',
    'accepted', 'blocked', 'accepted_secure', 'blocked_secure'
]
with raw_csv.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

# aggregate mean/std/sem
metrics = ['blocking_rate', 'expected_security_exposure', 'total_security_cost']
agg_rows = []
for load in LOADS:
    for alg_label in ALGORITHMS:
        group = [r for r in rows if r['load'] == float(load) and r['algorithm'] == alg_label]
        agg = {'load': float(load), 'algorithm': alg_label, 'repeat': len(group)}
        for metric in metrics:
            vals = [float(r[metric]) for r in group]
            agg[f'{metric}_mean'] = mean(vals)
            agg[f'{metric}_std'] = stdev(vals) if len(vals) > 1 else 0.0
            agg[f'{metric}_sem'] = (stdev(vals) / math.sqrt(len(vals))) if len(vals) > 1 else 0.0
        agg_rows.append(agg)

summary_csv = OUT_DIR / 'summary_mean_std_sem.csv'
summary_fields = ['load', 'algorithm', 'repeat']
for metric in metrics:
    summary_fields += [f'{metric}_mean', f'{metric}_std', f'{metric}_sem']
with summary_csv.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=summary_fields)
    writer.writeheader()
    writer.writerows(agg_rows)

# plots with std error bars
for metric, ylabel, filename in [
    ('blocking_rate', 'Blocking Rate', 'blocking_rate_errorbar.png'),
    ('expected_security_exposure', 'Expected Security Exposure', 'expected_security_exposure_errorbar.png'),
    ('total_security_cost', 'Total Security Cost', 'total_security_cost_errorbar.png'),
]:
    fig, ax = plt.subplots(figsize=(8.2, 5), dpi=180)
    for alg_label in ALGORITHMS:
        data = [r for r in agg_rows if r['algorithm'] == alg_label]
        data.sort(key=lambda x: x['load'])
        x = [r['load'] for r in data]
        y = [r[f'{metric}_mean'] for r in data]
        yerr = [r[f'{metric}_std'] for r in data]
        ax.errorbar(x, y, yerr=yerr, marker='o', linewidth=1.6, capsize=3, label=alg_label)
    ax.set_xlabel('Load')
    ax.set_ylabel(ylabel)
    ax.set_title(f'Nsfnet.graphml | 10 seeds mean ± std | {ylabel} vs Load')
    ax.set_xticks(LOADS)
    ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.65)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename)
    plt.close(fig)

# save the exact config used and a brief readme
shutil.copy2(CONFIG_PATH, OUT_DIR / 'config_used.toml')
readme = OUT_DIR / 'README.txt'
readme.write_text(
    'Based on uploaded config(4).toml.\n'
    'Loads: 1..10 (10 points).\n'
    'Seeds: 42..51 (10 runs per load).\n'
    'Error bars: standard deviation across 10 seeds.\n',
    encoding='utf-8'
)
print('DONE', flush=True)
