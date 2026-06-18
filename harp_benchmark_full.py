# %% [markdown]
# # HARP Ablation Study on Kaggle
#
# Upload `kaggle_harp_ablation.zip` as a Kaggle Dataset, attach it to this
# notebook, then run the cells below. The zip already contains the source code,
# dataset CSVs, and final model artifacts needed by `src.analytics.ablation_study`.

# %% Cell 1 - Install Dependencies
import sys
import subprocess

packages = [
    "gymnasium",
    "stable-baselines3[extra]",
    "sb3-contrib",
    "shimmy>=0.2.1",
    "matplotlib",
    "pandas",
    "networkx",
    "scipy",
]

for package in packages:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])

print("Dependencies installed")

# %% Cell 2 - Locate and Prepare Package
import os
import shutil
import zipfile
from pathlib import Path

KAGGLE_INPUT = Path("/kaggle/input")
WORK_DIR = Path("/kaggle/working/CoreRouter")

if WORK_DIR.exists():
    shutil.rmtree(WORK_DIR)
WORK_DIR.mkdir(parents=True, exist_ok=True)

def looks_like_harp_root(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "src" / "analytics" / "ablation_study.py").exists()
        and (path / "src" / "orchestration" / "jo_vdpr" / "env.py").exists()
    )


def zip_contains_harp_package(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() != ".zip":
        return False
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            return (
                "src/analytics/ablation_study.py" in names
                and "src/orchestration/jo_vdpr/env.py" in names
            )
    except zipfile.BadZipFile:
        return False


zip_candidates = [
    p for p in list(KAGGLE_INPUT.glob("**/*.zip")) + list(Path("/kaggle/working").glob("*.zip"))
    if zip_contains_harp_package(p)
]

if zip_candidates:
    package_path = zip_candidates[0]
    print(f"Using zip package: {package_path}")
    with zipfile.ZipFile(package_path, "r") as archive:
        archive.extractall(WORK_DIR)
else:
    # Kaggle often auto-extracts uploaded datasets. Dataset names are arbitrary,
    # so detect the package by its file structure instead of by dataset name.
    dir_candidates = [
        p for p in KAGGLE_INPUT.glob("**")
        if looks_like_harp_root(p)
    ]
    dir_candidates += [
        p.parent.parent.parent for p in KAGGLE_INPUT.glob("**/src/analytics/ablation_study.py")
        if looks_like_harp_root(p.parent.parent.parent)
    ]
    dir_candidates = list(dict.fromkeys(dir_candidates))

    if not dir_candidates:
        raise FileNotFoundError(
            "Cannot find HARP ablation package under /kaggle/input. "
            "Attach any Kaggle Dataset that contains src/analytics/ablation_study.py, "
            "or upload any zip containing that project structure."
        )

    package_path = dir_candidates[0]
    print(f"Using extracted dataset directory: {package_path}")
    for item in package_path.iterdir():
        dest = WORK_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # If the user attached an old notebook output, it might be in a different directory
    # Let's search for any 'results' folder in KAGGLE_INPUT and merge it to WORK_DIR/results
    print("\nScanning for previous results/models in Kaggle inputs...")
    for results_dir in KAGGLE_INPUT.rglob("results"):
        if results_dir.is_dir() and "models" in [d.name for d in results_dir.iterdir()]:
            print(f"Found results directory at: {results_dir}")
            # Merge contents of this results dir into WORK_DIR/results
            def merge_dirs(src: Path, dst: Path):
                dst.mkdir(parents=True, exist_ok=True)
                for item in src.iterdir():
                    s = item
                    d = dst / item.name
                    if s.is_dir():
                        merge_dirs(s, d)
                    elif not d.exists():
                        shutil.copy2(s, d)
            merge_dirs(results_dir, WORK_DIR / "results")
            print(f"Merged {results_dir} into {WORK_DIR / 'results'}")

os.chdir(WORK_DIR)
sys.path.insert(0, str(WORK_DIR))

def ensure_sb3_model_zip(topology: str) -> None:
    """Kaggle may auto-extract nested Stable-Baselines3 model zip files.

    The project loader expects results/models/v11/dgrl_v11_final_<topology>.zip
    to be a real zip file containing policy.pth. If Kaggle extracted it into a
    directory, re-pack that directory back into the expected archive name.
    """
    model_dir = WORK_DIR / "results" / "models" / "v11"
    expected_zip = model_dir / f"dgrl_v11_final_{topology}.zip"

    if expected_zip.is_file():
        return

    candidates = [
        expected_zip,
        model_dir / f"dgrl_v11_final_{topology}",
        model_dir / f"dgrl_v11_{topology}",
        model_dir / topology,
    ]
    candidates += [
        p for p in model_dir.rglob("*")
        if p.is_dir() and p.name.startswith(f"dgrl_v11") and topology in p.name
    ]
    candidates += [
        p.parent for p in model_dir.rglob("policy.pth")
        if topology in str(p.parent)
    ]

    source_dir = next((p for p in candidates if p.is_dir() and (p / "policy.pth").exists()), None)
    if source_dir is None:
        source_dir = next((p for p in candidates if p.is_dir() and list(p.rglob("policy.pth"))), None)
    if source_dir is None:
        raise FileNotFoundError(
            f"Cannot find extracted Stable-Baselines3 model directory for topology={topology}"
        )

    if expected_zip.exists() and expected_zip.is_dir():
        moved_dir = expected_zip.with_name(expected_zip.name + "_extracted")
        if moved_dir.exists():
            shutil.rmtree(moved_dir)
        shutil.move(str(expected_zip), str(moved_dir))
        source_dir = moved_dir

    print(f"Repacking extracted model for {topology}: {source_dir} -> {expected_zip}")
    with zipfile.ZipFile(expected_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        policy_files = list(source_dir.rglob("policy.pth"))
        root = policy_files[0].parent if policy_files else source_dir
        for file_path in root.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(root))

for topo in ["vietnam", "nsfnet", "geant2"]:
    try:
        ensure_sb3_model_zip(topo)
    except FileNotFoundError:
        print(f"Skipping model check for {topo} (file/folder not found)")

for required in [
    "src/analytics/ablation_study.py",
    "src/analytics/training/train_harp_ablation.py",
    "src/orchestration/jo_vdpr/env.py",
    "data/real_telecom_combined.csv",
]:
    assert Path(required).exists(), f"Missing required file: {required}"

print(f"Extracted to {WORK_DIR}")

# %% Cell 3 - End-to-End Worker Configuration
from pathlib import Path

# =====================================================================
# CHANGE THIS LINE FOR EACH KAGGLE ACCOUNT: "vietnam", "nsfnet", or "geant2"
# =====================================================================
WORKER_TOPOLOGY = "vietnam"  

STEPS = 3000
SEED = 42

# Define optimal steps based on topology size (action space)
_STEPS_MAP = {
    "vietnam": 500_000,   # 10 nodes -> 100 actions
    "nsfnet": 2_000_000,  # 14 nodes -> 196 actions
    "geant2": 2_000_000,  # 23 nodes -> 529 actions
}
TRAIN_TOTAL_STEPS = _STEPS_MAP.get(WORKER_TOPOLOGY, 500_000)
TRAIN_N_ENVS = 4

# Scenarios to evaluate
WORKER_SCENARIOS = [
    ("uniform", "uniform"),
    ("bursty", "bursty"),
    ("heavyTail", "heavy_tail"),
]

WORKER_ROOT = Path("/kaggle/working/harp_ablation") / f"worker_{WORKER_TOPOLOGY}"
WORKER_ROOT.mkdir(parents=True, exist_ok=True)

print(f"Worker topology: {WORKER_TOPOLOGY}")
print(f"Train steps per variant: {TRAIN_TOTAL_STEPS}")
print(f"Eval steps per scenario: {STEPS}")
print(f"Scenarios: {[label for label, _ in WORKER_SCENARIOS]}")

# %% Cell 4 - Train All Strict Ablation Checkpoints
import os
import subprocess
import sys

env = os.environ.copy()
env["PYTHONPATH"] = f"{WORK_DIR}:{env.get('PYTHONPATH', '')}"
env["OMP_NUM_THREADS"] = "1"
env["MKL_NUM_THREADS"] = "1"
env["OPENBLAS_NUM_THREADS"] = "1"
env["MPLCONFIGDIR"] = "/tmp/matplotlib"

train_cmd = [
    sys.executable,
    "-m",
    "src.analytics.training.train_harp_ablation",
    "--variant", "all",
    "--topology", WORKER_TOPOLOGY,
    "--scenario", "heavy_tail", # Train on hardest scenario
    "--total-steps", str(TRAIN_TOTAL_STEPS),
    "--n-envs", str(TRAIN_N_ENVS),
    "--seed", str(SEED),
    "--data-path", "data/real_telecom_combined.csv",
    "--output-root", "results/models/ablation",
]

# ─── Check if we already have trained models AND they are compatible ───────────
import zipfile, io, torch

def _check_model_compatible(model_zip: Path, expected_action_dim: int) -> bool:
    """Return True only if the model's action_net output dim matches the env."""
    if not model_zip.exists():
        return False
    try:
        with zipfile.ZipFile(model_zip) as z:
            pth_names = [n for n in z.namelist() if n.endswith("policy.pth")]
            if not pth_names:
                return False
            with z.open(pth_names[0]) as f:
                sd = torch.load(io.BytesIO(f.read()), map_location="cpu",
                                weights_only=False)
        w = sd.get("action_net.weight")
        if w is None:
            return True   # Can't determine – assume OK
        return int(w.shape[0]) == expected_action_dim
    except Exception as e:
        print(f"  Warning: could not inspect model {model_zip}: {e}")
        return False

def _compute_action_dim(topology: str) -> int:
    from src.orchestration.jo_vdpr.topology import TopologyManager
    tm = TopologyManager(topology)
    return tm.num_nodes * tm.num_nodes  # Discrete(N*N)


expected_dim = _compute_action_dim(WORKER_TOPOLOGY)
model_out = Path("results/models/ablation")
existing_zips = list(model_out.glob("**/*.zip")) if model_out.exists() else []

# Check if harp_full variant (used for load sweep) is compatible
harp_full_zip = model_out / "harp_full" / f"dgrl_v11_harp_full_{WORKER_TOPOLOGY}.zip"
all_compatible = (
    len(existing_zips) >= 5
    and _check_model_compatible(harp_full_zip, expected_dim)
)

if all_compatible:
    print(f"✅ Ablation models exist and are compatible (action_dim={expected_dim}). Skipping training.")
else:
    if existing_zips and not all_compatible:
        print(f"⚠️  Found existing models but action_dim mismatch (expected={expected_dim}). Retraining...")
    print("======================================================")
    print(f"Training ablation checkpoints for {WORKER_TOPOLOGY}...")
    print("======================================================")
    print(" ".join(train_cmd))
    subprocess.check_call(train_cmd, env=env)
    print("Training completed.")

# %% Cell 5 - Evaluate 3 Scenarios & Generate Summary for 5 Seeds
import pandas as pd
import shutil
from IPython.display import display

SEEDS = [42, 100, 2024, 8888, 9999]
summary_dfs = []

for scenario_label, env_scenario in WORKER_SCENARIOS:
    for seed in SEEDS:
        out_dir = WORKER_ROOT / f"{WORKER_TOPOLOGY}_{scenario_label}_{STEPS}_seed_{seed}"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        eval_cmd = [
            sys.executable,
            "-m",
            "src.analytics.ablation_study",
            "--topology", WORKER_TOPOLOGY,
            "--scenario", env_scenario,
            "--steps", str(STEPS),
            "--seed", str(seed),
            "--version", "v11",
            "--data-path", "data/real_telecom_combined.csv",
            "--model-root", "results/models",
            "--output-dir", str(out_dir),
        ]
        
        print(f"\nEvaluating topology={WORKER_TOPOLOGY}, scenario={scenario_label}, seed={seed}")
        try:
            subprocess.check_call(eval_cmd, env=env)
        except subprocess.CalledProcessError:
            print(f"⚠️ Evaluation failed for {scenario_label} (seed {seed}). Check logs.")
            continue

        summary_path = out_dir / "harp_ablation_summary.csv"
        if summary_path.exists():
            df_tmp = pd.read_csv(summary_path)
            df_tmp.insert(0, "Topology", WORKER_TOPOLOGY)
            df_tmp.insert(1, "Scenario", scenario_label)
            # Make sure seed is tracked
            df_tmp["seed"] = seed
            summary_dfs.append(df_tmp)

if not summary_dfs:
    raise RuntimeError("No summary files were produced!")

# Merge into a single master CSV for all seeds
raw_summary = pd.concat(summary_dfs, ignore_index=True)

# Group by variant, topology, scenario and calculate mean and std
# Only use numeric cols that actually exist in the CSV
all_possible_numeric = ["acceptance_rate", "safe_acceptance_rate", "attempted_msd_violation_rate",
                        "admitted_msd_violation_rate", "sla_violation_rate", "evacuation_hit_rate",
                        "switching_rate", "avg_latency_ms", "avg_reward"]
numeric_cols = [c for c in all_possible_numeric if c in raw_summary.columns]
group_cols = [g for g in ["variant", "Topology", "Scenario"] if g in raw_summary.columns]

print(f"Aggregating columns: {numeric_cols}")
mean_df = raw_summary.groupby(group_cols)[numeric_cols].mean().reset_index()
std_df  = raw_summary.groupby(group_cols)[numeric_cols].std().reset_index()

# Format as "mean ± std"
final_summary = mean_df.copy()
for col in numeric_cols:
    final_summary[col] = (mean_df[col].round(3).astype(str)
                          + " \u00b1 "
                          + std_df[col].round(3).astype(str))

# Also save the raw per-seed CSV for transparency
raw_summary.to_csv(WORKER_ROOT / f"{WORKER_TOPOLOGY}_raw_ablation_5seeds.csv", index=False)

final_summary_path = WORKER_ROOT / f"{WORKER_TOPOLOGY}_master_ablation_summary_5seeds.csv"
final_summary.to_csv(final_summary_path, index=False)

print("\n======================================================")
print("FINAL ABLATION SUMMARY (5 SEEDS)")
print("======================================================")
display(final_summary)

# %% Cell 6 - Load Sweep
print("\n======================================================")
print("RUNNING LOAD SWEEP")
print("======================================================")

sweep_cmd = [
    sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_load_sweep",
    "--topology", WORKER_TOPOLOGY,
    "--data-path", "data/real_telecom_combined.csv",
    "--model-root", "results/models",
    "--output-dir", "results/benchmark_algorithm/load_sweep",
]
try:
    subprocess.check_call(sweep_cmd, env=env)
except subprocess.CalledProcessError as e:
    print(f"⚠️ Load sweep failed: {e}")


# %% Cell 7 - Benchmark Algorithms (Greedy, DAI, SAF-H, HARP)
print("\n======================================================")
print("RUNNING BENCHMARK ALGORITHMS (FOR TABLE 7)")
print("======================================================")

benchmark_cmd = [
    sys.executable,
    "-m",
    "src.analytics.benchmark.benchmark_algorithm.run_all",
    "--topology", WORKER_TOPOLOGY,
    "--scenario", "ablation",   # elephant_stress + burst_surge + chaos
    "--skip-exhaustive",
    "--data-path", "data/real_telecom_combined.csv",
    "--model-root", "results/models",
]

print(f"Running benchmark for {WORKER_TOPOLOGY}...")
try:
    subprocess.check_call(benchmark_cmd, env=env)
    print("Benchmark completed successfully.")
except subprocess.CalledProcessError as e:
    print(f"⚠️ Benchmark failed for {WORKER_TOPOLOGY}. Check logs. Error: {e}")

# Move the benchmark results to the worker root so they get zipped
benchmark_out = Path("results/benchmark_algorithm")
if benchmark_out.exists():
    dest_dir = WORKER_ROOT / "benchmark_results"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for csv_file in benchmark_out.rglob("*.csv"):   # rglob to catch subfolders
        shutil.copy2(csv_file, dest_dir / csv_file.name)
    print(f"Copied {len(list(dest_dir.glob('*.csv')))} benchmark CSVs to {dest_dir}")

# %% Cell 8 - Zip Results
print("\n======================================================")
print("ZIPPING RESULTS FOR DOWNLOAD")
print("======================================================")

# Move load sweep results to worker root
# run_load_sweep.py saves to results/benchmark_algorithm/load_sweep/
load_sweep_out = Path("results/benchmark_algorithm/load_sweep")
if not load_sweep_out.exists():
    load_sweep_out = Path("results/load_sweep")  # legacy fallback
if load_sweep_out.exists():
    dest_dir = WORKER_ROOT / "load_sweep_results"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in load_sweep_out.rglob("*"):
        if f.is_file():
            shutil.copy2(f, dest_dir / f.name)
    print(f"Copied {len(list(dest_dir.glob('*')))} load sweep files to {dest_dir}")
else:
    print("⚠️ Load sweep output not found — may have failed earlier.")

archive_base = Path("/kaggle/working") / f"harp_ablation_results_{WORKER_TOPOLOGY}"
archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=WORKER_ROOT)

print(f"\n✅ All done for {WORKER_TOPOLOGY}!")
print(f"Master CSV: {final_summary_path}")
print(f"Download Archive: {archive_path}")
