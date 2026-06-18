# JO-VPPM: Current Evaluation Synthesis

This document records only the benchmark artifacts that currently exist in the project and separates them from evaluation items that are still pending. It is the source-of-truth companion for the thesis result sections.

## Completed Benchmark Artifacts

### Algorithm Benchmark

Artifact path:

```text
results/benchmark_algorithm/20260517_175737/vietnam_normal_load_normal
```

Scope:

- Topology: Vietnam 10-node backbone.
- Scenario: normal load.
- Seeds: `42, 100, 2024, 8888, 9999`.
- Available files: `aggregate_summary.csv`, `seed_summary.csv`, `results.json`, `dashboard.{png,pdf}`, `latency_cdf.{png,pdf}`, `rolling_acceptance_ci.{png,pdf}`.

Key mean results from `aggregate_summary.csv`:

| Algorithm | Requests Mean | Acceptance (%) | Unsafe MSD Accounting (%) | SLA Violation (%) | Avg Latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| traditional_greedy | 2010.8 | 89.92 | 10.08 | 4.07 | 2.48 |
| decoupled_ai | 2005.4 | 29.71 | 70.29 | 7.04 | 4.64 |
| jo_vppm | 2007.8 | 80.97 | 16.78 | 5.80 | 3.57 |

Interpretation:

- This completed run supports a Vietnam normal-load comparison only.
- It does not support GEANT2, NSFNET, ILP/Optimal, energy, or algorithm stress-test claims.
- The unsafe MSD metric is benchmark accounting. In the live backend, unsafe actions should be masked or rejected as `NO_SAFE_ACTION` rather than admitted to the data plane.

### Hardware-in-the-Loop Testbed Benchmark

Artifact path:

```text
results/benchmark_testbed/20260517_201632
```

Scope:

- Testbed: FastAPI backend, MicroK8s, Tekton, SDN controller, Mininet/BMv2 preflight.
- Scenarios: normal load, elephant heavy-tail, topology/physics stress, DDoS/MBB trigger, chaos.
- Available files: `summary.csv`, `all_records.csv`, `benchmark_results.json`, `preflight.json`, `benchmark_report.pdf`.

Key results from `summary.csv`:

| Scenario | JO-VPPM Acceptance (%) | JO-VPPM MSD Violation (%) | Hybrid Runtime Acceptance (%) | Hybrid Runtime MSD Violation (%) |
| --- | ---: | ---: | ---: | ---: |
| Normal Load | 100.00 | 0.00 | 100.00 | 0.00 |
| Elephant Heavy-Tail | 70.97 | 0.00 | 75.27 | 0.00 |
| Topology and Physics Stress | 21.19 | 0.00 | 21.19 | 0.00 |
| DDoS and Make-Before-Break | 23.01 | 0.00 | 24.78 | 0.00 |
| Chaos | 10.00 | 0.00 | 8.33 | 0.00 |

Important caveat:

- The DDoS/MBB scenario records migration triggers, but the completed benchmark reports `successful_migration_pipelines=0`. Treat it as evidence for the proactive trigger path and MSD-safe admission, not as final proof of zero-downtime migration.

## Current System Progress

- Real JO-VPPM DRL model loading is mandatory in the deployed backend through `JO_VPPM_REQUIRE_MODEL=1`.
- Telemetry ingestion now accepts CPU/RAM/MSD utilization and PPS samples.
- Forecasting is connected into the backend control loop:

```text
telemetry/pps -> TrafficForecastService -> forecast alert -> StateManager -> hysteresis gate -> DRL/MBB
```

- The forecasting module is Bi-GRU-ready and can load a checkpoint via `JO_VPPM_BIGRU_MODEL_PATH`. Without a checkpoint, it uses deterministic trend fallback.
- Tekton deploy/migrate pipelines now receive `nodeHostname` so AI node decisions can be aligned with Kubernetes placement.
- Manual server helper:

```text
scripts/manual_testbed_validation.sh
```

supports Mininet/controller, Tekton Dashboard, backend logs, telemetry smoke tests, orchestration calls, and focused phase tests.

## Pending Evaluation Items

- GEANT2 normal-load benchmark artifacts.
- NSFNET normal-load benchmark artifacts.
- Cross-topology stress benchmark artifacts.
- ILP/Optimal baseline results if the thesis keeps an optimality-gap section.
- Energy accounting if the thesis keeps energy/sustainability claims.
- Trained Bi-GRU checkpoint and forecast accuracy evaluation if the thesis claims real Bi-GRU inference.
- Dedicated Make-Before-Break continuity run with packet capture/TCP sequence evidence if the thesis claims zero downtime.

## Thesis Policy

Use completed artifacts for concrete numbers. Keep GEANT2/NSFNET/stress figures as placeholders until their result files exist. Do not claim trained Bi-GRU inference unless `JO_VPPM_BIGRU_MODEL_PATH` points to a trained checkpoint and `/api/orchestrate/state` reports `forecast.model_loaded=true`.
