# P1.2 runtime overhead and stability evidence

Date: 2026-11-24

## Live admission-only overhead

The existing live concurrency script resets state between levels, so it was not
used. A new no-reset runner measured 30 non-alert, selection-only admissions on
the running 10-node profile: 10 requests at each concurrency level 1, 2, and 4.
Each accepted reservation was checked by its exact returned VNF name, verified
pending and unactuated, then released through the scoped reservation endpoint.
There were 30/30 admissions and 30/30 verified cleanups. Inventory returned to
the baseline of 18 VNFs, with no pending or unaccounted VNF and no migration in
progress. The global reset endpoint was not called.

| Concurrency | Admission-validation P50/P95/P99 (ms) | Server-decision P95 (ms) | HTTP RTT P95 (ms) | API ops/s |
|---:|---:|---:|---:|---:|
| 1 | 24.57 / 35.05 / 35.05 | 215.92 | 220.18 | 6.22 |
| 2 | 17.73 / 28.60 / 28.60 | 170.01 | 311.09 | 7.13 |
| 4 | 15.11 / 26.24 / 26.24 | 127.67 | 463.47 | 9.26 |

These are small-sample admission-only measurements for the live 10-node profile.
`admission_validation_ms` encloses the `try_reserve` call, including its local lock,
state mutation, and durable checkpoint; it excludes deployment, steering, packet
forwarding, and the full lifecycle. HTTP RTT
includes the full orchestration response. The API throughput denominator is the
30 measured HTTP operations; scoped reservation cleanup is recorded separately.

Artifacts:

- Pilot: `results/rev1/p1_2_live_admission/20261124T091429Z/pilot.json`
- 30-request sweep: `results/rev1/p1_2_live_admission/20261124T091826Z/manifest.json`
- Per-request admission and cleanup records: `results/rev1/p1_2_live_admission/20261124T091826Z/requests.jsonl`
- Runner: `src/analytics/benchmark/benchmark_testbed/run_admission_overhead.py`

## Crossed simulator topology and occupancy matrix

The topology-specific saved checkpoints and normalizers were found in the
submission source bundle. They were not retrained. The normalizer pickle uses a
newer NumPy pickle format than the pinned Python 3.8/NumPy 1.24 environment, so
the saved observation mean, variance, clipping value, epsilon, and normalization
flag were staged losslessly as NPZ sidecars; the source pickle and checkpoints
remain unchanged. Preflight passed on all three topology-specific
checkpoint/normalizer pairs. Python 3.8 compatibility in synthetic topology
name parsing was fixed by replacing `str.removeprefix` with equivalent slicing.

The crossed matrix uses the 20 matched seeds already registered in the current
model-refresh evidence, load multiplier 1.0, and protected HARP/SAF-H on shared
offered traces. Each cell has 1,000 simulator decisions per seed. The exact
topology × active-chain grid is 25/50/100 nodes × 0/25/50/100 modeled background
chains. This is synthetic simulator evidence, not live Kubernetes occupancy.

**Status: complete.** The fixed run finished at 2026-11-24 17:46:26 UTC with
240/240 topology/occupancy/seed cells and 480 policy rows. Coverage is 20/20
seeds in each of the 12 cells; all HARP/SAF-H pairs have matching trace hashes,
all numeric values are finite, and every protected run has zero admitted hard
violations. The checkpoints, normalizers, input data, and evaluated source
hashes are recorded in `matrix_manifest.json`. No model was retrained.

The mean of seed-level P95 values changes primarily with topology size; the
modeled occupancy levels have relatively small effect within each topology.
Total decision P95 ranges across occupancy-cell means are:

| Synthetic nodes | HARP (ms) | SAF-H (ms) |
|---:|---:|---:|
| 25 | 10.36--10.72 | 9.64--10.29 |
| 50 | 26.94--27.93 | 35.25--36.39 |
| 100 | 106.67--118.45 | 251.53--257.11 |

At 100 nodes, SAF-H feasible-set construction P95 ranges from 200.43 to
204.38 ms across the four occupancy levels. Independent admission-predicate
P95 is 0.0214--0.0275 ms for HARP and 0.0117--0.0153 ms for SAF-H across the
full grid. At 100 nodes, HARP policy-inference P95 has sample SD 17.91--20.95
ms across the four occupancy conditions. Values are means over 20 seed-level
percentiles; Supplementary Table S29 includes each cell's mean and sample SD.
Component percentiles are not additive. These are simulator timings on the
evaluated host, not live Kubernetes occupancy or live API latency.

Artifacts are in
`results/rev1/p1_2_simulator/crossed_matrix_1000steps_fixed/`:
`matrix_manifest.json`, `per_seed.csv`, `aggregate_timing.csv`, `run.log`, and
240 per-seed cell JSON files. The separate 3,000-decision trial stopped after
11 cells and remains preserved under
`results/rev1/p1_2_simulator/crossed_matrix/`; its partial records are excluded
from the completed 1,000-decision matrix.

Runner: `scripts/rev1/run_p12_crossed_matrix.py`.
- Matrix manifest SHA-256: `0419909e048adc3aed9c21f3cd3415e8119aa814d6764d13473818558f8cc6c6`.
- Per-seed CSV SHA-256: `eeda57147012366a29ac87d8afa906283d69efb38995008e245c475d2d9898cf`.
- Aggregate CSV SHA-256: `f2d13b7be4c2e5b631ca2b0c3512704b3f03739544c3c3b74680a89dc18d4f97`.

## Three-hour repeated exact-old lifecycle

The API and Tekton guard were extended opt-in with an exact old-VNF
precondition; requests that omit it retain the existing behavior. A separate
three-hour live campaign then performed 18 sequential exact-old vVOC
make-before-break replacements at a 600-second cycle interval. All 18 cycles
passed the recorded readiness, exact steering confirmation, old-Deployment
deletion, probe, and zero-loss checks. The runner also reconciled inventory and
the migration lock after each cycle. It sent and received 4,952 packets in
total, with no loss or duplicate receive IDs; the maximum per-cycle receive gap
was 339.78 ms. No `msd_violation` counter increment was observed.

The run began with 18 active VNFs and stopped after the requested 10,800
seconds (`duration_elapsed`); `campaign.json` records all cycle results and has
a sidecar SHA-256. This provides repeated request-to-actuation and flow
continuity evidence for one vVOC service, one live testbed profile, and a
10-minute cadence. It does not establish ordered traversal through multiple
VNFs, behavior across services or occupancy levels, general zero-downtime
operation, production behavior, or multi-day stability. Raw per-cycle records
are retained under
`results/hil/p1_2_lifecycle_20261124/three_hour_retry/`.

