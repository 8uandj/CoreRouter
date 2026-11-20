#!/usr/bin/env python3
"""Refresh SHA-256 inventory for AIO-mesh-submit-2 after evidence updates."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE = {"FILE_SHA256SUMS", "PACKAGE_MANIFEST.json"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    paths = sorted(path for path in ROOT.rglob("*")
                   if path.is_file() and path.relative_to(ROOT).as_posix() not in EXCLUDE
                   and not path.is_symlink())
    lines = [f"{digest(path)}  {path.relative_to(ROOT).as_posix()}" for path in paths]
    (ROOT / "FILE_SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest_path = ROOT / "PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["hash_inventory_generated_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["hash_inventory_file"] = "FILE_SHA256SUMS"
    manifest["hash_inventory_entries"] = len(lines)
    manifest["hash_inventory_status"] = "point-in-time; refresh again if live processes were still writing"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(lines)} SHA-256 entries to {ROOT / 'FILE_SHA256SUMS'}")


if __name__ == "__main__":
    main()
