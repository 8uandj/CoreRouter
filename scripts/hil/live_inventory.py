#!/usr/bin/env python3
"""Fail-closed, read-only inventory of the running CoreRouter HIL testbed."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class InventoryError(RuntimeError):
    pass


def validate_expected_image(inventory, expected):
    if inventory["backend_image"] != expected:
        raise InventoryError("backend image mismatch: expected {}, observed {}".format(
            expected, inventory["backend_image"]))


def command_output(command):
    return subprocess.run(command, capture_output=True, text=True, timeout=15)


def collect_inventory(run=command_output):
    def required(command):
        try:
            result = run(command)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InventoryError("{}: {}".format(" ".join(command), exc)) from exc
        if result.returncode:
            raise InventoryError("{} failed: {}".format(
                " ".join(command), (result.stderr or result.stdout).strip()))
        return result.stdout.strip()

    names = set(required(["docker", "ps", "--format", "{{.Names}}"] ).splitlines())
    expected = ["bmv2-s{}".format(i) for i in range(1, 11)]
    missing = [name for name in ["3s-com-backend"] + expected if name not in names]
    if missing:
        raise InventoryError("missing live container(s): {}".format(", ".join(missing)))
    image = required(["docker", "inspect", "--format", "{{.Image}}", "3s-com-backend"])
    if not image.startswith("sha256:"):
        raise InventoryError("backend image digest unavailable")
    raw = required(["kubectl", "-n", "core-router", "get", "deployments", "-o", "json"])
    try:
        items = json.loads(raw)["items"]
        names = [item["metadata"]["name"] for item in items]
        ready = sum(item.get("status", {}).get("readyReplicas", 0) ==
                    item.get("status", {}).get("replicas", 1) for item in items)
    except (KeyError, TypeError, ValueError) as exc:
        raise InventoryError("invalid Kubernetes deployment inventory") from exc
    if not items or len(names) != len(set(names)):
        raise InventoryError("empty or duplicate Kubernetes deployments")
    return {"backend_image": image, "switches": expected,
            "deployments": {"count": len(items), "ready": ready, "names": sorted(names)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-image", help="fail if running backend digest differs")
    args = parser.parse_args()
    inventory = collect_inventory()
    if args.expected_image:
        validate_expected_image(inventory, args.expected_image)
    inventory["collected_utc"] = datetime.now(timezone.utc).isoformat()
    inventory["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    inventory["host_loadavg"] = list(os.getloadavg())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(args.out), "deployments": inventory["deployments"]["count"],
                      "ready": inventory["deployments"]["ready"]}))


if __name__ == "__main__":
    main()
