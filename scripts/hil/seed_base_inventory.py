#!/usr/bin/env python3
"""Build a new, offline reservation ledger from recovered HIL profiles.

This utility validates profile provenance and a proposed placement assignment,
then writes a new SQLite ledger. It never talks to Kubernetes and refuses to
replace an existing or live reservation ledger.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

_repo_root = os.getenv("CORE_ROUTER_REPO_ROOT") or str(Path(__file__).resolve().parents[2])
REPO_ROOT = Path(_repo_root).resolve()

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.state_manager import NetworkStateManager
from src.orchestration.jo_vdpr.topology import TopologyManager


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return value


def acquire_unlocked_owner_check(path: Path) -> None:
    """Reject an existing owner lock without modifying its lock file."""
    owner_path = Path(str(path) + ".owner")
    if not owner_path.exists():
        return
    with owner_path.open("r") as owner:
        try:
            fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(f"reservation ledger has a live owner lock: {owner_path}") from exc
        finally:
            try:
                fcntl.flock(owner.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def read_ledger_topology(path: Path) -> Optional[str]:
    """Read only the active ledger identity so a seed cannot target another runtime."""
    if not path.exists():
        return None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            row = connection.execute(
                "SELECT payload FROM reservation_snapshot WHERE id=1"
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ValueError(f"cannot safely read active ledger topology identity: {exc}") from exc
    if row is None:
        raise ValueError("active ledger has no reservation snapshot topology identity")
    try:
        topology_hash = json.loads(row[0]).get("topology")
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ValueError("active ledger reservation snapshot is invalid") from exc
    if not isinstance(topology_hash, str) or len(topology_hash) != 64:
        raise ValueError("active ledger topology identity is invalid")
    return topology_hash


def validate_inputs(profiles_doc: dict[str, Any], assignment_doc: dict[str, Any], topology: TopologyManager):
    profiles = profiles_doc.get("profiles")
    assignments = assignment_doc.get("assignments")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("profiles must be a nonempty list")
    if not isinstance(assignments, list) or not assignments:
        raise ValueError("assignments must be a nonempty list")
    if assignment_doc.get("status") != "proposed_not_applied":
        raise ValueError("assignment must remain marked proposed_not_applied")

    by_profile: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ValueError("each profile must be an object")
        name = profile.get("vnf_name")
        if not isinstance(name, str) or not name.strip() or name in by_profile:
            raise ValueError(f"invalid or duplicate profile name: {name!r}")
        source = profile.get("source")
        if not isinstance(source, dict) or not source.get("path") or not source.get("line"):
            raise ValueError(f"profile source provenance is missing: {name}")
        for key in ("cpu_req", "ram_req"):
            value = profile.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid {key} for {name}")
        depth = profile.get("msd_req")
        if isinstance(depth, bool) or not isinstance(depth, int) or depth <= 0:
            raise ValueError(f"invalid msd_req for {name}")
        by_profile[name] = profile

    by_assignment: dict[str, dict[str, Any]] = {}
    for assignment in assignments:
        if not isinstance(assignment, dict):
            raise ValueError("each assignment must be an object")
        name = assignment.get("vnf_name")
        if not isinstance(name, str) or name not in by_profile or name in by_assignment:
            raise ValueError(f"unknown or duplicate assignment name: {name!r}")
        for id_key, label_key in (("v_place", "placement"), ("v_route", "route")):
            node_id = assignment.get(id_key)
            label = assignment.get(label_key)
            if isinstance(node_id, bool) or not isinstance(node_id, int) or not 0 <= node_id < topology.num_nodes:
                raise ValueError(f"invalid {id_key} for {name}")
            if topology.names[node_id] != label:
                raise ValueError(f"{id_key}/{label_key} topology mismatch for {name}")
        by_assignment[name] = assignment

    if set(by_assignment) != set(by_profile):
        raise ValueError("assignment/profile name sets differ")

    cpu_by_node: dict[int, float] = defaultdict(float)
    ram_by_node: dict[int, float] = defaultdict(float)
    msd_by_route: dict[int, int] = defaultdict(int)
    max_cpu = float(assignment_doc.get("per_virtual_node_capacity", {}).get("cpu_req_max", 100.0))
    max_ram = float(assignment_doc.get("per_virtual_node_capacity", {}).get("ram_req_max", 100.0))
    if not math.isfinite(max_cpu) or not math.isfinite(max_ram) or max_cpu <= 0 or max_ram <= 0:
        raise ValueError("invalid per-node capacity limits")

    for name, profile in by_profile.items():
        assignment = by_assignment[name]
        place, route = assignment["v_place"], assignment["v_route"]
        cpu_by_node[place] += float(profile["cpu_req"])
        ram_by_node[place] += float(profile["ram_req"])
        depth = profile["msd_req"]
        if depth > float(topology.msd_limits[route]):
            raise ValueError(f"route MSD capability exceeded for {name}: {depth}>{topology.msd_limits[route]}")
        msd_by_route[route] = max(msd_by_route[route], depth)

    for node_id in cpu_by_node:
        if cpu_by_node[node_id] > max_cpu or ram_by_node[node_id] > max_ram:
            raise ValueError(
                f"placement capacity exceeded at {topology.names[node_id]}: "
                f"cpu={cpu_by_node[node_id]}/{max_cpu}, ram={ram_by_node[node_id]}/{max_ram}"
            )

    return by_profile, by_assignment, cpu_by_node, ram_by_node, msd_by_route


def build_ledger(args: argparse.Namespace) -> dict[str, Any]:
    profile_path = Path(args.profiles).resolve()
    assignment_path = Path(args.assignment).resolve()
    output_path = Path(args.output).resolve()
    summary_path = Path(args.summary).resolve()
    active_ledger = Path(os.getenv(
        "CORE_ROUTER_RESERVATION_DB", "results/rev1/runtime/reservations.sqlite3"
    )).resolve()
    if args.topology != "vietnam":
        raise ValueError("this recovered assignment is only approved for Vietnam topology validation")
    if output_path == active_ledger:
        raise ValueError("refusing to initialize the active reservation ledger path")
    if output_path.exists() or Path(str(output_path) + "-wal").exists() or Path(str(output_path) + "-shm").exists():
        raise ValueError(f"refusing to overwrite existing output ledger or SQLite sidecar: {output_path}")
    acquire_unlocked_owner_check(output_path)
    if summary_path.exists():
        raise ValueError(f"refusing to overwrite existing summary: {summary_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    topology = TopologyManager(args.topology)
    expected_topology_hash = args.expected_topology_hash or read_ledger_topology(active_ledger)
    if not expected_topology_hash:
        raise ValueError(
            "cannot prove runtime topology compatibility: provide --expected-topology-hash "
            "or run where the active ledger is readable"
        )
    profiles_doc = load_json(profile_path)
    assignment_doc = load_json(assignment_path)
    if profiles_doc.get("status") != "recovered_profiles_not_live_inventory":
        raise ValueError("recovered profiles provenance status is unexpected")
    by_profile, by_assignment, cpu_by_node, ram_by_node, msd_by_route = validate_inputs(
        profiles_doc, assignment_doc, topology
    )

    fd, temp_name = tempfile.mkstemp(prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent)
    os.close(fd)
    os.unlink(temp_name)
    temp_path = Path(temp_name)
    manager = None
    promoted = False
    try:
        manager = NetworkStateManager(topology_name=args.topology, reservation_path=temp_path)
        topology_hash = manager._topology_identity()
        if topology_hash != expected_topology_hash:
            raise ValueError(
                "runtime topology hash mismatch: "
                f"initializer={topology_hash}, active={expected_topology_hash}"
            )
        for name, profile in by_profile.items():
            assignment = by_assignment[name]
            accepted, reason = manager.try_reserve(
                assignment["v_place"], assignment["v_route"],
                float(profile["cpu_req"]), float(profile["ram_req"]),
                int(profile["msd_req"]), vnf_name=name,
            )
            if not accepted:
                raise ValueError(f"try_reserve rejected {name}: {reason}")

        public_state = manager.as_public_dict()
        if public_state["unaccounted_vnfs"]:
            raise ValueError("seed ledger contains accounting_unknown records")
        if len(public_state["active_vnfs"]) != len(by_profile):
            raise ValueError("seed ledger reservation count differs from profile count")
        state_version = public_state["state_version"]
        manager._reservation_store._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        manager.close()
        manager = None

        for sidecar in (Path(str(temp_path) + "-wal"), Path(str(temp_path) + "-shm")):
            if sidecar.exists():
                raise ValueError(f"SQLite sidecar remains after close: {sidecar}")
        check = sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)
        try:
            if check.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("temporary SQLite ledger failed quick_check")
            row = check.execute("SELECT payload FROM reservation_snapshot WHERE id=1").fetchone()
            if row is None:
                raise ValueError("temporary SQLite ledger has no reservation snapshot")
            payload = json.loads(row[0])
            if payload.get("topology") != topology_hash or len(payload.get("active", {})) != len(by_profile):
                raise ValueError("temporary SQLite ledger topology/profile validation failed")
            if any(item.get("accounting_unknown") for item in payload.get("active", {}).values()):
                raise ValueError("temporary SQLite ledger contains accounting_unknown")
        finally:
            check.close()

        summary = {
            "status": "seed_ready_not_applied",
            "topology": args.topology,
            "topology_hash": topology_hash,
            "expected_topology_hash": expected_topology_hash,
            "source_hashes": {
                str(profile_path): sha256(profile_path),
                str(assignment_path): sha256(assignment_path),
            },
            "profile_count": len(by_profile),
            "assignment_count": len(by_assignment),
            "state_version": state_version,
            "per_node_cpu_req": {str(k): cpu_by_node[k] for k in sorted(cpu_by_node)},
            "per_node_ram_req": {str(k): ram_by_node[k] for k in sorted(ram_by_node)},
            "route_msd_max": {str(k): msd_by_route[k] for k in sorted(msd_by_route)},
            "accounting_unknown_count": 0,
            "vnf_names": sorted(by_profile),
            "placement_source": "synthetic proposed assignment; not historical placement",
            "ledger_sha256": sha256(temp_path),
        }
        summary_temp = summary_path.with_name(f".{summary_path.name}.{os.getpid()}.tmp")
        with summary_temp.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(summary_temp, summary_path)
        with temp_path.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temp_path, output_path)
        promoted = True
        dir_fd = os.open(output_path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return summary
    finally:
        if manager is not None:
            manager.close()
        if not promoted and temp_path.exists():
            temp_path.unlink()
        temp_owner = Path(str(temp_path) + ".owner")
        if temp_owner.exists():
            temp_owner.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--assignment", required=True)
    parser.add_argument("--topology", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--expected-topology-hash")
    args = parser.parse_args()
    try:
        print(json.dumps(build_ledger(args), indent=2, sort_keys=True))
    except Exception as exc:
        parser.exit(2, f"seed_base_inventory: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
