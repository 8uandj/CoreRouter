# %% [markdown]
# # HARP Ablation Study on Kaggle
# #
# Upload `kaggle_harp_ablation.zip` as a Kaggle Dataset, attach it to this
# notebook, then run the cells below. The zip already contains the source code,
# dataset CSVs, and final model artifacts needed by `src.analytics.ablation_study`.

# %% Cell 2
import sys
import subprocess

packages = [
    "gymnasium==1.1.1",
    "stable-baselines3[extra]==2.7.1",
    "sb3-contrib==2.7.1",
    "shimmy==2.0.0",
    "matplotlib==3.9.4",
    "pandas==2.3.3",
    "networkx==3.2.1",
    "scipy==1.13.1",
    "numpy==2.0.2",
]

for package in packages:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])

print("Dependencies installed")

# %% Cell 3
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

# %% Cell 4
from pathlib import Path

# Set to one topology per Kaggle execution: vietnam, nsfnet, or geant2.
WORKER_TOPOLOGY = "vietnam"
STEPS = 3000
SEEDS = [42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718]
TRAIN_TOTAL_STEPS = {"vietnam": 500_000, "nsfnet": 2_000_000, "geant2": 2_000_000}[WORKER_TOPOLOGY]
TRAIN_N_ENVS = 4
WORKER_SCENARIOS = [("elephant_stress", "heavy_tail"), ("chaos", "chaos")]
WORKER_ROOT = Path("/kaggle/working/harp_revision") / WORKER_TOPOLOGY
WORKER_ROOT.mkdir(parents=True, exist_ok=True)
print("Topology:", WORKER_TOPOLOGY, "Seeds:", SEEDS, "Scenarios:", WORKER_SCENARIOS)

# %% Cell 5
import os, subprocess, sys
from pathlib import Path
from src.analytics.ablation_study import VARIANTS, resolve_variant_model_paths, preflight_variant
from src.analytics.benchmark.benchmark_algorithm.config import AlgorithmBenchmarkConfig
from src.analytics.benchmark.benchmark_algorithm.run_all import preflight_algorithm_inputs

env = os.environ.copy()
env["PYTHONPATH"] = f"{WORK_DIR}:{env.get('PYTHONPATH', '')}"
env["OMP_NUM_THREADS"] = env["MKL_NUM_THREADS"] = env["OPENBLAS_NUM_THREADS"] = "1"
env["MPLCONFIGDIR"] = "/tmp/matplotlib"
DATA = Path("data/real_telecom_combined.csv")
MODEL_ROOT = Path("results/models")

def ablation_artifacts_ready():
    try:
        artifacts = [resolve_variant_model_paths(MODEL_ROOT, "v11", WORKER_TOPOLOGY, v) for v in VARIANTS]
        for variant, (model, norm, _) in zip(VARIANTS, artifacts):
            preflight_variant(variant, WORKER_TOPOLOGY, "chaos", 2, DATA, model, norm, 1.0, (3, 5))
        return True
    except Exception as exc:
        print("Ablation preflight requires training:", exc)
        return False

if not ablation_artifacts_ready():
    subprocess.check_call([
        sys.executable, "-m", "src.analytics.training.train_harp_ablation",
        "--variant", "all", "--topology", WORKER_TOPOLOGY,
        "--scenario", "heavy_tail", "--total-steps", str(TRAIN_TOTAL_STEPS),
        "--n-envs", str(TRAIN_N_ENVS), "--seed", "42",
        "--data-path", str(DATA), "--output-root", str(MODEL_ROOT / "ablation"),
    ], env=env)

benchmark_config = AlgorithmBenchmarkConfig(topology=WORKER_TOPOLOGY, data_path=DATA, model_root=MODEL_ROOT)
try:
    preflight_algorithm_inputs(benchmark_config, [WORKER_TOPOLOGY], "chaos", "stress")
except Exception as exc:
    print("Main benchmark checkpoint requires training:", exc)
    subprocess.check_call([sys.executable, "-m", "src.analytics.training.train_v11",
                           "--topology", WORKER_TOPOLOGY], env=env)
    preflight_algorithm_inputs(benchmark_config, [WORKER_TOPOLOGY], "chaos", "stress")
print("Model/normalizer/topology/action/observation preflights passed.")

# %% Cell 6
import pandas as pd
from IPython.display import display
summary_frames = []
for scenario_label, env_scenario in WORKER_SCENARIOS:
    out_dir = WORKER_ROOT / scenario_label
    command = [sys.executable, "-m", "src.analytics.ablation_study",
        "--topology", WORKER_TOPOLOGY, "--scenario", env_scenario,
        "--steps", str(STEPS), "--seeds", *map(str, SEEDS),
        "--version", "v11", "--data-path", str(DATA),
        "--model-root", str(MODEL_ROOT), "--output-dir", str(out_dir)]
    print("Running strict ablation:", scenario_label)
    subprocess.check_call(command, env=env)
    summary_path = out_dir / WORKER_TOPOLOGY / env_scenario / "harp_ablation_summary.csv"
    frame = pd.read_csv(summary_path)
    expected_rows = len(SEEDS) * len(VARIANTS)
    if len(frame) != expected_rows or frame["seed"].nunique() != len(SEEDS):
        raise RuntimeError(f"Ablation coverage failed: {summary_path}, rows={len(frame)}")
    if frame.groupby("seed")["trace_sha256"].nunique().max() != 1:
        raise RuntimeError(f"Variant workload traces differ for a shared seed: {summary_path}")
    frame.insert(0, "scenario_label", scenario_label)
    summary_frames.append(frame)
raw = pd.concat(summary_frames, ignore_index=True)
raw.to_csv(WORKER_ROOT / f"{WORKER_TOPOLOGY}_ablation_per_seed.csv", index=False)
display(raw.groupby(["scenario_label", "key"])[[
    "safe_acceptance_rate", "proposed_cpu_violation_rate", "proposed_ram_violation_rate",
    "attempted_msd_violation_rate", "admitted_hard_violation_rate",
    "runtime_rejection_rate", "primary_cpu_rejection_rate", "primary_ram_rejection_rate",
    "primary_msd_rejection_rate", "primary_bw_rejection_rate",
]].agg(["mean", "std"]))

# %% Cell 7
print("Running matched protected load sweep")
subprocess.check_call([sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_load_sweep",
    "--topology", WORKER_TOPOLOGY, "--steps", str(STEPS), "--seeds", *map(str, SEEDS),
    "--data-path", str(DATA), "--model-root", str(MODEL_ROOT),
    "--output-dir", str(WORKER_ROOT / "load_sweep")], env=env)

# %% Cell 8
print("Running matched protected benchmark scenarios")
subprocess.check_call([sys.executable, "-m", "src.analytics.benchmark.benchmark_algorithm.run_all",
    "--topology", WORKER_TOPOLOGY, "--scenario", "thesis", "--steps", str(STEPS),
    "--workers", "1", "--skip-exhaustive", "--data-path", str(DATA),
    "--model-root", str(MODEL_ROOT), "--output-dir", str(WORKER_ROOT / "benchmark")], env=env)

# %% Cell 9
import shutil
archive = shutil.make_archive(str(Path("/kaggle/working") / f"harp_revision_{WORKER_TOPOLOGY}"),
                              "zip", root_dir=WORKER_ROOT)
print("Revision artifacts:", archive)
