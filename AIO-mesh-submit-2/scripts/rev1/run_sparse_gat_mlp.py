#!/usr/bin/env python3
"""Exploratory GAT vs MLP on a synthetic k-nearest-neighbour adjacency."""
import argparse,csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np,torch
import src.analytics.ablation_study as ab
from src.analytics.benchmark.benchmark_algorithm.config import EVAL_SEEDS
from src.orchestration.jo_vdpr.topology import TopologyManager
p=argparse.ArgumentParser();p.add_argument('--topology',choices=['vietnam','nsfnet','geant2'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();torch.set_num_threads(1)
data=ROOT/'data/real_telecom_combined.csv';model_root=ROOT/'results/models';a.output.mkdir(parents=True,exist_ok=False)
original_adj=TopologyManager._build_adj_matrix
def knn(self):
 n=self.num_nodes;adj=np.eye(n,dtype=np.float32)
 for i in range(n):
  for j in np.argsort(self.latency_matrix[i]+np.eye(n,dtype=np.float32)[i]*1e9)[:3]:adj[i,j]=adj[j,i]=1.
 return adj
TopologyManager._build_adj_matrix=knn
original_load=ab.load_policy_model
def load_model(env,path,variant):
 model=original_load(env,path,variant)
 if variant.use_gat_model:
  adj=torch.as_tensor(env.topo.adj_matrix,dtype=torch.float32);degree=adj.sum(1,keepdim=True).clamp(min=1e-9).sqrt();adj=adj/(degree*degree.T);matches=0
  for module in model.policy.modules():
   if module.__class__.__name__=='GNNFeaturesExtractor':module.adj.copy_(adj.to(module.adj.device));matches+=1
  if not matches:raise RuntimeError('GAT extractor adjacency not found')
 return model
ab.load_policy_model=load_model
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
variants=[v for v in ab.VARIANTS if v.key in ('harp_full','harp_wo_gat')];assets={}
for v in variants:
 m,n,_=ab.resolve_variant_model_paths(model_root,'v11',a.topology,v);assets[v.key]={'model':str(m),'sha256':sha(m),'normalizer':str(n),'normalizer_sha256':sha(n)}
topo=TopologyManager(a.topology);edges=[(int(i),int(j)) for i in range(topo.num_nodes) for j in range(i+1,topo.num_nodes) if topo.adj_matrix[i,j]]
(a.output/'manifest.json').write_text(json.dumps({'topology':a.topology,'adjacency':'synthetic symmetric 3-nearest-neighbour derived from latency; not a physical edge list','edges':edges,'nodes':topo.num_nodes,'protocol':'Bursty stress; 20 seeds x 3000 steps; existing separately trained full and MLP checkpoints; replace GAT adjacency after load','limitation':'simulator pair feasibility and pair link bandwidth do not model physical multi-hop forwarding; no sparse-graph retraining','models':assets,'seeds':list(EVAL_SEEDS),'data_sha256':sha(data),'script_sha256':sha(Path(__file__))},indent=2)+'\n')
for seed in EVAL_SEEDS:
 rows=[]
 for variant in variants:
  model,norm,source=ab.resolve_variant_model_paths(model_root,'v11',a.topology,variant)
  r=ab.run_variant(variant,a.topology,'bursty',3000,seed,data,model,norm,source,1.,(100,500));rows.append(r.row())
 if len({r['trace_sha256'] for r in rows})!=1:raise RuntimeError('offered trace mismatch')
 with (a.output/f'seed_{seed}.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 print(f'seed={seed} full={rows[0]["safe_acceptance_rate"]} mlp={rows[1]["safe_acceptance_rate"]} trace={rows[0]["trace_sha256"]}',flush=True)
