"""Rebuild stress QoS and unprotected violations from refreshed per-seed rows."""
import csv,hashlib,json,statistics
from pathlib import Path
BASE=Path(__file__).resolve().parents[2]; B=BASE if BASE.name=='AIO-mesh-submit-2' else BASE/'AIO-mesh-submit-2'; ROOT=B/'docs/AIO-mesh-rev1'; SOURCE=ROOT/'evidence/model_refresh_20261120/stress_per_seed_all_topologies.csv'; OUT=ROOT/'evidence/mentor_completion_20261121';OUT.mkdir(parents=True,exist_ok=True)
with SOURCE.open(newline='') as f:rows=list(csv.DictReader(f))
tops={'vietnam':'Vietnam','nsfnet':'NSFNET','geant2':'GEANT2'};scens={'elephant_stress':'Elephant stress','burst_surge':'Burst surge','chaos':'Chaos'};qos=[];unprot=[];tex=[]
for t,label in tops.items():
 for sc,sc_label in scens.items():
  vals=[]
  for alg in ('harp_protected','saf_h_protected'):
   x=[r for r in rows if r['topology']==t and r['scenario']==sc and r['algorithm']==alg]
   if len(x)!=20:raise ValueError((t,sc,alg,len(x)))
   item={'topology':t,'scenario':sc,'algorithm':alg,'n_seed':len(x)}
   for metric in ('avg_latency_ms','sla_violation_rate'):
    v=[float(r[metric]) for r in x];item[metric+'_mean']=statistics.mean(v);item[metric+'_sample_sd']=statistics.stdev(v)
   qos.append(item);vals += [f"{item['avg_latency_ms_mean']:.2f}",f"{item['sla_violation_rate_mean']:.2f}"]
  tex.append(f'{label} & {sc_label} & '+' & '.join(vals)+r' \\')
  for alg in ('traditional_greedy','decoupled_ai','saf_h','cspf','harp'):
   x=[r for r in rows if r['topology']==t and r['scenario']==sc and r['algorithm']==alg+'_unprotected']
   if len(x)!=20:raise ValueError((t,sc,alg,len(x)))
   z={'topology':t,'scenario':sc,'algorithm':alg,'n_seed':20}
   for metric in ('admitted_cpu_violation_rate','admitted_ram_violation_rate','admitted_bw_violation_rate','msd_violation_rate','admitted_hard_violation_rate'):
    v=[float(r[metric]) for r in x];z[metric+'_mean']=statistics.mean(v);z[metric+'_sample_sd']=statistics.stdev(v)
   unprot.append(z)
(ROOT/'generated/qos_rows.tex').write_text('\n'.join(tex)+'\n')
for name,items in [('qos_summary.csv',qos),('unprotected_stress_summary.csv',unprot)]:
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(items[0]),lineterminator='\n');w.writeheader();w.writerows(items)
labels={'traditional_greedy':'Greedy','decoupled_ai':'DAI','saf_h':'SAF-H','cspf':'CSPF','harp':'HARP'}
lines=[]
for r in unprot:
 metrics=['admitted_cpu_violation_rate','admitted_ram_violation_rate','admitted_bw_violation_rate','msd_violation_rate','admitted_hard_violation_rate']
 lines.append(f"{tops[r['topology']]} & {scens[r['scenario']]} & {labels[r['algorithm']]} & "+' & '.join(f"{r[k+'_mean']:.3f}" for k in metrics)+r' \\')
(OUT/'unprotected_stress_rows.tex').write_text('\n'.join(lines)+'\n')
(OUT/'qos_unprotected_manifest.json').write_text(json.dumps({'source':str(SOURCE.relative_to(B)),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'qos_denominator':'per-seed admitted requests; seed-level mean then arithmetic mean across 20 seeds','violation_denominator':'offered non-skipped requests; constraint categories overlap; union is unique admitted hard violation'},indent=2)+'\n')
print('qos rows',len(qos),'unprotected rows',len(unprot))
