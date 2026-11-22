#!/usr/bin/env python3
"""Regenerate five main and three supplementary figures from pinned sources."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('MPLCONFIGDIR', '/tmp/harp-final-figures')
os.environ.setdefault('MPLBACKEND', 'Agg')
FIG = ROOT / 'docs/AIO-mesh-rev1/figs'
EVIDENCE = ROOT / 'docs/AIO-mesh-rev1/evidence'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(script, *args):
    subprocess.run([sys.executable, str(ROOT / script), *map(str, args)], cwd=ROOT, check=True)

def main():
    run('scripts/paper/make_architecture_figures.py')
    run('scripts/rev1/plot_manuscript_benchmark.py')
    run('scripts/paper/make_load_sweep_figure.py')
    run('scripts/rev1/plot_manuscript_ablation.py')
    cost = ROOT / 'results/rev1/nonhil_studies/20261117_233441/controlled_policy_cost.json'
    scale = ROOT / 'results/rev1/nonhil_studies/20261117_235132/topology_scalability.json'
    run('scripts/rev1/plot_nonhil_studies.py', '--cost', cost, '--scale', scale,
        '--output', FIG / 'policy_cost_scalability.pdf')
    import matplotlib.pyplot as plt
    source = ROOT / 'results/evidence/mentor_completion_20261121/arrival_rate_only/arrival_rate_aggregate.csv'
    with source.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), sharey=True, layout='constrained')
    policies = [('harp_protected','HARP','o'), ('saf_h_protected','SAF-H','s'),
                ('cspf_protected','CSPF','^'), ('traditional_greedy_protected','Greedy','D'),
                ('decoupled_ai_protected','DAI','v')]
    for ax, topo in zip(axes, ['vietnam','nsfnet','geant2']):
        for policy, label, marker in policies:
            group = sorted([r for r in rows if r['topology']==topo and r['algorithm']==policy],
                           key=lambda r: float(r['arrival_rate']))
            if len(group)!=5 or any(int(r['seeds'])!=20 for r in group):
                raise ValueError(f'Incomplete arrival data: {topo}/{policy}')
            x=[float(r['arrival_rate']) for r in group]
            ax.plot(x,[float(r['safe_acceptance_mean']) for r in group],marker=marker,label=label,markersize=4)
            ax.fill_between(x,[float(r['safe_acceptance_ci95_low']) for r in group],
                            [float(r['safe_acceptance_ci95_high']) for r in group],alpha=.12)
        ax.set(title=topo.upper(),xlabel='Request arrival probability',xticks=[.2,.4,.6,.8,1.],ylim=(0,103))
        ax.grid(axis='y',alpha=.25)
    axes[0].set_ylabel('Safe acceptance (%)')
    axes[0].legend(fontsize=8,frameon=False)
    fig.savefig(FIG / 'arrival_rate_only.pdf')
    plt.close(fig)
    # Track each figure's actual source, including separate ablation/timing protocols.
    inputs = {
        'overview.pdf': [ROOT/'scripts/paper/make_architecture_figures.py'],
        'testbed.pdf': [ROOT/'scripts/paper/make_architecture_figures.py'],
        'arrival_rate_only.pdf': [source, source.parent/'arrival_rate_manifest.json'],
        'benchmark_paired_effects.pdf': [EVIDENCE/'model_refresh_20261120/stress_paired_statistics.csv', EVIDENCE/'model_refresh_20261120/stress_per_seed_all_topologies.csv'],
        'load_sweep_three_topologies.pdf': [EVIDENCE/'model_refresh_20261120/load_chain_per_seed.csv'],
        'policy_cost_scalability.pdf': [cost, scale],
        'ablation_mask_admission.pdf': [EVIDENCE/'e3/ablation_admission_summary.csv', EVIDENCE/'e3/manifest.json'],
        'ablation_compute_cost.pdf': [ROOT/f'results/rev1/e3_timed/vietnam/{w}/harp_ablation_summary.csv' for w in ('uniform','bursty')],
    }
    scripts = [Path(__file__), *[ROOT/p for p in ('scripts/paper/make_architecture_figures.py','scripts/rev1/plot_manuscript_benchmark.py','scripts/paper/make_load_sweep_figure.py','scripts/rev1/plot_manuscript_ablation.py','scripts/rev1/plot_nonhil_studies.py')]]
    manifest = {'command':'python scripts/paper/refresh_final_figures.py',
                'scope':'Five main and three supplementary figures; distinct experiment protocols are preserved. Final 2M training variation is reported in Supplementary Table S22.',
                'generators_sha256':{str(p.relative_to(ROOT)):digest(p) for p in scripts},
                'figures':{name:{'sha256':digest(FIG/name),'inputs_sha256':{str(p.relative_to(ROOT)):digest(p) for p in paths}} for name,paths in inputs.items()}}
    (FIG/'final_figures_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Regenerated and indexed {len(inputs)} figures (five main, three supplementary)')

if __name__ == '__main__':
    main()
