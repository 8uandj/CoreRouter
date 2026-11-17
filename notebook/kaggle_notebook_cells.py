"""
============================================================
KAGGLE NOTEBOOK — JO-VPPM Train + Benchmark (NSFNET & GEANT2)
============================================================
Dataset name: v11_train_nsfnet&geant22
Kaggle auto-extracts ZIP, files available at /kaggle/input/<slug>/

Settings: GPU T4x2 or P100, Internet ON (for pip install)
Expected runtime: ~4-6 hours total
============================================================
"""

# ══════════════════════════════════════════════════════════════
# CELL 1: Setup & Install Dependencies
# ══════════════════════════════════════════════════════════════

# !pip install -q sb3-contrib==2.3.0 stable-baselines3==2.3.2 torch-geometric gymnasium matplotlib pandas numpy

import os, sys, shutil, glob

# --- Kaggle auto-extracts ZIP — find dataset path recursively ---
INPUT_BASE = "/kaggle/input"

# Walk the entire input tree to find the directory containing 'src/'
DATASET_DIR = None
for root, dirs, files in os.walk(INPUT_BASE):
    if "src" in dirs and os.path.isdir(os.path.join(root, "src", "orchestration")):
        DATASET_DIR = root
        break

# Debug: print what we see if not found
if DATASET_DIR is None:
    print("❌ Cannot auto-detect dataset. Scanning /kaggle/input:")
    for root, dirs, files in os.walk(INPUT_BASE):
        level = root.replace(INPUT_BASE, '').count(os.sep)
        if level < 4:
            indent = '  ' * level
            print(f"{indent}{os.path.basename(root)}/  ({len(dirs)} dirs, {len(files)} files)")

assert DATASET_DIR is not None, "❌ Dataset not found! Check upload structure."
print(f"✅ Found dataset at: {DATASET_DIR}")

# --- Copy to working dir (input is read-only on Kaggle) ---
WORK_DIR = "/kaggle/working/CoreRouter"
if os.path.exists(WORK_DIR):
    shutil.rmtree(WORK_DIR)
shutil.copytree(DATASET_DIR, WORK_DIR)

os.chdir(WORK_DIR)
sys.path.insert(0, WORK_DIR)
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

# Create results dirs
os.makedirs("results/models/v11", exist_ok=True)
os.makedirs("results/benchmark_algorithm", exist_ok=True)

# Verify key files exist
assert os.path.exists("src/orchestration/jo_vdpr/env.py"), "❌ env.py missing!"
assert os.path.exists("src/analytics/training/train_v11.py"), "❌ train_v11.py missing!"
assert os.path.exists("data/telecom_trace.csv"), "❌ telecom_trace.csv missing!"

print("✅ Setup complete! Working directory:", WORK_DIR)
print(f"   data/telecom_trace.csv: {os.path.getsize('data/telecom_trace.csv')/1024:.0f} KB")
print(f"   data/real_telecom_combined.csv: {os.path.getsize('data/real_telecom_combined.csv')/1024:.0f} KB")

# ══════════════════════════════════════════════════════════════
# CELL 2: Train NSFNET (14 nodes) — ~1.5-2 hours
# ══════════════════════════════════════════════════════════════

import os, sys
os.chdir("/kaggle/working/CoreRouter")
if "/kaggle/working/CoreRouter" not in sys.path:
    sys.path.insert(0, "/kaggle/working/CoreRouter")

from src.analytics.training.train_v11 import train_dgrl

print("🚀 Starting NSFNET training (3M steps)...")
train_dgrl("nsfnet")
print("✅ NSFNET training complete!")

# ══════════════════════════════════════════════════════════════
# CELL 3: Train GEANT2 (23 nodes) — ~2-3 hours
# ══════════════════════════════════════════════════════════════

print("🚀 Starting GEANT2 training (3M steps)...")
train_dgrl("geant2")
print("✅ GEANT2 training complete!")

# ══════════════════════════════════════════════════════════════
# CELL 4: Verify & Rename trained models
# ══════════════════════════════════════════════════════════════

import os, shutil

MODEL_DIR = "/kaggle/working/CoreRouter/results/models/v11"
print("📁 Models in", MODEL_DIR + ":")
for f in sorted(os.listdir(MODEL_DIR)):
    fpath = os.path.join(MODEL_DIR, f)
    size = os.path.getsize(fpath) / 1024
    print(f"  {f:50s}  {size:.1f} KB")

# Rename: benchmark expects "dgrl_v11_final_{topo}.zip" but training saves "dgrl_v11_{topo}.zip"
for topo in ["nsfnet", "geant2"]:
    src = f"{MODEL_DIR}/dgrl_v11_{topo}.zip"
    dst = f"{MODEL_DIR}/dgrl_v11_final_{topo}.zip"
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy2(src, dst)
        print(f"  ✅ Copied {os.path.basename(src)} -> {os.path.basename(dst)}")

# Also need to convert VecNormalize .pkl to .npz for the benchmark loader
# The benchmark model_loader tries .pkl first, then falls back to .npz
for topo in ["nsfnet", "geant2"]:
    pkl = f"{MODEL_DIR}/vec_normalize_v11_{topo}.pkl"
    if os.path.exists(pkl):
        print(f"  ✅ VecNormalize found: {os.path.basename(pkl)}")
    else:
        print(f"  ⚠️ VecNormalize NOT found for {topo}!")

print("\n✅ Model verification complete!")

# ══════════════════════════════════════════════════════════════
# CELL 5: Run Algorithm Benchmark — NSFNET
# ══════════════════════════════════════════════════════════════

import subprocess, sys, os
os.chdir("/kaggle/working/CoreRouter")

print("🏃 Running NSFNET benchmark...")
print("=" * 60)

# Normal Load
print("\n--- NSFNET: normal_load ---")
subprocess.run([
    sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_all",
    "--topology", "nsfnet",
    "--scenario", "normal_load",
    "--steps", "2000",
    "--version", "v11",
    "--skip-exhaustive",
    "--data-path", "data/real_telecom_combined.csv",
    "--model-root", "results/models",
    "--output-dir", "results/benchmark_algorithm"
])

# Stress scenarios
for scenario in ["uniform", "bursty", "heavy_tail"]:
    print(f"\n--- NSFNET stress: {scenario} ---")
    subprocess.run([
        sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_all",
        "--topology", "nsfnet",
        "--scenario", scenario,
        "--load", "stress",
        "--steps", "2000",
        "--version", "v11",
        "--skip-exhaustive",
        "--data-path", "data/real_telecom_combined.csv",
        "--model-root", "results/models",
        "--output-dir", "results/benchmark_algorithm"
    ])

print("\n✅ NSFNET benchmark complete!")

# ══════════════════════════════════════════════════════════════
# CELL 6: Run Algorithm Benchmark — GEANT2
# ══════════════════════════════════════════════════════════════

print("🏃 Running GEANT2 benchmark...")
print("=" * 60)

# Normal Load
print("\n--- GEANT2: normal_load ---")
subprocess.run([
    sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_all",
    "--topology", "geant2",
    "--scenario", "normal_load",
    "--steps", "2000",
    "--version", "v11",
    "--skip-exhaustive",
    "--data-path", "data/real_telecom_combined.csv",
    "--model-root", "results/models",
    "--output-dir", "results/benchmark_algorithm"
])

# Stress scenarios
for scenario in ["uniform", "bursty", "heavy_tail"]:
    print(f"\n--- GEANT2 stress: {scenario} ---")
    subprocess.run([
        sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_all",
        "--topology", "geant2",
        "--scenario", scenario,
        "--load", "stress",
        "--steps", "2000",
        "--version", "v11",
        "--skip-exhaustive",
        "--data-path", "data/real_telecom_combined.csv",
        "--model-root", "results/models",
        "--output-dir", "results/benchmark_algorithm"
    ])

print("\n✅ GEANT2 benchmark complete!")

# ══════════════════════════════════════════════════════════════
# CELL 7: Show Summary & Zip Results for Download
# ══════════════════════════════════════════════════════════════

import zipfile, os

# Show what we got
results_dir = "/kaggle/working/CoreRouter/results"
print("📊 Results structure:")
for root, dirs, files in os.walk(results_dir):
    level = root.replace(results_dir, '').count(os.sep)
    indent = '  ' * level
    print(f'{indent}{os.path.basename(root)}/')
    if level < 3:
        for f in sorted(files):
            fsize = os.path.getsize(os.path.join(root, f)) / 1024
            print(f'{indent}  {f} ({fsize:.0f} KB)')

# Zip everything
output_zip = "/kaggle/working/benchmark_results_nsfnet_geant2.zip"
with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(results_dir):
        for f in files:
            fpath = os.path.join(root, f)
            arcname = os.path.relpath(fpath, "/kaggle/working/CoreRouter")
            zf.write(fpath, arcname)

size_mb = os.path.getsize(output_zip) / (1024 * 1024)
print(f"\n📦 Results saved to: {output_zip} ({size_mb:.1f} MB)")
print("👉 Download from Kaggle Output tab!")
