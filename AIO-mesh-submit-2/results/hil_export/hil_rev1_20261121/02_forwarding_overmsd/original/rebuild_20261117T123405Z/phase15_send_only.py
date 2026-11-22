import socket, struct
srcmac = bytes.fromhex('000000000001')
dstmac = bytes.fromhex('7eaeb12ab3f2')
src4 = socket.inet_aton('10.0.0.1')
dst4 = socket.inet_aton('10.1.189.159')
def checksum(data):
    if len(data) % 2: data += b'\0'
    total = sum(struct.unpack('!%dH' % (len(data)//2), data))
    total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff
payload = b'CoreRouter-HIL-246-phase15'
icmp = struct.pack('!BBHHH', 8, 0, 0, 246, 15) + payload
icmp = struct.pack('!BBHHH', 8, 0, checksum(icmp), 246, 15) + payload
iplen = 20 + len(icmp)
ip4 = struct.pack('!BBHHHBBH4s4s', 0x45, 0, iplen, 246, 0, 64, 1, 0, src4, dst4)
ip4 = ip4[:10] + struct.pack('!H', checksum(ip4)) + ip4[12:]
sids = [socket.inet_pton(socket.AF_INET6, x) for x in ('fc00:9::1', 'fc00:6::1', 'fc00:1::1')]
srh = struct.pack('!BBBBBBH', 4, 6, 4, 2, 2, 0, 0) + b''.join(sids)
payload6 = srh + ip4 + icmp
ip6 = struct.pack('!IHBB16s16s', 6 << 28, len(payload6), 43, 64, socket.inet_pton(socket.AF_INET6, '2001:db8::1'), sids[2])
frame = dstmac + srcmac + struct.pack('!H', 0x86dd) + ip6 + payload6
sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
sock.bind(('h1-eth0', 0))
print('sent_bytes=%d icmp_id=246 seq=15' % sock.send(frame))
