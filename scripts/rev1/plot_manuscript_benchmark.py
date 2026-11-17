"""Render archived paired benchmark effects; no simulated/example data."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/rev1-paper-mpl')
import glob
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/AIO-mesh-rev1/figs'
SCENARIOS = [('elephant_stress', 'Elephant stress'), ('burst_surge', 'Burst surge'), ('chaos', 'Chaos')]

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'pdf.fonttype': 42})
    fig, ax = plt.subplots(figsize=(9, 5))
    sources = []
    y = 8
    for topo, color in [('vietnam', '#2672a3'), ('nsfnet', '#c45b25'), ('geant2', '#25845b')]:
        for scenario, name in SCENARIOS:
            if topo == 'geant2':
                pattern = ROOT / f'results/rev1/geant2/benchmark/current_code_three_workloads/20261117_205637/geant2_{scenario}_stress/paired_statistics.json'
            else:
                pattern = ROOT / f'results/rev1/{topo}/benchmark/{scenario}/*/*/paired_statistics.json'
            paths = glob.glob(str(pattern))
            if len(paths) != 1:
                raise ValueError(f'Ambiguous/missing source: {paths}')
            path = Path(paths[0]); d = json.loads(path.read_text())[0]
            assert d['n'] == 20
            ax.errorbar(d['mean_delta'], y, xerr=[[d['mean_delta']-d['ci95_low']], [d['ci95_high']-d['mean_delta']]], fmt='o', color=color, capsize=4)
            ax.text(-2.65, y, f'{topo.upper() if topo != "vietnam" else "Vietnam"}: {name}', va='center', fontsize=9)
            sources.append(str(path.relative_to(ROOT))); y -= 1
    ax.axvline(0, color='0.4', linestyle='--', linewidth=1)
    ax.set_yticks([]); ax.set_xlim(-2.75, 1.3)
    ax.set_xlabel('Acceptance difference: HARP minus SAF-H (percentage points)')
    ax.grid(axis='x', alpha=.2); fig.tight_layout()
    fig.savefig(OUT/'benchmark_paired_effects.pdf', bbox_inches='tight')
    fig.savefig(OUT/'benchmark_paired_effects.png', dpi=180, bbox_inches='tight')
    (OUT/'benchmark_paired_effects.sources.json').write_text(json.dumps(sources, indent=2)+'\n')
    plt.close(fig)

if __name__ == '__main__':
    main()
