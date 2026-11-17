# 3S-COM Testbed Benchmark

Runtime benchmark suite for the live 3S-COM testbed. It calls the FastAPI
orchestrator, polls the SDN controller, tracks TTL expiry through
`/api/orchestrate/free`, runs local baseline simulations against the same
request streams, and exports CSV/JSON/PDF outputs.

Run all scenarios from the repository root:

```bash
python -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios
```

Useful options:

```bash
python -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios --steps 50
python -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios --scenario ddos_mbb
python -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios --api-base-url http://127.0.0.1:8000/api --sdn-base-url http://127.0.0.1:8765
python -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios --no-baselines
python -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios --baseline jo_vppm --baseline greedy
# Live extended stability run; choose a safe request interval for the target testbed.
python -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios --scenario normal_load --duration-hours 24 --request-interval-s 1 --no-baselines
# Matched request trace at increasing bounded client concurrency.
python -m src.analytics.benchmark.benchmark_testbed.run_concurrency --requests 1000 --concurrency 1 2 4 8 16
```

Outputs are written under `results/benchmark_testbed/<timestamp>/`:

- `preflight.json`
- `run_manifest.json` (seed, topology/MSD profile, workload, queue settings, hardware/software and source hashes)
- `summary.csv`
- `all_records.csv`
- `benchmark_results.json`
- `benchmark_report.pdf`
- `scenarios/<scenario>/summary.csv`
- `scenarios/<scenario>/all_records.csv`
- `scenarios/<scenario>/benchmark_results.json`
- `scenarios/<scenario>/benchmark_report.pdf`
- `scenarios/<scenario>/<scenario>_records.csv`
- `scenarios/<scenario>/<scenario>_hourly_summary.csv` (for duration-based runs)
- `scenarios/<scenario>/<scenario>_<algorithm>_records.csv`

The live runner separates API decision latency from simulated service latency,
records backend stage timings when returned by the API, reports measured
operations per wall-clock second, and waits for a requested deployment to become
visible as a non-pending Kubernetes VNF before counting it as deployed. A
duration-based run records UTC timestamps and hourly admission/deployment counts.
The concurrency runner resets state before each concurrency level and replays
the same request trace; do not combine its outputs with a long-running scenario.

### TTL and cleanup contract

Expiry sends the returned `vnf_name`. The server releases only selection-only
reservations through this API; live or unresolved actuation returns HTTP 409
until verified lifecycle cleanup. Failed expiry remains tracked and retried.
Scenario cleanup does not force-reset the ledger; an initial reset refused due
to live allocations stops the next run. Deployments count as ready only on
explicit positive Kubernetes replica readiness. De-steering and deletion for
deployed TTL expiry remain a required testbed teardown stage, not a local
resource-free operation.

Migration completion is read from the per-replacement journal endpoint and
requires matching old/new identities, a consistent operation ID, confirmed
steering and completed old cleanup. Exports include `migration_completed`,
`migration_operation_id`, `migration_recovery_state` and `completed_migrations`.
The legacy `successful_migration_pipelines` summary mirrors this verified count;
it no longer means the latest arbitrary Tekton pipeline succeeded.

MSD drop measurements require a nonempty valid counter snapshot from every
reported switch. Missing/unreadable counters and unavailable HTTP endpoints
fail measurement rather than imply zero drops. A switch disappearing or any individual switch counter decreasing
invalidates the run delta, even when the aggregate increased. Raw request/hourly CSVs are saved before the final
counter check, even if that check prevents a valid summary.
