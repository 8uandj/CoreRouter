import csv
import os
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", "/tmp/core-router-mpl-load")
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'results/rev1/load_sweep/current_code_20261117'
OUT = ROOT / 'docs/AIO-mesh-rev1/figs'
TOPOLOGIES = [('vietnam', 'Vietnam'), ('nsfnet', 'NSFNET'), ('geant2', 'GEANT2')]
POLICIES = [
    ('traditional_greedy_protected', 'Greedy', '#457B9D', 'o'),
    ('decoupled_ai_protected', 'Decoupled AI', '#7B2CBF', 'D'),
    ('saf_h_protected', 'SAF-H', '#E76F51', 's'),
    ('harp_protected', 'HARP', '#2A9D8F', '^'),
]
LOADS = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5]

def read_rows(topo):
    path = DATA / f'{topo}_load_sweep_per_seed.csv'
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    return rows

def ci(values, seed):
    values = np.asarray(values, dtype=float)
    if np.all(values == values[0]):
        return float(values[0]), float(values[0])
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(10000, len(values)), replace=True).mean(axis=1)
    return tuple(np.quantile(samples, [0.025, 0.975]).tolist())

def plot(axs, topo, title_prefix=''):
    rows = read_rows(topo)
    for policy_index, (key, name, color, marker) in enumerate(POLICIES):
        for metric_index, field in enumerate(['safe_acceptance_rate', 'runtime_rejection_rate']):
            means, lows, highs = [], [], []
            for load_index, load in enumerate(LOADS):
                group = [r for r in rows if r['algorithm'] == key and float(r['load_multiplier']) == load]
                assert len(group) == 20, (topo, key, load, len(group))
                vals = []
                for r in group:
                    if field == 'runtime_rejection_rate':
                        vals.append(sum(float(r[f'rejection_{reason}_rate']) for reason in ['cpu','ram','msd','bw','other']))
                    else:
                        vals.append(float(r[field]))
                means.append(float(np.mean(vals)))
                lo, hi = ci(vals, seed=20261117 + policy_index * 29 + metric_index * 7 + load_index)
                lows.append(lo); highs.append(hi)
            ax = axs[metric_index]
            ax.plot(LOADS, means, color=color, marker=marker, linewidth=1.7, markersize=4.5, label=name)
            ax.fill_between(LOADS, lows, highs, color=color, alpha=0.13, linewidth=0)
    axs[0].set_title(f'{title_prefix}Safe acceptance')
    axs[1].set_title('Runtime rejection')
    axs[0].set_ylabel('Requests (%)')
    axs[1].set_ylabel('Requests (%)')
    for ax in axs:
        ax.set_xlabel('Offered-intensity multiplier')
        ax.set_xticks(LOADS)
        ax.set_ylim(0, 105)
        ax.grid(True, linestyle=':', alpha=0.45)

OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.size': 9, 'axes.titlesize': 10, 'legend.fontsize': 8,
                     'pdf.fonttype': 42, 'ps.fonttype': 42})
fig, axes = plt.subplots(3, 2, figsize=(10.4, 9.3), sharex=True)
for (topo, name), row_axes in zip(TOPOLOGIES, axes):
    plot(row_axes, topo, f'{name}: ')
handles, labels = axes[0,0].get_legend_handles_labels()
fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.985))
fig.text(0.5, 0.014, 'All policies use the protected admission boundary; no admitted hard violations were observed.',
         ha='center', fontsize=8)
fig.tight_layout(rect=(0.02, 0.04, 1, 0.95), h_pad=1.4, w_pad=1.2)
fig.savefig(OUT / 'load_sweep_three_topologies.pdf', bbox_inches='tight')
plt.close(fig)
for topo, name in TOPOLOGIES:
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.2), sharex=True)
    plot(axes, topo, f'{name}: ')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.99))
    fig.text(0.5, 0.015, 'Protected admission; admitted hard violations were zero in all evaluated runs.', ha='center', fontsize=8)
    fig.tight_layout(rect=(0.02, 0.06, 1, 0.88), w_pad=1.2)
    fig.savefig(OUT / f'{topo}_load_sweep.pdf', bbox_inches='tight')
    plt.close(fig)
print('Generated combined and topology-specific load-sweep PDFs from 20-seed per-seed CSVs.')
