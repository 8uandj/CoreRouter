#!/usr/bin/env python3
"""Exploratory seed-specific burst phase: paired policies share the same trace."""
import argparse,csv,hashlib,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import torch
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env
from src.analytics.benchmark.benchmark_algorithm.algorithms import run_all_algorithms
from src.analytics.benchmark.benchmark_algorithm.config import EVAL_SEEDS
p=argparse.ArgumentParser();p.add_argument('--topology',choices=['vietnam','nsfnet','geant2'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();torch.set_num_threads(1)
data=ROOT/'data/real_telecom_combined.csv';base=ROOT/'results/models/retrain_v11_20261119_corrected'/a.topology;model=base/f'dgrl_v11_final_{a.topology}.zip';norm=base/f'vec_normalize_v11_{a.topology}.pkl';a.output.mkdir(parents=True,exist_ok=False)
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
manifest={'topology':a.topology,'seeds':list(EVAL_SEEDS),'steps':3000,'seeded_trace':'seed-specific cyclic offset of dataset rows, keeping original Bursty schedule; paired across policies','model_sha256':sha(model),'normalizer_sha256':sha(norm),'data_sha256':sha(data),'script_sha256':sha(Path(__file__))}
(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for seed in EVAL_SEEDS:
 offset=random.Random(seed+20261121).randrange(1000000)
 def factory():
  env=make_env(a.topology,data,3000,1.,(100,500),'bursty');original=env.repo.get_next_entry
  env.repo.get_next_entry=lambda step:original(step+offset)
  return env
 runs=run_all_algorithms(factory,'bursty',3000,seed,model,norm,False,include_unprotected=False)
 rows=[r.as_summary() for r in runs.values()]
 if len({r['trace_sha256'] for r in rows})!=1:raise RuntimeError('policies received different trace hashes')
 with (a.output/f'seed_{seed}.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');w.writeheader();w.writerows(rows)
 print(f'seed={seed} offset={offset} trace={rows[0]["trace_sha256"]}',flush=True)
