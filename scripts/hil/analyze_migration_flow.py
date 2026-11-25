#!/usr/bin/env python3
"""Summarize packet sequence evidence during make-before-break migration."""

import argparse
import json
from collections import Counter
from pathlib import Path


def analyze_flow(sent, received, events):
    if not sent or not received:
        raise ValueError("nonempty sent and received packet observations are required")
    ids = [row["id"] for row in sent]
    if len(ids) != len(set(ids)):
        raise ValueError("sent packet IDs must be unique")
    times = [float(row["t"]) for row in sent]
    if times != sorted(times):
        raise ValueError("sent packets must have monotonic timestamps")
    ready = float(events["ready"])
    confirmed = float(events["steer_confirmed"])
    deleted = float(events["old_deleted"])
    if not ready <= confirmed <= deleted:
        raise ValueError("make-before-break event order is invalid")
    count = Counter(row["id"] for row in received)
    unique_received = {row["id"] for row in received}
    if not unique_received.issubset(set(ids)):
        raise ValueError("received packet ID was not sent")
    receive_times = sorted(float(row["t"]) for row in received)
    longest_gap = max((b - a for a, b in zip(receive_times, receive_times[1:])), default=0.0)
    lost = [packet_id for packet_id in ids if packet_id not in unique_received]
    duplicates = sorted(packet_id for packet_id, n in count.items() if n > 1)
    return {"sent": len(sent), "received_unique": len(unique_received),
            "lost_ids": lost, "duplicate_receive_ids": duplicates,
            "longest_receive_gap_s": longest_gap,
            "zero_loss": not lost and not duplicates,
            "events": {"ready": ready, "steer_confirmed": confirmed, "old_deleted": deleted}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="JSON with sent, received, events")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.input.read_text())
    summary = analyze_flow(record["sent"], record["received"], record["events"])
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    if not summary["zero_loss"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
