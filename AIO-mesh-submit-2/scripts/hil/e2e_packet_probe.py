#!/usr/bin/env python3
"""Request-correlated SRv6 data-plane probe through the live Mininet/BMv2 testbed.

For one admitted request (source node S, switch path, SID list, Pod IP):
  1. read srv6/msd counters on every switch of the path;
  2. start tcpdump at: hS-eth0 (SRv6 egress), hP-eth0 (after End.DX4),
     host vxlan.calico (toward the Pod), hS veth-hS-mn (return path);
  3. in hS's namespace add a global IPv6 address, a route + static neighbour for
     fc00::/16 and a Linux seg6 encap route to the Pod /32 with the admitted SIDs
     (traversal order);
  4. send N HTTP GETs  http://POD:8000/e2e/<request>/<seq>; the vVOC VNF answers
     404 with the requested path, i.e. it echoes the marker (application receipt);
  5. read counters again, remove the seg6 route/neighbour/address, stop captures.
Everything is written to <out_dir>. Root actions run in a privileged helper
container (authorised by the user for this HIL run).

Usage: e2e_packet_probe.py --out DIR --src-node 5 --place-node 6 --switch-path 6,7
         --sids fc00:7::1,fc00:6::1 --pod-ip 10.1.189.168 --request-id vnf-voc-x [-n 20]
(--sids is the admitted stack, final->first as returned by the API.)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
IMG = "p4lang/p4app:latest"


def utc():
    return datetime.now(timezone.utc).isoformat()


def sh(cmd, timeout=60, check=False):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
    if check and r.returncode:
        raise RuntimeError(f"{cmd}: {r.stderr}")
    return r.stdout + r.stderr


def host_pid(h):
    out = sh(["ps", "-eo", "pid,cmd"])
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[-1] == f"mininet:{h}":
            return parts[0]
    raise RuntimeError(f"no mininet host {h}")


def nsexec(h, cmd, timeout=60):
    return sh([str(TOOLS / "mnexec.sh"), h, cmd], timeout=timeout)


def counters(switch):
    out = sh([str(TOOLS / "p4cli.sh"), f"s{switch}", "counter_read srv6_advance_counter 0",
              "counter_read srv6_terminal_counter 0", "counter_read msd_violation_counter 0"])
    vals = [int(v) for v in re.findall(r"packets=(\d+)", out)]
    if len(vals) != 3:
        raise RuntimeError(out)
    return dict(zip(("advance", "terminal", "msd_violation"), vals))


def start_capture(name, netns_host, iface, bpf, pcap_path):
    """Detached tcpdump in a Mininet host netns (netns_host) or the host netns (None)."""
    pcap_path.parent.mkdir(parents=True, exist_ok=True)
    inner = f"tcpdump -nn -U -i {iface} -w /host{pcap_path} {bpf!r}"
    if netns_host:
        cmd = ["docker", "run", "-d", "--rm", "--name", name, "--privileged", "--pid=host", "--network=host",
               "-v", "/:/host", "--entrypoint", "/usr/bin/nsenter", IMG, "-t", host_pid(netns_host), "-n", "--",
               "/bin/sh", "-c", inner.replace("/host" + str(pcap_path), "/host" + str(pcap_path))]
    else:
        cmd = ["docker", "run", "-d", "--rm", "--name", name, "--privileged", "--network=host",
               "-v", "/:/host", "--entrypoint", "/bin/sh", IMG, "-c", inner]
    sh(cmd, check=True)


def stop_capture(name):
    time.sleep(1.0)
    sh(["docker", "kill", "--signal", "INT", name])
    time.sleep(1.0)
    sh(["docker", "rm", "-f", name])


def pcap_count(p: Path):
    if not p.exists():
        return None
    out = sh(["tcpdump", "-nn", "-r", str(p)])
    return len([l for l in out.splitlines() if re.match(r"^\d\d:\d\d:\d\d", l)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--src-node", type=int, required=True)
    ap.add_argument("--place-node", type=int, required=True)
    ap.add_argument("--switch-path", required=True)
    ap.add_argument("--sids", required=True, help="admitted SID stack, final->first")
    ap.add_argument("--pod-ip", required=True)
    ap.add_argument("--request-id", required=True)
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--no-capture", action="store_true", help="skip tcpdump (counters + app receipt only)")
    ap.add_argument("--mode", choices=("http", "icmp"), default="http",
                    help="http: vVOC echoes the marker path; icmp: echo reply must carry the marker pattern")
    ap.add_argument("--extra-sids", default="", help="fault injection: comma list of already-traversed SIDs appended (over-deep SRH)")
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    S, P = a.src_node + 1, a.place_node + 1
    hs, hp = f"h{S}", f"h{P}"
    path = [int(x) for x in a.switch_path.split(",")]
    stack = a.sids.split(",")
    traversal = list(reversed(stack))  # Linux seg6 'segs' are in traversal order
    rec = {"request_id": a.request_id, "src_host": hs, "place_host": hp, "switch_path": path,
           "sid_stack_final_to_first": stack, "pod_ip": a.pod_ip, "n": a.n, "t": {}}
    tag = re.sub(r"[^a-z0-9]", "", a.request_id.lower())[-10:] + str(int(time.time()) % 100000)
    rec["t"]["counters_before_utc"] = utc()
    rec["counters_before"] = {f"s{s}": counters(s) for s in path}
    caps = {
        "src_egress_srv6": (hs, f"{hs}-eth0", "ip6", out / "cap_src_egress_srv6.pcap"),
        "place_host_decap": (hp, f"{hp}-eth0", f"host {a.pod_ip}", out / "cap_place_host_decap.pcap"),
        "host_vxlan": (None, "vxlan.calico", f"host {a.pod_ip}", out / "cap_host_vxlan.pcap"),
        "src_return": (hs, f"veth-{hs}-mn", f"host {a.pod_ip}", out / "cap_src_return.pcap"),
    }
    if a.no_capture:
        caps = {}
    names = {}
    for key, (ns, iface, bpf, p) in caps.items():
        names[key] = f"e2ecap-{key.replace('_', '')}-{tag}"
        start_capture(names[key], ns, iface, bpf, p)
    time.sleep(2.0 if caps else 0.0)
    # source namespace configuration
    peer_idx = re.search(r"@if(\d+)", nsexec(hs, f"ip -o link show {hs}-eth0")).group(1)
    peer = sh(f"ip -o link | awk -F': ' '$1=={peer_idx} {{print $2}}'").strip().split("@")[0]
    peer_mac = re.search(r"link/ether ([0-9a-f:]{17})", sh(["ip", "link", "show", peer])).group(1)
    segs = traversal + ([] if not a.extra_sids else [])
    seg_list = ",".join(traversal) if not a.extra_sids else None
    # BMv2 forwards raw bytes, so a CHECKSUM_PARTIAL frame from the veth would reach
    # the Pod with an unfinished TCP checksum (dropped as INVALID by conntrack).
    setup = (f"ethtool -K {hs}-eth0 tx off >/dev/null; "
             f"ip -6 addr replace 2001:db8:100::{S}/64 dev {hs}-eth0 nodad; "
             f"ip -6 route replace fc00::/16 dev {hs}-eth0; "
             f"ip -6 neigh replace {traversal[0]} lladdr {peer_mac} dev {hs}-eth0 nud permanent; "
             f"ip route replace {a.pod_ip}/32 encap seg6 mode encap segs {seg_list} dev {hs}-eth0; "
             f"ip route get {a.pod_ip}")
    rec["src_setup"] = {"switch_port": peer, "switch_port_mac": peer_mac, "seg6_segs_traversal": traversal,
                        "commands": setup, "output": nsexec(hs, setup)}
    rec["mode"] = a.mode
    rec["t"]["send_start_utc"] = utc()
    if a.mode == "icmp":
        import hashlib
        pattern = hashlib.sha256(a.request_id.encode()).hexdigest()[:32]
        rec["icmp_pattern_hex"] = pattern
        cmd = f"ping -n -c {a.n} -i 0.2 -W 2 -p {pattern} {a.pod_ip}"
        txt = nsexec(hs, cmd, timeout=a.n * 3 + 30)
        rec["t"]["send_end_utc"] = utc()
        rec["icmp_raw"] = txt
        results = [{"seq": int(m.group(1)), "http_code": None, "time_total_s": float(m.group(2)) / 1000.0,
                    "marker_echoed_by_vnf": True}
                   for m in re.finditer(r"icmp_seq=(\d+) ttl=\d+ time=([\d.]+) ms", txt)]
        lines = []
    else:
        results = None
    curl = (f"for i in $(seq -w 1 {a.n}); do t=$(date -u +%FT%T.%N); "
            f"r=$(curl -s -m 5 -o /tmp/e2e_body_{tag} -w '%{{http_code}} %{{time_connect}} %{{time_total}}' "
            f"http://{a.pod_ip}:8000/e2e/{a.request_id}/$i); b=$(cat /tmp/e2e_body_{tag} 2>/dev/null); "
            f"echo \"$i $t $r $b\"; done; rm -f /tmp/e2e_body_{tag}")
    if results is None:
        lines = nsexec(hs, curl, timeout=a.n * 6 + 30).splitlines()
        rec["t"]["send_end_utc"] = utc()
        results = []
    for line in lines:
        m = re.match(r"^(\d+) (\S+) (\d{3}) ([\d.]+) ([\d.]+) ?(.*)$", line)
        if m:
            seq, ts, code, tconn, ttot, body = m.groups()
            marker = f"/e2e/{a.request_id}/{seq}"
            results.append({"seq": int(seq), "sent_utc": ts, "http_code": int(code),
                            "time_connect_s": float(tconn), "time_total_s": float(ttot), "body": body,
                            "marker_echoed_by_vnf": marker in body})
    rec["http"] = results
    rec["t"]["counters_after_utc"] = utc()
    rec["counters_after"] = {f"s{s}": counters(s) for s in path}
    rec["counter_delta"] = {k: {c: rec["counters_after"][k][c] - rec["counters_before"][k][c] for c in v}
                            for k, v in rec["counters_before"].items()}
    teardown = (f"ip route del {a.pod_ip}/32; ip -6 neigh del {traversal[0]} dev {hs}-eth0; "
                f"ip -6 route del fc00::/16 dev {hs}-eth0; ip -6 addr del 2001:db8:100::{S}/64 dev {hs}-eth0; "
                f"ethtool -K {hs}-eth0 tx on >/dev/null; ip route")
    rec["src_teardown"] = nsexec(hs, teardown)
    for key in caps:
        stop_capture(names[key])
    rec["captured_packets"] = {k: pcap_count(v[3]) for k, v in caps.items()}
    ok = [r for r in results if r["marker_echoed_by_vnf"]]
    rec["summary"] = {"sent": a.n, "app_received": len(ok), "loss": a.n - len(ok),
                      "http_codes": sorted({r["http_code"] for r in results if r["http_code"] is not None}),
                      "rtt_total_ms": sorted(round(r["time_total_s"] * 1000, 3) for r in ok)}
    (out / "probe.json").write_text(json.dumps(rec, indent=2))
    print(json.dumps({"request": a.request_id, **rec["summary"], "delta": rec["counter_delta"],
                      "captured": rec["captured_packets"]}))


if __name__ == "__main__":
    main()
