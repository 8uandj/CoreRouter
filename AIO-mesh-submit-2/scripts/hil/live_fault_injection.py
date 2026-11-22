#!/usr/bin/env python3
"""Live data-plane SID-depth fault injection on an installed, admitted path.

Runs INSIDE Mininet host hS's network namespace (launched via mnexec.sh with the
host venv python). Sends N ICMP echo packets to a Pod through an SRH whose depth
is chosen per case, with Segments Left = (admitted depth - 1) so the packet follows
the installed rules; extra already-traversed SIDs only enlarge the SRH (parser
depth). Prints one JSON line per case with packets sent and echo replies seen.

Usage (inside netns): live_fault_injection.py --iface h6-eth0 --ret-iface veth-h6-mn
   --dst-mac MAC --stack fc00:7::1,fc00:6::1 --pod 10.1.189.168 --src 10.0.0.6
   --depths 2,7,9 -n 50
"""
import argparse
import json
import socket
import struct
import threading
import time

from scapy.all import ICMP, IP, IPv6, Ether, Raw, sendp, sniff


def srh_packet(src_mac, dst_mac, stack, depth, inner):
    extra = ["2001:db8:ffff::%d" % (i + 1) for i in range(max(0, depth - len(stack)))]
    segs = list(stack) + extra  # Segment List[0] = final SID
    sl = len(stack) - 1
    n = len(segs)
    srh = struct.pack("!BBBBBBH", 4, 2 * n, 4, sl, n - 1, 0, 0) + b"".join(
        socket.inet_pton(socket.AF_INET6, s) for s in segs)
    return Ether(src=src_mac, dst=dst_mac) / IPv6(src="2001:db8:100::1", dst=segs[sl], nh=43, hlim=32) / Raw(srh + bytes(inner))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True)
    ap.add_argument("--ret-iface", required=True)
    ap.add_argument("--src-mac", default=None)
    ap.add_argument("--dst-mac", required=True)
    ap.add_argument("--stack", required=True)
    ap.add_argument("--pod", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--depths", default="2,7,9")
    ap.add_argument("-n", type=int, default=50)
    ap.add_argument("--id", type=int, default=4242)
    a = ap.parse_args()
    stack = a.stack.split(",")
    src_mac = a.src_mac or open("/sys/class/net/%s/address" % a.iface).read().strip()
    for depth in [int(x) for x in a.depths.split(",")]:
        icmp_id = a.id + depth
        replies = []
        t = threading.Thread(target=lambda: replies.extend(sniff(
            iface=a.ret_iface, timeout=a.n * 0.02 + 4,
            lfilter=lambda p: p.haslayer(ICMP) and p[ICMP].type == 0 and p[ICMP].id == icmp_id)), daemon=True)
        t.start()
        time.sleep(0.5)
        pkts = [srh_packet(src_mac, a.dst_mac, stack, depth,
                           IP(src=a.src, dst=a.pod, ttl=64) / ICMP(id=icmp_id, seq=i) / Raw(b"HIL-DEPTH-%d-%04d" % (depth, i)))
                for i in range(a.n)]
        start = time.time()
        sendp(pkts, iface=a.iface, inter=0.01, verbose=False)
        t.join()
        print(json.dumps({"srh_depth": depth, "segments_left": len(stack) - 1, "sent": a.n,
                          "echo_replies": len({p[ICMP].seq for p in replies}), "send_start_epoch": start}), flush=True)


if __name__ == "__main__":
    main()
