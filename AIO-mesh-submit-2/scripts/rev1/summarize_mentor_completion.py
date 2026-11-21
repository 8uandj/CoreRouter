#!/usr/bin/env python3
"""Summarize completed mentor follow-up from matched, retained seed records."""
import csv,hashlib,importlib.util,json,random,statistics
from pathlib import Path
B=Path(__file__).resolve().parents[2];P=B/'results/evidence/mentor_completion_20261121';S=P/'supplement_10_seeds';O=B/'docs/AIO-mesh-rev1/evidence/mentor_completion_20261121';O.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('analysis',B/'scripts/rev1/summarize_model_refresh_evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
old=[42,100,2024,8888,9999,7,17,73,314,2718];new=[11,23,47,89,101,211,512,1024,4096,8192];seeds=old+new;inputs={}
def read(path):
 inputs[str(path.relative_to(B))]=hashlib.sha256(path.read_bytes()).hexdigest()
 with path.open(newline='') as f:return list(csv.DictReader(f))
def write(name,rows):
 with (O/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def paired(d,seed):
 rng=random.Random(seed);samples=sorted(statistics.mean(rng.choice(d) for _ in d) for _ in range(20000));p,effect=m.exact_wilcoxon(d);return statistics.mean(d),statistics.stdev(d),samples[499],samples[19499],p,effect
mask=[];oracle=[];sparse=[];bursty=[];sensitivity=[];chains=[]
for t in ('vietnam','nsfnet','geant2'):
 rows=read(P/'mask'/t/'per_seed.csv');assert {int(r['seed']) for r in rows}==set(seeds)
 keys=['empty','nonempty','rejected_empty','rejected_nonempty','empty_then_feasible','nonempty_expands','selected_not_in_mask']
 mask.append(dict(topology=t,n_seeds=len(rows),steps=sum(int(r['steps']) for r in rows),**{k:sum(int(r[k]) for r in rows) for k in keys}))
 for load in ('1.2','1.5'):
  path=P/'oracle'/f'{t}_{load}'/'results.json';inputs[str(path.relative_to(B))]=hashlib.sha256(path.read_bytes()).hexdigest();data=json.loads(path.read_text())['samples']
  for policy in ('harp','saf_h'):
   rr=[r for r in data if r['policy']==policy];assert {int(r['seed']) for r in rr}==set(old)
   oracle.append(dict(topology=t,load=load,policy=policy,n_seeds=len(rr),sampled_states=sum(r['sampled_decisions'] for r in rr),rejections=sum(r['selected_rejections'] for r in rr),with_alternative=sum(r['selected_rejections_with_feasible_alternative'] for r in rr)))
 for seed in seeds:
  root=P if seed in old else S
  sr=read(root/'sparse_gat_mlp'/t/f'seed_{seed}.csv');assert len(sr)==2 and len({r['trace_sha256'] for r in sr})==1
  br=read(root/'seeded_bursty'/t/f'seed_{seed}.csv');assert len(br)==5 and len({r['trace_sha256'] for r in br})==1
  sparse.extend(sr);bursty.extend(br)
  for n in (0,25,50,100):
   for load in ([.2,.4,.6,.8,1.,1.2,1.5] if n==0 else [1.]):
    rr=read(root/'seeded_load_chains'/f'{t}_{n}'/f'load_{load}_seed_{seed}.csv');assert len(rr)==5 and len({r['trace_sha256'] for r in rr})==1;chains.extend(rr)
  sub='saf_sensitivity' if seed in old else 'saf_weight_sensitivity'
  for load in (1.2,1.5):
   rr=[]
   for setting in ('baseline','double_latency','double_cpu','double_hops'):
    r=read(root/sub/t/f'{setting}_{load}_{seed}.csv');assert len(r)==1;rr.extend(r)
   assert len({r['trace_sha256'] for r in rr})==1;sensitivity.extend(rr)
write('mask_summary.csv',mask);write('oracle_load_summary.csv',oracle)
summary=[]
for t in ('vietnam','nsfnet','geant2'):
 rr=[r for r in sparse if r['topology']==t];by={r['key']:{int(x['seed']):x for x in rr if x['key']==r['key']} for r in rr};assert all(set(x)==set(seeds) for x in by.values())
 diffs=[float(by['harp_full'][s]['safe_acceptance_rate'])-float(by['harp_wo_gat'][s]['safe_acceptance_rate']) for s in seeds];mean,sd,lo,hi,p,effect=paired(diffs,20261122+len(summary));summary.append(dict(topology=t,n_pairs=20,full_mean=statistics.mean(float(r['safe_acceptance_rate']) for r in by['harp_full'].values()),mlp_mean=statistics.mean(float(r['safe_acceptance_rate']) for r in by['harp_wo_gat'].values()),delta_pp=mean,delta_sd=sd,ci_low=lo,ci_high=hi,p=p,rank_biserial=effect))
write('sparse_gat_mlp_summary.csv',summary)
for name,rows,group in [('seeded_bursty_summary.csv',bursty,['topology','algorithm']),('seeded_load_chains_summary.csv',chains,['topology','load_multiplier','initial_active_chains','algorithm']),('saf_sensitivity_summary.csv',sensitivity,['topology','load_multiplier','weight_setting'])]:
 groups={}
 for r in rows:groups.setdefault(tuple(r[k] for k in group),[]).append(r)
 out=[]
 for key,rr in sorted(groups.items()):
  assert len(rr)==20 and {int(r['seed']) for r in rr}==set(seeds),(name,key,len(rr))
  vals=[float(r['safe_acceptance_rate']) for r in rr];out.append(dict(zip(group,key),n_seeds=20,mean_safe_acceptance=statistics.mean(vals),sample_sd=statistics.stdev(vals)))
 write(name,out)
print('mask',len(mask),'oracle',len(oracle),'sparse',len(sparse),'seeded',len(bursty),'chains',len(chains),'sensitivity',len(sensitivity))
labels={'vietnam':'Vietnam','nsfnet':'NSFNET','geant2':'GEANT2'}
lines=[f"{labels[r['topology']]} & {r['empty']} & {r['rejected_empty']} & {r['rejected_nonempty']} & {r['empty_then_feasible']} "+r'\\' for r in mask]
(O/'mask_table.tex').write_text('\n'.join(lines)+'\n')
lines=[f"{labels[r['topology']]} & {r['load']} & {r['policy'].upper().replace('_','-')} & {r['sampled_states']} & {r['rejections']} & {r['with_alternative']} "+r'\\' for r in oracle]
(O/'oracle_table.tex').write_text('\n'.join(lines)+'\n')
lines=[f"{labels[r['topology']]} & {r['full_mean']:.2f} & {r['mlp_mean']:.2f} & {r['delta_pp']:.3f} & [{r['ci_low']:.3f}, {r['ci_high']:.3f}] "+r'\\' for r in summary]
(O/'sparse_table.tex').write_text('\n'.join(lines)+'\n')

(O/'manifest.json').write_text(json.dumps({'source_inputs_sha256':inputs,'output_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(O.iterdir()) if f.is_file() and f.name!='manifest.json'},'seeds':seeds,'oracle_seeds':old,'method':'means and sample SD; paired bootstrap 20,000; exact sign-flip signed-rank','scope':'simulator, fixed checkpoint; sparse adjacency is synthetic kNN and checkpoint was not retrained'},indent=2)+'\n')
