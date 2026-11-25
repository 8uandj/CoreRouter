#!/usr/bin/env python3
"""Run the opt-in Pod chain after a recorded successful pair-level HARP request.

This links evidence; it does not claim the HARP policy selected the full chain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAIN_RUNNER = ROOT / "scripts/hil/vnf_pod_chain_probe.py"
INVENTORY = ROOT / "scripts/hil/live_inventory.py"
CHAIN_RUN_ID = re.compile(r"[a-z0-9-]{1,32}\Z")
CHAIN_SOURCE_FILES = (
    CHAIN_RUNNER,
    ROOT / "scripts/hil/analyze_vnf_pod_chain.py",
    ROOT / "scripts/hil/vnf_chain_relay.py",
    ROOT / "scripts/hil/chain_handoff.py",
    ROOT / "scripts/hil/chain_packet.py",
    ROOT / "scripts/hil/vnf_chain_gateway.py",
    ROOT / "scripts/hil/chain_send.py",
    ROOT / "scripts/hil/chain_stage.py",
    ROOT / "infrastructure/k8s/manifests/vnf-chain-inputs.yaml",
    ROOT / "infrastructure/k8s/manifests/chain-relay-app.yaml",
    ROOT / "infrastructure/k8s/tekton/tasks/task-prepare-vnf-chain.yaml",
    ROOT / "infrastructure/k8s/tekton/pipeline-vnf-chain.yaml",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_orchestration_record(record: dict) -> dict:
    """Return pair-level linkage metadata only for a completed successful run."""
    if not isinstance(record, dict) or record.get("http_status") != 200:
        raise ValueError("orchestration record must contain an HTTP 200 response")
    response = record.get("response")
    if not isinstance(response, dict) or response.get("status") != "success":
        raise ValueError("orchestration response was not successful")
    request = record.get("request")
    if not isinstance(request, dict) or not isinstance(request.get("flow_id"), str) or not request["flow_id"]:
        raise ValueError("orchestration request flow_id is missing")
    baseline = record.get("baseline_inventory")
    if not isinstance(baseline, dict) or not isinstance(baseline.get("backend_image"), str):
        raise ValueError("orchestration record lacks the baseline backend image digest")
    name = record.get("vnf_name")
    realization = record.get("realization")
    if not isinstance(name, str) or not name or not isinstance(realization, dict):
        raise ValueError("pair-level VNF realization is incomplete")
    operation_id = realization.get("operation_id")
    request_id = realization.get("request_id")
    if not operation_id or not request_id or request_id != name:
        raise ValueError("pair-level request/operation identity is incomplete or inconsistent")
    corr = record.get("correlation_checks")
    required_checks = ("request_operation_identity", "pod_ready", "pipelinerun_succeeded",
                      "readback_all_present", "steering_confirmed")
    if not isinstance(corr, dict) or not all(corr.get(key) is True for key in required_checks):
        raise ValueError("successful pair-level actuation and steering checks are required")
    actuation = record.get("actuation_status")
    actuation_data = actuation.get("data", {}) if isinstance(actuation, dict) else {}
    if (not isinstance(actuation, dict) or actuation.get("status") != "success"
            or not isinstance(actuation_data, dict)
            or actuation_data.get("steer_status") != "CONFIRMED"
            or actuation_data.get("steer_operation_id") != operation_id):
        raise ValueError("matching successful controller steering confirmation is required")
    response_data = response.get("data")
    if not isinstance(response_data, dict):
        raise ValueError("orchestration response data is missing")
    pair = response_data.get("admitted_realization", {})
    if (not isinstance(pair, dict) or pair.get("operation_id") != operation_id
            or pair.get("request_id") != request_id or not pair.get("switch_path")
            or not pair.get("sid_stack")):
        raise ValueError("response pair-level realization is malformed")
    response_migration = response_data.get("migration_result")
    if not isinstance(response_migration, dict):
        raise ValueError("response migration request is missing")
    migration_vnf = response_migration.get("vnf_name") or response_migration.get("new_vnf")
    response_operation_id = response_migration.get("operation_id")
    if (migration_vnf != name
            or (response_operation_id is not None and response_operation_id != operation_id)):
        raise ValueError("response migration request does not match the pair realization")
    pilot_record = record.get("pilot")
    run20_record = record.get("run20")
    pilot = pilot_record.get("summary", {}) if isinstance(pilot_record, dict) else {}
    run20 = run20_record.get("summary", {}) if isinstance(run20_record, dict) else {}
    if not isinstance(pilot, dict) or not isinstance(run20, dict):
        raise ValueError("pair-level probe summaries are malformed")
    if pilot.get("sent") != 3 or pilot.get("app_received") != 3 or pilot.get("loss") != 0:
        raise ValueError("successful three-packet pair-level pilot is required")
    if run20.get("sent") != 20 or run20.get("app_received") != 20 or run20.get("loss") != 0:
        raise ValueError("successful 20-packet pair-level follow-up is required")
    return {
        "flow_id": request["flow_id"],
        "vnf_name": name,
        "operation_id": operation_id,
        "request_id": request_id,
        "pair_switch_path": realization.get("switch_path", []),
        "pair_sid_stack": realization.get("sid_stack", []),
        "placement": record.get("placement"),
        "routing_anchor": record.get("route"),
    }


def verify_child_manifest(chain_dir: Path, run_id: str) -> dict:
    path = chain_dir / "manifest.json"
    if not path.is_file():
        raise ValueError("chain runner did not produce manifest.json")
    manifest = json.loads(path.read_text())
    for relative, expected in manifest.get("evidence_sha256", {}).items():
        evidence = (ROOT / relative).resolve()
        try:
            evidence.relative_to(chain_dir.resolve())
        except ValueError as exc:
            raise ValueError("chain manifest evidence escapes its run directory: {}".format(relative)) from exc
        if not evidence.is_file() or sha256(evidence) != expected:
            raise ValueError("chain evidence is missing or hash-mismatched: {}".format(relative))
    if manifest.get("run_id") != run_id or len(manifest.get("p4_legs", [])) != 3:
        raise ValueError("chain manifest lacks its run identity or all three P4 legs")
    if manifest.get("pilot", {}).get("complete_packets") != 3:
        raise ValueError("chain pilot did not deliver all three packets")
    if manifest.get("run20", {}).get("complete_packets") != 20:
        raise ValueError("chain follow-up did not deliver all 20 packets")
    return manifest


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def collect_parent_evidence(out: Path) -> dict:
    return {str(path.relative_to(out)): sha256(path)
            for path in sorted(out.rglob("*"))
            if path.is_file() and path.name not in ("manifest.json", "manifest.json.sha256")}


def preflight_unused_run_id(run_id: str) -> dict:
    """Fail before the child cleanup path if any cluster object already owns this ID."""
    command = ["kubectl", "-n", "core-router", "get",
               "deployments,services,pods,pvc,pipelineruns",
               "-l", "core-router/chain-run={}".format(run_id), "-o", "json"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError("chain run-ID preflight failed: {}".format(
            (result.stderr or result.stdout)[-1500:]))
    try:
        items = json.loads(result.stdout).get("items", [])
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("chain run-ID preflight returned invalid JSON") from exc
    existing = ["{}/{}".format(item.get("kind", "Object"),
                               item.get("metadata", {}).get("name", "<unnamed>"))
                for item in items]
    if existing:
        raise RuntimeError("refusing reused chain run ID; existing resources: {}".format(
            ", ".join(existing)))
    return {"command": command, "items": [], "checked_utc": datetime.now(timezone.utc).isoformat()}


def run_chain_child(command: list[str], timeout: int = 1200) -> subprocess.CompletedProcess:
    """Allow the child's finally cleanup to run if the outer time bound expires."""
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=45)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            stderr += "\nchain child exceeded time limit; forced stop after cleanup grace period"
            return subprocess.CompletedProcess(command, 124, stdout, stderr)
        return subprocess.CompletedProcess(command, 124, stdout,
                                           stderr + "\nchain child exceeded time limit; sent SIGINT for cleanup")
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True,
                        help="successful output orchestration.json from orchestrated_vnf_chain.py")
    parser.add_argument("--run-id", required=True,
                        help="must equal the linked HARP request flow_id and be new to the chain pipeline")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resume", action="store_true",
                        help="re-verify/finalize an existing parent record without rerunning the chain child")
    args = parser.parse_args()

    record_path = args.record.resolve()
    out = args.out.resolve()
    if not CHAIN_RUN_ID.fullmatch(args.run_id):
        parser.error("run ID must match [a-z0-9-]{1,32}")
    if out.exists() and not out.is_dir():
        parser.error("output path exists and is not a directory")
    if out.exists() and any(out.iterdir()) and not args.resume:
        parser.error("refusing to reuse a non-empty output directory")
    try:
        record = json.loads(record_path.read_text())
        linkage = validate_orchestration_record(record)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error("invalid orchestration record: {}".format(exc))
    if args.run_id != linkage["flow_id"]:
        parser.error("chain run ID must equal the orchestration request flow_id")
    out.mkdir(parents=True, exist_ok=True)
    chain_dir = out / "chain"
    if chain_dir.exists() and not args.resume:
        parser.error("refusing to reuse existing chain output directory")

    if args.resume:
        try:
            record_doc = json.loads((out / "orchestration.json").read_text())
        except (OSError, ValueError) as exc:
            parser.error("--resume requires an existing parent orchestration record: {}".format(exc))
        if (record_doc.get("status") not in ("failed", "success") or record_doc.get("chain_returncode") != 0
                or not (chain_dir / "manifest.json").is_file()):
            parser.error("--resume requires an existing parent and an already successful chain child")
        if record_doc.get("upstream_record_sha256") != sha256(record_path):
            parser.error("upstream orchestration record differs from the failed run")
    else:
        record_doc = {
            "status": "running",
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "linkage": linkage,
            "upstream_record": str(record_path),
            "upstream_record_sha256": sha256(record_path),
            "scope_note": "A successful pair-level HARP record is a fail-closed correlation prerequisite for this separate opt-in chain run. It neither selects nor installs the full chain path.",
        }
    record_doc["scope_note"] = (
        "The pair-level HARP operation is a correlation prerequisite only. Its pair path does not configure the separately specified chain legs."
    )
    write_json(out / "orchestration.json", record_doc)
    try:
        baseline_path = out / "live_inventory.json"
        baseline = subprocess.run(
            [sys.executable, str(INVENTORY), "--out", str(baseline_path),
             "--expected-image", record["baseline_inventory"]["backend_image"]],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        if baseline.returncode:
            raise RuntimeError("read-only live preflight failed: {}".format(
                (baseline.stderr or baseline.stdout)[-2000:]))
        live = json.loads(baseline_path.read_text())
        if live["deployments"]["ready"] != live["deployments"]["count"]:
            raise RuntimeError("live preflight found non-Ready Deployments")

        if not args.resume:
            run_id_check = preflight_unused_run_id(args.run_id)
            write_json(out / "run_id_preflight.json", run_id_check)
            chain = run_chain_child(
                [sys.executable, str(CHAIN_RUNNER), "--run-id", args.run_id, "--out", str(chain_dir)])
            record_doc["chain_returncode"] = chain.returncode
            record_doc["chain_stdout"] = chain.stdout
            record_doc["chain_stderr"] = chain.stderr[-4000:]
            if chain.returncode:
                raise RuntimeError("SRv6/P4 chain runner failed with exit {}".format(chain.returncode))

        child_manifest = verify_child_manifest(chain_dir, args.run_id)
        record_doc.pop("error", None)
        record_doc["status"] = "success"
        record_doc["completed_utc"] = datetime.now(timezone.utc).isoformat()
        record_doc["live_inventory_sha256"] = sha256(baseline_path)
        record_doc["chain_manifest_sha256"] = sha256(chain_dir / "manifest.json")
        record_doc["chain_summary"] = {"pilot": child_manifest["pilot"],
                                      "run20": child_manifest["run20"],
                                      "p4_legs": child_manifest["p4_legs"],
                                      "p4_counter_deltas": child_manifest["p4_counter_deltas"]}
        write_json(out / "orchestration.json", record_doc)
        manifest = {
            "run_id": args.run_id,
            "evidence_class": "pair-level HARP orchestration record linked to an opt-in two-Pod SRv6/P4 chain experiment",
            "linkage": linkage,
            "upstream_record_sha256": sha256(record_path),
            "chain_manifest_sha256": sha256(chain_dir / "manifest.json"),
            "source_sha256": {str(path.relative_to(ROOT)): sha256(path)
                              for path in (Path(__file__).resolve(), INVENTORY, *CHAIN_SOURCE_FILES)},
            "evidence_sha256": collect_parent_evidence(out),
            "scope_note": "The existing HARP policy selected one placement-routing pair. The two-Pod chain was run by an opt-in testbed pipeline and was not selected as a full chain by HARP.",
        }
        manifest_path = out / "manifest.json"
        write_json(manifest_path, manifest)
        (out / "manifest.json.sha256").write_text(sha256(manifest_path) + "  manifest.json\n")
        print(json.dumps({"run_id": args.run_id, "status": "success",
                          "pilot_packets": child_manifest["pilot"]["complete_packets"],
                          "run20_packets": child_manifest["run20"]["complete_packets"],
                          "manifest": str(manifest_path)}, sort_keys=True))
        return 0
    except Exception as exc:
        record_doc["status"] = "failed"
        record_doc["error"] = str(exc)
        record_doc["completed_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(out / "orchestration.json", record_doc)
        print("orchestrated chain failed: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
