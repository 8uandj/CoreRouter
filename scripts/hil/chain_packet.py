"""Packet format for bounded SRv6/P4 chain probes."""

import re
import socket
import struct

from scapy.all import Ether, IP, IPv6, Raw, UDP


PORT = 49555


def build_srv6_frame(src_mac, dst_mac, sid_stack, inner_bytes):
    if not sid_stack or len(sid_stack) > 10:
        raise ValueError("invalid SID stack depth")
    if not isinstance(inner_bytes, bytes) or not inner_bytes or inner_bytes[0] >> 4 != 4:
        raise ValueError("inner packet must be IPv4 bytes")
    packed = b"".join(socket.inet_pton(socket.AF_INET6, sid) for sid in sid_stack)
    count = len(sid_stack)
    srh = struct.pack("!BBBBBBH", 4, 2 * count, 4, count - 1,
                      count - 1, 0, 0) + packed
    return (Ether(src=src_mac, dst=dst_mac)
            / IPv6(src="2001:db8:100::1", dst=sid_stack[-1], nh=43, hlim=32)
            / Raw(srh + inner_bytes))


def packet_identity(packet, run_id):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,32}", run_id):
        raise ValueError("invalid run ID")
    if Ether in packet and packet[Ether].type != 0x0800:
        return None
    if IP not in packet or UDP not in packet or Raw not in packet or packet[UDP].dport != PORT:
        return None
    payload = bytes(packet[Raw].load)
    match = re.fullmatch(rb"CRCHAIN\|" + run_id.encode() + rb"\|([0-9]+)", payload)
    return int(match.group(1)) if match else None
