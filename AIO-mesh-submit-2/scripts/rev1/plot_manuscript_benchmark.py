"""Render archived paired benchmark effects; no simulated/example data."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/rev1-paper-mpl')
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_BASE = Path(__file__).resolve().parents[2]
ROOT = _BASE.parent if _BASE.name == 'AIO-mesh-submit-2' else _BASE
BUNDLE = _BASE if _BASE.name == 'AIO-mesh-submit-2' else ROOT / 'AIO-mesh-submit-2'
OUT = BUNDLE / 'docs/AIO-mesh-rev1/figs'
SCENARIOS = [('elephant_stress', 'Elephant stress'), ('burst_surge', 'Burst surge'), ('chaos', 'Chaos')]

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'pdf.fonttype': 42})
    fig, ax = plt.subplots(figsize=(9, 5))
    source = BUNDLE / 'docs/AIO-mesh-rev1/evidence/model_refresh_20261120/stress_per_seed_all_topologies.csv'
    with source.open(newline='') as f: rows = list(csv.DictReader(f))
    sources = [str(source.relative_to(ROOT))]
    y = 8
    for topo, color in [('vietnam', '#2672a3'), ('nsfnet', '#c45b25'), ('geant2', '#25845b')]:
        for scenario, name in SCENARIOS:
            vals={}
            for policy in ('harp_protected','saf_h_protected'):
                vals[policy]=[float(r['safe_acceptance_rate']) for r in rows if r['topology']==topo and r['scenario']==scenario and r['algorithm']==policy]
            diffs=[a-b for a,b in zip(vals['harp_protected'],vals['saf_h_protected'])]
            if len(diffs)!=20: raise ValueError(f'Expected 20 paired seeds: {topo}/{scenario}')
            mean=sum(diffs)/len(diffs); rng=__import__('random').Random(20261120+len(sources)*31+y)
            samples=sorted(sum(diffs[rng.randrange(20)] for _ in range(20))/20 for _ in range(20000))
            lo,hi=samples[499],samples[19499]
            ax.errorbar(mean, y, xerr=[[mean-lo], [hi-mean]], fmt='o', color=color, capsize=4)
            ax.text(-2.65, y, f'{topo.upper() if topo != "vietnam" else "Vietnam"}: {name}', va='center', fontsize=9)
            y -= 1
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
