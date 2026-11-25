#!/usr/bin/env python3
"""Mininet-host gateway that waits for a real VNF Pod receipt before the next P4 leg."""

import argparse
import hashlib
import json
import re
import socket
import time
from pathlib import Path

from scapy.all import Ether, IP, PcapWriter, get_if_hwaddr, sendp, sniff

from chain_handoff import decode, encode
from chain_packet import build_srv6_frame, packet_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iface", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True, type=int)
    parser.add_argument("--pod-ip", required=True)
    parser.add_argument("--pod-port", type=int, default=49557)
    parser.add_argument("--next-stack", required=True, help="final-to-first SID list")
    parser.add_argument("--dst-mac", required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", args.run_id):
        parser.error("invalid run ID")
    if not 1 <= args.stage <= 2 or not 1 <= args.count <= 20:
        parser.error("pilot supports stages 1..2 and 1..20 packets")
    if args.start_id < 1 or args.start_id + args.count - 1 > 65535:
        parser.error("invalid packet ID interval")
    if not 1 <= args.timeout <= 120:
        parser.error("timeout outside bounded range")
    stack = args.next_stack.split(",")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    src_mac = get_if_hwaddr(args.iface)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)
    rx_pcap = PcapWriter(str(args.out.with_suffix(".pcap")), append=False, sync=True, linktype=1)
    tx_pcap = PcapWriter(str(args.out.with_name(args.out.stem + "_srv6.pcap")),
                         append=False, sync=True, linktype=1)
    seen = set()
    try:
        with args.out.open("w", buffering=1) as log:
            args.out.with_suffix(".ready").write_text("ready\n")

            def handle(packet):
                packet_id = packet_identity(packet, args.run_id)
                if packet_id is None or not args.start_id <= packet_id < args.start_id + args.count:
                    return
                if packet_id in seen or Ether not in packet or packet[Ether].type != 0x0800:
                    raise RuntimeError("duplicate ID or non-inner frame received")
                inner = bytes(packet[IP])
                digest = hashlib.sha256(inner).hexdigest()
                handoff = encode(args.run_id, packet_id, args.stage, inner)
                sock.sendto(handoff, (args.pod_ip, args.pod_port))
                reply, _peer = sock.recvfrom(65535)
                run, returned_id, stage, returned_inner, returned_hash = decode(
                    reply, args.run_id, args.stage)
                if (run != args.run_id or returned_id != packet_id or stage != args.stage
                        or returned_inner != inner or returned_hash != digest):
                    raise RuntimeError("VNF Pod reply changed packet identity or bytes")
                rx_pcap.write(packet)
                event = {"event": "pod_roundtrip_verified", "run_id": run,
                         "stage": stage, "packet_id": packet_id,
                         "inner_sha256": digest, "inner_len": len(inner),
                         "time_ns": time.time_ns(), "pod_ip": args.pod_ip}
                log.write(json.dumps(event, sort_keys=True) + "\n")
                frame = build_srv6_frame(src_mac, args.dst_mac, stack, inner)
                tx_pcap.write(frame)
                sendp(frame, iface=args.iface, verbose=False)
                seen.add(packet_id)

            sniff(iface=args.iface, timeout=args.timeout, count=args.count,
                  lfilter=lambda p: packet_identity(p, args.run_id) is not None,
                  prn=handle, store=False)
    finally:
        sock.close()
        rx_pcap.close()
        tx_pcap.close()
        args.out.with_suffix(".ready").unlink(missing_ok=True)
    expected = set(range(args.start_id, args.start_id + args.count))
    if seen != expected:
        raise SystemExit("received {} unique Pod roundtrips; expected {}".format(len(seen), args.count))


if __name__ == "__main__":
    main()
