#!/usr/bin/env python3
"""Verify the export package: checksums and byte-identical regeneration.

1. Every entry in SHA256SUMS must match the file on disk (and no file may be
   missing from SHA256SUMS except SHA256SUMS itself).
2. Every generator is re-run into a scratch tree whose input folders are
   symlinks to this package; each regenerated file must be byte-identical to
   the stored copy under generated/.

Usage: /home/CoreRouter/venv/bin/python scripts/check_export.py <export_root> [--sums-only]
Exit code 0 only if all checks pass.
"""
from __future__ import annotations

import filecmp
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

PY = "/home/CoreRouter/venv/bin/python"
REPO = Path("/home/CoreRouter")
INPUT_DIRS = ["00_inventory", "01_hil12h", "02_forwarding_overmsd", "03_inventory50", "04_new_experiments", "scripts"]
GENERATED = [
    # (command template, files relative to export root that the command produces)
    ([PY, "{root}/scripts/analyze_hil12h.py", "{root}"],
     ["generated/hil12h/per_request_hil12h.csv", "generated/hil12h/reject_decomposition.csv",
      "generated/hil12h/hourly_hil12h.csv", "generated/hil12h/crosscheck_hil12h.json"]),
    ([PY, str(REPO / "scripts/paper/make_table11.py"), "--run-dir",
      "{root}/01_hil12h/original/e6_12h_control_plane/runs/20261117_190242", "--output-dir", "{root}/generated/table11"],
     ["generated/table11/table11.tex"]),
    ([PY, "{root}/scripts/analyze_forwarding_history.py", "{root}"],
     ["generated/forwarding_history_evidence_matrix.csv"]),
    ([PY, "{root}/scripts/analyze_inventory50.py", "{root}"],
     ["generated/inventory50_summary.json", "generated/inventory50_deployments.csv"]),
    ([PY, "{root}/scripts/summarize_overmsd.py", "{root}"],
     ["generated/overmsd/overmsd_table.csv", "generated/overmsd/overmsd_table.tex", "generated/overmsd/overmsd_summary.json"]),
    ([PY, "{root}/scripts/summarize_injection7.py", "{root}"],
     ["generated/injection7/injection7_table.csv", "generated/injection7/injection7_table.tex"]),
    ([PY, "{root}/scripts/summarize_concurrency.py", "{root}"],
     ["generated/concurrency/concurrency_by_level.csv", "generated/concurrency/concurrency_by_level.tex"]),
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_sums(root: Path) -> list[str]:
    errors = []
    sums = root / "SHA256SUMS"
    listed = {}
    for line in sums.read_text().splitlines():
        digest, rel = line.split("  ", 1)
        listed[rel] = digest
        p = root / rel
        if not p.is_file():
            errors.append(f"missing: {rel}")
        elif sha256(p) != digest:
            errors.append(f"hash mismatch: {rel}")
    on_disk = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - {"SHA256SUMS"}
    for extra in sorted(on_disk - set(listed)):
        errors.append(f"not in SHA256SUMS: {extra}")
    print(f"SHA256SUMS entries={len(listed)} errors={len(errors)}")
    return errors


def check_regeneration(root: Path) -> list[str]:
    errors = []
    with tempfile.TemporaryDirectory(prefix="export_regen_") as tmp:
        t = Path(tmp)
        for d in INPUT_DIRS:
            (t / d).symlink_to(root / d)
        (t / "generated").mkdir()
        for cmd, outputs in GENERATED:
            if not (root / outputs[0]).exists():
                errors.append(f"stored output absent, generator skipped: {outputs[0]}")
                continue
            for o in outputs:
                (t / o).parent.mkdir(parents=True, exist_ok=True)
            argv = [c.format(root=t) for c in cmd]
            r = subprocess.run(argv, capture_output=True, text=True)
            if r.returncode not in (0,):
                errors.append(f"generator failed ({r.returncode}): {' '.join(argv)}\n{r.stderr[-500:]}")
                continue
            for o in outputs:
                if not filecmp.cmp(t / o, root / o, shallow=False):
                    errors.append(f"regenerated file differs: {o}")
                else:
                    print(f"identical: {o}")
    return errors


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    errors = check_sums(root)
    if "--sums-only" not in sys.argv:
        errors += check_regeneration(root)
    for e in errors:
        print("ERROR", e)
    print("RESULT", "PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
