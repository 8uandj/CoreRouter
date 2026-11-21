#!/usr/bin/env python3
"""Exhaustive pair oracle for the refreshed offered-intensity protocol."""
import argparse,hashlib,json,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import torch
import scripts.rev1.run_nonhil_studies as study
from src.analytics.benchmark.benchmark_algorithm.run_load_sweep import build_env_factory
p=argparse.ArgumentParser();p.add_argument('--topology',choices=['vietnam','nsfnet','geant2'],required=True);p.add_argument('--load',type=float,choices=[1.2,1.5],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
torch.set_num_threads(1);data=ROOT/'data/real_telecom_combined.csv';base=ROOT/'results/models/retrain_v11_20261119_corrected'/a.topology;model=base/f'dgrl_v11_final_{a.topology}.zip';norm=base/f'vec_normalize_v11_{a.topology}.pkl'
study.env_factory=lambda topology,data,steps:build_env_factory(topology,data,steps,a.load,0)
a.output.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'topology':a.topology,'load':a.load,'steps':3000,'stride':25,'seeds':list(study.SEEDS),'data_sha256':sha(data),'model_sha256':sha(model),'normalizer_sha256':sha(norm),'script_sha256':sha(Path(__file__)),'python':platform.python_version(),'torch':torch.__version__,'protocol':'refreshed load sweep factory; exhaustive simulator pair oracle after TTL expiration'}
(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
samples=[]
for policy in ['harp','saf_h']:
 samples.extend(study.run_oracle_policy(a.topology,policy,study.SEEDS,3000,25,data,model,norm))
 (a.output/f'{policy}_samples.json').write_text(json.dumps(samples,indent=2)+'\n')
(a.output/'results.json').write_text(json.dumps({'samples':samples},indent=2)+'\n')
