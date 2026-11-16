from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import List

from .baseline_simulator import BASELINE_ALGORITHMS, BaselineSimulator
from .config import BenchmarkConfig
from .exporters import write_json, write_records_csv, write_summary_csv
from .http_client import TestbedClient
from .models import RequestRecord, ScenarioSummary
from .preflight import run_preflight
from .report_pdf import write_pdf_report
from .runner import ScenarioRunner
from .scenarios import ALL_SCENARIOS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the 3S-COM runtime testbed benchmark.")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000/api")
    parser.add_argument("--sdn-base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--output-dir", default="results/benchmark_testbed")
    parser.add_argument("--steps", type=int, default=0, help="Override steps for every scenario.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--request-timeout-s", type=float, default=60.0)
    parser.add_argument("--sdn-timeout-s", type=float, default=15.0)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=[scenario.name for scenario in ALL_SCENARIOS],
        help="Run one scenario. Can be passed multiple times. Defaults to all.",
    )
    parser.add_argument("--no-reset", action="store_true", help="Do not reset AI state before each scenario.")
    parser.add_argument("--no-cleanup", action="store_true", help="Do not free TTL reservations after each scenario.")
    parser.add_argument("--no-wait-migration", action="store_true", help="Do not wait for MBB background tasks.")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument(
        "--no-baselines",
        action="store_true",
        help="Only run the live Hybrid API path; skip local baseline simulations.",
    )
    parser.add_argument(
        "--baseline",
        action="append",
        choices=BASELINE_ALGORITHMS,
        help="Baseline algorithm to simulate. Can be passed multiple times. Defaults to all.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.output_dir) / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    config = BenchmarkConfig(
        api_base_url=args.api_base_url,
        sdn_base_url=args.sdn_base_url,
        output_dir=run_dir,
        steps=args.steps,
        seed=args.seed,
        request_timeout_s=args.request_timeout_s,
        sdn_timeout_s=args.sdn_timeout_s,
        reset_before_scenario=not args.no_reset,
        cleanup_after_scenario=not args.no_cleanup,
        wait_for_migration=not args.no_wait_migration,
    )
    client = TestbedClient(
        api_base_url=config.api_base_url,
        sdn_base_url=config.sdn_base_url,
        request_timeout_s=config.request_timeout_s,
        sdn_timeout_s=config.sdn_timeout_s,
    )

    if not args.skip_preflight:
        ok, checks = run_preflight(client)
        (run_dir / "preflight.json").write_text(
            __import__("json").dumps(checks, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        if not ok:
            raise SystemExit(f"Preflight failed. See {run_dir / 'preflight.json'}")

    selected = [s for s in ALL_SCENARIOS if not args.scenario or s.name in args.scenario]
    runner = ScenarioRunner(config, client)
    baseline_runner = BaselineSimulator(seed=config.seed, steps=config.steps)
    all_records: List[RequestRecord] = []
    summaries: List[ScenarioSummary] = []

    for scenario in selected:
        scenario_dir = run_dir / "scenarios" / scenario.name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        print(f"Running {scenario.title} ({scenario.name})")
        records, summary = runner.run(scenario, scenario_dir)
        all_records.extend(records)
        summaries.append(summary)
        print(
            f"  hybrid_runtime requests={summary.generated_requests} "
            f"accept={summary.acceptance_rate:.1f}% "
            f"no_safe={summary.no_safe_rate:.1f}% "
            f"msd_viol={summary.msd_violation_rate:.1f}% "
            f"decision_ms={summary.mean_decision_latency_ms:.1f} "
            f"svc_lat={summary.mean_service_latency_ms:.2f}ms "
            f"timeouts={summary.timeout_count} "
            f"migrations={summary.migration_triggers}"
        )
        if not args.no_baselines:
            baselines = args.baseline or BASELINE_ALGORITHMS
            for algorithm in baselines:
                baseline_records, baseline_summary = baseline_runner.run(scenario, algorithm, scenario_dir)
                all_records.extend(baseline_records)
                summaries.append(baseline_summary)
                print(
                    f"  {algorithm} requests={baseline_summary.generated_requests} "
                    f"accept={baseline_summary.acceptance_rate:.1f}% "
                    f"no_safe={baseline_summary.no_safe_rate:.1f}% "
                    f"msd_viol={baseline_summary.msd_violation_rate:.1f}% "
                    f"decision_ms={baseline_summary.mean_decision_latency_ms:.1f} "
                    f"svc_lat={baseline_summary.mean_service_latency_ms:.2f}ms"
                )
        scenario_summaries = [s for s in summaries if s.scenario == scenario.name]
        scenario_records = [r for r in all_records if r.scenario == scenario.name]
        write_summary_csv(scenario_dir / "summary.csv", scenario_summaries)
        write_records_csv(scenario_dir / "all_records.csv", scenario_records)
        write_json(scenario_dir / "benchmark_results.json", scenario_summaries, scenario_records)
        write_pdf_report(
            scenario_dir / "benchmark_report.pdf",
            scenario_summaries,
            scenario_records,
            report_title=f"3S-COM Testbed Scenario Report - {scenario.title}",
        )

    write_summary_csv(run_dir / "summary.csv", summaries)
    write_records_csv(run_dir / "all_records.csv", all_records)
    write_json(run_dir / "benchmark_results.json", summaries, all_records)
    write_pdf_report(run_dir / "benchmark_report.pdf", summaries, all_records)
    print(f"Saved benchmark outputs to {run_dir}")


if __name__ == "__main__":
    main()
