#!/usr/bin/env python3
"""Compare greedy and decoupled choices on their own trajectories and paired traces."""
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env
from src.analytics.benchmark.benchmark_algorithm.algorithms import run_greedy,run_decoupled
seeds=[42,100,2024,8888,9999,7,17,73,314,2718,11,23,47,89,101,211,512,1024,4096,8192];data=ROOT/'data/real_telecom_combined.csv';out=ROOT/'results/evidence/mentor_completion_20261121/greedy_decoupled';out.mkdir(parents=True,exist_ok=True)
for t in ('vietnam','nsfnet','geant2'):
 for scenario in ('heavy_tail','bursty','chaos'):
  for seed in seeds:
   records={}
   for label,runner in [('greedy',run_greedy),('decoupled',run_decoupled)]:
    actions=[]
    def factory():
     env=make_env(t,data,3000,1.,(100,500),scenario);step=env.step
     def capture(action):
      actions.append(tuple(map(int,action)));return step(action)
     env.step=capture;return env
    metrics=runner(factory,scenario,3000,seed,True);records[label]=(actions,metrics.as_summary())
   ga,g=records['greedy'];da,d=records['decoupled'];assert len(ga)==len(da)==3000 and g['trace_sha256']==d['trace_sha256']
   row={'topology':t,'scenario':scenario,'seed':seed,'steps':3000,'same_placement':sum(x[0]==y[0] for x,y in zip(ga,da)),'same_route':sum(x[1]==y[1] for x,y in zip(ga,da)),'same_pair':sum(x==y for x,y in zip(ga,da)),'greedy_safe_acceptance':g['safe_acceptance_rate'],'decoupled_safe_acceptance':d['safe_acceptance_rate'],'trace_sha256':g['trace_sha256']}
   with (out/f'{t}_{scenario}_{seed}.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=row,lineterminator='\n');w.writeheader();w.writerow(row)
   print(json.dumps(row),flush=True)
