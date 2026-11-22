#!/usr/bin/env python3
"""Execute the planned protected/bypass over-MSD comparison on isolated BMv2.

Python 3.5 compatible (p4lang/p4app image). Run ONLY inside a disposable
container started with --network none and NET_ADMIN/NET_RAW, e.g.:

  docker run --rm --network none --cap-add NET_ADMIN --cap-add NET_RAW \
    -v <plan_dir>:/plan:ro -v <offline_p4_build>:/build:ro \
    -v <this_scripts_dir>:/tests:ro -v <out_dir>:/out \
    --entrypoint python3 p4lang/p4app:latest /tests/exec_overmsd_isolated.py

All veths and BMv2 processes live in the container's private network namespace.
For each planned (case, mode) and trial it starts fresh switches with the
per-switch compiled MSD profile, installs the bootstrap local SIDs (as the live
controller does) and - only if the plan allows - the request's rules; reads every
table back; reads per-switch counters before/after; sends N marked packets;
captures at every switch egress and at the sink; then tears everything down.
"""

import csv
import json
import re
import socket
import struct
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from scapy.all import Ether, IP, IPv6, Raw, UDP, sendp, sniff, wrpcap

PLAN = Path("/plan/plan.json")
BUILD = Path("/build")
OUT = Path("/out")
COUNTERS = ("srv6_advance_counter", "srv6_terminal_counter", "msd_violation_counter")
CLIENT_MAC = "02:00:00:00:00:01"
SINK_MAC = "02:00:00:00:00:02"


def utc():
    return datetime.utcnow().isoformat() + "Z"


def run(args, input_text=None, timeout=20, check=True):
    p = subprocess.run(args, input=input_text, universal_newlines=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError("{} failed ({}): {}{}".format(" ".join(args), p.returncode, p.stdout, p.stderr))
    return p.stdout + p.stderr


def mac(sw, port):
    return "02:00:00:00:{:02x}:{:02x}".format(sw, port)


def veth(a, b, mac_a, mac_b):
    run(["ip", "link", "add", a, "type", "veth", "peer", "name", b])
    for name, m in ((a, mac_a), (b, mac_b)):
        run(["ip", "link", "set", name, "address", m])
        run(["sysctl", "-q", "-w", "net.ipv6.conf.{}.disable_ipv6=1".format(name)], check=False)
        run(["ip", "link", "set", name, "up"])


def cli(port, commands, transcript):
    out = run(["simple_switch_CLI", "--thrift-port", str(port)], input_text="\n".join(commands) + "\n")
    transcript.append({"utc": utc(), "thrift_port": port, "commands": commands, "output": out})
    if re.search(r"\berror\b|exception|invalid", out, re.I):
        raise RuntimeError("CLI rejected: " + out)
    return out


def counters(port, transcript):
    out = cli(port, ["counter_read {} 0".format(c) for c in COUNTERS], transcript)
    vals = re.findall(r"packets\s*[:=]\s*(\d+)", out)
    if len(vals) != len(COUNTERS):
        raise RuntimeError("counter parse failed: " + out)
    return dict(zip(COUNTERS, [int(v) for v in vals]))


def hexint(text):
    return int(text.strip(), 16)


def mac_int(m):
    return int(m.replace(":", ""), 16)


def parse_dump(out):
    """Return list of (key_hex, action, [param ints]) for non-default entries."""
    entries = []
    for block in out.split("Dumping entry")[1:]:
        key = re.search(r":\s*(?:EXACT|LPM)\s+([0-9a-f]+)(?:/(\d+))?", block)
        act = re.search(r"Action entry:[ \t]*\S+\.(\w+)[ \t]*-[ \t]*([^\n]*)", block)
        if key and act:
            params = [hexint(x) for x in act.group(2).split(",") if x.strip()]
            entries.append((key.group(1), act.group(1), params))
    return entries


def ipv6_hex(addr):
    return socket.inet_pton(socket.AF_INET6, addr).hex()


def expected_entry(rule):
    if rule["type"] == "ipv6_route":
        return ("routing_v6", ipv6_hex(rule["prefix"]), "ipv6_forward",
                [mac_int(rule["dst_mac"]), mac_int(rule["src_mac"]), rule["out_port"]])
    return ("srv6_end_dx4_table", ipv6_hex(rule["sid"]), "srv6_end_dx4",
            [mac_int(rule["dst_mac"]), mac_int(rule["src_mac"]), rule["out_port"]])


def table_cmd(rule):
    if rule["type"] == "ipv6_route":
        return "table_add routing_v6 ipv6_forward {}/{} => {} {} {}".format(
            rule["prefix"], rule["prefix_len"], rule["dst_mac"], rule["src_mac"], rule["out_port"])
    return "table_add srv6_end_dx4_table srv6_end_dx4 {} => {} {} {}".format(
        rule["sid"], rule["dst_mac"], rule["src_mac"], rule["out_port"])


def srv6_packet(sid_list_final_to_first, payload, segments_left=None):
    """RFC 8754 SRH. Default SL = Last Entry (fresh packet); a smaller SL models
    segments already traversed, so the parser still sees Last Entry + 1 SIDs."""
    count = len(sid_list_final_to_first)
    sl = count - 1 if segments_left is None else segments_left
    segs = b"".join(socket.inet_pton(socket.AF_INET6, s) for s in sid_list_final_to_first)
    srh = struct.pack("!BBBBBBH", 4, 2 * count, 4, sl, count - 1, 0, 0) + segs
    return (Ether(src=CLIENT_MAC, dst=None) / IPv6(src="2001:db8::1", dst=sid_list_final_to_first[sl], nh=43, hlim=32)
            / Raw(srh + bytes(payload)))


def start_capture(iface, marker, timeout, store):
    def job():
        store[iface] = sniff(iface=iface, timeout=timeout, lfilter=lambda p: marker in bytes(p))
    t = threading.Thread(target=job, daemon=True)
    t.start()
    return t


def one_trial(run_spec, trial, plan, trial_dir):
    transcript, stamps = [], {"trial_start_utc": utc()}
    path = run_spec["switch_path"]
    names = ["s{}".format(s) for s in path]
    procs, logs, created = [], [], []
    try:
        veth("client0", "{}-p1".format(names[0]), CLIENT_MAC, mac(path[0], 1)); created.append("client0")
        for a, b, na, nb in zip(path, path[1:], names, names[1:]):
            veth("{}-p2".format(na), "{}-p1".format(nb), mac(a, 2), mac(b, 1)); created.append("{}-p2".format(na))
        veth("{}-p2".format(names[-1]), "sink0", mac(path[-1], 2), SINK_MAC); created.append("{}-p2".format(names[-1]))
        ports = {}
        for idx, (sw, name) in enumerate(zip(path, names)):
            profile = run_spec["switch_profile_file"][name]
            msd = profile.split("_")[-1].split(".")[0]
            jf = BUILD / "msd_{}".format(msd) / profile
            port = 19090 + idx + 1
            log = (trial_dir / "{}.log".format(name)).open("w")
            p = subprocess.Popen(["simple_switch", "--device-id", str(idx + 1), "--thrift-port", str(port),
                                  "--log-console", "--log-level", "warn", "-i", "1@{}-p1".format(name),
                                  "-i", "2@{}-p2".format(name), str(jf)], stdout=log, stderr=subprocess.STDOUT)
            procs.append(p); logs.append(log); ports[name] = port
            deadline = time.time() + 15
            while True:
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                    break
                except OSError:
                    if time.time() > deadline or p.poll() is not None:
                        raise RuntimeError("switch {} did not start".format(name))
                    time.sleep(0.1)
        stamps["switches_ready_utc"] = utc()
        # bootstrap identical to the live controller: local SID per switch
        for sw, name in zip(path, names):
            cli(ports[name], ["table_add srv6_local_sid srv6_advance_segment fc00:{}::1 =>".format(sw)], transcript)
        t_install = time.monotonic()
        for rule in run_spec["rules"]:
            cli(ports[rule["switch"]], [table_cmd(rule)], transcript)
        stamps["rules_installed_utc"] = utc()
        install_ms = (time.monotonic() - t_install) * 1000.0
        # readback of every table on every switch
        t_rb = time.monotonic()
        dumps, readback = {}, []
        for name in names:
            dumps[name] = {t: parse_dump(cli(ports[name], ["table_dump {}".format(t)], transcript))
                           for t in ("srv6_local_sid", "routing_v6", "srv6_end_dx4_table")}
        for rule in run_spec["rules"] + run_spec["rules_compiled_but_not_installed"]:
            table, key, action, params = expected_entry(rule)
            present = any(k == key and a == action and p == params for k, a, p in dumps[rule["switch"]][table])
            readback.append({"switch": rule["switch"], "table": table, "key": key, "action": action,
                             "installed_by_plan": rule in run_spec["rules"], "present": present})
        extra = sum(len(v["routing_v6"]) + len(v["srv6_end_dx4_table"]) for v in dumps.values()) - \
            sum(1 for r in readback if r["present"])
        stamps["readback_done_utc"] = utc()
        readback_ms = (time.monotonic() - t_rb) * 1000.0
        before = {n: counters(ports[n], transcript) for n in names}
        n = plan["packets_per_trial"] if run_spec["send_packets"] else 0
        marker = "OVERMSD|{}|{}|t{}|".format(run_spec["case"], run_spec["mode"], trial).encode()
        captures, threads = {}, []
        cap_ifaces = ["{}-p2".format(x) for x in names[:-1]] + ["sink0"]
        timeout = max(2.0, n * plan["send_interval_s"] + 3.0)
        if n:
            for iface in cap_ifaces:
                threads.append(start_capture(iface, marker, timeout, captures))
            time.sleep(0.5)
        sent = []
        for seq in range(n):
            inner = IP(src="192.0.2.1", dst="198.51.100.2", ttl=64) / UDP(sport=45000, dport=8000) / \
                Raw(marker + "seq={:06d}".format(seq).encode())
            pkt = srv6_packet(run_spec.get("packet_sid_list_final_to_first") or run_spec["sid_stack_final_to_first"],
                              inner, run_spec.get("packet_segments_left"))
            pkt[Ether].dst = mac(path[0], 1)
            sent.append(pkt)
        stamps["send_start_utc"] = utc()
        if n:
            sendp(sent, iface="client0", inter=plan["send_interval_s"], verbose=False)
        stamps["send_end_utc"] = utc()
        for t in threads:
            t.join(timeout + 2)
        stamps["capture_end_utc"] = utc()
        time.sleep(0.3)
        after = {x: counters(ports[x], transcript) for x in names}
        delta = {x: {c: after[x][c] - before[x][c] for c in COUNTERS} for x in names}
        seen = {iface: len(captures.get(iface, [])) for iface in cap_ifaces}
        sink_payloads = [bytes(p) for p in captures.get("sink0", [])]
        sink_ipv4 = sum(1 for p in captures.get("sink0", []) if p.haslayer(IP) and not p.haslayer(IPv6))
        wrpcap(str(trial_dir / "sent_client0.pcap"), sent) if sent else None
        for iface, pkts in captures.items():
            if pkts:
                wrpcap(str(trial_dir / "cap_{}.pcap".format(iface)), pkts)
        result = {
            "case": run_spec["case"], "mode": run_spec["mode"], "trial": trial,
            "admission_decision": run_spec["admission"]["decision"],
            "admission_error": run_spec["admission"].get("error"),
            "switch_path": names, "switch_msd": run_spec["switch_msd"],
            "sid_depth": len(run_spec.get("packet_sid_list_final_to_first") or run_spec["sid_stack_final_to_first"]),
            "admitted_path_depth": len(run_spec["sid_stack_final_to_first"]),
            "sid_stack_final_to_first": run_spec["sid_stack_final_to_first"],
            "rules_installed": len(run_spec["rules"]),
            "rules_readback_present": sum(1 for r in readback if r["present"] and r["installed_by_plan"]),
            "rejected_rules_absent": all(not r["present"] for r in readback if not r["installed_by_plan"]),
            "unexpected_entries": extra,
            "readback": readback,
            "install_ms": round(install_ms, 3), "readback_ms": round(readback_ms, 3),
            "packets_sent": n, "packets_received_sink": seen["sink0"], "sink_inner_ipv4_frames": sink_ipv4,
            "loss": n - seen["sink0"],
            "per_hop_egress_captured": seen,
            "counters_before": before, "counters_after": after, "counter_delta": delta,
            "msd_drops_total_delta": sum(d["msd_violation_counter"] for d in delta.values()),
            "unique_sink_seqs": len(set(re.findall(rb"seq=\d{6}", b"".join(sink_payloads)))),
            "stamps": stamps,
        }
        (trial_dir / "result.json").write_text(json.dumps(result, indent=2))
        (trial_dir / "cli_transcript.json").write_text(json.dumps(transcript, indent=2))
        return result
    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        for log in logs:
            log.close()
        for name in created:
            run(["ip", "link", "del", name], check=False)


def main():
    plan = json.loads(PLAN.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    meta = {"started_utc": utc(), "uname": run(["uname", "-a"]).strip(),
            "simple_switch_version": run(["simple_switch", "--version"], check=False).strip()}
    for spec in plan["runs"]:
        for trial in range(1, plan["trials"] + 1):
            d = OUT / "trials" / "{}__{}__t{}".format(spec["case"], spec["mode"], trial)
            d.mkdir(parents=True, exist_ok=False)
            r = one_trial(spec, trial, plan, d)
            results.append(r)
            print(json.dumps({k: r[k] for k in ("case", "mode", "trial", "admission_decision", "rules_installed",
                                                "packets_sent", "packets_received_sink", "msd_drops_total_delta")}))
    meta["finished_utc"] = utc()
    (OUT / "results.json").write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    cols = ["case", "mode", "trial", "admission_decision", "admission_error", "sid_depth", "rules_installed",
            "rules_readback_present", "rejected_rules_absent", "unexpected_entries", "packets_sent",
            "packets_received_sink", "loss", "msd_drops_total_delta", "install_ms", "readback_ms"]
    with (OUT / "trials.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols + ["switch_path", "drop_switch_msd_delta", "per_hop_egress_captured"])
        for r in results:
            drops = {s: d["msd_violation_counter"] for s, d in r["counter_delta"].items() if d["msd_violation_counter"]}
            w.writerow([r[c] for c in cols] + ["-".join(r["switch_path"]), json.dumps(drops),
                                               json.dumps(r["per_hop_egress_captured"])])


if __name__ == "__main__":
    main()
