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
    ensure_sb3_model_zip(topo)

for required in [
    "src/analytics/ablation_study.py",
    "src/analytics/training/train_harp_ablation.py",
    "src/orchestration/jo_vdpr/env.py",
    "data/real_telecom_combined.csv",
    "results/models/v11/dgrl_v11_final_vietnam.zip",
    "results/models/v11/vec_normalize_v11_vietnam.pkl",
]:
    assert Path(required).exists(), f"Missing required file: {required}"

print(f"Extracted to {WORK_DIR}")

# %% Cell 3 - Choose Run Configuration
from pathlib import Path

TOPOLOGY = "vietnam"       # "vietnam", "nsfnet", or "geant2"
SCENARIO = "heavy_tail"    # "heavy_tail", "bursty", or "uniform"
STEPS = 3000               # use 100-300 for a quick smoke run
SEED = 42

# Training ablation checkpoints is the scientifically clean setting.
# Use 100_000 for a short sanity run, 500_000+ for thesis-grade runs,
# and 3_000_000 if you want to match the original full HARP training budget.
TRAIN_VARIANTS = True
TRAIN_TOTAL_STEPS = 500_000
TRAIN_N_ENVS = 4

OUTPUT_DIR = Path("/kaggle/working/harp_ablation") / f"{TOPOLOGY}_{SCENARIO}_{STEPS}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Run config")
print(f"  topology: {TOPOLOGY}")
print(f"  scenario: {SCENARIO}")
print(f"  steps:    {STEPS}")
print(f"  train variants: {TRAIN_VARIANTS}")
print(f"  train steps:    {TRAIN_TOTAL_STEPS}")
print(f"  output:   {OUTPUT_DIR}")

# %% Cell 4 - Train Variant-Specific Ablation Checkpoints
import os
import subprocess
import sys

env = os.environ.copy()
env["PYTHONPATH"] = f"{WORK_DIR}:{env.get('PYTHONPATH', '')}"
env["OMP_NUM_THREADS"] = "1"
env["MKL_NUM_THREADS"] = "1"
env["OPENBLAS_NUM_THREADS"] = "1"
env["MPLCONFIGDIR"] = "/tmp/matplotlib"

if TRAIN_VARIANTS:
    train_cmd = [
        sys.executable,
        "-m",
        "src.analytics.training.train_harp_ablation",
        "--variant", "all",
        "--topology", TOPOLOGY,
        "--scenario", SCENARIO,
        "--total-steps", str(TRAIN_TOTAL_STEPS),
        "--n-envs", str(TRAIN_N_ENVS),
        "--seed", str(SEED),
        "--data-path", "data/real_telecom_combined.csv",
        "--output-root", "results/models/ablation",
    ]
    print("Training ablation checkpoints:")
    print(" ".join(train_cmd))
    subprocess.check_call(train_cmd, env=env)
else:
    print("Skipping training. Evaluation requires existing strict variant checkpoints under results/models/ablation/<variant>/.")

# %% Cell 5 - Run the Five HARP Ablation Variants
import os
import subprocess
import sys

cmd = [
    sys.executable,
    "-m",
    "src.analytics.ablation_study",
    "--topology", TOPOLOGY,
    "--scenario", SCENARIO,
    "--steps", str(STEPS),
    "--seed", str(SEED),
    "--version", "v11",
    "--data-path", "data/real_telecom_combined.csv",
    "--model-root", "results/models",
    "--output-dir", str(OUTPUT_DIR),
]

print("Running:")
print(" ".join(cmd))
subprocess.check_call(cmd, env=env)

print("Ablation finished")

# %% Cell 6 - Inspect Results
import pandas as pd
from IPython.display import display, Image

summary_path = OUTPUT_DIR / "harp_ablation_summary.csv"
json_path = OUTPUT_DIR / "harp_ablation_results.json"
dashboard_path = OUTPUT_DIR / "harp_ablation_dashboard.png"

df = pd.read_csv(summary_path)
preferred_cols = [
    "variant",
    "policy_source",
    "acceptance_rate",
    "safe_acceptance_rate",
    "attempted_msd_violation_rate",
    "admitted_msd_violation_rate",
    "sla_violation_rate",
    "avg_latency_ms",
    "avg_reward",
]
display(df[[c for c in preferred_cols if c in df.columns]])

print("\nInterpretation notes:")
print("- Use safe_acceptance_rate, not raw acceptance_rate, when comparing hard vs soft MSD.")
print("- Evaluation is strict: every row must have policy_source=variant_checkpoint:...")
print("- w/o GAT is a separately trained, parameter-matched flat MLP policy, not a heuristic fallback.")
print("- Each variant uses its own VecNormalize statistics from results/models/ablation/<variant>/.")

print(f"CSV:  {summary_path}")
print(f"JSON: {json_path}")
print(f"PNG:  {dashboard_path}")

display(Image(filename=str(dashboard_path)))

# %% Cell 7 - Optional: Run All Three Stress Scenarios
import subprocess
import sys

for scenario in ["heavy_tail", "bursty", "uniform"]:
    out_dir = Path("/kaggle/working/harp_ablation") / f"{TOPOLOGY}_{scenario}_{STEPS}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "src.analytics.ablation_study",
        "--topology", TOPOLOGY,
        "--scenario", scenario,
        "--steps", str(STEPS),
        "--seed", str(SEED),
        "--version", "v11",
        "--data-path", "data/real_telecom_combined.csv",
        "--model-root", "results/models",
        "--output-dir", str(out_dir),
    ]
    print("Running", scenario)
    subprocess.check_call(cmd, env=env)

print("All selected scenarios finished")
