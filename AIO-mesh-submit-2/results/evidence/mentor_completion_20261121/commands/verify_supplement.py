#!/usr/bin/env python3
"""Validate the original ten and supplementary ten seed results without overwriting them."""
import csv,json,hashlib
from pathlib import Path
p=Path('AIO-mesh-submit-2/results/evidence/mentor_completion_20261121');q=p/'supplement_10_seeds'
old=[42,100,2024,8888,9999,7,17,73,314,2718];new=[11,23,47,89,101,211,512,1024,4096,8192];missing=[];checked=0
for t in ('vietnam','nsfnet','geant2'):
 for root,seeds in [(p,old),(q,new)]:
  for seed in seeds:
   for name in ('seeded_bursty','sparse_gat_mlp'):
    f=root/name/t/f'seed_{seed}.csv'
    if not f.is_file():missing.append(str(f));continue
    rows=list(csv.DictReader(f.open()));checked+=1
    if len(rows)!=(5 if name=='seeded_bursty' else 2) or len({r['trace_sha256'] for r in rows})!=1:raise ValueError(f'invalid paired output {f}')
   for n in (0,25,50,100):
    for load in ([.2,.4,.6,.8,1.,1.2,1.5] if n==0 else [1.]):
     f=root/'seeded_load_chains'/f'{t}_{n}'/f'load_{load}_seed_{seed}.csv'
     if not f.is_file():missing.append(str(f));continue
     rows=list(csv.DictReader(f.open()));checked+=1
     if len(rows)!=5 or len({r['trace_sha256'] for r in rows})!=1:raise ValueError(f'invalid paired output {f}')
   sensitivity='saf_sensitivity' if root==p else 'saf_weight_sensitivity'
   for label in ('baseline','double_latency','double_cpu','double_hops'):
    for load in (1.2,1.5):
     f=root/sensitivity/t/f'{label}_{load}_{seed}.csv'
     if not f.is_file():missing.append(str(f));continue
     rows=list(csv.DictReader(f.open()));checked+=1
     if len(rows)!=1 or not rows[0].get('trace_sha256'):raise ValueError(f'invalid output {f}')
for seed in (7,2024):
 base=p/'independent_training'/f'matched_seed_{seed}'
 for name in ('dgrl_v11_final_vietnam.zip','vec_normalize_v11_vietnam.pkl'):
  if not (base/name).is_file():missing.append(str(base/name))
for train_seed in (42,7,2024):
 for eval_seed in old+new:
  f=p/'independent_training/evaluation'/f'train_{train_seed}_eval_{eval_seed}.csv'
  if not f.is_file(): missing.append(str(f))
for eval_seed in old+new:
 files=[p/'independent_training/evaluation'/f'train_{s}_eval_{eval_seed}.csv' for s in (42,7,2024)]
 if all(f.is_file() for f in files):
  traces=[next(csv.DictReader(f.open()))['trace_sha256'] for f in files]
  if len(set(traces))!=1: raise ValueError(f'independent checkpoint trace mismatch seed {eval_seed}')
report={'checked_csv_files':checked,'expected_csv_files':1200,'missing':missing,'seed_sets':{'original':old,'supplementary':new},'status':'complete' if not missing and checked==1200 else 'incomplete'}
(p/'completion_validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));raise SystemExit(0 if report['status']=='complete' else 1)
