"""
run_load_sweep.py — Load Sweep for HARP Policy

Simulates offered load by:
  - load <= 1.0: probability-based arrival (arrival_rate = load)
  - load > 1.0: arrival_rate=1.0 (every step has a request) + CPU/RAM demand
    is scaled by `load` multiplier to simulate higher resource pressure.
    TTL is also increased to accumulate more concurrent active flows.

This produces a realistic capacity curve:
  - At low load: high safe acceptance, zero MSD violations
  - At overload: acceptance degrades, MSD violations emerge as HARP rejects
    or routes through overloaded nodes
"""
import argparse
import os
from pathlib import Path
from typing import List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import matplotlib.pyplot as plt
import numpy as np

from .env_factory import make_env
from .algorithms import run_jo_vppm


def _build_env_factory(topology: str, data_path: Path, steps: int, load: float):
    """
    Build an env factory function calibrated for the given load multiplier.

    - Normalize baseline TTL by topology size so that 'Load 1.0' corresponds
      to a similar % of hardware utilization across all topologies.
    - load <= 1.0  → probability-based skip (arrival_rate = load), normal TTL
    - load > 1.0   → every step has a request, TTL & demands scale by load.
    """
    topo_scale = {"vietnam": 1.0, "nsfnet": 1.4, "geant2": 2.3}.get(topology, 1.0)
    base_ttl_min = max(5, int(15 * topo_scale))
    base_ttl_max = max(20, int(60 * topo_scale))

    if load <= 1.0:
        arrival_rate = load
        ttl_range = (base_ttl_min, base_ttl_max)
        demand_scale = 1.0
    else:
        arrival_rate = 1.0
        ttl_range = (int(base_ttl_min * load), int(base_ttl_max * load))
        demand_scale = load  # Scale CPU/RAM requirements by load multiplier

    def make_env_fn():
        base_env = make_env(
            topology_name=topology,
            data_path=data_path,
            steps=steps,
            arrival_rate=arrival_rate,
            ttl_range=ttl_range,
            scenario="bursty",   # bursty is more realistic for stress testing
            sla_scale=1.0,
        )
        if demand_scale != 1.0:
            original_loader = base_env._load_request_for_step

            def scaled_loader(step: int) -> None:
                original_loader(step)
                req = base_env._current_req
                base_env._current_req = {
                    'cpu': min(base_env.max_cpu * 0.9, req['cpu'] * demand_scale),
                    'ram': min(base_env.max_ram * 0.9, req['ram'] * demand_scale),
                    'msd': min(int(base_env.node_msd_limits.max()) - 1,
                               int(req['msd'] * max(1, round(demand_scale)))),
                    'service_type': req.get('service_type', 'Data'),
                    'ddos': req.get('ddos', 0),
                }

            base_env._load_request_for_step = scaled_loader
            scaled_loader(0)

        return base_env

    return make_env_fn


def run_sweep(
    topology: str,
    loads: List[float],
    steps: int,
    seed: int,
    data_path: Path,
    model_path: Path,
    norm_path: Path
) -> Tuple[List[float], List[float]]:

    safe_acceptances = []
    admitted_msds = []

    for load in loads:
        make_env_fn = _build_env_factory(topology, data_path, steps, load)

        metrics = run_jo_vppm(
            make_env_fn=make_env_fn,
            model_path=model_path,
            norm_path=norm_path,
            scenario="bursty",
            steps=steps,
            seed=seed
        )

        # safe_acc = requests accepted WITHOUT MSD violation
        # = (accepted / total) - (msd_violated / total)  [both as %, from metrics]
        # But msd_rate is over ALL requests, not just accepted ones.
        # The meaningful metric: accepted requests that are MSD-safe
        acc_rate = metrics.acc_rate
        msd_rate = metrics.msd_rate
        safe_acc = max(0.0, acc_rate - msd_rate)

        safe_acceptances.append(safe_acc)
        admitted_msds.append(msd_rate)

        print(f"Topology {topology} | Load {load:.2f} | Safe Acc: {safe_acc:.1f}% | MSD: {msd_rate:.1f}%")

    return safe_acceptances, admitted_msds


def plot_load_sweep_single(
    loads: List[float],
    acc_rates: List[float],
    msd_rates: List[float],
    out_path: Path,
    title: str
):
    fig, ax1 = plt.subplots(figsize=(7, 5))

    color1 = "tab:blue"
    ax1.set_xlabel("Offered Load Multiplier", fontsize=12)
    ax1.set_ylabel("Safe Acceptance Rate (%)", color=color1, fontsize=12)
    ax1.plot(loads, acc_rates, marker="o", color=color1, linewidth=2,
             label="Safe Acceptance")
    ax1.axvline(x=1.0, color="gray", linestyle=":", linewidth=1.5, label="Nominal Load")
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.set_ylim(0, 105)
    ax1.set_xticks(loads)
    ax1.set_xticklabels([f"{l:.1f}x" for l in loads], rotation=30)

    ax2 = ax1.twinx()
    color2 = "tab:red"
    ax2.set_ylabel("Admitted MSD Violation Rate (%)", color=color2, fontsize=12)
    ax2.plot(loads, msd_rates, marker="s", color=color2, linewidth=2,
             linestyle="--", label="MSD Violation")
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(-5, 105)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="center left", fontsize=10)

    # plt.title(f"Load Sweep: {title}", fontsize=13)
    fig.tight_layout()
    plt.savefig(out_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Run load sweep for HARP policy.")
    parser.add_argument("--topology", default="vietnam",
                        choices=["vietnam", "nsfnet", "geant2", "all"])
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir",
                        default="results/benchmark_algorithm/load_sweep")
    parser.add_argument("--data-path",
                        default="data/processed/real_telecom_combined.csv")
    parser.add_argument("--model-root", default="results/models")
    parser.add_argument("--version", default="v11")
    args = parser.parse_args()

    loads = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5]

    data_path = Path(args.data_path)
    model_root = Path(args.model_root)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    topologies = (["vietnam", "geant2"] if args.topology == "all"
                  else [args.topology])

    for topo in topologies:
        print(f"\nRunning load sweep for {topo.upper()} topology...")

        # Prefer freshly-trained ablation/harp_full model; fall back to v11 final
        model_path = (model_root / "ablation/harp_full"
                      / f"dgrl_{args.version}_harp_full_{topo}.zip")
        norm_path  = (model_root / "ablation/harp_full"
                      / f"vec_normalize_{args.version}_harp_full_{topo}.pkl")

        if not model_path.exists():
            model_path = (model_root / args.version
                          / f"dgrl_{args.version}_final_{topo}.zip")
            norm_path  = (model_root / args.version
                          / f"vec_normalize_{args.version}_{topo}.pkl")

        acc, msd = run_sweep(
            topo, loads, args.steps, args.seed, data_path, model_path, norm_path
        )

        title_map = {
            "vietnam": "Vietnam Topology",
            "geant2":  "GEANT2 Topology",
            "nsfnet":  "NSFNET Topology",
        }
        title = title_map.get(topo, topo.upper())
        plot_load_sweep_single(
            loads, acc, msd, out_dir / f"load_sweep_{topo}.pdf", title
        )

    print(f"\nPlots saved to {out_dir}")


if __name__ == "__main__":
    main()
