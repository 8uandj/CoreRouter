#!/usr/bin/env python3
"""Send a bounded fixed-flow SRv6/P4 chain probe from a Mininet host."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from scapy.all import IP, UDP, Raw, get_if_hwaddr, sendp, wrpcap

if __package__:
    from scripts.hil.chain_packet import PORT, build_srv6_frame
else:
    from chain_packet import PORT, build_srv6_frame


def build_inner_probe(run_id, packet_id):
    return (IP(src="198.18.0.1", dst="198.18.0.2", ttl=64)
            / UDP(sport=45000, dport=PORT)
            / Raw("CRCHAIN|{}|{}".format(run_id, packet_id).encode()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iface", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stack", required=True, help="final-to-first SID list")
    parser.add_argument("--dst-mac", required=True)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.count < 1 or args.count > 100 or args.start_id < 1 or args.start_id + args.count - 1 > 65535:
        parser.error("count is outside the bounded pilot range")
    stack = args.stack.split(",")
    src_mac = get_if_hwaddr(args.iface)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    with args.out.open("w") as log:
        for packet_id in range(args.start_id, args.start_id + args.count):
            inner = bytes(build_inner_probe(args.run_id, packet_id))
            frame = build_srv6_frame(src_mac, args.dst_mac, stack, inner)
            frames.append(frame)
            sendp(frame, iface=args.iface, verbose=False)
            log.write(json.dumps({"request_id": args.run_id, "packet_id": packet_id,
                                  "sent_ns": time.time_ns(),
                                  "inner_sha256": hashlib.sha256(inner).hexdigest()}) + "\n")
            log.flush()
            time.sleep(0.3)
    wrpcap(str(args.out.with_suffix(".pcap")), frames)


if __name__ == "__main__":
    main()
