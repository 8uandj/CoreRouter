#!/usr/bin/env python3
"""Compare current mask with hypothetical post-expiry mask on matched simulator traces."""
import csv,hashlib,json,random,sys
from pathlib import Path
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env
from src.analytics.benchmark.benchmark_algorithm.model_loader import build_model_from_policy_weights,load_normalizer,normalized_obs
from src.analytics.benchmark.benchmark_algorithm.algorithms import _snapshot_env,_restore_env
from src.analytics.benchmark.benchmark_algorithm.metrics import RunMetrics
from scripts.rev1.audit_mask_ttl import expire,SEEDS
torch.set_num_threads(1);data=ROOT/'data/real_telecom_combined.csv';out=ROOT/'results/evidence/mentor_completion_20261121/mask_expiry_intervention';out.mkdir(parents=True,exist_ok=True)
for topo in ('vietnam','nsfnet','geant2'):
 base=ROOT/'results/models/retrain_v11_20261119_corrected'/topo;model=base/f'dgrl_v11_final_{topo}.zip';norm=base/f'vec_normalize_v11_{topo}.pkl'
 for seed in SEEDS:
  rows=[]
  for mode in ('pre_expiry','post_expiry_mask'):
   env=make_env(topo,data,3000,1.,(100,500),'bursty');env.enforce_resource_constraints=True;np.random.seed(seed);random.seed(seed);env.reset(seed=seed);policy=build_model_from_policy_weights(env,model);normalizer=load_normalizer(norm,policy.get_env());obs,_=env.reset(seed=seed);metrics=RunMetrics(mode,'bursty',topo,seed)
   for step in range(3000):
    if mode=='post_expiry_mask':
     snap=_snapshot_env(env);expire(env);mask=env.action_masks();_restore_env(env,snap)
    else:mask=env.action_masks()
    action,_=policy.predict(normalized_obs(normalizer,obs),action_masks=np.asarray([mask if mask.any() else np.ones(env.action_space.n,dtype=bool)]),deterministic=True)
    obs,reward,done,_,info=env.step(action[0]);metrics.collect(info,reward)
    if done and step<2999:obs,_=env.reset(seed=seed)
   row=metrics.as_summary();row['mode']=mode;rows.append(row)
  if rows[0]['trace_sha256']!=rows[1]['trace_sha256']:raise ValueError('unpaired offered traces')
  f=out/f'{topo}_{seed}.csv'
  with f.open('x',newline='') as h:w=csv.DictWriter(h,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');w.writeheader();w.writerows(rows)
  print(f'{topo} seed={seed} before={rows[0]["safe_acceptance_rate"]} after={rows[1]["safe_acceptance_rate"]}',flush=True)
