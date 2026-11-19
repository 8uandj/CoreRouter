"""Check indexed input hashes without rewriting the evidence index."""
import argparse
import json

from paper.make_evidence_index import OUT, ROOT, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-missing", action="store_true",
                        help="Report missing original files as gaps without failing.")
    args = parser.parse_args()
    missing, mismatches, verified = [], [], 0
    manifests = {p.stem: json.loads(p.read_text()) for p in sorted(OUT.glob("*.json"))}
    training = manifests.pop("training_metadata", {})
    records = training.get("main_checkpoint_artifacts", [])
    if records:
        manifests["training_metadata"] = {"artifacts": [
            {"path": record[kind], "sha256": record[f"{kind}_sha256"],
             "recorded_original_sha256": None}
            for record in records for kind in ("checkpoint", "normalizer")
        ]}
    for name, manifest in manifests.items():
        for artifact in manifest["artifacts"]:
            relative = artifact["path"]
            path = ROOT / relative
            if not path.exists():
                missing.append(f"{name}: {relative}")
            elif path.is_file():
                expected = artifact["recorded_original_sha256"] or artifact["sha256"]
                if not expected or sha256(path) != expected:
                    mismatches.append(f"{name}: {relative}")
                else:
                    verified += 1
    for relative in missing:
        print(f"MISSING {relative}")
    for relative in mismatches:
        print(f"MISMATCH {relative}")
    print(f"{verified} hashes match, {len(missing)} missing paths, {len(mismatches)} mismatches")
    return bool(mismatches or (missing and not args.allow_missing))


if __name__ == "__main__":
    raise SystemExit(main())
