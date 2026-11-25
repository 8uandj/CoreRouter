#!/usr/bin/env python3
"""Validate packet-correlated receipts from an ordered VNF chain."""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def analyze_chain(request_id, packet_ids, vnfs, events, sent_records=None):
    if not request_id or not packet_ids or len(packet_ids) != len(set(packet_ids)):
        raise ValueError("request and unique sent packet IDs are required")
    if len(vnfs) < 2 or len(vnfs) != len(set(vnfs)) or "egress" in vnfs:
        raise ValueError("at least two distinct VNFs are required")
    expected = list(vnfs) + ["egress"]
    source_hashes = None
    if sent_records is not None:
        source_rows = [row for row in sent_records if row.get("request_id") == request_id]
        source_hashes = {row["packet_id"]: row["inner_sha256"] for row in source_rows}
        if (len(source_rows) != len(packet_ids) or len(source_hashes) != len(packet_ids)
                or set(source_hashes) != set(packet_ids)):
            raise ValueError("sent source records are incomplete or duplicated")
    receipts = defaultdict(list)
    for event in events:
        if event.get("request_id") == request_id and event.get("packet_id") in packet_ids:
            receipts[event["packet_id"]].append(event)
    invalid = []
    for packet_id in packet_ids:
        rows = receipts[packet_id]
        if len(rows) != len(expected):
            invalid.append(packet_id)
            continue
        try:
            ordered = sorted(rows, key=lambda row: row["seq"])
            sequences = [row["seq"] for row in ordered]
            stages = [row["stage"] for row in ordered]
        except (KeyError, TypeError, ValueError):
            invalid.append(packet_id)
            continue
        hashes = [row.get("inner_sha256") for row in ordered]
        if (len(sequences) != len(set(sequences)) or stages != expected
                or len(set(hashes)) != 1
                or not isinstance(hashes[0], str)
                or not re.fullmatch(r"[0-9a-f]{64}", hashes[0])
                or (source_hashes is not None and hashes[0] != source_hashes[packet_id])):
            invalid.append(packet_id)
    return {"request_id": request_id, "sent_packets": len(packet_ids),
            "complete_packets": len(packet_ids) - len(invalid),
            "invalid_packets": invalid, "ordered_vnfs": list(vnfs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--sent", required=True, help="JSON array of sent packet IDs")
    parser.add_argument("--vnfs", required=True, help="ordered, comma-separated VNF names")
    parser.add_argument("--events", type=Path, required=True, help="JSONL receipt events")
    parser.add_argument("--sent-records", type=Path, help="JSONL source records with inner hashes")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    events = [json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
    sent = ([json.loads(line) for line in args.sent_records.read_text().splitlines() if line.strip()]
            if args.sent_records else None)
    summary = analyze_chain(args.request_id, json.loads(args.sent), args.vnfs.split(","), events, sent)
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    if summary["invalid_packets"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
