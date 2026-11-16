# JO-VPPM Algorithm Benchmark

Offline algorithm benchmark split from `src/analytics/benchmark_v10_final.py`.

It evaluates algorithms inside the Gym environment, without hitting the live
testbed:

- `jo_vppm`
- `traditional_greedy`
- `decoupled_ai`
- `exhaustive_pair_search` as an upper-bound search when enabled

Run a quick single-seed Vietnam benchmark:

```bash
python -m src.analytics.benchmark.benchmark_algorithm.run_all \
  --topology vietnam \
  --scenario heavy_tail \
  --load stress \
  --version v11 \
  --steps 1000 \
  --single-seed \
  --skip-exhaustive
```

Run all Vietnam scenarios:

```bash
python -m src.analytics.benchmark.benchmark_algorithm.run_all \
  --topology vietnam \
  --scenario all \
  --load stress \
  --version v11 \
  --steps 3000 \
  --skip-exhaustive
```

Run the thesis-oriented scenario suite:

```bash
python -m src.analytics.benchmark.benchmark_algorithm.run_all \
  --topology vietnam \
  --scenario thesis \
  --version v11 \
  --steps 10000 \
  --workers 5 \
  --skip-exhaustive
```

Use stricter SLA thresholds when Vietnam latency is too low to expose SLA
violations:

```bash
python -m src.analytics.benchmark.benchmark_algorithm.run_all \
  --topology vietnam \
  --scenario thesis \
  --version v11 \
  --steps 10000 \
  --workers 5 \
  --sla-scale 0.2 \
  --skip-exhaustive
```

Outputs are stored under `results/benchmark_algorithm/<timestamp>/`:

- `seed_summary.csv`
- `aggregate_summary.csv`
- `results.json`
- `dashboard.pdf`
- `latency_cdf.pdf`
- `rolling_acceptance_ci.pdf` for multi-seed runs
