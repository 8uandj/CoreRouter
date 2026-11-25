#!/usr/bin/env python3
"""Bounded Mininet-host VNF stage for an experimental SRv6/P4 packet chain.

This is an instrumented forwarding function in a Mininet host namespace, not
a Kubernetes VNF Pod. It preserves the exact inner IPv4 bytes while adding a
fresh SRv6 outer header for the next P4 leg.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

from scapy.all import IP, PcapWriter, get_if_hwaddr, sendp, sniff

if __package__:
    from scripts.hil.chain_packet import build_srv6_frame, packet_identity
else:
    from chain_packet import build_srv6_frame, packet_identity


def process_frame(packet, run_id, stage, next_stack, src_mac, dst_mac, send):
    packet_id = packet_identity(packet, run_id)
    if packet_id is None:
        return None
    inner = bytes(packet[IP])
    event = {"request_id": run_id, "packet_id": packet_id, "stage": stage,
             "seq": time.time_ns(), "inner_sha256": hashlib.sha256(inner).hexdigest()}
    if next_stack:
        send(build_srv6_frame(src_mac, dst_mac, next_stack, inner))
    return event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iface", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--next-stack", default="", help="final-to-first SID list for next leg")
    parser.add_argument("--dst-mac", default="", help="next ingress switch host-facing MAC")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.count < 1 or args.count > 100 or args.timeout < 1 or args.timeout > 120:
        parser.error("count or timeout is outside the bounded pilot range")
    stack = args.next_stack.split(",") if args.next_stack else []
    if bool(stack) != bool(args.dst_mac):
        parser.error("next stack and destination MAC must be specified together")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pcap = PcapWriter(str(args.out.with_suffix(".pcap")), append=False, sync=True, linktype=1)
    out_pcap = (PcapWriter(str(args.out.with_name(args.out.stem + "_srv6.pcap")),
                           append=False, sync=True, linktype=1) if stack else None)
    src_mac = get_if_hwaddr(args.iface)
    seen = set()
    try:
        with args.out.open("w") as log:
            def forward(frame):
                out_pcap.write(frame)
                sendp(frame, iface=args.iface, verbose=False)

            def on_packet(packet):
                event = process_frame(packet, args.run_id, args.stage, stack,
                                      src_mac, args.dst_mac, forward if stack else None)
                if event is not None:
                    pcap.write(packet)
                    log.write(json.dumps(event) + "\n")
                    log.flush()
                    seen.add(event["packet_id"])

            args.out.with_suffix(".ready").write_text("ready\n")
            sniff(iface=args.iface, timeout=args.timeout, count=args.count,
                  lfilter=lambda packet: packet_identity(packet, args.run_id) is not None,
                  prn=on_packet, store=False)
    finally:
        pcap.close()
        if out_pcap is not None:
            out_pcap.close()
        args.out.with_suffix(".ready").unlink(missing_ok=True)
    if len(seen) != args.count:
        raise SystemExit("received {} distinct packets, expected {}".format(len(seen), args.count))


if __name__ == "__main__":
    main()
