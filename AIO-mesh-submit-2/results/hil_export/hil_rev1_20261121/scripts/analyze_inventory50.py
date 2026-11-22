#!/usr/bin/env python3
"""Summarize the preserved 50-Deployment inventory snapshot and its reduction to 7.

Inputs: 03_inventory50/original/... (copied, hash-verified originals).
Output: generated/inventory50_summary.json and generated/inventory50_deployments.csv
Usage: python3 scripts/analyze_inventory50.py <export_root>
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def main() -> int:
    export = Path(sys.argv[1]).resolve()
    base = export / "03_inventory50/original/rebuild_20261117T123405Z"
    base0 = export / "03_inventory50/original/rebuild_20261117T122432Z"
    dep = json.loads((base / "deployments.json").read_text())
    items = dep.get("items", [])
    rows = []
    for it in items:
        md, sp, st = it["metadata"], it.get("spec", {}), it.get("status", {})
        tmpl = sp.get("template", {}).get("spec", {})
        rows.append({
            "name": md["name"], "namespace": md.get("namespace"), "created": md.get("creationTimestamp"),
            "replicas": sp.get("replicas"), "ready_replicas": st.get("readyReplicas", 0),
            "available_replicas": st.get("availableReplicas", 0),
            "image": ";".join(c.get("image", "") for c in tmpl.get("containers", [])),
            "node_selector": json.dumps(tmpl.get("nodeSelector", {}), sort_keys=True),
        })
    expected = [l.strip() for l in (base / "expected_50_names.txt").read_text().splitlines() if l.strip()]
    keep = [l.strip() for l in (base0 / "keep_names.txt").read_text().splitlines() if l.strip()]
    retire = [l.strip() for l in (base0 / "retire_names.txt").read_text().splitlines() if l.strip()]
    names = {r["name"] for r in rows}
    ready = [r for r in rows if r["replicas"] and r["ready_replicas"] == r["replicas"]]
    images = {}
    for r in rows:
        images[r["image"]] = images.get(r["image"], 0) + 1
    final_gate = json.loads((base / "phase4_final_inventory_gate.json").read_text())
    summary = {
        "snapshot_file": "03_inventory50/original/rebuild_20261117T123405Z/deployments.json",
        "snapshot_file_mtime_note": "captured 2026-11-17 ~12:36 UTC (see ORIGINAL_SOURCE_INVENTORY.csv)",
        "deployments_in_snapshot": len(rows),
        "deployments_fully_ready": len(ready),
        "matches_expected_50_names": sorted(names) == sorted(expected),
        "keep_names": keep, "retire_count": len(retire),
        "keep_plus_retire_equals_snapshot": sorted(keep + retire) == sorted(names),
        "images": images,
        "creation_timestamp_range": [min(r["created"] for r in rows), max(r["created"] for r in rows)],
        "after_retirement_gate": final_gate,
        "relation_to_12h_hil": "The 12-h HIL run (2026-11-17 19:02 UTC onward) observed only the 7 keep_names; "
                               "the 50-Deployment snapshot predates the retirement of 43 Deployments at ~13:05 UTC "
                               "and is not a state during the HIL run.",
    }
    out = export / "generated"
    (out / "inventory50_summary.json").write_text(json.dumps(summary, indent=2))
    with (out / "inventory50_deployments.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["name"]))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("keep_names", "after_retirement_gate")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
