#!/usr/bin/env python3
"""Analyze refreshed benchmark and timing components from retained seed records."""
import csv, hashlib, importlib.util, json, random, statistics
from pathlib import Path
B=Path(__file__).resolve().parents[2]; O=B/'results/evidence/completion_20261121/analysis'; O.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('summary',B/'scripts/rev1/summarize_model_refresh_evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=B/'docs/AIO-mesh-rev1/evidence/model_refresh_20261120/stress_per_seed_all_topologies.csv'
with p.open(newline='') as f: rows=list(csv.DictReader(f))
def write(name,rr):
 with (O/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]),lineterminator='\n');w.writeheader();w.writerows(rr)
paired=[];timing=[]
for top in m.TOPOS:
 for sc in m.SCENARIOS:
  g=[r for r in rows if r['topology']==top and r['scenario']==sc and r['algorithm'].endswith('_protected')]
  by={a:{int(r['seed']):r for r in g if r['algorithm']==a} for a in [p+'_protected' for p in m.POLICIES]}
  if any(len(x)!=20 for x in by.values()):raise ValueError((top,sc))
  for seed in by['harp_protected']:
   if len({by[a][seed]['trace_sha256'] for a in by})!=1:raise ValueError('trace mismatch')
  best=max((p+'_protected' for p in m.POLICIES if p!='harp'),key=lambda a:statistics.mean(float(r['safe_acceptance_rate']) for r in by[a].values()))
  ds=[float(by['harp_protected'][s]['safe_acceptance_rate'])-float(by[best][s]['safe_acceptance_rate']) for s in sorted(by[best])]
  rng=random.Random(20261121+len(paired));bs=sorted(statistics.mean(rng.choice(ds) for _ in ds) for _ in range(20000));pval,effect=m.exact_wilcoxon(ds)
  paired.append(dict(topology=top,scenario=sc,baseline_selected_by_mean=best,n=20,n_effective=sum(d!=0 for d in ds),mean_delta_pp=statistics.mean(ds),sample_sd_delta_pp=statistics.stdev(ds),ci95_low=bs[499],ci95_high=bs[19499],p=pval,rank_biserial=effect))
  for alg in by:
   x={'topology':top,'scenario':sc,'algorithm':alg,'n':20}
   for field in ('decision_latency_p95_ms','normalization_ms_p95_ms','mask_construction_ms_p95_ms','policy_inference_ms_p95_ms','admission_validation_ms_p95_ms','feasible_set_ms_p95_ms','heuristic_selection_ms_p95_ms'):
    vals=[float(r[field]) for r in by[alg].values() if r.get(field) not in ('',None)]
    x[field+'_mean']=statistics.mean(vals) if vals else '';x[field+'_n']=len(vals)
   timing.append(x)
for subset in (paired[:9],paired[9:]):
 order=sorted(range(len(subset)),key=lambda i:subset[i]['p']);running=0
 for rank,i in enumerate(order):
  running=max(running,min(1,(len(order)-rank)*subset[i]['p']));subset[i]['holm_p']=running
write('strongest_baseline_paired.csv',paired);write('timing_components.csv',timing)
(O/'manifest.json').write_text(json.dumps({'input':str(p.relative_to(B)),'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bootstrap_replicates':20000,'holm':'separate 9-cell real and 9-cell synthetic families','timing_scope':'means of seed-level p95 values; benchmark runs executed concurrently; components may overlap and cannot be added into p95','caveat':'baseline chosen on same data; results exploratory, selection not accounted for'},indent=2)+'\n')
print('paired',len(paired),'timing',len(timing))
