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
```

Outputs are written under `results/benchmark_testbed/<timestamp>/`:

- `preflight.json`
- `<scenario>_records.csv`
- `summary.csv`
- `benchmark_results.json`
- `benchmark_report.pdf`
