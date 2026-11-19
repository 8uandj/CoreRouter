"""Tabulate service outcomes available in the retained stress summaries."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs/AIO-mesh-rev1"
SOURCE = ROOT / "evidence/policy_tradeoffs/benchmark_tradeoffs.csv"
OUTPUT = ROOT / "generated/qos_rows.tex"
TOPOLOGIES = {"vietnam": "Vietnam", "nsfnet": "NSFNET", "geant2": "GEANT2"}
WORKLOADS = {"elephant_stress": "Elephant stress", "burst_surge": "Burst surge", "chaos": "Chaos"}


def main():
    with SOURCE.open() as stream:
        rows = list(csv.DictReader(stream))
    cells = {(r["topology"], r["scenario"], r["algorithm"]): r for r in rows}
    result = []
    for topo, topo_name in TOPOLOGIES.items():
        for traffic, traffic_name in WORKLOADS.items():
            row = [topo_name, traffic_name]
            for policy in ("harp_protected", "saf_h_protected"):
                cell = cells[topo, traffic, policy]
                if int(cell["n_seeds"]) != 20:
                    raise ValueError(f"Incomplete seed group: {topo}, {traffic}, {policy}")
                row.extend(f"{float(cell[field]):.2f}" for field in (
                    "avg_latency_ms_mean", "sla_violation_rate_mean"))
            result.append(" & ".join(row) + r" \\" + "\n")
    OUTPUT.write_text("".join(result))


if __name__ == "__main__":
    main()
