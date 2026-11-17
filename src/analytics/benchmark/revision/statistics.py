from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from scipy.stats import rankdata, wilcoxon


PAIR_KEY = ("topology", "scenario", "seed")


def paired_statistics(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare policy rows only when seed and exact offered trace are paired.

    Required config: comparisons=[{name, treatment, control}], metric,
    optional n_bootstrap (default 10000), analysis_seed (default 20261116).
    Rows must be run summaries with one row per algorithm/topology/scenario/seed.
    """
    metric = config["metric"]
    comparisons = config["comparisons"]
    n_bootstrap = int(config.get("n_bootstrap", 10_000))
    seed = int(config.get("analysis_seed", 20261116))
    if n_bootstrap < 1:
        raise ValueError("n_bootstrap must be positive")
    by_algorithm: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        if row.get("status", "ok") not in ("ok", "success", None):
            raise ValueError(f"Failed run cannot enter paired analysis: {row}")
        value = row.get(metric)
        if value is None or not np.isfinite(float(value)):
            raise ValueError(f"Missing/non-finite {metric}: {row}")
        if not row.get("trace_sha256"):
            raise ValueError(f"Missing trace_sha256: {row}")
        algorithm = str(row["algorithm"])
        key = tuple(row[name] for name in PAIR_KEY)
        if algorithm in by_algorithm[key]:
            raise ValueError(f"Duplicate algorithm row for pair key {key}: {algorithm}")
        by_algorithm[key][algorithm] = row

    outputs = []
    for comparison in comparisons:
        treatment, control = comparison["treatment"], comparison["control"]
        pairs = []
        for key, group in by_algorithm.items():
            if treatment not in group and control not in group:
                continue
            if treatment not in group or control not in group:
                raise ValueError(f"Unmatched algorithm rows for {key}: need {treatment} and {control}")
            a, b = group[treatment], group[control]
            if a["trace_sha256"] != b["trace_sha256"]:
                raise ValueError(f"Trace mismatch for paired key {key}")
            pairs.append((key, float(a[metric]) - float(b[metric])))
        if not pairs:
            raise ValueError(f"No paired observations for {comparison['name']}")
        differences = np.asarray([delta for _, delta in sorted(pairs)], dtype=np.float64)
        rng = np.random.default_rng(seed)
        samples = rng.choice(differences, size=(n_bootstrap, len(differences)), replace=True).mean(axis=1)
        ci_low, ci_high = np.quantile(samples, [0.025, 0.975])
        if np.all(differences == 0):
            p_value, effect = 1.0, 0.0
        else:
            p_value = float(wilcoxon(differences, alternative="two-sided", zero_method="wilcox").pvalue)
            nonzero = differences[differences != 0]
            ranks = rankdata(np.abs(nonzero))
            positive = float(ranks[nonzero > 0].sum())
            negative = float(ranks[nonzero < 0].sum())
            effect = (positive - negative) / (positive + negative)
        outputs.append({
            "comparison": comparison["name"], "treatment": treatment, "control": control,
            "metric": metric, "n": int(len(differences)), "mean_delta": float(differences.mean()),
            "ci95_low": float(ci_low), "ci95_high": float(ci_high),
            "wilcoxon_p": p_value, "paired_rank_biserial": float(effect),
            "all_zero_differences": bool(np.all(differences == 0)),
            "paired_keys": [list(key) for key, _ in sorted(pairs)],
        })
    # Holm step-down family-wise correction over the requested comparisons.
    ordered = sorted(range(len(outputs)), key=lambda i: outputs[i]["wilcoxon_p"])
    adjusted = [0.0] * len(outputs)
    running = 0.0
    count = len(outputs)
    for rank, index in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * outputs[index]["wilcoxon_p"]))
        adjusted[index] = running
    for result, p_adj in zip(outputs, adjusted):
        result["holm_p"] = float(p_adj)
    return outputs
