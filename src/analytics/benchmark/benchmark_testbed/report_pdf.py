from __future__ import annotations

from pathlib import Path
from typing import List

from .models import RequestRecord, ScenarioSummary


def write_pdf_report(path: Path, summaries: List[ScenarioSummary], records: List[RequestRecord]) -> None:
    import os
    import tempfile

    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "matplotlib"))
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(path) as pdf:
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        ax.set_title("3S-COM Testbed Benchmark Report", fontsize=18, pad=20)
        table_data = [
            [
                s.title,
                f"{s.generated_requests}",
                f"{s.acceptance_rate:.1f}%",
                f"{s.no_safe_rate:.1f}%",
                f"{s.mean_decision_latency_ms:.1f}",
                f"{s.migration_triggers}",
                f"{s.msd_drop_delta}",
            ]
            for s in summaries
        ]
        table = ax.table(
            cellText=table_data,
            colLabels=[
                "Scenario",
                "Requests",
                "Accept",
                "No safe",
                "Mean latency ms",
                "Migrations",
                "MSD drops",
            ],
            loc="center",
            cellLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.5)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        labels = [s.scenario for s in summaries]
        algorithms = sorted({s.algorithm for s in summaries})
        scenario_labels = sorted({s.scenario for s in summaries})
        acceptance_by_algorithm = {
            algorithm: [
                next((s.acceptance_rate for s in summaries if s.algorithm == algorithm and s.scenario == scenario), 0.0)
                for scenario in scenario_labels
            ]
            for algorithm in algorithms
        }
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        x_values = list(range(len(scenario_labels)))
        width = min(0.8 / max(1, len(algorithms)), 0.18)
        for idx, algorithm in enumerate(algorithms):
            offset = (idx - (len(algorithms) - 1) / 2) * width
            ax.bar(
                [x + offset for x in x_values],
                acceptance_by_algorithm[algorithm],
                width=width,
                label=algorithm,
            )
        ax.set_xticks(x_values)
        ax.set_xticklabels(scenario_labels, rotation=25, ha="right")
        ax.set_ylabel("Acceptance rate (%)")
        ax.set_title("Algorithm Acceptance Comparison")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        latency_groups = [
            [r.decision_latency_ms for r in records if r.algorithm == algorithm] or [0.0]
            for algorithm in algorithms
        ]
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.boxplot(latency_groups, labels=algorithms, showfliers=False)
        ax.set_xticklabels(algorithms, rotation=25, ha="right")
        ax.set_ylabel("Decision latency (ms)")
        ax.set_title("Decision Latency by Algorithm")
        ax.grid(axis="y", alpha=0.25)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        labels = [f"{s.algorithm}:{s.scenario}" for s in summaries if s.migration_triggers]
        triggered = [s.migration_triggers for s in summaries if s.migration_triggers]
        succeeded = [s.successful_migration_pipelines for s in summaries if s.migration_triggers]
        if not labels:
            labels = ["none"]
            triggered = [0]
            succeeded = [0]
        x_values = list(range(len(labels)))
        ax.bar([x - 0.2 for x in x_values], triggered, width=0.4, label="Triggered")
        ax.bar([x + 0.2 for x in x_values], succeeded, width=0.4, label="Succeeded")
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.set_ylabel("Count")
        ax.set_title("Make-Before-Break Activity")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
