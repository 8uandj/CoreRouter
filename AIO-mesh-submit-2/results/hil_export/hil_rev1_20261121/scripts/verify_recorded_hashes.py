#!/usr/bin/env python3
"""Re-check every SHA-256 manifest recorded during the November 17-19 HIL work.

Reads sha256sum-style manifests (``<hash>  <path>``) in the HIL run directories
plus the JSON run indexes in docs/AIO-mesh-rev1/evidence/run_index. Paths are
resolved relative to the repository root first, then to the manifest's
directory. Writes a CSV with one row per recorded entry.

Classification:
  match              current file hash equals the recorded hash
  mismatch_mutable   differs, but the entry describes a file that was still
                     being written or is a self-referencing manifest/source file
  MISMATCH           differs for an artifact that should be immutable
  missing            path not found

Usage: python3 -I scripts/verify_recorded_hashes.py <export_root>
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path("/home/CoreRouter")
MANIFEST_GLOBS = [
    "results/hil/rebuild_20261117T123405Z/*sha256*",
    "results/hil/rebuild_20261117T123405Z/*SHA256*",
    "results/hil/rebuild_20261117T123405Z/*hashes*",
    "results/hil/rebuild_20261117T122432Z/*sha256*",
    "results/hil/rebuild_20261117T122432Z/*SHA256*",
    "results/hil/rebuild_20261117T122432Z/*hashes*",
    "results/hil/rebuild_20261117T123405Z/phase20_live_recheck/SHA256SUMS",
]
RUN_INDEX = REPO / "docs/AIO-mesh-rev1/evidence/run_index"
LINE = re.compile(r"^([0-9a-f]{64})\s+\*?(.+)$")
# Files that legitimately change after their hash was recorded.
MUTABLE_HINTS = ("sha256", "SHA256", "hashes", "progress.md", "HANDOFF.md", "FINAL_REPORT.md",
                 "src/", "infrastructure/", "tests/", "scripts/", "docs/", "configs/",
                 "reservations.sqlite3", "migrations.sqlite3", ".py")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(path_text: str, manifest: Path) -> Path | None:
    path_text = path_text.strip()
    candidates = [Path(path_text)] if path_text.startswith("/") else [
        REPO / path_text, manifest.parent / path_text]
    for c in candidates:
        if c.exists():
            return c
    return None


def main() -> int:
    export = Path(sys.argv[1]).resolve()
    rows = []
    manifests = sorted({m for g in MANIFEST_GLOBS for m in REPO.glob(g) if m.is_file()})
    for manifest in manifests:
        for line in manifest.read_text(errors="replace").splitlines():
            m = LINE.match(line.strip())
            if not m:
                continue
            recorded, path_text = m.groups()
            target = resolve(path_text, manifest)
            if target is None:
                status, current = "missing", ""
            else:
                current = sha256(target) if target.is_file() else ""
                if current == recorded:
                    status = "match"
                elif any(h in path_text for h in MUTABLE_HINTS):
                    status = "mismatch_mutable"
                else:
                    status = "MISMATCH"
            rows.append({"manifest": manifest.relative_to(REPO).as_posix(), "path": path_text,
                         "recorded_sha256": recorded, "current_sha256": current, "status": status})
    for idx in sorted(RUN_INDEX.glob("*.json")):
        data = json.loads(idx.read_text())
        if data.get("experiment") not in ("hil12h", "forwarding"):
            continue
        for art in data.get("artifacts", []):
            p = REPO / art["path"]
            rec = art.get("sha256")
            if not rec:
                status, cur = ("missing" if not p.exists() else "no_recorded_hash"), ""
            else:
                cur = sha256(p) if p.is_file() else ""
                status = "match" if cur == rec else ("missing" if not p.exists() else "MISMATCH")
            rows.append({"manifest": idx.relative_to(REPO).as_posix(), "path": art["path"],
                         "recorded_sha256": rec or "", "current_sha256": cur, "status": status})
    out = export / "generated" / "recorded_hash_verification.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(json.dumps({"manifests": len(manifests), "entries": len(rows), "status_counts": counts}, indent=2))
    for r in rows:
        if r["status"] in ("MISMATCH", "missing"):
            print(r["status"], r["manifest"], r["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
