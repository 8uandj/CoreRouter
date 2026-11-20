#!/usr/bin/env python3
"""Build a read-only provenance inventory for the 2026-11-19 evidence audit.

This script hashes files and reads SB3 ZIP metadata. It never edits source
artifacts; it only creates the audit package directory and refuses to replace
an existing package.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/AIO-mesh-rev1/evidence/audit_20261119"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def action_info(path: Path):
    with zipfile.ZipFile(path) as zf:
        if "data" not in zf.namelist():
            return "unreadable", "", ""
        data = json.loads(zf.read("data"))
    space = data.get("action_space") or {}
    n = space.get("n")
    nvec = space.get("nvec")
    if n is not None:
        number = int(n)
        root = round(number ** 0.5)
        return "Discrete", str(number), f"N^2={root * root}" if root * root == number else "not_square"
    if nvec is not None:
        dims = [int(x) for x in re.findall(r"\d+", str(nvec))]
        return "MultiDiscrete", ";".join(map(str, dims)), f"logits_sum={sum(dims)}"
    return "unknown", "", ""


def write_csv(path: Path, rows: List[Dict], columns: Optional[List[str]] = None):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns = columns or list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    models = ROOT / "results/models"
    checkpoints = []
    for p in sorted(models.rglob("*.zip")):
        try:
            kind, dims, note = action_info(p)
        except Exception as exc:  # retain unparseable files in the inventory
            kind, dims, note = "unreadable", "", type(exc).__name__
        checkpoints.append({"path": p.relative_to(ROOT), "sha256": sha(p),
                            "bytes": p.stat().st_size, "action_space": kind,
                            "action_dims": dims, "head_interpretation": note})
    write_csv(OUT / "checkpoint_action_space_inventory.csv", checkpoints)

    artifacts = []
    for base in (ROOT / "data", models, ROOT / "results/ablation/HARP-model"):
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in {".zip", ".pkl", ".npz", ".csv", ".json", ".log", ".yaml", ".yml"}:
                continue
            artifacts.append({"path": p.relative_to(ROOT), "bytes": p.stat().st_size,
                              "sha256": sha(p), "suffix": p.suffix.lower()})
    write_csv(OUT / "artifact_hashes.csv", artifacts)

    index_rows = []
    for index in sorted((ROOT / "docs/AIO-mesh-rev1/evidence/run_index").glob("*.json")):
        obj = json.loads(index.read_text(encoding="utf-8"))
        for item in obj.get("artifacts", []):
            p = ROOT / item["path"]
            status = "missing" if not p.exists() else "directory" if p.is_dir() else "file"
            index_rows.append({"experiment": obj.get("experiment", index.stem),
                               "indexed_path": item["path"], "indexed_kind": item.get("kind"),
                               "current_status": status,
                               "current_sha256": sha(p) if p.is_file() else "",
                               "indexed_sha256": item.get("sha256") or "",
                               "recorded_original_sha256": item.get("recorded_original_sha256") or ""})
    write_csv(OUT / "run_index_presence_check.csv", index_rows)

    manifest = {
        "created_utc": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip(),
        "host": subprocess.check_output(["hostname"], text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "worktree_porcelain": subprocess.check_output(["git", "status", "--porcelain=v2"], cwd=ROOT, text=True).strip(),
        "python": subprocess.check_output([str(ROOT / "venv/bin/python"), "--version"], cwd=ROOT, text=True).strip(),
        "scope": "Inventory and hashes are read-only; evaluation reruns are stored separately under results/evidence_audit/reruns_20261119/.",
        "counts": {"checkpoint_zip_files": len(checkpoints), "artifact_files_hashed": len(artifacts),
                   "run_index_entries_checked": len(index_rows)},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
