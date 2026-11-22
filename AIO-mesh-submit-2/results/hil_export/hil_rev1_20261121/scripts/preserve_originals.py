#!/usr/bin/env python3
"""Copy selected original HIL artifacts into the export without modifying sources.

* Source directories are only read.
* Every source file under the listed roots is hashed (full inventory), even if it
  is not copied; large or unrelated files are referenced by path + SHA-256.
* Each copied file is re-hashed after copying and must match its source.

Usage: python3 -I scripts/preserve_originals.py <export_root>
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/CoreRouter")
MAX_COPY_BYTES = 20 * 1024 * 1024  # files above this are referenced, not copied

# (source root relative to repo, destination relative to export, copy filter)
HIL12H = "results/rev1/e6_12h_control_plane"
REBUILD = "results/hil/rebuild_20261117T123405Z"
REBUILD0 = "results/hil/rebuild_20261117T122432Z"
PILOT24 = "results/rev1/e6_24h_control_plane"
MANUAL = "results/hil/manual-20261117_094746"


def copy_all(_rel: str) -> bool:
    return True


FORWARDING_PREFIXES = (
    "phase10_", "phase11_", "phase12_", "phase13_", "phase14_", "phase15_",
    "phase16_", "phase17_", "phase18_", "phase19_", "phase20_live_recheck/",
    "offline_p4_build/", "phase9_",
)
FORWARDING_FILES = {
    "report.json", "table_readback.txt", "s1.log", "s2.log", "boundary_in.pcap",
    "boundary_out.pcap", "over_msd_in.pcap", "p4_compile_offline.log",
    "P4_REALIZATION_IMPLEMENTATION_PLAN.md", "FULL_HIL_EXECUTION_PLAN.md",
    "progress.md", "PROGRESS_20261117.md", "FINAL_REPORT.md", "HANDOFF.md",
    "live_p4_readonly_audit.txt", "live_p4_ports_all.txt", "live_switch_interface_audit.txt",
    "live_k8s_bridge_audit.txt", "live_mininet_tmux_tail.txt", "live_p4_ports_s1.txt",
    "admission_only_smoke.py", "admission_only_smoke.log", "admission_smoke_request.json",
    "admission_smoke_response.json", "admission_smoke_summary.json",
    "admission_smoke_cleanup_response.json", "admission_smoke_state_after_cleanup.json",
    "unsupported_realization_smoke.py", "unsupported_realization_smoke.log",
    "unsupported_smoke_request.json", "unsupported_smoke_response.json",
    "unsupported_smoke_summary.json", "unsupported_smoke_state_after.json",
    "artifact_sha256.txt", "final_key_hashes.sha256", "phase_status.json",
    "phase8_report.md", "phase9_report.md", "phase8_gate_summary.json",
    "LIVE_BASELINE_SNAPSHOT_20261117.md",
}
INVENTORY_FILES = {
    "expected_50_names.txt", "deployments.json", "inventory_gate.txt", "gate1_summary.txt",
    "phase4_final_inventory_gate.json", "phase4_deployment_delete_verify.txt",
    "phase4_delete_deployments.log", "phase4_predelete_gate.txt", "retire_names.phase4.txt",
    "phase7_final_summary.json", "seed_summary.json", "phase4_ledger_gate.json",
}
INVENTORY0_FILES = {
    "deployments_50.yaml", "deployments.txt", "inventory_comparison.json", "keep_names.txt",
    "retire_names.txt", "manifest_hashes.sha256", "artifact_manifest.sha256",
    "nodes.txt", "phase_status.json", "session_transcript.md",
}


def forwarding_filter(rel: str) -> bool:
    return rel in FORWARDING_FILES or rel.startswith(FORWARDING_PREFIXES)


PLAN = [
    # root, export destination, filter, label
    (HIL12H, "01_hil12h/original/e6_12h_control_plane", copy_all, "hil12h"),
    (PILOT24, "01_hil12h/original/e6_24h_control_plane_pilot", copy_all, "pilot24h_not_used"),
    (REBUILD, "02_forwarding_overmsd/original/rebuild_20261117T123405Z", forwarding_filter, "forwarding_overmsd"),
    (REBUILD, "03_inventory50/original/rebuild_20261117T123405Z", lambda r: r in INVENTORY_FILES, "inventory50"),
    (REBUILD0, "03_inventory50/original/rebuild_20261117T122432Z", lambda r: r in INVENTORY0_FILES, "inventory50"),
    (MANUAL, None, lambda r: False, "reference_only"),
    ("results/rev1/runtime", None, lambda r: False, "live_ledger_reference_only"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    export = Path(sys.argv[1]).resolve()
    rows = []
    hashes: dict[str, str] = {}
    errors = []
    for root_rel, dest_rel, keep, label in PLAN:
        root = REPO / root_rel
        for src in sorted(p for p in root.rglob("*") if p.is_file() or p.is_symlink()):
            rel = src.relative_to(root).as_posix()
            if "__pycache__" in rel:
                continue
            key = f"{root_rel}/{rel}"
            try:
                digest = hashes.get(key) or sha256(src)
            except PermissionError as exc:
                rows.append({"source": key, "bytes": "", "sha256": "", "mtime_utc": "",
                             "label": label, "copied_to": "", "copy_verified": f"unreadable: {exc}"})
                continue
            hashes[key] = digest
            st = src.stat()
            copied_to, verified = "", ""
            if dest_rel and keep(rel):
                if st.st_size > MAX_COPY_BYTES:
                    verified = "referenced_only_size_limit"
                else:
                    dst = export / dest_rel / rel
                    if dst.exists():
                        errors.append(f"refusing to overwrite {dst}")
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    ok = sha256(dst) == digest
                    copied_to = dst.relative_to(export).as_posix()
                    verified = "match" if ok else "MISMATCH"
                    if not ok:
                        errors.append(f"hash mismatch after copy: {key}")
            rows.append({
                "source": key, "bytes": st.st_size, "sha256": digest,
                "mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                "label": label, "copied_to": copied_to, "copy_verified": verified,
            })
    out = export / "ORIGINAL_SOURCE_INVENTORY.csv"
    if out.exists():
        print(f"refusing to overwrite {out}", file=sys.stderr)
        return 2
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_files_hashed": len(rows),
        "copied": sum(1 for r in rows if r["copied_to"]),
        "referenced_only_size_limit": sum(1 for r in rows if r["copy_verified"] == "referenced_only_size_limit"),
        "unreadable": sum(1 for r in rows if str(r["copy_verified"]).startswith("unreadable")),
        "errors": errors,
    }
    (export / "ORIGINAL_SOURCE_INVENTORY.summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
