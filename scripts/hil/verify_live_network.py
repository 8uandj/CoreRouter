#!/usr/bin/env python3
"""Fail-closed read-only HIL startup check for Kubernetes, SRv6/P4, and VXLAN."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:8000/api"
SDN = "http://127.0.0.1:8765"
SWITCHES = ["bmv2-s{}".format(i) for i in range(1, 11)]
P4CLI = ROOT / "results/hil/e2e_tools/p4cli.sh"


class VerificationError(RuntimeError):
    pass


def run(command, *, timeout=30, check=True, input_text=None):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                                input=input_text)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError("{}: {}".format(" ".join(command), exc)) from exc
    if check and result.returncode:
        raise VerificationError("{} failed ({}): {}".format(
            " ".join(command), result.returncode, (result.stderr or result.stdout).strip()))
    return result


def http_json(url):
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(), exc.code
    except (urllib.error.URLError, TimeoutError) as exc:
        return 0, {"error": str(exc)}
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, {"raw": raw.decode(errors="replace")}


def kubectl_json(*args):
    raw = run(["kubectl", *args, "-o", "json"]).stdout
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise VerificationError("invalid kubectl JSON for {}".format(" ".join(args))) from exc


def host_firewall_snapshot():
    """Read firewalld through a short-lived, uniquely named host diagnostic Pod."""
    name = "hil-netcheck-{}".format(datetime.now(timezone.utc).strftime("%H%M%S%f"))
    manifest = {
        "apiVersion": "v1", "kind": "Pod",
        "metadata": {"name": name, "namespace": "core-router",
                     "labels": {"purpose": "hil-network-readonly-check"}},
        "spec": {"nodeName": "k8s-master", "hostNetwork": True, "hostPID": True,
                 "restartPolicy": "Never", "activeDeadlineSeconds": 300,
                 "terminationGracePeriodSeconds": 0, "tolerations": [{"operator": "Exists"}],
                 "containers": [{"name": "diag", "image": "10.10.6.231:32000/alpine:latest",
                                 "imagePullPolicy": "IfNotPresent", "command": ["sleep", "240"],
                                 "securityContext": {"privileged": True}}]}}
    run(["kubectl", "apply", "-f", "-"], input_text=json.dumps(manifest))
    try:
        run(["kubectl", "-n", "core-router", "wait", "--for=condition=Ready",
             "pod/" + name, "--timeout=120s"])

        def host(*command):
            return run(["kubectl", "-n", "core-router", "exec", name, "--", "nsenter",
                        "-t", "1", "-m", "-u", "-n", "-i", "-p", "--", "chroot",
                        "/proc/1/root", *command], check=False)

        state = host("/usr/bin/firewall-cmd", "--state")
        active_port = host("/usr/bin/firewall-cmd", "--zone=public", "--query-port=4789/udp")
        permanent_port = host("/usr/bin/firewall-cmd", "--permanent", "--zone=public",
                              "--query-port=4789/udp")
        active_interface = host("/usr/bin/firewall-cmd", "--zone=trusted",
                                "--query-interface=vxlan.calico")
        permanent_interface = host("/usr/bin/firewall-cmd", "--permanent", "--zone=trusted",
                                   "--query-interface=vxlan.calico")
        vxlan = host("/usr/sbin/ip", "-d", "link", "show", "vxlan.calico")
        return {"diagnostic_pod": name, "firewalld_state": state.stdout.strip(),
                "runtime_public_4789_udp": active_port.stdout.strip(),
                "permanent_public_4789_udp": permanent_port.stdout.strip(),
                "runtime_trusted_vxlan_calico": active_interface.stdout.strip(),
                "permanent_trusted_vxlan_calico": permanent_interface.stdout.strip(),
                "vxlan_link": vxlan.stdout.strip(),
                "commands": {"state_rc": state.returncode, "runtime_port_rc": active_port.returncode,
                             "permanent_port_rc": permanent_port.returncode,
                             "runtime_interface_rc": active_interface.returncode,
                             "permanent_interface_rc": permanent_interface.returncode,
                             "vxlan_rc": vxlan.returncode}}
    finally:
        run(["kubectl", "-n", "core-router", "delete", "pod", name,
             "--ignore-not-found", "--wait=true"], timeout=30, check=False)


def p4_snapshot():
    result = {}
    for index in range(1, 11):
        switch = "s{}".format(index)
        counters = run([str(P4CLI), switch,
                        "counter_read srv6_advance_counter 0",
                        "counter_read srv6_terminal_counter 0",
                        "counter_read msd_violation_counter 0"]).stdout
        values = [int(x) for x in re.findall(r"packets=(\d+)", counters)]
        if len(values) != 3:
            raise VerificationError("could not read all P4 counters on " + switch)
        tables = run([str(P4CLI), switch, "table_dump routing_v6",
                      "table_dump srv6_end_dx4_table"]).stdout
        result[switch] = {
            "advance": values[0], "terminal": values[1], "msd_violation": values[2],
            "tables_sha256": hashlib.sha256(tables.encode()).hexdigest(),
        }
    return result


def collect_snapshot():
    containers = set(run(["docker", "ps", "--format", "{{.Names}}"], timeout=15).stdout.splitlines())
    expected_containers = set(["3s-com-backend"] + SWITCHES)
    image = run(["docker", "inspect", "--format", "{{.Image}}", "3s-com-backend"]).stdout.strip()
    deployments = kubectl_json("-n", "core-router", "get", "deployments").get("items", [])
    nodes = kubectl_json("get", "nodes").get("items", [])
    state_code, state = http_json(API + "/orchestrate/state")
    health_code, health = http_json(API + "/health")
    topology_code, topology = http_json(SDN + "/topology")
    controller_health_code, controller_health = http_json(SDN + "/health")
    firewall = host_firewall_snapshot()
    deployment_rows = []
    for item in deployments:
        spec_replicas = item.get("spec", {}).get("replicas", 1)
        ready = item.get("status", {}).get("readyReplicas", 0)
        deployment_rows.append({"name": item.get("metadata", {}).get("name"),
                                "desired": spec_replicas, "ready": ready})
    node_rows = []
    for item in nodes:
        conditions = {c.get("type"): c.get("status") for c in item.get("status", {}).get("conditions", [])}
        node_rows.append({"name": item.get("metadata", {}).get("name"), "ready": conditions.get("Ready") == "True"})
    return {
        "collected_utc": datetime.now(timezone.utc).isoformat(),
        "backend": {"container_present": "3s-com-backend" in containers,
                    "image": image, "health_http": health_code, "health": health},
        "containers": {"expected": sorted(expected_containers),
                       "present": sorted(containers & expected_containers),
                       "missing": sorted(expected_containers - containers)},
        "kubernetes": {"deployments": deployment_rows, "nodes": node_rows,
                       "state_http": state_code,
                       "unaccounted_vnfs": state.get("data", {}).get("unaccounted_vnfs", []),
                       "state_version": state.get("data", {}).get("state_version"),
                       "alert_flag": state.get("data", {}).get("alert_flag")},
        "controller": {"topology_http": topology_code, "topology": topology,
                       "health_http": controller_health_code, "switches": controller_health},
        "p4": p4_snapshot(), "firewall": firewall,
        "host_loadavg": list(__import__("os").getloadavg()),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (Path(__file__).resolve(), P4CLI)},
    }


def evaluate_network_snapshot(snapshot, expected_backend_image=None,
                              expected_p4_topology_hash=None):
    """Return blockers; a non-empty list means do not start a HIL experiment."""
    blockers = []
    backend = snapshot.get("backend", {})
    if backend.get("health_http") != 200:
        blockers.append("backend health endpoint is not HTTP 200")
    if not backend.get("container_present") or not str(backend.get("image", "")).startswith("sha256:"):
        blockers.append("backend container/image identity unavailable")
    if expected_backend_image and backend.get("image") != expected_backend_image:
        blockers.append("backend image digest differs from expected baseline")
    if snapshot.get("containers", {}).get("missing"):
        blockers.append("one or more backend/BMv2 containers are missing")
    kube = snapshot.get("kubernetes", {})
    deployments = kube.get("deployments", [])
    if not deployments or any(d.get("desired", 0) < 1 or d.get("ready", 0) != d.get("desired", 0)
                              for d in deployments):
        blockers.append("Kubernetes Deployment readiness is incomplete")
    nodes = kube.get("nodes", [])
    if not nodes or any(not n.get("ready") for n in nodes):
        blockers.append("one or more Kubernetes nodes are not Ready")
    if kube.get("state_http") != 200 or kube.get("unaccounted_vnfs"):
        blockers.append("orchestration ledger is unavailable or has unaccounted VNFs")
    controller = snapshot.get("controller", {})
    topology = controller.get("topology", {})
    p4_hash = topology.get("p4_topology_hash")
    if (controller.get("topology_http") != 200 or topology.get("ready") is not True
            or topology.get("profile_id") != "p4-path-candidate-v1"
            or not isinstance(p4_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", p4_hash)):
        blockers.append("controller topology/profile is not ready")
    if expected_p4_topology_hash and p4_hash != expected_p4_topology_hash:
        blockers.append("live P4 topology hash differs from expected baseline")
    switches = controller.get("switches", {})
    if controller.get("health_http") != 200 or len(switches) != 10 or any(
            not row.get("reachable") for row in switches.values()):
        blockers.append("controller does not report all ten P4 switches reachable")
    p4 = snapshot.get("p4", {})
    if len(p4) != 10 or any(not isinstance(v.get("tables_sha256"), str) for v in p4.values()):
        blockers.append("P4 table/counter readback is incomplete")
    firewall = snapshot.get("firewall", {})
    if firewall.get("firewalld_state") != "running":
        blockers.append("k8s-master firewalld is not running")
    for key in ("runtime_public_4789_udp", "runtime_trusted_vxlan_calico",
                "permanent_public_4789_udp", "permanent_trusted_vxlan_calico"):
        if firewall.get(key) != "yes":
            blockers.append("k8s-master firewall prerequisite missing: " + key)
    if "vxlan id 4096" not in firewall.get("vxlan_link", "") or "dstport 4789" not in firewall.get("vxlan_link", ""):
        blockers.append("k8s-master VXLAN interface is missing or mismatched")
    return blockers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-image")
    parser.add_argument("--expected-p4-hash")
    args = parser.parse_args()
    snapshot = collect_snapshot()
    blockers = evaluate_network_snapshot(snapshot, args.expected_image, args.expected_p4_hash)
    record = {"snapshot": snapshot, "blockers": blockers, "ready_for_hil": not blockers}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(args.out), "ready_for_hil": not blockers, "blockers": blockers}))
    raise SystemExit(0 if not blockers else 2)


if __name__ == "__main__":
    main()
