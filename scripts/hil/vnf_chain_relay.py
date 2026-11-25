#!/usr/bin/env python3
"""Pod side of the measured handoff: log exact inner bytes and echo them back."""

import http.server
import json
import os
import re
import socket
import threading
import time

from chain_handoff import decode

RUN_ID = os.environ["CHAIN_RUN_ID"]
STAGE = int(os.environ["CHAIN_STAGE"])
LISTEN_PORT = int(os.environ.get("CHAIN_RELAY_PORT", "49557"))
LOG_PATH = os.environ.get("CHAIN_LOG", "/var/run/chain/receipts.jsonl")
if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", RUN_ID) or not 1 <= STAGE <= 255:
    raise SystemExit("invalid run ID or stage")


class Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/healthz", "/readyz"):
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok\n")

    def log_message(self, *_args):
        pass


def marker_matches(inner, packet_id):
    import struct
    if len(inner) < 28 or inner[9] != 17:
        return False
    ihl = (inner[0] & 15) * 4
    if ihl < 20 or len(inner) < ihl + 8:
        return False
    udp = inner[ihl:]
    if struct.unpack_from("!H", udp, 2)[0] != 49555:
        return False
    payload = udp[8:]
    expected = "CRCHAIN|{}|{}".format(RUN_ID, packet_id).encode("ascii")
    return payload == expected


def main():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    threading.Thread(target=lambda: http.server.ThreadingHTTPServer(
        ("0.0.0.0", 8080), Health).serve_forever(), daemon=True).start()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", LISTEN_PORT))
    with open(LOG_PATH, "a", buffering=1) as log:
        while True:
            data, peer = sock.recvfrom(65535)
            try:
                run_id, packet_id, stage, inner, digest = decode(data, RUN_ID, STAGE)
            except ValueError:
                continue
            if not marker_matches(inner, packet_id):
                continue
            event = {"event": "vnf_pod_rx", "run_id": run_id, "stage": stage,
                     "packet_id": packet_id, "inner_sha256": digest,
                     "inner_len": len(inner), "time_ns": time.time_ns(),
                     "handoff_peer": peer[0]}
            line = json.dumps(event, sort_keys=True)
            log.write(line + "\n")
            print(line, flush=True)
            # Echo the identical envelope, including the full original IP bytes.
            sock.sendto(data, peer)


if __name__ == "__main__":
    main()
