#!/usr/bin/env python3
"""Build revision table rows from retained per-seed evaluation results."""
import csv,statistics
from pathlib import Path
B=Path(__file__).resolve().parents[2]; O=B/'docs/AIO-mesh-rev1/evidence/completion_20261121';O.mkdir(parents=True,exist_ok=True)
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def cell(rows):
 if len(rows)!=20:raise ValueError(f'expected 20 rows, got {len(rows)}')
 v=[float(r['safe_acceptance_rate']) for r in rows];return f'{statistics.mean(v):.2f} $\\pm$ {statistics.stdev(v):.2f}'
names={'vietnam':'Vietnam','nsfnet':'NSFNET','geant2':'GEANT2'};sc={'elephant_stress':'E','burst_surge':'B','chaos':'C'}
p=read(B/'results/evidence/completion_20261121/analysis/strongest_baseline_paired.csv');lines=[]
for r in p:
 if r['topology'] not in names: continue
 baseline={'traditional_greedy_protected':'Greedy','decoupled_ai_protected':'DAI','saf_h_protected':'SAF-H','cspf_protected':'CSPF'}[r['baseline_selected_by_mean']]
 lines.append(f"{names[r['topology']]} & {sc[r['scenario']]} & {baseline} & {float(r['mean_delta_pp']):.3f} & [{float(r['ci95_low']):.3f}, {float(r['ci95_high']):.3f}] & {float(r['holm_p']):.3g} & {r['n_effective']} "+r'\\')
(O/'best_baseline.tex').write_text('\n'.join(lines)+'\n')
timing=read(B/'results/evidence/completion_20261121/analysis/timing_components.csv');lines=[]
for n in (25,50,100):
 r=next(x for x in timing if x['topology']==f'synthetic_{n}' and x['scenario']=='burst_surge' and x['algorithm']=='harp_protected')
 fields=['normalization_ms_p95_ms_mean','mask_construction_ms_p95_ms_mean','policy_inference_ms_p95_ms_mean','decision_latency_p95_ms_mean'];lines.append(f'{n} & '+' & '.join(f"{float(r[k]):.3f}" for k in fields)+r' \\')
(O/'timing_components.tex').write_text('\n'.join(lines)+'\n')
base=B/'results/evidence/model_refresh_reruns_20261120_163000/load_chain';load=[];chains=[]
for t in names:
 for n in (0,25,50,100):
  rows=read(base/t/f'chains_{n}'/f'{t}_load_sweep_per_seed.csv')
  if n==0:
   for intensity in (.2,.4,.6,.8,1.,1.2,1.5):
    vals=[cell([r for r in rows if float(r['load_multiplier'])==intensity and r['algorithm']==p+'_protected']) for p in ('traditional_greedy','decoupled_ai','saf_h','cspf','harp')]
    load.append(f'{names[t]} & {intensity:.1f} & '+' & '.join(vals)+r' \\')
  vals=[cell([r for r in rows if float(r['load_multiplier'])==1. and r['algorithm']==p+'_protected']) for p in ('harp','saf_h','cspf')]
  chains.append(f'{names[t]} & {n} & '+' & '.join(vals)+r' \\')
(O/'load_cspf.tex').write_text('\n'.join(load)+'\n');(O/'chains_cspf.tex').write_text('\n'.join(chains)+'\n')
