from __future__ import annotations

import csv
import math
import os
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


# delayed imports after patching
os.chdir(PROJECT_DIR)
from models.config import SimulationConfig
from simulation.runner import SimulationRunner
import random

OUT_DIR = Path('data/')
OUT_DIR.mkdir(parents=True, exist_ok=True)

LOADS = [x*5 for x in range(1, 11)]  # 10 points: 1..10
print(LOADS)
SEEDS = random.sample(range(1, 100), 1)  # 10 runs per load
ALGORITHMS = {
    'ag_cf_grooming': 'CFG',
    'ag_sf_grooming': 'SFG',
    'ag_jdr_grooming': 'JDRG',
}
config = SimulationConfig()
config.load_config(path=str(CONFIG_PATH))
rows = []

for load in LOADS:
    print(f'LOAD {load} start', flush=True)
    for seed in SEEDS:
        for alg_label, alg_name in ALGORITHMS.items():
            cfg = replace(
                config,
                traffic=replace(config.traffic, load=float(load), seed=int(seed)),
                algorithm=replace(config.algorithm, name=alg_name),
            )
            runner = SimulationRunner()
            runner.build(cfg)
            summary = runner.run()
            rows.append({
                'topology': cfg.topology.path,
                'algorithm': alg_label,
                'algorithm_config_name': alg_name,
                'calls': cfg.traffic.calls,
                'load': float(load),
                'seed': int(seed),
                'blocking_rate': summary['blocking_rate'],
                'average_security_exposure': summary['average_security_exposure'],
                'average_num_recip_channels': summary['average_num_recip_channels'],
                'average_security_cost': summary['average_security_cost'],
            })
    print(f'LOAD {load} done', flush=True)

from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d-%H%M")
raw_csv = OUT_DIR / f'{timestamp}-results.csv'
fieldnames = [
    'topology', 'algorithm', 'algorithm_config_name',
    'calls', 'load', 'seed',
    'blocking_rate',
    'average_security_exposure', 'average_num_recip_channels',
    'average_security_cost'
]
with raw_csv.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

# aggregate mean/std/sem
metrics = ['blocking_rate', 'average_security_exposure', 'average_security_cost']
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
    ('average_security_exposure', 'Average Security Exposure', 'average_security_exposure_errorbar.png'),
    ('average_security_cost', 'Average Security Cost', 'average_security_cost_errorbar.png'),
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
    ax.set_xticks(LOADS)
    ax.grid(True, linestyle='--', linewidth=0.5, alpha=0.65)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename)
    plt.close(fig)

print('DONE', flush=True)
