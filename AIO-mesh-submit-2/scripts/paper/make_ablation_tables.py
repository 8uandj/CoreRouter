"""Generate Tables 9–10 from the preserved equal-weight summary export."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs/AIO-mesh-rev1"
DATA = ROOT / "evidence/e3"
OUT = ROOT / "generated"
LABELS = {
    "harp_full": "Full",
    "harp_wo_gat": "MLP",
    "harp_wo_adaptive_penalty": "NoAdapt",
    "harp_wo_hard_masking": "NoMask",
    "harp_wo_mask_unchecked": "NoMask (MSD off)",
    "harp_soft_msd_penalty": "SoftMSD (MSD off)",
    "harp_soft_msd_admission": "SoftMSD (MSD on)",
}


def read(filename):
    with (DATA / filename).open() as stream:
        return list(csv.DictReader(stream))


def table(rows, name):
    (OUT / name).write_text("".join(" & ".join(row) + " \\\\\n" for row in rows))


def main():
    runs = read("ablation_admission_summary.csv")
    totals = read("ablation_pooled_summary.csv")
    if len(runs) != 21 or len(totals) != 7:
        raise ValueError("The ablation exports do not contain all seven variants")

    def mean_sd(row, metric):
        return f"{float(row[metric + '_mean']):.2f} $\\pm$ {float(row[metric + '_sample_sd']):.2f}"

    lines = []
    for topology in ("vietnam", "nsfnet", "geant2"):
        cells = {row["variant"]: row for row in runs if row["topology"].lower() == topology}
        for variant, label in LABELS.items():
            row = cells[variant]
            if int(row["n_seed_workload_cells"]) != 80:
                raise ValueError(f"Incomplete group: {topology} {variant}")
            empty = float(row["mask_empty_rate_mean"])
            pruned = float(row["mask_eliminated_candidate_rate_mean"])
            nonempty = 100 * (pruned - empty) / (100 - empty) if empty < 100 else None
            lines.append([
                "Vietnam" if topology == "vietnam" else topology.upper(), label,
                mean_sd(row, "mask_eliminated_candidate_rate"),
                f"{empty:.2f}", "--" if nonempty is None else f"{nonempty:.2f}",
                mean_sd(row, "admitted_hard_violation_rate"),
                mean_sd(row, "safe_acceptance_rate"),
            ])
    table(lines, "table09_rows.tex")

    metrics = ("proposed_cpu_violation_rate_mean", "proposed_ram_violation_rate_mean",
               "proposed_bw_violation_rate_mean", "attempted_msd_violation_rate_mean",
               "proposed_hard_violation_rate_mean", "admitted_hard_violation_rate_mean")
    cells = {row["variant"]: row for row in totals}
    table([[label] + [f"{float(cells[variant][field]):.3f}" for field in metrics]
           for variant, label in LABELS.items()], "table10_rows.tex")


if __name__ == "__main__":
    main()
