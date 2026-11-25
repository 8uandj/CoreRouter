#!/usr/bin/env python3
"""Deploy two isolated VNF relay Pods with Tekton and run the bounded SRv6/P4 chain."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from analyze_vnf_pod_chain import analyze


ROOT = Path(__file__).resolve().parents[2]
RELAY = ROOT / "scripts/hil/vnf_chain_relay.py"
HANDOFF = ROOT / "scripts/hil/chain_handoff.py"
P4CLI = ROOT / "results/hil/e2e_tools/p4cli.sh"
RUN_DEFAULT = "podchain20261124a"
P4_IMAGE = "p4lang/p4app:latest"

HOSTS = ("h1", "h6", "h9", "h10")
SWITCHES = (1, 6, 9, 10)
MACS = {"s1_host": "4e:76:a8:a5:f6:8d",
        "s6_host": "ae:7f:6b:c2:79:48",
        "s9_host": "b6:ce:71:72:6e:98"}


def run(command, *, input_text=None, timeout=60, check=True, cwd=None):
    result = subprocess.run(command, input=input_text, capture_output=True,
                            text=True, timeout=timeout, cwd=cwd)
    if check and result.returncode:
        raise RuntimeError("{} failed ({}): {}".format(
            " ".join(map(str, command)), result.returncode,
            (result.stderr or result.stdout).strip()))
    return result


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def p4_process_pid():
    result = run(["pgrep", "-f", "^/home/CoreRouter/venv/bin/python3 infrastructure/sdn/topo_p4.py --p4$"])
    pids = [line for line in result.stdout.splitlines() if line.strip()]
    if len(pids) != 1:
        raise RuntimeError("expected one live P4 topology process, found {}".format(len(pids)))
    return pids[0]


def p4_container(pid):
    ids = run(["docker", "ps", "--no-trunc", "-q", "--filter", "ancestor=" + P4_IMAGE]).stdout.split()
    matches = []
    for ident in ids:
        state_pid = run(["docker", "inspect", "--format", "{{.State.Pid}}", ident]).stdout.strip()
        if state_pid == pid:
            matches.append(ident)
    if len(matches) != 1:
        raise RuntimeError("could not uniquely identify live Mininet/P4 container")
    return matches[0]


def mininet_pids():
    table = run(["ps", "-eo", "pid=,args="]).stdout.splitlines()
    found = {}
    for host in HOSTS:
        suffix = "--norc --noediting -is mininet:{}".format(host)
        pids = [line.strip().split(None, 1)[0] for line in table if line.strip().endswith(suffix)]
        if len(pids) != 1:
            raise RuntimeError("expected one running Mininet namespace for {}, found {}".format(host, len(pids)))
        found[host] = pids[0]
    return found


def ns_command(container, pid, args):
    return ["docker", "exec", container, "nsenter", "-t", pid, "-n",
            "chroot", "/host", "/home/CoreRouter/venv/bin/python3"] + list(map(str, args))


def counter_snapshot(out, switches=SWITCHES):
    out.mkdir(parents=True, exist_ok=True)
    result = {}
    for switch in switches:
        commands = ["counter_read srv6_advance_counter 0",
                    "counter_read srv6_terminal_counter 0",
                    "counter_read msd_violation_counter 0",
                    "table_dump routing_v6", "table_dump srv6_end_dx4_table"]
        cli = run([str(P4CLI), "s{}".format(switch)] + commands,
                  timeout=30, cwd=ROOT).stdout
        (out / "s{}_readback.txt".format(switch)).write_text(cli)
        counters = {}
        for name in ("srv6_advance_counter", "srv6_terminal_counter", "msd_violation_counter"):
            match = re.search(r"{}\[0\].*?packets=(\d+)".format(name), cli, re.S)
            if not match:
                raise RuntimeError("cannot read {} on s{}".format(name, switch))
            counters[name] = int(match.group(1))
        result["s{}".format(switch)] = counters
    return result


def deploy_support(run_id, out):
    app = run(["kubectl", "create", "configmap", "vnf-chain-relay-app",
               "--namespace=core-router", "--from-file=vnf_chain_relay.py={}".format(RELAY),
               "--from-file=chain_handoff.py={}".format(HANDOFF),
               "--dry-run=client", "-o", "yaml"], cwd=ROOT).stdout
    app_doc = json.loads(run(["kubectl", "create", "configmap", "vnf-chain-relay-app",
                              "--namespace=core-router", "--from-file=vnf_chain_relay.py={}".format(RELAY),
                              "--from-file=chain_handoff.py={}".format(HANDOFF),
                              "--dry-run=client", "-o", "json"], cwd=ROOT).stdout)
    app_doc.setdefault("metadata", {}).setdefault("labels", {})["core-router/component"] = "chain-relay-app"
    run(["kubectl", "apply", "-f", "-"], input_text=json.dumps(app_doc), cwd=ROOT)
    (out / "relay_configmap.yaml").write_text(app)
    for path in (ROOT / "infrastructure/k8s/manifests/vnf-chain-inputs.yaml",
                 ROOT / "infrastructure/k8s/tekton/tasks/task-prepare-vnf-chain.yaml",
                 ROOT / "infrastructure/k8s/tekton/pipeline-vnf-chain.yaml"):
        run(["kubectl", "apply", "-f", str(path)], cwd=ROOT)


def create_workspace(run_id):
    name = "chain-ws-{}".format(run_id)
    doc = {"apiVersion": "v1", "kind": "PersistentVolumeClaim",
           "metadata": {"name": name, "namespace": "core-router",
                        "labels": {"core-router/chain-run": run_id}},
           "spec": {"accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "50Mi"}}}}
    run(["kubectl", "create", "-f", "-"], input_text=json.dumps(doc), cwd=ROOT)
    # microk8s-hostpath uses WaitForFirstConsumer; Tekton's first task binds it.
    return name


def run_pipeline(run_id, stage, deploy_name, pvc, out):
    name = "chain-{}-s{}".format(run_id, stage)
    selector = "app={}".format(deploy_name)
    doc = {"apiVersion": "tekton.dev/v1", "kind": "PipelineRun",
           "metadata": {"name": name, "namespace": "core-router",
                        "labels": {"core-router/chain-run": run_id,
                                   "core-router/chain-stage": str(stage)}},
           "spec": {"pipelineRef": {"name": "vnf-chain-deploy"},
                    "taskRunTemplate": {"serviceAccountName": "tekton-admin"},
                    "params": [{"name": "deployName", "value": deploy_name},
                               {"name": "labelSelector", "value": selector},
                               {"name": "fileName", "value": "vnf-chain-relay.yaml"},
                               {"name": "chainRunID", "value": run_id},
                               {"name": "chainStage", "value": str(stage)}],
                    "workspaces": [{"name": "ws", "persistentVolumeClaim": {"claimName": pvc}}]}}
    run(["kubectl", "create", "-f", "-"], input_text=json.dumps(doc), cwd=ROOT)
    run(["kubectl", "-n", "core-router", "wait", "--for=condition=Succeeded",
         "pipelinerun/" + name, "--timeout=300s"], timeout=320, cwd=ROOT)
    details = run(["kubectl", "-n", "core-router", "get", "pipelinerun", name, "-o", "json"], cwd=ROOT)
    (out / (name + ".json")).write_text(
        json.dumps(json.loads(details.stdout), indent=2, sort_keys=True) + "\n")
    pod = run(["kubectl", "-n", "core-router", "get", "pods", "-l", selector,
               "-o", "json"], cwd=ROOT)
    pods = [item for item in json.loads(pod.stdout)["items"]
            if item.get("status", {}).get("phase") == "Running"]
    if len(pods) != 1 or not pods[0].get("status", {}).get("podIP"):
        raise RuntimeError("Tekton did not create exactly one Ready relay Pod")
    return pods[0]["status"]["podIP"]


def wait_file(path, process, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if Path(path).exists():
            return
        if process.poll() is not None:
            raise RuntimeError("gateway exited before readiness: {}".format(path))
        time.sleep(0.2)
    raise RuntimeError("timed out waiting for gateway readiness: {}".format(path))


def launch_ns(container, pid, args, console):
    stream = Path(console).open("w")
    process = subprocess.Popen(ns_command(container, pid, args),
                               stdout=stream, stderr=subprocess.STDOUT,
                               cwd=ROOT, text=True)
    process._log_stream = stream
    return process


def finish_process(process, label, timeout=120):
    try:
        code = process.wait(timeout=timeout)
    finally:
        process._log_stream.close()
    if code:
        raise RuntimeError("{} failed with exit {}".format(label, code))


def run_phase(run_id, out, pids, container, pod_ips, start_id, count, sink_iface="h10-eth0"):
    phase = "pilot" if count == 3 else "run20"
    phase_dir = out / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    sources = [
        ("h6", 1, "fc00:9::1,fc00:6::1", MACS["s6_host"], pod_ips[0]),
        ("h9", 2, "fc00:10::1,fc00:9::1", MACS["s9_host"], pod_ips[1]),
    ]
    gateways = []
    for host, stage, stack, dst_mac, pod_ip in sources:
        output = phase_dir / ("gateway_stage{}.jsonl".format(stage))
        command = ["/home/CoreRouter/scripts/hil/vnf_chain_gateway.py",
                   "--iface", host + "-eth0", "--run-id", run_id,
                   "--stage", str(stage), "--pod-ip", pod_ip,
                   "--next-stack", stack, "--dst-mac", dst_mac,
                   "--count", str(count), "--start-id", str(start_id),
                   "--timeout", "30", "--out", str(output)]
        process = launch_ns(container, pids[host], command,
                            phase_dir / ("gateway_stage{}.console.log".format(stage)))
        gateways.append((process, output.with_suffix(".ready")))

    sink_out = phase_dir / "egress.jsonl"
    sink = launch_ns(container, pids["h10"], [
        "/home/CoreRouter/scripts/hil/chain_stage.py", "--iface", sink_iface,
        "--run-id", run_id, "--stage", "egress", "--count", str(count),
        "--timeout", "50", "--out", str(sink_out)], phase_dir / "egress.console.log")
    processes = [process for process, _ready in gateways] + [sink]
    try:
        wait_file(sink_out.with_suffix(".ready"), sink)
        for process, ready in gateways:
            wait_file(ready, process)

        source_out = phase_dir / "source.jsonl"
        sender = run(ns_command(container, pids["h1"], [
            "/home/CoreRouter/scripts/hil/chain_send.py", "--iface", "h1-eth0",
            "--run-id", run_id, "--stack", "fc00:6::1,fc00:1::1",
            "--dst-mac", MACS["s1_host"], "--count", str(count),
            "--start-id", str(start_id), "--out", str(source_out)]),
            timeout=max(60, count * 3), cwd=ROOT)
        (phase_dir / "sender.console.log").write_text(sender.stdout + sender.stderr)
        for process, _ready in gateways:
            finish_process(process, "gateway", timeout=100)
        finish_process(sink, "egress sink", timeout=100)
        return phase_dir
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if not process._log_stream.closed:
                process._log_stream.close()
        for phase_file in phase_dir.glob("*.ready"):
            phase_file.unlink(missing_ok=True)


def capture_pod_logs(run_id, names, out):
    for stage, name in enumerate(names, 1):
        logs = run(["kubectl", "-n", "core-router", "logs", "deployment/" + name],
                   timeout=30).stdout
        (out / "pod_stage{}.jsonl".format(stage)).write_text(logs)


def verify_phase(out, phase, start_id, count):
    p = out / phase
    summary = analyze(p / "source.jsonl", out / "pod_stage1.jsonl", out / "pod_stage2.jsonl",
                      p / "gateway_stage1.jsonl", p / "gateway_stage2.jsonl",
                      p / "egress.jsonl", (start_id, count))
    (p / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def expected_counter_deltas(before, after, count):
    expected = {
        "s1": {"srv6_advance_counter": count, "srv6_terminal_counter": 0,
               "msd_violation_counter": 0},
        "s6": {"srv6_advance_counter": count, "srv6_terminal_counter": count,
               "msd_violation_counter": 0},
        "s9": {"srv6_advance_counter": count, "srv6_terminal_counter": count,
               "msd_violation_counter": 0},
        "s10": {"srv6_advance_counter": 0, "srv6_terminal_counter": count,
                "msd_violation_counter": 0},
    }
    deltas = {}
    for switch, values in expected.items():
        deltas[switch] = {key: after[switch][key] - before[switch][key] for key in values}
        if deltas[switch] != values:
            raise RuntimeError("P4 counter mismatch on {}: got {}, expected {}".format(
                switch, deltas[switch], values))
    return deltas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=RUN_DEFAULT)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "results/hil/vnf_pod_chain_20261124")
    parser.add_argument("--cleanup", action="store_true", default=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,32}", args.run_id):
        parser.error("invalid run ID")
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    names = ["vnf-chain-{}-s1".format(args.run_id), "vnf-chain-{}-s2".format(args.run_id)]
    pvc = "chain-ws-{}".format(args.run_id)
    try:
        topology_pid = p4_process_pid()
        container = p4_container(topology_pid)
        pids = mininet_pids()
        args.out.joinpath("live_processes.json").write_text(json.dumps(
            {"topology_pid": topology_pid, "p4_container": container,
             "mininet_host_pids": pids}, indent=2, sort_keys=True) + "\n")
        deploy_support(args.run_id, args.out)
        pvc = create_workspace(args.run_id)
        for stage, name in enumerate(names, 1):
            run_pipeline(args.run_id, stage, name, pvc, args.out)
        pod_ips = []
        for name in names:
            pod_ips.append(run(["kubectl", "-n", "core-router", "get", "pods", "-l",
                                "app={}".format(name), "-o",
                                "jsonpath={.items[0].status.podIP}"]).stdout.strip())
        args.out.joinpath("relay_pods.json").write_text(json.dumps(
            [{"deployment": name, "pod_ip": ip, "node": "worker2"}
             for name, ip in zip(names, pod_ips)], indent=2) + "\n")

        before = counter_snapshot(args.out / "counters_before")
        p4_snapshots = {"before": before}
        pilot = run_phase(args.run_id, args.out, pids, container, pod_ips, 1, 3)
        capture_pod_logs(args.run_id, names, args.out)
        pilot_summary = verify_phase(args.out, "pilot", 1, 3)
        after_pilot = counter_snapshot(args.out / "counters_after_pilot")
        p4_snapshots["after_pilot"] = after_pilot
        pilot_delta = expected_counter_deltas(before, after_pilot, 3)

        run20 = run_phase(args.run_id, args.out, pids, container, pod_ips, 4, 20)
        capture_pod_logs(args.run_id, names, args.out)
        summary20 = verify_phase(args.out, "run20", 4, 20)
        after = counter_snapshot(args.out / "counters_after_run20")
        p4_snapshots["after_run20"] = after
        total_delta = expected_counter_deltas(before, after, 23)
        args.out.joinpath("p4_counters.json").write_text(json.dumps(
            {"snapshots": p4_snapshots, "pilot_delta": pilot_delta,
             "total_delta": total_delta}, indent=2, sort_keys=True) + "\n")

        evidence_files = sorted(path for path in args.out.rglob("*")
                                if path.is_file() and path.name != "manifest.json")
        manifest = {"run_id": args.run_id,
                    "scope": "two Kubernetes VNF relay Pods with unchanged inner IPv4 packet bytes across three SRv6/P4 legs",
                    "p4_legs": [
                        {"from": "h1", "to": "h6", "switch_path": ["s1", "s6"],
                         "sid_stack_final_to_first": ["fc00:6::1", "fc00:1::1"], "msd_depth": 2},
                        {"from": "h6", "to": "h9", "switch_path": ["s6", "s9"],
                         "sid_stack_final_to_first": ["fc00:9::1", "fc00:6::1"], "msd_depth": 2},
                        {"from": "h9", "to": "h10", "switch_path": ["s9", "s10"],
                         "sid_stack_final_to_first": ["fc00:10::1", "fc00:9::1"], "msd_depth": 2}],
                    "handoff": "Mininet h6/h9 UDP envelope to CNI relay Pod and exact-byte echo; not counted as P4",
                    "pilot": pilot_summary, "run20": summary20,
                    "total_packets": 23, "p4_counter_deltas": total_delta,
                    "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in
                                      (RELAY, HANDOFF, ROOT / "scripts/hil/vnf_chain_gateway.py",
                                       ROOT / "scripts/hil/chain_send.py",
                                       ROOT / "scripts/hil/chain_stage.py",
                                       ROOT / "scripts/hil/analyze_vnf_pod_chain.py",
                                       ROOT / "scripts/hil/vnf_pod_chain_probe.py",
                                       ROOT / "infrastructure/k8s/manifests/vnf-chain-inputs.yaml",
                                       ROOT / "infrastructure/k8s/manifests/chain-relay-app.yaml",
                                       ROOT / "infrastructure/k8s/tekton/tasks/task-prepare-vnf-chain.yaml",
                                       ROOT / "infrastructure/k8s/tekton/pipeline-vnf-chain.yaml")},
                    "evidence_sha256": {str(path.relative_to(ROOT)): sha(path)
                                        for path in evidence_files}}
        (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"pilot_packets": pilot_summary["complete_packets"],
                          "run20_packets": summary20["complete_packets"],
                          "total_packets": 23, "p4_counter_deltas": total_delta,
                          "manifest": str(args.out / "manifest.json")}, sort_keys=True))
    finally:
        if args.cleanup:
            for name in names:
                run(["kubectl", "-n", "core-router", "delete", "deployment/" + name,
                     "service/" + name + "-svc", "--ignore-not-found=true"],
                    check=False, timeout=60)
            run(["kubectl", "-n", "core-router", "delete", "pods", "-l",
                 "tekton.dev/pipeline=vnf-chain-deploy,core-router/chain-run={}".format(args.run_id),
                 "--ignore-not-found=true", "--timeout=30s"], check=False, timeout=40)
            run(["kubectl", "-n", "core-router", "delete", "pvc/" + pvc,
                 "--ignore-not-found=true", "--timeout=30s"], check=False, timeout=40)


if __name__ == "__main__":
    main()
