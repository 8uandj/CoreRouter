"""Render the two architecture diagrams shipped with the manuscript."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

FIGURES = Path(__file__).resolve().parents[2] / "docs/AIO-mesh-rev1/figs"


def diagram(filename, title, boxes, arrows, footer):
    fig, ax = plt.subplots(figsize=(9, 2.65))
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set(xlim=(0, 9), ylim=(0, 2.65))
    ax.axis("off")
    ax.text(0.12, 2.47, title, fontsize=12, weight="bold", va="center")
    for x, y, width, height, heading, description in boxes:
        ax.add_patch(FancyBboxPatch(
            (x, y), width, height, boxstyle="round,pad=.02,rounding_size=.08",
            facecolor="#eff6f1", edgecolor="#28744d", linewidth=1,
        ))
        ax.text(x + width / 2, y + height * .72, heading, ha="center",
                va="center", fontsize=11, weight="bold", color="#143f2e")
        ax.text(x + width / 2, y + height * .34, description, ha="center",
                va="center", fontsize=9, linespacing=1.25)
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops={
            "arrowstyle": "->", "color": "#324e42", "linewidth": 1.1,
        })
    ax.text(.12, .17, footer, fontsize=9, va="center")
    fig.savefig(FIGURES / filename)
    plt.close(fig)


def main():
    positions = [.12, 2.35, 4.58, 6.81]
    arrows = [((x + 2.03, 1.39), (next_x - .02, 1.39))
              for x, next_x in zip(positions, positions[1:])]
    diagram("overview.pdf", "AIO-Mesh orchestration loop", [
        (x, .82, 2, 1.14, *label) for x, label in zip(positions, [
            ("State construction", "Requests, resource state\nand optional alert input"),
            ("Candidate selection", "HARP with action masking\nor a heuristic"),
            ("Runtime admission", "Validate selected pair\nand reserve resources"),
            ("Actuation", "Lifecycle operations and\nprogrammable steering"),
        ])
    ], arrows, "Infrastructure telemetry and execution status feed subsequent decisions.")
    diagram("testbed.pdf", "Control and forwarding interfaces in the testbed", [
        (x, .82, 2, 1.14, *label) for x, label in zip(positions, [
            ("Orchestration API", "Request generator and\nKubernetes monitoring"),
            ("Policy", "Placement and route proposal\nwith policy-side masking"),
            ("Admission", "Independent validation\nand resource accounting"),
            ("Actuation interfaces", "MicroK8s / Tekton lifecycle\nMininet / BMv2 steering"),
        ])
    ], arrows, "The 12-hour experiment exercises the API and admission path and samples baseline readiness.")


if __name__ == "__main__":
    main()
