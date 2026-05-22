"""
============================================================
KAGGLE NOTEBOOK — JO-VPPM v11 Train + Benchmark Algorithm
============================================================
Upload zip: kaggle_train_benchmark_v11_code_data.zip
Run on 3 Kaggle accounts in parallel:
  Account 1: TOPOLOGY = "vietnam"
  Account 2: TOPOLOGY = "nsfnet"
  Account 3: TOPOLOGY = "geant2"

Internet: ON for pip install
Accelerator: GPU recommended
Benchmark testbed: NOT needed here
============================================================
"""

# ══════════════════════════════════════════════════════════════
# CELL 1 — Setup & Install Dependencies
# ══════════════════════════════════════════════════════════════

TOPOLOGY = "nsfnet"  # "vietnam" | "nsfnet" | "geant2"
BENCHMARK_STEPS = "10000"  # use "2000" for quick validation, "10000" for thesis run
BENCHMARK_WORKERS = "2"

!pip install -q sb3-contrib==2.3.0 stable-baselines3==2.3.2 torch-geometric gymnasium matplotlib pandas numpy

import os, sys, shutil, glob

INPUT_BASE = "/kaggle/input"

# Walk the entire input tree to find the directory containing src/
DATASET_DIR = None
for root, dirs, files in os.walk(INPUT_BASE):
    if "src" in dirs and os.path.isdir(os.path.join(root, "src", "orchestration")):
        DATASET_DIR = root
        break

if DATASET_DIR is None:
    print("Cannot auto-detect dataset. Scanning /kaggle/input:")
    for root, dirs, files in os.walk(INPUT_BASE):
        level = root.replace(INPUT_BASE, '').count(os.sep)
        if level < 4:
            indent = '  ' * level
            print(f"{indent}{os.path.basename(root)}/  ({len(dirs)} dirs, {len(files)} files)")

assert DATASET_DIR is not None, "Dataset not found. Check upload structure."
print(f"Found dataset at: {DATASET_DIR}")

WORK_DIR = "/kaggle/working/CoreRouter"
if os.path.exists(WORK_DIR):
    shutil.rmtree(WORK_DIR)
shutil.copytree(DATASET_DIR, WORK_DIR)

os.chdir(WORK_DIR)
sys.path.insert(0, WORK_DIR)
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

os.makedirs("results/models/v11", exist_ok=True)
os.makedirs("results/benchmark_algorithm", exist_ok=True)

assert TOPOLOGY in {"vietnam", "nsfnet", "geant2"}, f"Unsupported TOPOLOGY={TOPOLOGY}"
assert os.path.exists("src/orchestration/jo_vdpr/env.py"), "env.py missing"
assert os.path.exists("src/analytics/training/train_v11.py"), "train_v11.py missing"
assert os.path.exists("src/analytics/benchmark/benchmark_algorithm/run_all.py"), "run_all.py missing"
assert os.path.exists("data/telecom_trace.csv"), "telecom_trace.csv missing"
assert os.path.exists("data/real_telecom_combined.csv"), "real_telecom_combined.csv missing"

print("Setup complete. Working directory:", WORK_DIR)
print("TOPOLOGY:", TOPOLOGY)
print(f"data/telecom_trace.csv: {os.path.getsize('data/telecom_trace.csv')/1024:.0f} KB")
print(f"data/real_telecom_combined.csv: {os.path.getsize('data/real_telecom_combined.csv')/1024:.0f} KB")


# ══════════════════════════════════════════════════════════════
# CELL 2 — Train One Topology
# ══════════════════════════════════════════════════════════════

import os, sys, shutil
os.chdir("/kaggle/working/CoreRouter")
if "/kaggle/working/CoreRouter" not in sys.path:
    sys.path.insert(0, "/kaggle/working/CoreRouter")

from src.analytics.training.train_v11 import train_dgrl

print(f"Starting {TOPOLOGY.upper()} training (3M steps)...")
train_dgrl(TOPOLOGY)
print(f"{TOPOLOGY.upper()} training complete.")

MODEL_DIR = "results/models/v11"
raw_model = os.path.join(MODEL_DIR, f"dgrl_v11_{TOPOLOGY}.zip")
final_model = os.path.join(MODEL_DIR, f"dgrl_v11_final_{TOPOLOGY}.zip")
normalizer = os.path.join(MODEL_DIR, f"vec_normalize_v11_{TOPOLOGY}.pkl")

assert os.path.exists(raw_model), f"Missing trained model: {raw_model}"
assert os.path.exists(normalizer), f"Missing VecNormalize stats: {normalizer}"
shutil.copy2(raw_model, final_model)

print("Prepared benchmark model path:", final_model)
print(f"Model size: {os.path.getsize(final_model)/1024/1024:.1f} MB")
print("Normalizer:", normalizer)


# ══════════════════════════════════════════════════════════════
# CELL 3 — Quick Model/Normalizer Verification
# ══════════════════════════════════════════════════════════════

import os, zipfile
MODEL_DIR = "/kaggle/working/CoreRouter/results/models/v11"
model_path = f"{MODEL_DIR}/dgrl_v11_final_{TOPOLOGY}.zip"
norm_path = f"{MODEL_DIR}/vec_normalize_v11_{TOPOLOGY}.pkl"

assert os.path.exists(model_path), f"Model not found: {model_path}"
assert os.path.exists(norm_path), f"Normalizer not found: {norm_path}"

with zipfile.ZipFile(model_path, "r") as zf:
    names = zf.namelist()
    assert any(name.endswith("policy.pth") for name in names), "policy.pth missing inside model zip"

print(f"Model found: {os.path.basename(model_path)} ({os.path.getsize(model_path)/1024/1024:.2f} MB)")
print(f"Normalizer found: {os.path.basename(norm_path)}")
print("Verification complete.")


# ══════════════════════════════════════════════════════════════
# CELL 4 — Run Benchmark Algorithm
# ══════════════════════════════════════════════════════════════

import subprocess, sys, os
os.chdir("/kaggle/working/CoreRouter")

print(f"Running {TOPOLOGY.upper()} benchmark_algorithm thesis suite...")
print("=" * 60)

cmd = [
    sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_all",
    "--topology", TOPOLOGY,
    "--scenario", "thesis",
    "--steps", BENCHMARK_STEPS,
    "--version", "v11",
    "--workers", BENCHMARK_WORKERS,
    "--skip-exhaustive",
    "--data-path", "data/real_telecom_combined.csv",
    "--model-root", "results/models",
    "--output-dir", "results/benchmark_algorithm",
]
print(" ".join(cmd))
result = subprocess.run(cmd)
assert result.returncode == 0, f"Benchmark failed with exit code {result.returncode}"

print(f"{TOPOLOGY.upper()} benchmark complete.")


# ══════════════════════════════════════════════════════════════
# CELL 5 — Show Summary & Zip Results
# ══════════════════════════════════════════════════════════════

import os, zipfile, pandas as pd
from pathlib import Path

os.chdir("/kaggle/working/CoreRouter")
results_dir = Path("results")
bench_root = Path("results/benchmark_algorithm")
runs = sorted([p for p in bench_root.iterdir() if p.is_dir()])
assert runs, "No benchmark result directory found"
latest = runs[-1]
print("Latest benchmark run:", latest)

summary_path = latest / "all_seed_summary.csv"
if summary_path.exists():
    df = pd.read_csv(summary_path)
    display(df.groupby(["topology", "scenario", "algorithm"])[[
        "acceptance_rate", "msd_violation_rate", "sla_violation_rate", "avg_latency_ms"
    ]].mean().round(3))
else:
    print("Missing summary:", summary_path)

print("Results structure:")
for root, dirs, files in os.walk(results_dir):
    level = root.replace(str(results_dir), '').count(os.sep)
    if level < 4:
        indent = '  ' * level
        print(f"{indent}{os.path.basename(root)}/")
        for f in sorted(files):
            fsize = os.path.getsize(os.path.join(root, f)) / 1024
            print(f"{indent}  {f} ({fsize:.0f} KB)")

output_zip = Path(f"/kaggle/working/jo_vppm_v11_{TOPOLOGY}_train_benchmark_outputs.zip")
with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in results_dir.rglob("*"):
        if path.is_file():
            zf.write(path, path.relative_to("/kaggle/working/CoreRouter"))

print(f"Output zip: {output_zip} ({output_zip.stat().st_size/1024/1024:.1f} MB)")
print("Download from Kaggle Output tab.")
