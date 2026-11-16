"""
============================================================
KAGGLE NOTEBOOK — Vietnam Network Benchmark Only (10K Steps)
============================================================
Dataset name: v11_train_nsfnet&geant22 (or custom dataset containing Vietnam model)
Kaggle auto-extracts ZIP, files available at /kaggle/input/<slug>/

Settings: GPU or CPU, Internet ON (for pip install)
Expected runtime: ~1-2 hours
============================================================
"""

# ══════════════════════════════════════════════════════════════
# CELL 1: Setup & Install Dependencies
# ══════════════════════════════════════════════════════════════

# !pip install -q sb3-contrib==2.3.0 stable-baselines3==2.3.2 torch-geometric gymnasium matplotlib pandas numpy

import os, sys, shutil, glob

# --- Kaggle auto-extracts ZIP — find dataset path recursively ---
INPUT_BASE = "/kaggle/input"
DATASET_DIR = None
for root, dirs, files in os.walk(INPUT_BASE):
    if "src" in dirs and os.path.isdir(os.path.join(root, "src", "orchestration")):
        DATASET_DIR = root
        break

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

# --- Set Thread Limit Env Variables in Parent Process ---
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# --- Dynamic patch to run_all.py to prevent thread contention / QR hangs ---
run_all_path = os.path.join(WORK_DIR, "src/analytics/benchmark/benchmark_algorithm/run_all.py")
if os.path.exists(run_all_path):
    with open(run_all_path, "r") as f:
        content = f.read()
    
    # Check if env variables are already set
    if "OMP_NUM_THREADS" not in content:
        print("🔧 Patching run_all.py with thread limit environment variables...")
        patch_code = (
            "import os\n"
            "os.environ['OMP_NUM_THREADS'] = '1'\n"
            "os.environ['MKL_NUM_THREADS'] = '1'\n"
            "os.environ['OPENBLAS_NUM_THREADS'] = '1'\n"
            "os.environ['VECLIB_MAXIMUM_THREADS'] = '1'\n"
            "os.environ['NUMEXPR_NUM_THREADS'] = '1'\n"
        )
        if "from __future__ import annotations" in content:
            content = content.replace(
                "from __future__ import annotations",
                "from __future__ import annotations\n\n" + patch_code
            )
        else:
            content = patch_code + "\n" + content
            
        with open(run_all_path, "w") as f:
            f.write(content)
        print("✅ run_all.py patched successfully!")
    else:
        print("✅ run_all.py already has thread limit patch.")

# Create results dirs
os.makedirs("results/models/v11", exist_ok=True)
os.makedirs("results/benchmark_algorithm", exist_ok=True)

# Verify key files exist
assert os.path.exists("src/orchestration/jo_vdpr/env.py"), "❌ env.py missing!"
assert os.path.exists("src/analytics/benchmark/benchmark_algorithm/run_all.py"), "❌ run_all.py missing!"
assert os.path.exists("data/real_telecom_combined.csv"), "❌ real_telecom_combined.csv missing!"

print("✅ Setup complete! Working directory:", WORK_DIR)
print(f"   data/real_telecom_combined.csv: {os.path.getsize('data/real_telecom_combined.csv')/1024:.0f} KB")

# ══════════════════════════════════════════════════════════════
# CELL 2: Verify Vietnam Model & Normalizer Files
# ══════════════════════════════════════════════════════════════

import os, zipfile

MODEL_DIR = "/kaggle/working/CoreRouter/results/models/v11"
print("📁 Target Models directory:", MODEL_DIR)

vietnam_model = f"{MODEL_DIR}/dgrl_v11_final_vietnam.zip"
vietnam_dir = f"{MODEL_DIR}/dgrl_v11_final_vietnam"

# Check if Kaggle recursively unzipped the model zip and re-zip it if so
if not os.path.exists(vietnam_model) and os.path.isdir(vietnam_dir):
    print("📦 Detected that Kaggle recursively unzipped the Vietnam model. Re-zipping it back...")
    with zipfile.ZipFile(vietnam_model, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(vietnam_dir):
            for f in files:
                fpath = os.path.join(root, f)
                arcname = os.path.relpath(fpath, vietnam_dir)
                zf.write(fpath, arcname)
    print("✅ Re-zipped model successfully!")

# Verify Vietnam Model
if os.path.exists(vietnam_model):
    print(f"  ✅ Vietnam model found: {os.path.basename(vietnam_model)} ({os.path.getsize(vietnam_model)/1024/1024:.2f} MB)")
else:
    print(f"  ❌ Vietnam model NOT found: {os.path.basename(vietnam_model)}")
    print("  👉 Make sure you zipped 'results/models/v11/dgrl_v11_final_vietnam.zip' and uploaded it.")

# Verify Vietnam VecNormalize
vietnam_pkl = f"{MODEL_DIR}/vec_normalize_v11_vietnam.pkl"
if os.path.exists(vietnam_pkl):
    print(f"  ✅ Vietnam normalizer (.pkl) found: {os.path.basename(vietnam_pkl)}")
else:
    print(f"  ⚠️ Vietnam normalizer (.pkl) NOT found! Benchmark might fail to load normalizer.")

print("\n✅ Verification complete!")

# ══════════════════════════════════════════════════════════════
# CELL 3: Run Algorithm Benchmark — Vietnam
# ══════════════════════════════════════════════════════════════

import subprocess, sys, os
os.chdir("/kaggle/working/CoreRouter")

print("🏃 Running Vietnam benchmark...")
print("=" * 60)

# We run scenario 'thesis' (which covers normal_load + 3 stress scenarios: elephant_stress, burst_surge, chaos)
# for 10,000 steps as required for Vietnam topology in the thesis.
subprocess.run([
    sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_all",
    "--topology", "vietnam",
    "--scenario", "thesis",
    "--steps", "10000",
    "--version", "v11",
    "--skip-exhaustive",
    "--data-path", "data/real_telecom_combined.csv",
    "--model-root", "results/models",
    "--output-dir", "results/benchmark_algorithm"
])

print("\n✅ Vietnam benchmark complete!")

# ══════════════════════════════════════════════════════════════
# CELL 4: Show Summary & Zip Results for Download
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
output_zip = "/kaggle/working/benchmark_results_vietnam.zip"
with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(results_dir):
        for f in files:
            fpath = os.path.join(root, f)
            arcname = os.path.relpath(fpath, "/kaggle/working/CoreRouter")
            zf.write(fpath, arcname)

size_mb = os.path.getsize(output_zip) / (1024 * 1024)
print(f"\n📦 Results saved to: {output_zip} ({size_mb:.1f} MB)")
print("👉 Download from Kaggle Output tab!")
