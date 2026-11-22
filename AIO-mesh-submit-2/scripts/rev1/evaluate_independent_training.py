#!/usr/bin/env python3
"""Compare independently trained Vietnam checkpoints with paired evaluation seeds."""
import csv,hashlib,json,sys,zipfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import torch
from src.analytics.benchmark.benchmark_algorithm.env_factory import make_env
from src.analytics.benchmark.benchmark_algorithm.algorithms import run_jo_vppm
seeds=[42,100,2024,8888,9999,7,17,73,314,2718,11,23,47,89,101,211,512,1024,4096,8192]
out=ROOT/'results/evidence/mentor_completion_20261121/independent_training/evaluation_2m';out.mkdir(parents=True,exist_ok=True);torch.set_num_threads(1)
data=ROOT/'data/real_telecom_combined.csv';models={42:(ROOT/'results/models/retrain_v11_20261119_corrected/vietnam/dgrl_v11_final_vietnam.zip',ROOT/'results/models/retrain_v11_20261119_corrected/vietnam/vec_normalize_v11_vietnam.pkl',2001920),7:(out.parent/'matched_seed_7/dgrl_v11_final_vietnam.zip',out.parent/'matched_seed_7/vec_normalize_v11_vietnam.pkl',2001920),2024:(out.parent/'matched_seed_2024/dgrl_v11_final_vietnam.zip',out.parent/'matched_seed_2024/vec_normalize_v11_vietnam.pkl',800000)}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'scenario':'bursty stress; matched offered traces; 3000 steps per seed; deterministic policy','evaluation_seeds':seeds,'training_seeds':list(models),'data_sha256':sha(data),'checkpoints':{}}
for train_seed,(model,norm,training_steps) in models.items():
 with zipfile.ZipFile(model) as archive: training_steps=int(json.loads(archive.read('data'))['num_timesteps'])
 if training_steps < 2_000_000: raise ValueError(f'Checkpoint below 2M: {model}')
 manifest['checkpoints'][train_seed]={'model':str(model.relative_to(ROOT)),'model_sha256':sha(model),'normalizer':str(norm.relative_to(ROOT)),'normalizer_sha256':sha(norm),'training_steps':training_steps}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 if os.environ.get('EVAL_TRAINING_SEED') and str(train_seed) != os.environ['EVAL_TRAINING_SEED']: continue
 for seed in seeds:
  run=run_jo_vppm(lambda:make_env('vietnam',data,3000,1.,(100,500),'bursty'),model,norm,'bursty',3000,seed,True);row=run.as_summary();row['training_seed']=train_seed;row['training_steps']=training_steps
  with (out/f'train_{train_seed}_eval_{seed}.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(row),lineterminator='\n');w.writeheader();w.writerow(row)
  print(f'train_seed={train_seed} eval_seed={seed} safe_acceptance={row["safe_acceptance_rate"]} trace={row["trace_sha256"]}',flush=True)
