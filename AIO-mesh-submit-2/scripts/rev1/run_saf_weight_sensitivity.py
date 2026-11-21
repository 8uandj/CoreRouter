#!/usr/bin/env python3
"""SAF-H one-factor sensitivity with protected admission and fixed offered traces."""
import argparse,csv,hashlib,inspect,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import torch
from src.analytics.benchmark.benchmark_algorithm import algorithms
from src.analytics.benchmark.benchmark_algorithm.run_load_sweep import build_env_factory
from src.analytics.benchmark.benchmark_algorithm.config import EVAL_SEEDS
p=argparse.ArgumentParser();p.add_argument('--topology',choices=['vietnam','nsfnet','geant2'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();torch.set_num_threads(1)
d=ROOT/'data/real_telecom_combined.csv';a.output.mkdir(parents=True,exist_ok=False)
weights={'baseline':(.5,100.,5.),'double_latency':(1.,100.,5.),'double_cpu':(.5,200.,5.),'double_hops':(.5,100.,10.)}
src=inspect.getsource(algorithms.run_saf_h);needle='cost = latency * 0.5 + cpu_util * 100.0 + hop_count * 5.0'
if src.count(needle)!=1:raise RuntimeError('SAF-H cost implementation changed; abort')
sha=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
(a.output/'manifest.json').write_text(json.dumps({'topology':a.topology,'seeds':list(EVAL_SEEDS),'loads':[1.2,1.5],'steps':3000,'weights_latency_cpu_hops':weights,'data_sha256':sha(d),'algorithm_sha256':sha(Path(algorithms.__file__)),'script_sha256':sha(Path(__file__)),'interpretation':'one-factor doubled weight, exploratory; protected SAF-H only'},indent=2)+'\n')
for label,(lw,cw,hw) in weights.items():
 code=src.replace(needle,f'cost = latency * {lw!r} + cpu_util * {cw!r} + hop_count * {hw!r}');namespace=dict(vars(algorithms));exec(compile(code,str(Path(algorithms.__file__)),'exec'),namespace);runner=namespace['run_saf_h']
 for load in (1.2,1.5):
  for seed in EVAL_SEEDS:
   run=runner(build_env_factory(a.topology,d,3000,load,0),'bursty',3000,seed,protected=True);row=run.as_summary();row.update(weight_setting=label,weight_latency=lw,weight_cpu=cw,weight_hops=hw,load_multiplier=load)
   with (a.output/f'{label}_{load}_{seed}.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(row),lineterminator='\n');w.writeheader();w.writerow(row)
   print(f'setting={label} load={load} seed={seed} trace={row["trace_sha256"]}',flush=True)
