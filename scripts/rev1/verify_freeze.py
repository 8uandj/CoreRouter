#!/usr/bin/env python3
"""Read-only code-freeze environment and input-package verifier."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import zipfile


CLI_ENTRYPOINTS = (
    "scripts/rev1/phase_driver.py",
    "scripts/rev1/package_inputs.py",
    "scripts/rev1/result_coverage.py",
)
REQUIRED_DISTRIBUTIONS = ("numpy", "scipy", "torch")
OPTIONAL_DISTRIBUTIONS = ("p4runtime-shell",)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_input_package_mode(manifest, expected_mode=None):
    mode = manifest.get("mode")
    if mode not in {"training", "evaluation"}:
        raise ValueError("input package mode must be training or evaluation")
    if expected_mode is not None and mode != expected_mode:
        raise ValueError("input package mode mismatch: expected {}, got {}".format(expected_mode, mode))
    return mode


def verify_cli_contracts(root, *, runner=subprocess.run):
    results = []
    for entrypoint in CLI_ENTRYPOINTS:
        command = [sys.executable, entrypoint, "--help"]
        result = runner(command, cwd=str(root), capture_output=True, text=True)
        results.append({"command": command, "returncode": result.returncode,
                        "output": (result.stdout or "")[-2000:],
                        "error": (result.stderr or "")[-2000:]})
    return {"status": "passed" if all(item["returncode"] == 0 for item in results) else "failed",
            "commands": results}


def collect_report(root, *, input_package, input_sha256, protocol_path=None,
                   expected_mode=None, runner=subprocess.run):
    root = Path(root).resolve()
    errors = []
    revision = runner(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True,
                      text=True, check=False)
    status = runner(["git", "status", "--porcelain"], cwd=str(root), capture_output=True,
                    text=True, check=False)
    commit = revision.stdout.strip() if revision.returncode == 0 else None
    dirty_paths = [line[3:] for line in (status.stdout or "").splitlines() if line]
    if not commit:
        errors.append("git commit SHA unavailable")
    if dirty_paths:
        errors.append("working tree is dirty")

    dependencies = {}
    for distribution in REQUIRED_DISTRIBUTIONS + OPTIONAL_DISTRIBUTIONS:
        try:
            dependencies[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            dependencies[distribution] = None
            if distribution in REQUIRED_DISTRIBUTIONS:
                errors.append("required dependency missing: " + distribution)

    package_report = {"path": str(input_package) if input_package else None,
                      "sha256": None, "manifest": None, "mode": None}
    package_path = Path(input_package) if input_package else None
    if package_path is not None and not package_path.is_absolute():
        package_path = root / package_path
    packaged_protocol = None
    if not input_package or not input_sha256:
        errors.append("input package and external SHA-256 are required")
    else:
        try:
            actual_hash = sha256_file(package_path)
            package_report["sha256"] = actual_hash
            if actual_hash != input_sha256:
                raise ValueError("input package SHA-256 mismatch")
            try:
                from .package_inputs import verify_package, verify_protocol_matches, verify_workspace_inputs
            except ImportError:
                from package_inputs import verify_package, verify_protocol_matches, verify_workspace_inputs
            package_manifest = verify_package(package_path, input_sha256)
            package_report["mode"] = validate_input_package_mode(package_manifest, expected_mode)
            verify_workspace_inputs(package_path, package_manifest, root)
            with zipfile.ZipFile(package_path) as archive:
                packaged_protocol = archive.read('CoreRouter/configs/rev1/protocol.resolved.json')
            protocol_file = Path(protocol_path) if protocol_path else None
            if protocol_file is not None and not protocol_file.is_absolute():
                protocol_file = root / protocol_file
            if protocol_file and protocol_file.is_file():
                verify_protocol_matches(package_path, protocol_file)
            elif protocol_file:
                raise FileNotFoundError("protocol missing: " + str(protocol_file))
            package_report["manifest"] = package_manifest
        except Exception as exc:
            errors.append("evaluation package invalid: {}: {}".format(type(exc).__name__, exc))

    protocol = None
    protocol_sha256 = None
    if packaged_protocol is not None:
        protocol_sha256 = hashlib.sha256(packaged_protocol).hexdigest()
        try:
            protocol = json.loads(packaged_protocol.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append("packaged protocol unreadable: " + str(exc))
    for distribution, expected in (protocol or {}).get("runtime_versions", {}).items():
        actual = dependencies.get(distribution)
        if actual is None:
            try:
                actual = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                pass
        if actual != str(expected):
            errors.append("protocol dependency mismatch: {} expected {}, found {}".format(
                distribution, expected, actual))

    cli_report = verify_cli_contracts(root, runner=runner)
    if cli_report["status"] != "passed":
        errors.append("one or more CLI help contracts failed")
    return {
        "status": "ready" if not errors else "blocked",
        "commit_sha": commit,
        "dirty": bool(dirty_paths),
        "dirty_paths": dirty_paths,
        "python": sys.version,
        "dependencies": dependencies,
        "protocol": {"path": str(protocol_path) if protocol_path else "embedded in input package",
                     "sha256": protocol_sha256},
        "input_package": package_report,
        "cli_contracts": cli_report,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--protocol", type=Path,
                        help="Optional extracted protocol that must byte-match the package")
    parser.add_argument("--input-package", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--expected-mode", choices=["training", "evaluation"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = collect_report(args.root, input_package=args.input_package,
                            input_sha256=args.input_sha256, protocol_path=args.protocol,
                            expected_mode=args.expected_mode)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
