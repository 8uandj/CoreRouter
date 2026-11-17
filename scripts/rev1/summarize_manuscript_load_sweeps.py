"""Validate and summarize all current-code sweep modes for manuscript evidence."""
import csv,json,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/rev1/load_sweep/current_code_20261117'
OUT=ROOT/'docs/AIO-mesh-rev1/evidence/load_sweep'
OUT.mkdir(parents=True,exist_ok=True)
allrows=[];summary=[];paired=[];sources={}
for topo in ['vietnam','nsfnet','geant2']:
 path=DATA/f'{topo}_load_sweep_per_seed.csv';rows=list(csv.DictReader(path.open()));assert len(rows)==1120
 sources[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
 allrows.extend(rows)
 for load in sorted({float(r['load_multiplier']) for r in rows}):
  for alg in sorted({r['algorithm'] for r in rows}):
   rr=[r for r in rows if float(r['load_multiplier'])==load and r['algorithm']==alg];assert len(rr)==20
   item={'topology':topo,'load_multiplier':load,'algorithm':alg,'n_seeds':20}
   for metric in ['safe_acceptance_rate','candidate_hard_infeasible_rate','admitted_hard_violation_rate','rejection_cpu_rate','rejection_ram_rate','rejection_msd_rate','rejection_bw_rate','rejection_other_rate']:
    v=[float(r[metric]) for r in rr];item[metric+'_mean']=statistics.mean(v);item[metric+'_sample_sd']=statistics.stdev(v)
   summary.append(item)
 ds=json.load(open(DATA/f'{topo}_load_sweep_paired.json'))
 for d in ds:d['topology']=topo
 paired.extend(ds)
# Correct across the full family of 21 topology-load comparisons.
order=sorted(range(len(paired)),key=lambda i:paired[i]['wilcoxon_p']);running=0
for rank,i in enumerate(order):
 running=max(running,min(1,(len(order)-rank)*paired[i]['wilcoxon_p']))
 paired[i]['holm_p_21']=running
for name,rows in [('all_modes_summary.csv',summary),('all_modes_per_seed.csv',allrows)]:
 with (OUT/name).open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(OUT/'paired_statistics_21.json').write_text(json.dumps(paired,indent=2)+'\n')
(OUT/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
# Generate protected-method mean/SD rows, including all seven loads.
lines=[]
for topo in ['vietnam','nsfnet','geant2']:
 for load in [.2,.4,.6,.8,1.,1.2,1.5]:
  cells=[]
  for alg in ['traditional_greedy_protected','decoupled_ai_protected','saf_h_protected','harp_protected']:
   r=next(x for x in summary if x['topology']==topo and x['load_multiplier']==load and x['algorithm']==alg)
   cells.append(f"{r['safe_acceptance_rate_mean']:.2f} $\\pm$ {r['safe_acceptance_rate_sample_sd']:.2f}")
  lines.append(('Vietnam' if topo=='vietnam' else topo.upper())+f' & {load:.1f} & '+' & '.join(cells)+' '+chr(92)*2)
(OUT/'protected_table_rows.tex').write_text('\n'.join(lines)+'\n')
print('Wrote all 168 mode/load summaries, 3360 seed rows and 21 corrected paired comparisons.')
for d in paired:
 if d['load_multiplier']>=1:print(d['topology'],d['load_multiplier'],f"delta={d['mean_delta']:.3f}",f"Holm21={d['holm_p_21']:.3g}")
