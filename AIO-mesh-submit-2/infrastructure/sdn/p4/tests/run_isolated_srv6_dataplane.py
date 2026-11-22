#!/usr/bin/env python3
"""Run a two-BMv2 SRv6-to-IPv4 decapsulation smoke in an isolated container.

The caller must run this inside a disposable p4lang/p4app container with
--network none, NET_ADMIN/NET_RAW capabilities, compiled JSON mounted read-only
at /build, this script mounted read-only at /tests, and an output directory at
/out. It creates only container-local veth pairs and BMv2 processes.
"""

import argparse
import json
import re
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path

from scapy.all import Ether, IP, IPv6, Raw, UDP, sendp, sniff, wrpcap


MAC = {
    "client": "02:00:00:00:00:01",
    "s1_in": "02:00:00:00:00:11",
    "s1_out": "02:00:00:00:00:12",
    "s2_in": "02:00:00:00:00:21",
    "s2_out": "02:00:00:00:00:22",
    "sink": "02:00:00:00:00:02",
}


def run(args, *, input_text=None, timeout=15):
    result = subprocess.run(args, input=input_text, universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout)
    if result.returncode:
        raise RuntimeError("{} failed ({}): {}{}".format(
            " ".join(args), result.returncode, result.stdout, result.stderr))
    return result.stdout + result.stderr


def set_link(name, mac):
    run(["ip", "link", "set", name, "address", mac])
    run(["ip", "link", "set", name, "up"])


def add_pair(left, right, left_mac, right_mac):
    run(["ip", "link", "add", left, "type", "veth", "peer", "name", right])
    set_link(left, left_mac)
    set_link(right, right_mac)


def start_switch(name, device_id, port1, port2, thrift_port, p4_json, output_dir):
    log = (output_dir / (name + ".log")).open("w")
    process = subprocess.Popen([
        "simple_switch", "--device-id", str(device_id),
        "--thrift-port", str(thrift_port), "--log-console", "--log-level", "error",
        "-i", "1@" + port1, "-i", "2@" + port2, str(p4_json),
    ], stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log.flush()
            raise RuntimeError("{} exited early; see {}".format(name, log.name))
        try:
            with socket.create_connection(("127.0.0.1", thrift_port), timeout=0.2):
                return process, log
        except OSError:
            time.sleep(0.1)
    process.terminate()
    raise TimeoutError("{} Thrift port {} did not open".format(name, thrift_port))


def cli(thrift_port, commands):
    output = run(["simple_switch_CLI", "--thrift-port", str(thrift_port)],
                 input_text="\n".join(commands) + "\n")
    if re.search(r"\berror\b|exception", output, re.I):
        raise RuntimeError("BMv2 CLI rejected commands: " + output)
    return output


def counter(thrift_port, name):
    output = cli(thrift_port, ["counter_read {} 0".format(name)])
    match = re.search(r"packets\s*[:=]\s*(\d+)", output)
    if not match:
        raise RuntimeError("counter output was not understood: " + output)
    return int(match.group(1))


def capture_one(interface, marker, timeout=2.0):
    packets = []
    thread = threading.Thread(target=lambda: packets.extend(sniff(
        iface=interface, timeout=timeout,
        lfilter=lambda packet: marker in bytes(packet),
    )), daemon=True)
    thread.start()
    time.sleep(0.2)
    return thread, packets


def srv6_packet(source_mac, switch_mac, sid_list, payload):
    # Build RFC 8754 fields directly because the image's Scapy 2.4.x routing
    # header class predates the explicit Last Entry field.
    final_to_first = b"".join(socket.inet_pton(socket.AF_INET6, sid) for sid in sid_list)
    count = len(sid_list)
    srh = struct.pack("!BBBBBBH", 4, 2 * count, 4, count - 1,
                      count - 1, 0, 0) + final_to_first
    return (Ether(src=source_mac, dst=switch_mac)
            / IPv6(src="2001:db8::1", dst=sid_list[-1], nh=43, hlim=32)
            / Raw(srh + bytes(payload)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("/build"))
    parser.add_argument("--output-dir", type=Path, default=Path("/out"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    p4_json = args.build_dir / "srv6_msd_4.json"
    if not p4_json.is_file():
        raise FileNotFoundError(str(p4_json))

    add_pair("client0", "s1-eth1", MAC["client"], MAC["s1_in"])
    add_pair("s1-eth2", "s2-eth1", MAC["s1_out"], MAC["s2_in"])
    add_pair("s2-eth2", "sink0", MAC["s2_out"], MAC["sink"])

    switches = []
    try:
        switches.append(start_switch("s1", 1, "s1-eth1", "s1-eth2", 19091,
                                     p4_json, args.output_dir))
        switches.append(start_switch("s2", 2, "s2-eth1", "s2-eth2", 19092,
                                     p4_json, args.output_dir))

        cli(19091, [
            "table_add srv6_local_sid srv6_advance_segment fc00:1::1 =>",
            "table_add routing_v6 ipv6_forward fc00:6::1/128 => {} {} 2".format(
                MAC["s2_in"], MAC["s1_out"]),
        ])
        cli(19092, [
            "table_add srv6_end_dx4_table srv6_end_dx4 fc00:6::1 => {} {} 2".format(
                MAC["sink"], MAC["s2_out"]),
        ])
        readbacks = {
            "s1_local_sid": cli(19091, ["table_dump srv6_local_sid"]),
            "s1_routing_v6": cli(19091, ["table_dump routing_v6"]),
            "s2_end_dx4": cli(19092, ["table_dump srv6_end_dx4_table"]),
        }
        (args.output_dir / "table_readback.txt").write_text(
            "\n".join("=== {} ===\n{}".format(key, value)
                       for key, value in sorted(readbacks.items())))

        advance_before = counter(19091, "srv6_advance_counter")
        terminal_before = counter(19092, "srv6_terminal_counter")
        msd_before = counter(19091, "msd_violation_counter")
        marker = b"HIL-SRV6-END-DX4-BOUNDARY"
        addresses = ["fc00:6::1", "fc00:1::1"]
        inner = IP(src="192.0.2.1", dst="198.51.100.2", ttl=64) / UDP(
            sport=45000, dport=8000) / Raw(marker)
        packet = srv6_packet(MAC["client"], MAC["s1_in"], addresses, inner)
        listener, captured = capture_one("sink0", marker)
        sendp(packet, iface="client0", verbose=False)
        listener.join(3)
        if listener.is_alive():
            raise TimeoutError("sink capture did not finish")
        if len(captured) != 1:
            raise AssertionError("expected one decapsulated packet, got {}".format(len(captured)))
        received = captured[0]
        if received.type != 0x0800 or IP not in received or marker not in bytes(received):
            raise AssertionError("terminal action did not emit the inner IPv4 packet")

        advance_after = counter(19091, "srv6_advance_counter")
        terminal_after = counter(19092, "srv6_terminal_counter")
        msd_after = counter(19091, "msd_violation_counter")

        overflow_marker = b"HIL-SRV6-MSD-OVERFLOW"
        overflow_addresses = ["2001:db8:ffff::{}".format(index + 1) for index in range(5)]
        overflow_inner = IP(src="192.0.2.1", dst="198.51.100.2", ttl=64) / UDP(
            sport=45001, dport=8000) / Raw(overflow_marker)
        overflow = srv6_packet(MAC["client"], MAC["s1_in"],
                               overflow_addresses, overflow_inner)
        overflow_listener, overflow_capture = capture_one("sink0", overflow_marker)
        sendp(overflow, iface="client0", verbose=False)
        overflow_listener.join(3)
        if overflow_listener.is_alive():
            raise TimeoutError("overflow capture did not finish")
        msd_overflow_after = counter(19091, "msd_violation_counter")

        report = {
            "test": "isolated-bmv2-srv6-end-dx4-v1",
            "compiled_profile": str(p4_json),
            "switches": ["s1", "s2"],
            "wire_sids": addresses,
            "boundary_forward": {
                "captured_packets": len(captured),
                "ether_type": "0x{:04x}".format(received.type),
                "inner_ipv4": IP in received,
                "advance_counter_delta": advance_after - advance_before,
                "terminal_counter_delta": terminal_after - terminal_before,
                "passed": (len(captured) == 1 and received.type == 0x0800
                           and IP in received and advance_after - advance_before == 1
                           and terminal_after - terminal_before == 1),
            },
            "over_msd_drop": {
                "sid_depth": len(overflow_addresses),
                "compiled_msd": 4,
                "captured_packets": len(overflow_capture),
                "violation_counter_delta": msd_overflow_after - msd_after,
                "passed": (len(overflow_capture) == 0
                           and msd_overflow_after - msd_after == 1),
            },
        }
        report["passed"] = all(item["passed"] for item in
                                (report["boundary_forward"], report["over_msd_drop"]))
        wrpcap(str(args.output_dir / "boundary_in.pcap"), [packet])
        wrpcap(str(args.output_dir / "boundary_out.pcap"), captured)
        wrpcap(str(args.output_dir / "over_msd_in.pcap"), [overflow])
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        if not report["passed"]:
            raise SystemExit(1)
    finally:
        for process, log in reversed(switches):
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            log.close()


if __name__ == "__main__":
    main()
