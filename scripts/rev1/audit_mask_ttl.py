#!/usr/bin/env python3
"""Count mask/rejection intersections and expiry effects without changing policy trajectories."""
import argparse,csv,hashlib,json,random,sys
from pathlib import Path
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env
from src.analytics.benchmark.benchmark_algorithm.model_loader import build_model_from_policy_weights,load_normalizer,normalized_obs
from src.analytics.benchmark.benchmark_algorithm.algorithms import _snapshot_env,_restore_env
SEEDS=[42,100,2024,8888,9999,7,17,73,314,2718,11,23,47,89,101,211,512,1024,4096,8192]
def expire(env):
 for flow in list(env.active_flows):
  if flow['ttl']>1: continue
  env.active_flows.remove(flow);v1=flow.get('placement_node',flow.get('v1'));v2=flow.get('routing_node',flow.get('v2'))
  env._state[v1*3]=max(0.,env._state[v1*3]-flow.get('cpu_allocated',flow.get('cpu',0)))
  env._state[v1*3+1]=max(0.,env._state[v1*3+1]-flow.get('ram_allocated',flow.get('ram',0)))
  if v1!=v2:env._link_bw[v1][v2]+=flow['bw'];env._link_bw[v2][v1]+=flow['bw']
 env._state[2::3]=0
 for f in env.active_flows:
  v=f.get('routing_node',f.get('v2'));env._state[v*3+2]=max(env._state[v*3+2],f.get('msd_allocated',f.get('msd',0)))
def main():
 p=argparse.ArgumentParser();p.add_argument('--topology',choices=['vietnam','nsfnet','geant2'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--steps',type=int,default=3000);p.add_argument('--seeds',type=int,nargs='+',default=SEEDS);args=p.parse_args()
 torch.set_num_threads(1);d=ROOT/'data/real_telecom_combined.csv';base=ROOT/'results/models/retrain_v11_20261119_corrected'/args.topology;model=base/f'dgrl_v11_final_{args.topology}.zip';norm=base/f'vec_normalize_v11_{args.topology}.pkl';out=[]
 for seed in args.seeds:
  env=make_env(args.topology,d,args.steps,1.,(100,500),'bursty');env.enforce_resource_constraints=True;env.reset(seed=seed);np.random.seed(seed);random.seed(seed)
  policy=build_model_from_policy_weights(env,model);normalizer=load_normalizer(norm,policy.get_env());obs,_=env.reset(seed=seed)
  c=dict(topology=args.topology,seed=seed,steps=args.steps,empty=0,nonempty=0,rejected_empty=0,rejected_nonempty=0,empty_then_feasible=0,nonempty_expands=0,selected_not_in_mask=0,rejected_cpu=0,rejected_ram=0,rejected_msd=0,rejected_bw=0,rejected_other=0)
  for i in range(args.steps):
   mask=env.action_masks();empty=not mask.any();snap=_snapshot_env(env);expire(env);after=env.action_masks();_restore_env(env,snap)
   c['empty' if empty else 'nonempty']+=1;c['empty_then_feasible']+=int(empty and after.any());c['nonempty_expands']+=int(not empty and np.any(after & ~mask))
   action,_=policy.predict(normalized_obs(normalizer,obs),action_masks=np.asarray([mask if not empty else np.ones(env.action_space.n,dtype=bool)]),deterministic=True)
   idx=int(np.asarray(action).ravel()[0]);c['selected_not_in_mask']+=int(not empty and not mask[idx]);obs,_,done,_,info=env.step(idx)
   if not info.get('skipped') and not info.get('accepted'):
    c['rejected_empty' if empty else 'rejected_nonempty']+=1;key=info.get('rejection_reason') or 'other';key=key if key in ('cpu','ram','msd','bw') else 'other';c['rejected_'+key]+=1
   if done and i+1<args.steps:obs,_=env.reset(seed=seed)
  out.append(c);print(json.dumps(c),flush=True)
 args.output.mkdir(parents=True,exist_ok=True)
 with (args.output/'per_seed.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]),lineterminator='\n');w.writeheader();w.writerows(out)
 def digest(x):return hashlib.sha256(x.read_bytes()).hexdigest()
 (args.output/'manifest.json').write_text(json.dumps({'model':str(model.relative_to(ROOT)),'model_sha256':digest(model),'normalizer_sha256':digest(norm),'data_sha256':digest(d),'script_sha256':digest(Path(__file__)),'steps':args.steps,'seeds':args.seeds,'scope':'Bursty stress; pre-step mask and counterfactual mask after expiry; actual trajectory unchanged'},indent=2)+'\n')
if __name__=='__main__':main()
