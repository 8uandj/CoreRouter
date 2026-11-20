#!/usr/bin/env python3
"""Build a self-contained HARP/AIO-Mesh revision evidence submission folder.

Live evidence is moved atomically at directory granularity into the bundle;
the original results/evidence path is then a symlink to the bundle so existing
tmux jobs keep writing into the canonical package location.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "AIO-mesh-submit-2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_path(source: Path, destination: Path) -> None:
    if source.is_dir():
        def ignore_generated(directory: str, names: list[str]) -> set[str]:
            ignored = {name for name in names if name in {"__pycache__", ".pytest_cache", "node_modules"}
                       or name.endswith(".pyc")}
            if Path(directory) == ROOT / "src/portal/backend":
                ignored.add("env")
            if Path(directory) == ROOT / "data":
                ignored.add("_raw_cache")
            return ignored

        shutil.copytree(source, destination, symlinks=True, ignore=ignore_generated)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    else:
        raise FileNotFoundError(source)


def git_text(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def main() -> None:
    if BUNDLE.exists() or BUNDLE.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing package: {BUNDLE}")
    (BUNDLE / "provenance").mkdir(parents=True)

    # Runnable source snapshot: preserves current uncommitted source/document edits.
    for name in ("src", "notebook", "data"):
        copy_path(ROOT / name, BUNDLE / name)
    for name in ("configs/rev1", "scripts/rev1", "scripts/paper", "tests/rev1"):
        copy_path(ROOT / name, BUNDLE / name)
    copy_path(ROOT / "docs/AIO-mesh-rev1", BUNDLE / "docs/AIO-mesh-rev1")
    copy_path(ROOT / "docs/response_rev1.tex", BUNDLE / "docs/response_rev1.tex")
    for name in ("README.md", "REPRODUCE.md", "Makefile", "requirements.txt", "requirements-dev.txt"):
        copy_path(ROOT / name, BUNDLE / name)

    # Current primary N^2 models, all checkpoint/normalizer pairs, and ablations.
    for relative in (
        "results/models/retrain_v11_20261119_corrected",
        "results/models/ablation",
        "results/models/v11_synthetic_25",
        "results/models/v11_synthetic_50",
        "results/models/v11_synthetic_100",
    ):
        copy_path(ROOT / relative, BUNDLE / relative)

    # Latest model training logs only; obsolete pre-correction retrains are omitted.
    (BUNDLE / "results/rev1/training_logs").mkdir(parents=True)
    for name in ("retrain_v11_20261119_corrected",):
        copy_path(ROOT / "results/rev1/training_logs" / name,
                  BUNDLE / "results/rev1/training_logs" / name)
    for name in ("synthetic_25_batch32.log", "synthetic_50_batch32.log", "synthetic_100_batch32.log"):
        copy_path(ROOT / "results/rev1/training_logs" / name,
                  BUNDLE / "results/rev1/training_logs" / name)

    # Existing N^2 ablation outputs and analyses referenced by the revision.
    for relative in (
        "results/rev1/e3_timed",
        "results/rev1/e3_ablation_analysis",
        "results/rev1/vietnam/ablation",
        "results/rev1/nsfnet/ablation",
        "results/rev1/geant2/ablation",
        "results/evidence_audit",
    ):
        copy_path(ROOT / relative, BUNDLE / relative)

    # Capture exact checkout state and environment needed to interpret the snapshot.
    (BUNDLE / "provenance/source_commit.txt").write_text(git_text("rev-parse", "HEAD"), encoding="utf-8")
    (BUNDLE / "provenance/source_branch.txt").write_text(git_text("branch", "--show-current"), encoding="utf-8")
    (BUNDLE / "provenance/source_status_porcelain.txt").write_text(git_text("status", "--short"), encoding="utf-8")
    (BUNDLE / "provenance/source_diff.patch").write_text(git_text("diff", "--binary", "HEAD"), encoding="utf-8")
    (BUNDLE / "provenance/python_version.txt").write_text(sys.version, encoding="utf-8")
    (BUNDLE / "provenance/platform.txt").write_text(platform.platform() + "\n", encoding="utf-8")
    freeze = subprocess.run([str(ROOT / "venv/bin/python"), "-m", "pip", "freeze"],
                            cwd=ROOT, text=True, capture_output=True, check=True)
    (BUNDLE / "provenance/requirements-lock.txt").write_text(freeze.stdout, encoding="utf-8")

    evidence_source = ROOT / "results/evidence"
    evidence_target = BUNDLE / "results/evidence"
    if evidence_source.is_symlink() or not evidence_source.is_dir() or evidence_target.exists():
        raise RuntimeError(f"Unexpected live-evidence paths: {evidence_source}, {evidence_target}")
    evidence_target.parent.mkdir(parents=True, exist_ok=True)
    # Existing tmux processes hold open log file descriptors; rename keeps those
    # descriptors valid. Future open() calls resolve through the compatibility link.
    os.replace(evidence_source, evidence_target)
    relative_target = os.path.relpath(evidence_target, evidence_source.parent)
    evidence_source.symlink_to(relative_target, target_is_directory=True)

    README = f"""# AIO-Mesh revision submission bundle

Canonical folder for the current paper revision source and evidence. The
`results/evidence` directory here is the physical home of all live benchmark,
load/chain, and oracle evidence. The workspace path `{evidence_source.relative_to(ROOT)}`
is a compatibility symlink to this directory, so existing tmux jobs continue
writing here after this package was created.

## Contents

- `src/`, `configs/`, `scripts/`, `infrastructure/`, `tests/`, `notebook/`,
  `data/`: current source snapshot and required input data.
- `docs/AIO-mesh-rev1/` and `docs/response_rev1.tex`: current revision and
  mentor-response material, including prior audit evidence.
- `results/models/`: corrected Vietnam/NSFNET/GEANT2 main retrains, synthetic
  25/50/100-node models, all paired normalizers/checkpoints, and current
  ablation models.
- `results/rev1/training_logs/`: corrected main-retrain logs and latest
  synthetic batch32 training logs.
- `results/rev1/e3_*` and topology `ablation/`: retained N^2 ablation records.
- `results/evidence/`: live six-topology benchmark and refreshed-model
  load/background-chain/oracle reruns, with logs, commands, manifests, and
  generated CSV/JSON/plots.
- `provenance/`: source commit/branch/dirty-state, tracked diff, Python/runtime
  package versions.

## Evidence status at packaging

The benchmark sessions and model-refresh reruns were active at package time.
Their log files were moved without stopping the processes; subsequent CSV,
JSON, and manifest writes are directed into this bundle through the workspace
compatibility symlink. Regenerate the hash inventory after all sessions finish
with `python3 scripts/rev1/refresh_submission_manifest.py`.

The HIL/testbed machine is separate. No HIL logs or measurements are claimed
or included as if they were present on this server. Legacy pre-correction
main-model training and benchmark archives are intentionally excluded; the
current main models are under `results/models/retrain_v11_20261119_corrected/`.
"""
    (BUNDLE / "SUBMISSION_README.md").write_text(README, encoding="utf-8")
    package = {
        "bundle": BUNDLE.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": git_text("rev-parse", "HEAD").strip(),
        "source_branch": git_text("branch", "--show-current").strip(),
        "source_worktree_dirty": bool(git_text("status", "--porcelain").strip()),
        "live_evidence_canonical_path": "results/evidence",
        "workspace_evidence_compatibility_symlink": os.readlink(evidence_source),
        "mutable_paths_until_jobs_finish": [
            "results/evidence/multinode_benchmark_20261120_084017",
            "results/evidence/model_refresh_reruns_20261120_163000",
        ],
        "excluded": [
            "legacy pre-correction main model checkpoints/training logs",
            "HIL/testbed artifacts, which are on a separate server",
            "venv and machine-specific caches",
        ],
        "hash_inventory_status": "generate after live processes complete",
    }
    (BUNDLE / "PACKAGE_MANIFEST.json").write_text(json.dumps(package, indent=2), encoding="utf-8")
    print(f"Created {BUNDLE}")
    print(f"Live evidence path now resolves to {evidence_target}")


if __name__ == "__main__":
    main()
