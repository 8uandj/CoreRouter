from pathlib import Path
import csv,statistics,json,hashlib
root=Path(__file__).resolve().parents[4]; out=root/'docs/AIO-mesh-rev1/evidence/reconciliation_20261124';out.mkdir(exist_ok=True)
sources={}
def read(p):
 sources[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
 return list(csv.DictReader(p.open()))
source=root/'AIO-mesh-submit-2/docs/AIO-mesh-rev1/evidence/model_refresh_20261120/stress_per_seed_all_topologies.csv'
rows=read(source);summary=[]
for n in (25,50,100):
 for pol in ('harp','saf_h'):
  rr=[r for r in rows if r['topology']==f'synthetic_{n}' and r['scenario']=='burst_surge' and r['algorithm']==pol+'_protected']
  assert len(rr)==20 and len({r['seed'] for r in rr})==20
  other=[r for r in rows if r['topology']==f'synthetic_{n}' and r['scenario']=='burst_surge' and r['algorithm']==('saf_h' if pol=='harp' else 'harp')+'_protected']
  assert {r['seed']:r['trace_sha256'] for r in rr}=={r['seed']:r['trace_sha256'] for r in other}
  d={'nodes':n,'policy':pol,'n_seeds':20}
  fields={'normalize':'normalization_ms_p95_ms','candidate':'mask_construction_ms_p95_ms' if pol=='harp' else 'feasible_set_ms_p95_ms','selection':'policy_inference_ms_p95_ms' if pol=='harp' else 'heuristic_selection_ms_p95_ms','validation':'admission_validation_ms_p95_ms','decision':'decision_latency_p95_ms'}
  for name,col in fields.items():
   vals=[float(r[col]) for r in rr if r[col]]
   if name=='normalize' and pol=='saf_h':continue
   assert len(vals)==20
   d[name+'_mean']=statistics.mean(vals);d[name+'_sd']=statistics.stdev(vals)
  summary.append(d)
(out/'timing_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
# Background occupancy: retain the actual named substrates rather than claiming synthetic-size cross-product.
loadsource=root/'AIO-mesh-submit-2/docs/AIO-mesh-rev1/evidence/model_refresh_20261120/load_chain_per_seed.csv'
load=read(loadsource);occupancy=[]
for topo in ('vietnam','nsfnet','geant2'):
 for n in (0,25,50,100):
  d={'topology':topo,'background_chains':n}
  for pol in ('harp','saf_h'):
   rr=[r for r in load if r['topology']==topo and int(float(r['initial_active_chains']))==n and float(r['load_multiplier'])==1.0 and r['algorithm']==pol+'_protected']
   assert len(rr)==20,(topo,n,pol,len(rr))
   vals=[float(r['admission_validation_ms_p95_ms']) for r in rr];d[pol+'_mean']=statistics.mean(vals);d[pol+'_sd']=statistics.stdev(vals)
  occupancy.append(d)
(out/'occupancy_validation.json').write_text(json.dumps(occupancy,indent=2)+'\n')
(out/'sources.json').write_text(json.dumps({'inputs_sha256':sources,'scope':'Existing concurrent shared-host stress benchmark, Bursty, 20 matched seeds; occupancy on named substrates, not a crossed synthetic-size experiment. No reruns.','aggregation':'mean and sample SD of seed-level P95; validation timer covers predicates, excludes reservation/actuation.'},indent=2)+'\n')
