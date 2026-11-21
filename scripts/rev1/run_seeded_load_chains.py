#!/usr/bin/env python3
"""Evaluate protected policies with seed-dependent dataset offset under load and occupancy."""
import argparse,csv,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import torch
from src.analytics.benchmark.benchmark_algorithm.run_load_sweep import build_env_factory
from src.analytics.benchmark.benchmark_algorithm.algorithms import run_all_algorithms
from src.analytics.benchmark.benchmark_algorithm.config import EVAL_SEEDS
p=argparse.ArgumentParser();p.add_argument('--topology',choices=['vietnam','nsfnet','geant2'],required=True);p.add_argument('--chains',type=int,choices=[0,25,50,100],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();torch.set_num_threads(1)
d=ROOT/'data/real_telecom_combined.csv';base=ROOT/'results/models/retrain_v11_20261119_corrected'/a.topology;model=base/f'dgrl_v11_final_{a.topology}.zip';norm=base/f'vec_normalize_v11_{a.topology}.pkl';a.output.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
loads=[.2,.4,.6,.8,1.,1.2,1.5] if a.chains==0 else [1.]
(a.output/'manifest.json').write_text(json.dumps({'topology':a.topology,'chains':a.chains,'loads':loads,'steps':3000,'seeds':list(EVAL_SEEDS),'seeded_trace':'seed-specific cyclic offset of dataset rows; original Bursty schedule; policies paired','model_sha256':sha(model),'normalizer_sha256':sha(norm),'data_sha256':sha(d),'script_sha256':sha(Path(__file__))},indent=2)+'\n')
for load in loads:
 for seed in EVAL_SEEDS:
  offset=random.Random(seed+20261121).randrange(1000000);make_base=build_env_factory(a.topology,d,3000,load,a.chains)
  def factory():
   env=make_base();original=env.repo.get_next_entry;env.repo.get_next_entry=lambda step:original(step+offset);return env
  runs=run_all_algorithms(factory,'bursty',3000,seed,model,norm,False,include_unprotected=False);rows=[r.as_summary() for r in runs.values()]
  if len({r['trace_sha256'] for r in rows})!=1:raise RuntimeError('policies received different traces')
  for r in rows:r.update(load_multiplier=load,initial_active_chains=a.chains,trace_offset=offset)
  with (a.output/f'load_{load}_seed_{seed}.csv').open('x',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');w.writeheader();w.writerows(rows)
  print(f'load={load} chains={a.chains} seed={seed} trace={rows[0]["trace_sha256"]}',flush=True)
