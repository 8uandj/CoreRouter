"""Describe fixed-checkpoint benchmark acceptance, service QoS and local timing.

Local wall-clock fields are descriptive only: execution contention is not
controlled across the archived runs. Service latency is simulated, not inference.
"""
import csv,glob,statistics,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/AIO-mesh-rev1/evidence/policy_tradeoffs'
OUT.mkdir(parents=True,exist_ok=True)
records=[];sources={}
for topo in ['vietnam','nsfnet','geant2']:
 for scenario in ['elephant_stress','burst_surge','chaos']:
  if topo=='geant2':path=ROOT/'results/rev1/geant2/benchmark/current_code_three_workloads/20261117_205637/all_seed_summary.csv'
  else:
   paths=glob.glob(str(ROOT/f'results/rev1/{topo}/benchmark/{scenario}/*/all_seed_summary.csv'))
   assert len(paths)==1,paths
   path=Path(paths[0])
  sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
  rows=[r for r in csv.DictReader(path.open()) if r['scenario']==scenario]
  for alg in ['harp_protected','saf_h_protected']:
   group=[r for r in rows if r['algorithm']==alg];assert len(group)==20
   item={'topology':topo,'scenario':scenario,'algorithm':alg,'n_seeds':len(group)}
   for metric in ['acceptance_rate','safe_acceptance_rate','avg_latency_ms','sla_violation_rate','decision_latency_p95_ms','run_wall_time_s','offered_decisions_per_s']:
    vals=[float(r[metric]) for r in group if r.get(metric)]
    assert len(vals)==20,(metric,len(vals))
    item[metric+'_mean']=statistics.mean(vals);item[metric+'_sample_sd']=statistics.stdev(vals)
   records.append(item)
with (OUT/'benchmark_tradeoffs.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
(OUT/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
(OUT/'README.md').write_text('''# Benchmark policy tradeoffs\n\n18 groups = 3 substrates × 3 workloads × HARP/SAF-H, 20 seeds each. Acceptance, simulated service latency and admitted-request SLA violations describe the fixed-policy outcomes. Service latency concerns different admitted request populations under each policy, so it is not a paired latency treatment effect. Local decision p95 and elapsed throughput are descriptive: execution contention was not controlled across all archived jobs. They do not establish a controlled computation advantage. A serialized same-machine rerun with warm-up and machine/load metadata is required for that claim.\n''')
print('Exported 18 policy tradeoff groups with source hashes.')
