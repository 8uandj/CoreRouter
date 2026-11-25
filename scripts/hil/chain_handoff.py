"""Checksummed, bounded envelope used only across the Pod/Mininet handoff."""

import hashlib
import re
import struct

MAGIC = b"CRPOD001"
HEADER = struct.Struct("!8sBHBH32s")
PORT = 49555


def encode(run_id, packet_id, stage, inner):
    raw_id = run_id.encode("ascii")
    if not re.fullmatch(rb"[A-Za-z0-9_-]{1,32}", raw_id):
        raise ValueError("invalid run ID")
    if not 1 <= packet_id <= 65535 or not 1 <= stage <= 255:
        raise ValueError("invalid packet or stage number")
    if not inner or inner[0] >> 4 != 4 or len(inner) < 20:
        raise ValueError("handoff must contain an IPv4 packet")
    total = struct.unpack_from("!H", inner, 2)[0]
    if total != len(inner) or len(inner) + HEADER.size + len(raw_id) > 65507:
        raise ValueError("invalid or oversized IPv4 packet")
    return HEADER.pack(MAGIC, len(raw_id), packet_id, stage, len(inner),
                       hashlib.sha256(inner).digest()) + raw_id + inner


def decode(data, expected_run=None, expected_stage=None):
    if len(data) < HEADER.size:
        raise ValueError("truncated envelope")
    magic, run_len, packet_id, stage, ip_len, digest = HEADER.unpack_from(data)
    if magic != MAGIC or not 1 <= run_len <= 32:
        raise ValueError("invalid envelope header")
    try:
        run_id = data[HEADER.size:HEADER.size + run_len].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid run ID") from exc
    inner = data[HEADER.size + run_len:]
    if len(inner) != ip_len or hashlib.sha256(inner).digest() != digest:
        raise ValueError("envelope checksum or size mismatch")
    if expected_run is not None and run_id != expected_run:
        raise ValueError("unexpected run ID")
    if expected_stage is not None and stage != expected_stage:
        raise ValueError("unexpected stage")
    if not inner or inner[0] >> 4 != 4 or struct.unpack_from("!H", inner, 2)[0] != len(inner):
        raise ValueError("invalid inner IPv4 packet")
    return run_id, packet_id, stage, inner, hashlib.sha256(inner).hexdigest()
