#!/usr/bin/env python3
"""Exercise MSD parsing on a running BMv2 switch.

Unlike the former predicate-only script, this harness sends SRv6 packets
through an actual switch and checks egress captures plus the P4 violation
counter. It does not test the controller's runtime admission decision; packets
are injected directly into the data plane to test the independent P4 check.

Run against an isolated BMv2 switch loaded with the requested MSD profile:

    sudo python3 infrastructure/sdn/p4/tests/test_msd_enforcement.py \\
      --container bmv2-s1 --thrift-port 19091 \\
      --ingress-iface s1-eth1 --egress-iface s1-eth2 --egress-port 2 \\
      --msd 4 --output results/p4_msd_run.json

The harness adds one unique IPv6 route, reads the existing
`msd_violation_counter`, and writes ingress/egress pcaps and a JSON run record.
It requires Docker, Scapy, packet-capture privileges, and a running test switch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _run_switch_cli(container: str, thrift_port: int, commands: list[str]) -> str:
    command = [
        "docker", "exec", "-i", container,
        "simple_switch_CLI", "--thrift-port", str(thrift_port),
    ]
    completed = subprocess.run(
        command, input="\n".join(commands) + "\n", text=True,
        capture_output=True, check=False,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode != 0 or re.search(r"\berror\b|\bexception\b", output, re.I):
        raise RuntimeError(f"BMv2 CLI command failed: {output.strip()}")
    return output


def _read_counter(container: str, thrift_port: int) -> int:
    output = _run_switch_cli(container, thrift_port, ["counter_read msd_violation_counter 0"])
    match = re.search(r"packets:\s*(\d+)", output)
    if not match:
        raise RuntimeError(f"Could not parse msd_violation_counter output: {output.strip()}")
    return int(match.group(1))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compiled_sid_limit(path: Path) -> int:
    profile = json.loads(path.read_text(encoding="utf-8"))
    limits = [int(stack["size"]) for stack in profile.get("header_stacks", [])
              if stack.get("name") == "sid_list"]
    if len(limits) != 1:
        raise ValueError(f"Compiled profile {path} has no unique sid_list header stack")
    return limits[0]


def _validate_compiled_sid_limit(path: Path, requested_msd: int) -> int:
    compiled_msd = _compiled_sid_limit(path)
    if compiled_msd != requested_msd:
        raise ValueError(f"Requested MSD {requested_msd} does not match compiled sid_list size {compiled_msd}")
    return compiled_msd


def _send_and_capture(scapy, ingress_iface: str, egress_iface: str,
                      packet, marker: bytes, timeout_s: float):
    captured = []

    def capture():
        captured.extend(scapy.sniff(
            iface=egress_iface, timeout=timeout_s,
            lfilter=lambda candidate: marker in bytes(candidate),
        ))

    listener = threading.Thread(target=capture, daemon=True)
    listener.start()
    time.sleep(0.15)  # let the capture socket attach before transmitting
    scapy.sendp(packet, iface=ingress_iface, verbose=False)
    listener.join(timeout_s + 1.0)
    if listener.is_alive():
        raise TimeoutError(f"Capture on {egress_iface} did not stop")
    return captured


def run(args: argparse.Namespace) -> dict:
    try:
        from scapy.all import Ether, IPv6, IPv6ExtHdrRouting, Raw, sendp, sniff, wrpcap
    except ImportError as exc:
        raise RuntimeError("Scapy is required for an actual BMv2 packet test") from exc

    scapy = type("ScapyFacade", (), {"sniff": sniff, "sendp": sendp})
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcap_dir = output_path.parent / f"{output_path.stem}_pcaps"
    pcap_dir.mkdir(parents=True, exist_ok=True)

    profile = args.switch_json.resolve()
    if not profile.is_file():
        raise FileNotFoundError(f"BMv2 JSON profile does not exist: {profile}")
    compiled_msd = _validate_compiled_sid_limit(profile, args.msd)
    running = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", args.container],
        text=True, capture_output=True, check=False,
    )
    if running.returncode != 0 or running.stdout.strip().lower() != "true":
        raise RuntimeError(f"BMv2 container is not running: {args.container}")
    image = subprocess.run(
        ["docker", "inspect", "-f", "{{.Config.Image}}", args.container],
        text=True, capture_output=True, check=False,
    )
    if image.returncode != 0:
        raise RuntimeError(f"Could not identify BMv2 image for {args.container}")

    run_id = uuid.uuid4().hex[:8]
    sid_base = f"2001:db8:{run_id[:4]}:{run_id[4:]}::"
    overflow_marker = f"HARP-MSD-OVER-{run_id}".encode()
    boundary_marker = f"HARP-MSD-BOUNDARY-{run_id}".encode()
    overflow_sids = [f"{sid_base}{index + 1}" for index in range(args.msd + 3)]
    boundary_sids = [f"{sid_base}{index + 101}" for index in range(args.msd)]

    # A route entry lets the valid boundary packet reach the selected egress.
    # The over-depth packet must be discarded before this forwarding action.
    _run_switch_cli(args.container, args.thrift_port, [
        f"table_add routing_v6 ipv6_forward {boundary_sids[0]}/128 => "
        f"{args.dst_mac} {args.src_mac} {args.egress_port}"
    ])

    def build_packet(sids: list[str], marker: bytes):
        return (
            Ether(src=args.src_mac, dst=args.dst_mac)
            / IPv6(src=args.source_ip, dst=sids[0], nh=43, hlim=64)
            / IPv6ExtHdrRouting(type=4, segleft=0, addresses=sids)
            / Raw(marker)
        )

    over_packet = build_packet(overflow_sids, overflow_marker)
    boundary_packet = build_packet(boundary_sids, boundary_marker)
    counter_before = _read_counter(args.container, args.thrift_port)

    over_egress = _send_and_capture(
        scapy, args.ingress_iface, args.egress_iface, over_packet,
        overflow_marker, args.capture_timeout,
    )
    counter_after_over = _read_counter(args.container, args.thrift_port)
    boundary_egress = _send_and_capture(
        scapy, args.ingress_iface, args.egress_iface, boundary_packet,
        boundary_marker, args.capture_timeout,
    )
    counter_after_boundary = _read_counter(args.container, args.thrift_port)

    wrpcap(str(pcap_dir / "injected_packets.pcap"), [over_packet, boundary_packet])
    if over_egress:
        wrpcap(str(pcap_dir / "over_depth_egress.pcap"), over_egress)
    if boundary_egress:
        wrpcap(str(pcap_dir / "boundary_egress.pcap"), boundary_egress)
    over_delta = counter_after_over - counter_before
    boundary_delta = counter_after_boundary - counter_after_over
    report = {
        "protocol": "bmv2-msd-enforcement-v1",
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target": "BMv2 software switch",
        "container": args.container,
        "container_image": image.stdout.strip(),
        "thrift_port": args.thrift_port,
        "switch_json": str(profile),
        "switch_json_sha256": _sha256(profile),
        "msd_profile": args.msd,
        "compiled_sid_list_size": compiled_msd,
        "p4_source": str(REPO_ROOT / "infrastructure/sdn/p4/srv6_basic.p4"),
        "p4_source_sha256": _sha256(REPO_ROOT / "infrastructure/sdn/p4/srv6_basic.p4"),
        "ingress_interface": args.ingress_iface,
        "egress_interface": args.egress_iface,
        "egress_port": args.egress_port,
        "tests": {
            "over_depth": {
                "sid_depth": len(overflow_sids),
                "expected": "drop and increment parser violation counter",
                "egress_packets_with_marker": len(over_egress),
                "counter_before": counter_before,
                "counter_after": counter_after_over,
                "counter_delta": over_delta,
                "passed": len(over_egress) == 0 and over_delta == 1,
            },
            "at_boundary": {
                "sid_depth": len(boundary_sids),
                "expected": "forward",
                "egress_packets_with_marker": len(boundary_egress),
                "counter_delta": boundary_delta,
                "passed": len(boundary_egress) >= 1 and boundary_delta == 0,
            },
        },
        "runtime_admission": "not exercised; packets were injected directly into BMv2",
        "parser_error_observation": (
            "inferred from the P4 violation-counter increment; per-packet parser error is not exported"
        ),
        "packet_captures": {"directory": str(pcap_dir), "injected": "injected_packets.pcap",
                             "over_depth_egress": "over_depth_egress.pcap" if over_egress else None,
                             "boundary_egress": "boundary_egress.pcap" if boundary_egress else None},
    }
    report["passed"] = all(test["passed"] for test in report["tests"].values())
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True, help="Running BMv2 Docker container")
    parser.add_argument("--thrift-port", required=True, type=int)
    parser.add_argument("--ingress-iface", required=True, help="Host interface attached to BMv2 ingress")
    parser.add_argument("--egress-iface", required=True, help="Host interface attached to BMv2 egress")
    parser.add_argument("--egress-port", required=True, type=int, help="BMv2 port for egress interface")
    parser.add_argument("--msd", required=True, type=int, help="Compiled switch MSD profile")
    parser.add_argument("--switch-json", type=Path, help="Compiled profile JSON")
    parser.add_argument("--source-ip", default="2001:db8::ffff")
    parser.add_argument("--src-mac", default="00:00:00:00:00:01")
    parser.add_argument("--dst-mac", default="00:00:00:00:00:02")
    parser.add_argument("--capture-timeout", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path("results/p4_msd_run.json"))
    args = parser.parse_args()
    if args.msd < 1 or args.egress_port < 0 or args.capture_timeout <= 0:
        parser.error("MSD and capture timeout must be positive; egress port must be non-negative")
    if args.switch_json is None:
        args.switch_json = REPO_ROOT / f"infrastructure/sdn/p4/build/msd_{args.msd}/srv6_msd_{args.msd}.json"
    return args


if __name__ == "__main__":
    try:
        result = run(parse_args())
    except Exception as exc:
        print(f"BMv2 MSD test failed to execute: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(0 if result["passed"] else 1)
