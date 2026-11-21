#!/usr/bin/env python3
"""Regenerate manuscript-facing tables from completed N^2 model-refresh CSVs."""
import csv, hashlib, json, math, random, statistics
import subprocess
from pathlib import Path

_BASE = Path(__file__).resolve().parents[2]
ROOT = _BASE.parent if _BASE.name == "AIO-mesh-submit-2" else _BASE
BUNDLE = _BASE if _BASE.name == "AIO-mesh-submit-2" else ROOT / "AIO-mesh-submit-2"
EVIDENCE = BUNDLE / "results/evidence"
OUT = BUNDLE / "docs/AIO-mesh-rev1/evidence/model_refresh_20261120"
STRESS = EVIDENCE / "multinode_benchmark_20261120_084017"
REFRESH = EVIDENCE / "model_refresh_reruns_20261120_163000"
TOPOS = ("vietnam", "nsfnet", "geant2", "synthetic_25", "synthetic_50", "synthetic_100")
SCENARIOS = ("elephant_stress", "burst_surge", "chaos")
POLICIES = ("traditional_greedy", "decoupled_ai", "saf_h", "cspf", "harp")

def read(path):
    with path.open(newline="", encoding="utf-8") as f: return list(csv.DictReader(f))
def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]),lineterminator="\n"); w.writeheader(); w.writerows(rows)
def avg_sd(rows, metric):
    x=[float(r[metric]) for r in rows]
    return statistics.mean(x), statistics.stdev(x)
def fmt(x): return f"{x:.2f}"
def exact_wilcoxon(diffs):
    nz=[float(d) for d in diffs if float(d)!=0]
    if not nz: return 1.0,0.0
    from scipy.stats import rankdata
    ranks=rankdata([abs(d) for d in nz],method='average')
    wp=sum(r for d,r in zip(nz,ranks) if d>0); total=sum(ranks)
    doubled=[int(round(2*r)) for r in ranks]; counts={0:1}
    for rank in doubled:
        nxt=dict(counts)
        for v,c in counts.items(): nxt[v+rank]=nxt.get(v+rank,0)+c
        counts=nxt
    obs2=int(round(2*wp)); center=sum(doubled)
    p=min(1.0,sum(c for v,c in counts.items() if abs(2*v-center)>=abs(2*obs2-center))/(2**len(nz)))
    return p,(2*wp-total)/total if total else 0.0

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stress=[]; sources={}
    for t in TOPOS:
        attempts=[p for p in (STRESS/t).glob("*/all_seed_summary.csv")]
        if len(attempts)!=1: raise RuntimeError(f"expected exactly one final summary for {t}, got {attempts}")
        rows=read(attempts[0]); sources[str(attempts[0].relative_to(BUNDLE))]=hashlib.sha256(attempts[0].read_bytes()).hexdigest()
        stress.extend(rows)
        if len(rows)!=600: raise RuntimeError(f"{t}: expected 600 rows, got {len(rows)}")
    write(OUT/"stress_per_seed_all_topologies.csv", stress)
    stress_summary=[]
    for t in TOPOS:
      for sc in SCENARIOS:
       for pol in (p+"_protected" for p in POLICIES):
        rr=[r for r in stress if r['topology']==t and r['scenario']==sc and r['algorithm']==pol]
        if len(rr)!=20: raise RuntimeError((t,sc,pol,len(rr)))
        m,sd=avg_sd(rr,'safe_acceptance_rate')
        stress_summary.append(dict(topology=t,scenario=sc,algorithm=pol,n=len(rr),mean=m,sample_sd=sd))
    write(OUT/"stress_summary.csv",stress_summary)
    names={'vietnam':'Vietnam','nsfnet':'NSFNET','geant2':'GEANT2'}
    # Paired HARP comparisons with the identical traces present in each benchmark CSV.
    paired=[]
    for t in TOPOS[:3]:
      for sc in SCENARIOS:
       for baseline in ('saf_h','cspf'):
        a={int(r['seed']):float(r['safe_acceptance_rate']) for r in stress if r['topology']==t and r['scenario']==sc and r['algorithm']=='harp_protected'}
        b={int(r['seed']):float(r['safe_acceptance_rate']) for r in stress if r['topology']==t and r['scenario']==sc and r['algorithm']==baseline+'_protected'}
        seeds=sorted(a)
        if len(seeds)!=20 or set(seeds)!=set(b): raise RuntimeError('paired stress coverage mismatch')
        ds=[a[s]-b[s] for s in seeds]
        rng=random.Random(20261121+len(paired)); bs=sorted(sum(ds[rng.randrange(20)] for _ in range(20))/20 for _ in range(20000))
        pvalue,effect=exact_wilcoxon(ds)
        paired.append(dict(topology=t,scenario=sc,baseline=baseline,n=20,mean_delta_pp=statistics.mean(ds),sample_sd_delta_pp=statistics.stdev(ds),ci95_low_pp=bs[499],ci95_high_pp=bs[19499],wilcoxon_exact_p=pvalue,rank_biserial=effect))
    # Holm is adjusted independently for the SAF-H and CSPF nine-test families.
    for baseline in ('saf_h','cspf'):
      fam=[r for r in paired if r['baseline']==baseline]; order=sorted(range(9),key=lambda i:fam[i]['wilcoxon_exact_p']); running=0
      for rank,i in enumerate(order):
        running=max(running,min(1,(9-rank)*fam[i]['wilcoxon_exact_p'])); fam[i]['holm_p']=running
    write(OUT/"stress_paired_statistics.csv",paired)
    prof={'elephant_stress':'E','burst_surge':'B','chaos':'C'}
    for baseline,label in [('saf_h','benchmark_paired_rows.tex'),('cspf','cspf_paired_rows.tex')]:
      tex=[]
      for r in [x for x in paired if x['baseline']==baseline]:
       tex.append(f"{names[r['topology']]} & {prof[r['scenario']]} & {r['mean_delta_pp']:.3f} & [{r['ci95_low_pp']:.3f}, {r['ci95_high_pp']:.3f}] & {r['holm_p']:.3g} & {r['rank_biserial']:.3f} "+r'\\')
      (OUT/label).write_text('\n'.join(tex)+'\n')
    lines=[]
    codes={'elephant_stress':'E','burst_surge':'B','chaos':'C'}
    for t in TOPOS[:3]:
      for sc in SCENARIOS:
        cells=[]
        for p in POLICIES:
          z=next(x for x in stress_summary if x['topology']==t and x['scenario']==sc and x['algorithm']==p+'_protected')
          cells.append((fmt(z['mean']),fmt(z['sample_sd'])))
        best=max(range(len(cells)),key=lambda i:float(cells[i][0]))
        vals=[(r'\textbf{'+m+r'}' if i==best else m)+r' $\pm$ '+sd for i,(m,sd) in enumerate(cells)]
        lines.append(names[t]+' & '+codes[sc]+' & '+' & '.join(vals)+r' \\')
    (OUT/"stress_table_rows.tex").write_text('\n'.join(lines)+'\n')

    load=[]; chain=[]
    for t in ('vietnam','nsfnet','geant2'):
      for n in (0,25,50,100):
       p=REFRESH/'load_chain'/t/f'chains_{n}'/f'{t}_load_sweep_per_seed.csv'
       rows=read(p); sources[str(p.relative_to(BUNDLE))]=hashlib.sha256(p.read_bytes()).hexdigest()
       if len(rows)!=1400: raise RuntimeError(f"{p}: expected 1400 rows, got {len(rows)}")
       for r in rows:
        r['initial_active_chains']=str(n)
       load.extend(rows)
       if n==0: chain.extend(rows)
    write(OUT/"load_chain_per_seed.csv",load)
    (OUT/"load_chain_sources.json").write_text(json.dumps(sources,indent=2)+"\n")
    # 0-chain load sweep: protected-policy means and sample SD for seven intensities.
    load_summary=[]
    for t in ('vietnam','nsfnet','geant2'):
      rr=[r for r in chain if r['topology']==t and r['algorithm'].endswith('_protected')]
      for lm in sorted({float(r['load_multiplier']) for r in rr}):
       row={'topology':t,'load_multiplier':lm}
       for p in ('traditional_greedy','decoupled_ai','saf_h','harp'):
        sub=[r for r in rr if float(r['load_multiplier'])==lm and r['algorithm']==p+'_protected']
        m,sd=avg_sd(sub,'safe_acceptance_rate'); row[p+'_mean']=m; row[p+'_sample_sd']=sd
       load_summary.append(row)
    write(OUT/"load_sweep_summary.csv",load_summary)
    rows=[]
    for t in ('vietnam','nsfnet','geant2'):
      for lm in sorted({x['load_multiplier'] for x in load_summary if x['topology']==t}):
       x=next(x for x in load_summary if x['topology']==t and x['load_multiplier']==lm)
       vals=[f"{x[p+'_mean']:.2f} $\\pm$ {x[p+'_sample_sd']:.2f}" for p in ('traditional_greedy','decoupled_ai','saf_h','harp')]
       rows.append(names[t]+f" & {lm:.1f} & "+' & '.join(vals)+r' \\')
    (OUT/"load_sweep_table_rows.tex").write_text('\n'.join(rows)+'\n')
    # Unified paired load-sweep statistics and all three unprotected-topology tables.
    paired_load=[]; unprotected=[]
    for t in ('vietnam','nsfnet','geant2'):
      for lm in sorted({float(r['load_multiplier']) for r in chain if r['topology']==t}):
       for p in ('traditional_greedy','decoupled_ai','saf_h','harp'):
        h={int(r['seed']):r for r in chain if r['topology']==t and float(r['load_multiplier'])==lm and r['algorithm']==p+'_unprotected'}
        if len(h)!=20: raise RuntimeError(f'unprotected rows: {t}/{lm}/{p}: {len(h)}')
        fields={'CPU':'admitted_cpu_violation_rate','RAM':'admitted_ram_violation_rate','BW':'admitted_bw_violation_rate','MSD':'msd_violation_rate','unique hard-violation union':'admitted_hard_violation_rate'}
        q={'topology':t,'load_multiplier':f'{lm:.1f}','policy':p,'n_seed_runs':20,'denominator':'offered non-skipped requests; rates are percentages'}
        for label,field in fields.items():
         vals=[float(r[field]) for r in h.values()]
         q[label+'_mean_pct']=statistics.mean(vals);q[label+'_sample_sd_pp']=statistics.stdev(vals)
        unprotected.append(q)
       h={int(r['seed']):float(r['safe_acceptance_rate']) for r in chain if r['topology']==t and float(r['load_multiplier'])==lm and r['algorithm']=='harp_protected'}
       c={int(r['seed']):float(r['safe_acceptance_rate']) for r in chain if r['topology']==t and float(r['load_multiplier'])==lm and r['algorithm']=='saf_h_protected'}
       ds=[h[k]-c[k] for k in sorted(h)]
       rng=random.Random(20261121+len(paired_load)); bs=sorted(sum(ds[rng.randrange(20)] for _ in range(20))/20 for _ in range(20000))
       pvalue,effect=exact_wilcoxon(ds)
       paired_load.append(dict(topology=t,load_multiplier=f'{lm:.1f}',n_pairs=20,n_effective=sum(d!=0 for d in ds),mean_delta_pp=statistics.mean(ds),sample_sd_delta_pp=statistics.stdev(ds),ci95_low_pp=bs[499],ci95_high_pp=bs[19499],wilcoxon_exact_p=pvalue,rank_biserial=effect if any(ds) else '',zero_differences=20-sum(d!=0 for d in ds)))
    order=sorted(range(len(paired_load)),key=lambda i:paired_load[i]['wilcoxon_exact_p']); running=0
    for rank,i in enumerate(order): running=max(running,min(1,(21-rank)*paired_load[i]['wilcoxon_exact_p']));paired_load[i]['holm_p_21']=running
    write(OUT/"load_sweep_paired_statistics.csv",paired_load)
    tab=[]
    for r in paired_load:
      effect='--' if r['rank_biserial']=='' else f"{r['rank_biserial']:.3f}"
      tab.append(f"{r['topology'].upper()} & {float(r['load_multiplier']):.1f} & {r['mean_delta_pp']:.3f} & [{r['ci95_low_pp']:.3f}, {r['ci95_high_pp']:.3f}] & {r['wilcoxon_exact_p']:.3g} & {effect} & {r['n_effective']} & {r['holm_p_21']:.3g} "+r'\\')
    (OUT/"load_sweep_paired_rows.tex").write_text('\n'.join(tab)+'\n')
    legacy= BUNDLE/'docs/AIO-mesh-rev1/evidence/load_sweep'
    write(legacy/'mentor_b2_load_sweep_21.csv',paired_load)
    pairtex=[r'\begin{table*}[p]',r'\centering',r'\color{revisiongreen}\small',r'\begin{tabular}{llrrrrrr}',r'\toprule',r'Topology & Intensity & $\Delta$ (pp) & 95\% CI & $p$ & $r_{rb}$ & $n_{eff}$ & $p_{Holm}$ \\',r'\midrule']+tab+[r'\bottomrule',r'\end{tabular}',r'\caption{Paired HARP--SAF-H safe-acceptance differences in the refreshed-model load sweep. $Δ$ is the matched-seed mean; CI is a 20,000-resample paired percentile-bootstrap 95\% interval. $p$ is the exact two-sided Wilcoxon signed-rank test after dropping zeros and averaging tied absolute ranks; Holm correction covers all 21 topology--intensity tests.}',r'\label{tab:load_sweep_paired_statistics}',r'\end{table*}']
    (legacy/'mentor_b2_load_sweep_21.tex').write_text('\n'.join(pairtex)+'\n')
    write(legacy/'mentor_d1_unprotected_load_sweep.csv',unprotected)
    tex=[]
    for t in ('vietnam','nsfnet','geant2'):
      tex.extend([r'\begin{table*}[p]',r'\centering',r'\color{revisiongreen}\small',r'\begin{tabular}{llrrrrr}',r'\toprule',r'Intensity & Policy & CPU & RAM & BW & MSD & Any hard violation \\',r'\midrule'])
      for r in [x for x in unprotected if x['topology']==t]:
       label={'traditional_greedy':'Greedy','decoupled_ai':'DAI','saf_h':'SAF-H','harp':'HARP'}[r['policy']]
       vals=[]
       for c in ('CPU','RAM','BW','MSD','unique hard-violation union'): vals.append(f"{r[c+'_mean_pct']:.3f} $\\pm$ {r[c+'_sample_sd_pp']:.3f}")
       tex.append(f"{float(r['load_multiplier']):.1f} & {label} & "+' & '.join(vals)+r' \\')
      label={'vietnam':'Vietnam','nsfnet':'NSFNET','geant2':'GEANT2'}[t]
      tex.extend([r'\bottomrule',r'\end{tabular}',r'\caption{'+label+r' offered-intensity experiment with admission disabled. Rates are mean and sample SD in percent over 20 seeds. The denominator is all offered requests; violation categories can overlap.}',r'\label{tab:load_sweep_unprotected'+('_'+t if t!='vietnam' else '')+r'}',r'\end{table*}'])
    (legacy/'mentor_d1_unprotected_load_sweep.tex').write_text('\n'.join(tex)+'\n')
    chain_rows=[]
    for t in ('vietnam','nsfnet','geant2'):
      for n in (0,25,50,100):
       row={'topology':t,'chains':n}
       for p in ('harp','saf_h'):
        sub=[r for r in load if r['topology']==t and int(r['initial_active_chains'])==n and r['algorithm']==p+'_protected' and float(r['load_multiplier'])==1.0]
        if len(sub)!=20: raise RuntimeError(f"chain cell n={len(sub)} {t}/{n}/{p}")
        row[p+'_mean'],row[p+'_sample_sd']=avg_sd(sub,'safe_acceptance_rate')
       chain_rows.append(row)
    write(OUT/"background_chain_summary.csv",chain_rows)
    tex=[]
    for x in chain_rows:
      tex.append(f"{names[x['topology']]} & {x['chains']} & {x['harp_mean']:.2f} $\\pm$ {x['harp_sample_sd']:.2f} & {x['saf_h_mean']:.2f} $\\pm$ {x['saf_h_sample_sd']:.2f} "+r'\\')
    (OUT/"background_chain_table_rows.tex").write_text('\n'.join(tex)+'\n')
    oracle_rows=[]
    for t in ('vietnam','nsfnet','geant2'):
      p=next((REFRESH/'oracle'/t).glob('*/missed_feasible_oracle.json'))
      d=json.loads(p.read_text())
      for policy in ('harp','saf_h'):
       rr=[r for r in d['samples'] if r['policy']==policy]
       if len(rr)!=10: raise RuntimeError(f"oracle seeds {t}/{policy}: {len(rr)}")
       selected=sum(int(r['selected_rejections']) for r in rr)
       alternatives=sum(int(r['selected_rejections_with_feasible_alternative']) for r in rr)
       rates=[float(r['avoidable_rejection_rate_pct']) for r in rr]
       oracle_rows.append(dict(topology=t,policy=policy,n_seeds=len(rr),sampled_states=sum(int(r['sampled_decisions']) for r in rr),
         selected_rejections=selected,with_accepted_alternative=alternatives,
         conditional_rate_mean_pct=statistics.mean(rates),conditional_rate_sample_sd_pct=statistics.stdev(rates),
         all_mask_empty_samples=sum(int(r['all_mask_empty_samples']) for r in rr),source=str(p.relative_to(BUNDLE)),
         source_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    write(OUT/"pair_oracle_summary.csv",oracle_rows)
    (OUT/"README.md").write_text("""# Refreshed N² model evidence tables\n\nGenerated by `scripts/rev1/summarize_model_refresh_evidence.py` from completed per-seed benchmark CSVs and model-refresh load/chain CSVs. Stress values use mean and **sample SD** across 20 evaluation seeds. Load and chain values use the same paired seeds and traces recorded in source CSVs. Source SHA-256 values are in `load_chain_sources.json`; full benchmark and refresh manifests remain under `results/evidence/`. No historical 2N outputs are included.\n""")
    output_files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!='generator_manifest.json')
    inputs={k:v for k,v in sources.items()}
    manifest={
      'generator': 'scripts/rev1/summarize_model_refresh_evidence.py',
      'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'command': 'python3 scripts/rev1/summarize_model_refresh_evidence.py',
      'repository_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
      'stress_launch_manifest': str((STRESS/'launch_manifest.json').relative_to(BUNDLE)),
      'refresh_launch_manifest': str((REFRESH/'launch_manifest.json').relative_to(BUNDLE)),
      'inputs_sha256': inputs,
      'outputs_sha256': {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output_files},
      'analysis': {'seed_aggregation':'arithmetic mean and sample SD', 'paired_tests':'exact two-sided sign-flip Wilcoxon signed-rank; zeros dropped; tied absolute ranks averaged', 'bootstrap':'20,000 paired percentile resamples, deterministic seed', 'holm':'21 load contrasts; separate nine-condition stress comparison families'}
    }
    (OUT/'generator_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f"stress_rows={len(stress)} load_chain_rows={len(load)} stress_cells={len(stress_summary)}")

if __name__=='__main__': main()
