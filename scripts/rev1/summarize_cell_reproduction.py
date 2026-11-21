#!/usr/bin/env python3
"""Compare requested cell reruns against their matching original seed rows."""
import csv,hashlib,json
from pathlib import Path
B=Path(__file__).resolve().parents[2];P=B/'results/evidence/completion_20261121/reruns';E=B/'results/evidence';O=B/'docs/AIO-mesh-rev1/evidence/mentor_completion_20261121';O.mkdir(exist_ok=True,parents=True)
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def one(pattern):
 x=list(pattern);assert len(x)==1,x;return x[0]
cases=[('vietnam_burst_42',one((P/'benchmark').glob('*/all_seed_summary.csv')),one((E/'multinode_benchmark_20261120_084017/vietnam').glob('*/all_seed_summary.csv')),'algorithm'),('nsfnet_chaos_7',P/'ablation/nsfnet/chaos/harp_ablation_summary.csv',B/'results/rev1/e3_timed/nsfnet/chaos/harp_ablation_summary.csv','key'),('geant2_load12_2024',P/'load/load_geant2_1.2_2024.csv',E/'model_refresh_reruns_20261120_163000/load_chain/geant2/chains_0/geant2_load_sweep_per_seed.csv','algorithm')]
out=[];inputs={}
for case,rp,op,key in cases:
 rr=read(rp);original=read(op)
 for p in (rp,op):inputs[str(p.relative_to(B))]=hashlib.sha256(p.read_bytes()).hexdigest()
 for r in rr:
  if case=='vietnam_burst_42' and not r[key].endswith('_protected'):continue
  candidate=[x for x in original if x[key]==r[key] and x['seed']==r['seed'] and (case!='vietnam_burst_42' or x['scenario']=='burst_surge') and (case!='geant2_load12_2024' or float(x['load_multiplier'])==1.2)]
  if len(candidate)!=1:raise ValueError((case,r[key],len(candidate)))
  q=candidate[0];delta=float(r['safe_acceptance_rate'])-float(q['safe_acceptance_rate']);match=r['trace_sha256']==q['trace_sha256'];out.append(dict(case=case,seed=r['seed'],policy=r[key],original_safe_acceptance=q['safe_acceptance_rate'],rerun_safe_acceptance=r['safe_acceptance_rate'],delta_pp=delta,trace_match=match,policy_source_match=(r.get('policy_source')==q.get('policy_source')) if case=='nsfnet_chaos_7' else 'not recorded in row'))
with (O/'cell_rerun_comparison.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]),lineterminator='\n');w.writeheader();w.writerows(out)
(O/'cell_rerun_manifest.json').write_text(json.dumps({'inputs_sha256':inputs,'note':'compares safe acceptance, offered trace and ablation policy source only; timing and other metrics are not asserted identical'},indent=2)+'\n')
print('rows',len(out),'nonzero',sum(abs(r['delta_pp'])>1e-9 for r in out),'trace mismatches',sum(not r['trace_match'] for r in out))
