import os, json
import numpy as np

base_dir = "/home/hung8uandj/Study/CoreRouter/results/figures/"
data = []

for root, dirs, files in os.walk(base_dir):
    if "checkpoint.json" in files:
        folder = os.path.basename(root)
        if "benchmark_" in folder and ("_normal" in folder or "_stress" in folder):
            with open(os.path.join(root, "checkpoint.json")) as f:
                content = json.load(f)
                data.append((folder, content))

for folder, results in sorted(data, key=lambda x: x[0]):
    print(f"\n=== {folder} ===")
    for algo, seeds in results.items():
        if not seeds: continue
        algo_clean = algo.replace("★ ", "")
        acc_vals = [s.get('acc', 0) for s in seeds]
        sla_vals = [s.get('sla', 0) for s in seeds]
        lat_vals = [s.get('avg_lat', 0) for s in seeds]
        
        acc_mean = np.mean(acc_vals)
        sla_mean = np.mean(sla_vals)
        lat_mean = np.mean(lat_vals)
        
        print(f"  {algo_clean:<25} | Acc: {acc_mean:>6.1f}% | SLA: {sla_mean:>5.2f}% | Lat: {lat_mean:>5.2f}ms")
