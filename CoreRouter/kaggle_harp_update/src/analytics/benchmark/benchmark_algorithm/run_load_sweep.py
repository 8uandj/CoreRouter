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

from .config import AlgorithmBenchmarkConfig
from .env_factory import make_env
from .algorithms import run_jo_vppm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run load sweep for HARP policy.")
    parser.add_argument("--topology", default="vietnam", choices=["vietnam", "nsfnet", "geant2", "all"])
    parser.add_argument("--steps", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="results/benchmark_algorithm/load_sweep")
    parser.add_argument("--data-path", default="data/processed/real_telecom_combined.csv")
    parser.add_argument("--model-root", default="results/models")
    parser.add_argument("--version", default="v11")
    return parser.parse_args()


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

    for arrival_rate in loads:
        def make_env_fn():
            return make_env(
                topology_name=topology,
                data_path=data_path,
                steps=steps,
                arrival_rate=arrival_rate,
                ttl_range=(10, 50),
                scenario="uniform",
                sla_scale=1.0,
            )
        
        metrics = run_jo_vppm(
            make_env_fn=make_env_fn,
            model_path=model_path,
            norm_path=norm_path,
            scenario="uniform",
            steps=steps,
            seed=seed
        )
        
        safe_acc = metrics.acc_rate - metrics.msd_rate
        safe_acceptances.append(safe_acc)
        admitted_msds.append(metrics.msd_rate)
        
        print(f"Topology {topology} | Load {arrival_rate:.2f} | Safe Acc: {safe_acc:.1f}% | MSD: {metrics.msd_rate:.1f}%")
        
    return safe_acceptances, admitted_msds


def plot_load_sweep_single(loads: List[float], acc_rates: List[float], msd_rates: List[float], out_path: Path, title: str):
    fig, ax1 = plt.subplots(figsize=(7, 5))

    color1 = "tab:blue"
    ax1.set_xlabel("Offered Load Multiplier")
    ax1.set_ylabel("Safe Acceptance Rate (%)", color=color1)
    ax1.plot(loads, acc_rates, marker="o", color=color1, linewidth=2, label="Acceptance")
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.set_ylim(0, 105)

    ax2 = ax1.twinx()
    color2 = "tab:red"
    ax2.set_ylabel("Admitted MSD Violation Rate (%)", color=color2)
    ax2.plot(loads, msd_rates, marker="s", color=color2, linewidth=2, linestyle="--", label="MSD Violation")
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(-5, 105)

    plt.title(f"Load Sweep: {title}")
    fig.tight_layout()
    plt.savefig(out_path, format="pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    args = parse_args()
    loads = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5]
    
    data_path = Path(args.data_path)
    model_root = Path(args.model_root)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    topologies = ["vietnam", "geant2"] if args.topology == "all" else [args.topology]
    
    for topo in topologies:
        print(f"\nRunning load sweep for {topo.upper()} topology...")
        model_path = model_root / "ablation/harp_full" / f"dgrl_{args.version}_harp_full_{topo}.zip"
        norm_path = model_root / "ablation/harp_full" / f"vec_normalize_{args.version}_harp_full_{topo}.pkl"
        
        if not model_path.exists(): # Fallback to standard if ablation not found
            model_path = model_root / args.version / f"dgrl_{args.version}_final_{topo}.zip"
            norm_path = model_root / args.version / f"vec_normalize_{args.version}_{topo}.pkl"
            
        acc, msd = run_sweep(topo, loads, args.steps, args.seed, data_path, model_path, norm_path)
        
        title = "Vietnam Topology" if topo == "vietnam" else "GEANT2 Topology" if topo == "geant2" else "NSFNET Topology"
        plot_load_sweep_single(loads, acc, msd, out_dir / f"load_sweep_{topo}.pdf", title)
    
    print(f"\nPlots saved to {out_dir}")


if __name__ == "__main__":
    main()
