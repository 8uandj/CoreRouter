#!/usr/bin/env python3
"""Verify source, Pod receipts, Mininet handoffs, and egress agree per packet."""

import argparse
import hashlib
import json
from pathlib import Path


def read_events(path, allowed=None):
    rows = []
    with Path(path).open() as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if allowed is None or row.get("event") in allowed:
                rows.append(row)
    return rows


def index(events, label, expected=None):
    result = {}
    for row in events:
        packet_id = row.get("packet_id")
        if expected is not None and packet_id not in expected:
            continue
        if packet_id in result:
            raise ValueError("duplicate {} packet ID {}".format(label, packet_id))
        result[packet_id] = row
    return result


def analyze(source, stage1, stage2, gateway1, gateway2, egress, expected):
    src = index(read_events(source), "source")
    required = set(range(expected[0], expected[0] + expected[1]))
    src = {key: value for key, value in src.items() if key in required}
    pod1 = index(read_events(stage1, {"vnf_pod_rx"}), "Pod stage 1", required)
    pod2 = index(read_events(stage2, {"vnf_pod_rx"}), "Pod stage 2", required)
    gw1 = index(read_events(gateway1, {"pod_roundtrip_verified"}), "gateway stage 1", required)
    gw2 = index(read_events(gateway2, {"pod_roundtrip_verified"}), "gateway stage 2", required)
    out = index(read_events(egress), "egress")
    out = {key: value for key, value in out.items() if key in required}
    maps = {"source": src, "pod1": pod1, "pod2": pod2, "gateway1": gw1,
            "gateway2": gw2, "egress": out}
    for label, rows in maps.items():
        if set(rows) != required:
            raise ValueError("{} IDs differ: got {}, expected {}".format(
                label, sorted(rows), sorted(required)))
    complete = []
    for packet_id in sorted(required):
        hashes = [maps[name][packet_id].get("inner_sha256") for name in maps]
        if len(set(hashes)) != 1 or None in hashes:
            raise ValueError("inner hash differs for packet {}".format(packet_id))
        if pod1[packet_id].get("stage") != 1 or pod2[packet_id].get("stage") != 2:
            raise ValueError("VNF stage identity mismatch for packet {}".format(packet_id))
        complete.append({"packet_id": packet_id, "inner_sha256": hashes[0]})
    return {"run_id": next(iter(src.values())).get("request_id"),
            "sent_packets": len(src), "complete_packets": len(complete),
            "ordered_vnfs": ["pod-stage-1", "pod-stage-2"],
            "verified_handoffs": ["stage-1", "stage-2"],
            "packets": complete}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--stage2", type=Path, required=True)
    parser.add_argument("--gateway1", type=Path, required=True)
    parser.add_argument("--gateway2", type=Path, required=True)
    parser.add_argument("--egress", type=Path, required=True)
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.source, args.stage1, args.stage2, args.gateway1,
                     args.gateway2, args.egress, (args.start_id, args.count))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"complete_packets": result["complete_packets"],
                      "sent_packets": result["sent_packets"],
                      "ordered_vnfs": result["ordered_vnfs"]}))


if __name__ == "__main__":
    main()
