#!/usr/bin/env python3
"""Stage-by-stage evidence matrix for every recorded forwarding probe (Nov 17).

Reads only the preserved originals under
02_forwarding_overmsd/original/rebuild_20261117T123405Z (and the 95 MB loop pcap
by reference at its original path). Packet counts come from `tcpdump -nn -r`
(no privileges needed to read a file). Each row states, per stage, what file
supports it, or "absent".

Usage: python3 scripts/analyze_forwarding_history.py <export_root>
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ORIG_BIG = Path("/home/CoreRouter/results/hil/rebuild_20261117T123405Z/phase12_s6_out.pcap")


def pcap_count(p: Path) -> int:
    out = subprocess.run(["tcpdump", "-nn", "-r", str(p)], capture_output=True, text=True, timeout=300)
    return len([l for l in out.stdout.splitlines() if l.strip()])


def counter_vals(p: Path) -> dict:
    txt = p.read_text(errors="replace")
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"(\w+_counter)\[0\]=\s*BmCounterValue\(packets=(\d+)", txt)}


def main() -> int:
    export = Path(sys.argv[1]).resolve()
    d = export / "02_forwarding_overmsd/original/rebuild_20261117T123405Z"
    rows = []

    # Phase 12: s1->s6->s9 with OVS still active (failed; loop)
    c12 = {s: (counter_vals(d / f"phase12_{s}_counters_before.txt"), counter_vals(d / f"phase12_{s}_counters_after.txt"),
               counter_vals(d / f"phase12_{s}_counters_final.txt"))
           for s in ("s1", "s6", "s9")}
    rows.append({
        "probe": "phase12 (2026-11-17 ~16:13-16:22 UTC)", "request_correlated": "no (manual diagnostic, no /orchestrate request)",
        "function_order": "single endpoint (one Pod 10.1.189.159, alpine sleep placeholder); no ordered VNF chain",
        "sid_list": "fc00:9::1, fc00:6::1, fc00:1::1 (segment list final->first; depth 3) - phase12_send_srv6_icmp.py",
        "msd_profile_on_path": "s1=10, s6=8, s9=10 (live profiles)",
        "rule_install": "phase11_path_rules.json via controller /bootstrap: HTTP 500 (s9 readback comparator bug) - phase11_gate_failure.txt",
        "rule_readback": "s1, s6 passed; s9 rejected by comparator (later fixed)",
        "packets_sent": "1 (phase12_result.txt)",
        "per_point_evidence": "counters before->after->final: s1 advance {}->{}->{}, s6 advance {}->{}->{}, s9 terminal {}->{}->{}; phase12_forward.pcap {} pkts; phase12_s6_out.pcap {} pkts (loop)".format(
            c12["s1"][0].get("srv6_advance_counter"), c12["s1"][1].get("srv6_advance_counter"), c12["s1"][2].get("srv6_advance_counter"),
            c12["s6"][0].get("srv6_advance_counter"), c12["s6"][1].get("srv6_advance_counter"), c12["s6"][2].get("srv6_advance_counter"),
            c12["s9"][0].get("srv6_terminal_counter"), c12["s9"][1].get("srv6_terminal_counter"), c12["s9"][2].get("srv6_terminal_counter"),
            pcap_count(d / "phase12_forward.pcap"), pcap_count(ORIG_BIG) if ORIG_BIG.exists() else "missing"),
        "packet_received_at_target": "no (phase12_result.txt: no echo reply; duplication/looping suspected)",
        "outcome": "FAILED - looping with OVS bridges active; rules rolled back by handle",
    })
    # Phase 13/14: after OVS detachment
    c13 = {s: (counter_vals(d / f"phase13_{s}_counters_before.txt"), counter_vals(d / f"phase13_{s}_counters_after.txt"),
               counter_vals(d / f"phase14_{s}_counters.txt")) for s in ("s1", "s6", "s9")}
    rb = (d / "phase13_rule_readback.txt").read_text().strip().replace("\n", "; ")
    rows.append({
        "probe": "phase13-14 (2026-11-17 16:29-16:42 UTC)", "request_correlated": "no (manual diagnostic)",
        "function_order": "single endpoint (same placeholder Pod); no ordered VNF chain",
        "sid_list": "fc00:9::1, fc00:6::1, fc00:1::1 (depth 3) - phase13_send_srv6_icmp.py",
        "msd_profile_on_path": "s1=10, s6=8, s9=10",
        "rule_install": "phase13_path_rules.json via /bootstrap: HTTP 200 (phase13_path_rules_response.json)",
        "rule_readback": rb,
        "packets_sent": "1 first smoke, then further single probes (cumulative counters)",
        "per_point_evidence": "s1 advance {}->{}->{} (phase14), s6 advance {}->{}->{}, s9 terminal {}->{}->{}; msd_violation 0; h9 captures phase13_h9_ingress {} / phase14_h9_link {} / phase14_s9_port_return {} pkts".format(
            c13["s1"][0].get("srv6_advance_counter"), c13["s1"][1].get("srv6_advance_counter"), c13["s1"][2].get("srv6_advance_counter"),
            c13["s6"][0].get("srv6_advance_counter"), c13["s6"][1].get("srv6_advance_counter"), c13["s6"][2].get("srv6_advance_counter"),
            c13["s9"][0].get("srv6_terminal_counter"), c13["s9"][1].get("srv6_terminal_counter"), c13["s9"][2].get("srv6_terminal_counter"),
            pcap_count(d / "phase13_h9_ingress.pcap"), pcap_count(d / "phase14_h9_link.pcap"), pcap_count(d / "phase14_s9_port_return.pcap")),
        "packet_received_at_target": "no (no echo reply; h9 captures empty)",
        "outcome": "PARTIAL - switch counters show transit/terminal action; no frame observed beyond s9 in these phases",
    })
    rows.append({
        "probe": "phase16-19 (2026-11-17 17:06-17:09 UTC), ICMP id 246 seq 15", "request_correlated": "no (manual diagnostic)",
        "function_order": "single endpoint; no ordered VNF chain",
        "sid_list": "same installed path s1->s6->s9 (depth 3); no per-probe counter snapshot",
        "msd_profile_on_path": "s1=10, s6=8, s9=10",
        "rule_install": "unchanged from phase13 (temporary diagnostic rules)",
        "rule_readback": "not repeated for this probe",
        "packets_sent": "1 per capture point attempt (phase15_send_only.py)",
        "per_point_evidence": "s9-eth1 {} | h9-eth0 {} | h9 veth egress {} | host peer veth {} | vxlan.calico {} pkts (TTL 64/63/62); phase16_s9_seq15 {} pkts".format(
            pcap_count(d / "phase17_s9_seq15.pcap"), pcap_count(d / "phase17_h9_seq15.pcap"), pcap_count(d / "phase18_h9_egress.pcap"),
            pcap_count(d / "phase19_host_peer.pcap"), pcap_count(d / "phase19_vxlan.pcap"), pcap_count(d / "phase16_s9_seq15.pcap")),
        "packet_received_at_target": "not observed at the Pod (no capture in Pod netns; Pod has no listener; no reply)",
        "outcome": "ENDPOINT PROBE ONLY - reaches Calico overlay toward one Pod; not chain evidence",
    })
    rep = json.loads((d / "report.json").read_text())
    rows.append({
        "probe": "isolated-bmv2-srv6-end-dx4-v1 (2026-11-17 14:48 UTC)", "request_correlated": "no (unit-style isolated test)",
        "function_order": "none (2 isolated BMv2, sink interface)",
        "sid_list": "in-limit: {} (depth 2); overflow: 5 x 2001:db8:ffff::N (depth 5)".format(", ".join(rep["wire_sids"])),
        "msd_profile_on_path": "compiled MSD {} on both switches".format(rep["over_msd_drop"]["compiled_msd"]),
        "rule_install": "simple_switch_CLI table_add (no controller, no admission)",
        "rule_readback": "table_readback.txt (3 entries present)",
        "packets_sent": "1 in-limit + 1 overflow",
        "per_point_evidence": "in-limit: advance +{}, terminal +{}, sink {} pkt; overflow: msd_violation +{}, sink {} pkt".format(
            rep["boundary_forward"]["advance_counter_delta"], rep["boundary_forward"]["terminal_counter_delta"],
            rep["boundary_forward"]["captured_packets"], rep["over_msd_drop"]["violation_counter_delta"],
            rep["over_msd_drop"]["captured_packets"]),
        "packet_received_at_target": "in-limit yes (inner IPv4 at sink); overflow no",
        "outcome": "PASS for parser drop on 1 packet; no admission comparison (bypass only), n=1",
    })
    out = export / "generated" / "forwarding_history_evidence_matrix.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(out)
    for r in rows:
        print("-", r["probe"], "|", r["outcome"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
