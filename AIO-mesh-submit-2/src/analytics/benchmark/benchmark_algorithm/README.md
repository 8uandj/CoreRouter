# HARP Algorithm Benchmark

Offline algorithm benchmark split from `src/analytics/benchmark_v10_final.py`.

It evaluates algorithms inside the Gym environment, without hitting the live
testbed:

- `harp` (legacy runner name `run_jo_vppm`)
- `saf_h`
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

## Synthetic topology size sweep

The benchmark and v11/ablation training CLIs accept `synthetic_25`,
`synthetic_50`, and `synthetic_100`. These deterministic square-grid fixtures
have uniform node capacities and 25 km coordinate spacing. They are useful for
measuring node-count effects in the current pair-level simulator; they are not
operator network topologies and do not add full-chain path realization.
Each size needs a checkpoint and matching normalizer trained for its `N²`
action space before HARP benchmark runs. Exhaustive pair search is disabled on
these topologies because its cost grows with the action space.

Example checkpoint preparation and benchmark:

```bash
python -m src.analytics.training.train_v11 --topology scalability
python -m src.analytics.benchmark.benchmark_algorithm.run_all \
  --topology scalability --scenario chaos --steps 3000 --skip-exhaustive
```

`scalability` trains/evaluates Vietnam (10 nodes) plus synthetic 25/50/100 node
fixtures. Training writes size-specific checkpoints and normalizers. For the
load-sweep runner, use the same topology argument after those artifacts exist.
Vary initial active chains independently of arrival rate/concurrent API
requests by replaying the same load sweep with, for example,
`--active-chains 0`, `--active-chains 25`, `--active-chains 50`, and
`--active-chains 100`. Background chains use a fixed 2 CPU / 2 RAM / 20 Mbps
profile, round-robin placement and a TTL longer than the measured episode; the
manifest records this profile. The fixture rejects counts that exceed total
per-node CPU/RAM capacity.

## Revision caveat

`chaos` uses a separate seeded two-state Markov demand profile. Calm-to-stress
transition probability is 0.08 and stress-to-calm is 0.35. In the stress state,
CPU demand is multiplied by 2.5 (capped at 85% capacity), RAM by 1.75 (same
cap), SID depth increases by 2 (capped below the topology maximum), and service
class is `Attack`. `elephant_stress` remains the independent heavy-tail profile
(20% per-request shock, CPU ×3.5 and SID depth +3). Both generators use the Gym
seeded RNG and must be rerun before comparing their results. Historical files
retain their original labels and provenance.
