import socket
import struct
import time

SRC_MAC = bytes.fromhex("000000000001")
INGRESS_MAC = bytes.fromhex("7eaeb12ab3f2")
SRC_IPV4 = socket.inet_aton("10.0.0.1")
DST_IPV4 = socket.inet_aton("10.1.189.159")
SRC_IPV6 = socket.inet_pton(socket.AF_INET6, "2001:db8::1")
SID_LIST = [
    socket.inet_pton(socket.AF_INET6, "fc00:9::1"),
    socket.inet_pton(socket.AF_INET6, "fc00:6::1"),
    socket.inet_pton(socket.AF_INET6, "fc00:1::1"),
]


def checksum(data):
    if len(data) % 2:
        data += b"\0"
    words = struct.unpack("!%dH" % (len(data) // 2), data)
    total = sum(words)
    total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff


payload = b"CoreRouter-HIL-246-smoke"
icmp = struct.pack("!BBHHH", 8, 0, 0, 246, 1) + payload
icmp = struct.pack("!BBHHH", 8, 0, checksum(icmp), 246, 1) + payload
inner_len = 20 + len(icmp)
ipv4 = struct.pack("!BBHHHBBH4s4s", 0x45, 0, inner_len, 246, 0, 64, 1, 0, SRC_IPV4, DST_IPV4)
ipv4 = ipv4[:10] + struct.pack("!H", checksum(ipv4)) + ipv4[12:]
srh = struct.pack("!BBBBBBH", 4, 6, 4, 2, 2, 0, 0) + b"".join(SID_LIST)
ipv6_payload = srh + ipv4 + icmp
ipv6 = struct.pack("!IHBB16s16s", 6 << 28, len(ipv6_payload), 43, 64, SRC_IPV6, SID_LIST[2])
frame = INGRESS_MAC + SRC_MAC + struct.pack("!H", 0x86dd) + ipv6 + ipv6_payload

rx = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
rx.bind(("h1-eth0", 0))
rx.settimeout(3.0)
tx = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
tx.bind(("h1-eth0", 0))
sent = tx.send(frame)
print("sent_bytes=%d src_node=h1 sid_stack=%s dst_vnf_ip=10.1.189.159 icmp_id=246" % (
    sent, ",".join(["fc00:1::1", "fc00:6::1", "fc00:9::1"])))
deadline = time.monotonic() + 3.0
while time.monotonic() < deadline:
    try:
        packet = rx.recv(65535)
    except socket.timeout:
        break
    if len(packet) < 14 + 20 + 8 or packet[12:14] != b"\x08\x00":
        continue
    ip = packet[14:]
    ihl = (ip[0] & 0x0f) * 4
    if ip[9] != 1 or ip[12:16] != DST_IPV4 or ip[16:20] != SRC_IPV4:
        continue
    reply = ip[ihl:ihl + 8]
    if len(reply) == 8 and reply[0] == 0 and struct.unpack("!H", reply[4:6])[0] == 246:
        print("echo_reply=received src=10.1.189.159 dst=10.0.0.1")
        break
else:
    print("echo_reply=not_observed")
