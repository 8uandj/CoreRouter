# P1.2 Runtime Overhead and Stability Design

## Intent

Close the remaining P1.2 evidence gap for the AIO-Mesh revision using current checkpoints and instrumentation where possible. Produce reproducible evidence for the crossed simulator topology/occupancy matrix, live admission-validation overhead under bounded concurrency, and repeated admission-to-actuation behavior over a multi-hour interval if the live testbed can meet strict ownership and cleanup gates.

## Approaches considered

1. **Reuse existing scripts unchanged.** Fastest, but the live concurrency runner resets state before each concurrency level, and the duration runner does not correlate a packet probe with each admitted deployment. Rejected for live execution because it can mutate shared state and cannot prove the full lifecycle.
2. **Extend the existing harnesses with opt-in, no-reset measurements and explicit lifecycle correlation.** Reuse the existing model timing instrumentation, load-sweep implementation, live API client, migration journal, and packet-flow probe. Add fail-closed run ownership, scoped cleanup, request-level timing and delivery linkage, and a pilot gate before any multi-hour campaign. Selected because it fills the measured gaps without retraining or changing HARP policy.
3. **Clone the backend/testbed into an isolated environment.** This offers stronger isolation but requires infrastructure access and recreation of Kubernetes, Tekton, BMv2, and controller state, so it does not measure the currently running testbed.

## Goals

- Run the full crossed simulator matrix for topology sizes 25/50/100 and background occupancy 0/25/50/100 with current compatible checkpoints; do not retrain models.
- Measure live API admission-validation timing and end-to-end latency/throughput at bounded concurrency without calling global reset.
- Attempt a multi-hour repeated admission-to-actuation protocol with request-correlated deployment, steering, and packet receipts, while preserving all pre-existing workloads and ledger state.
- Record raw per-request evidence, exact denominators, environment/source/model hashes, and a manifest that distinguishes simulator, live admission, and lifecycle results.
- Leave the paper's claim limited to what the collected evidence supports.

## Non-goals

- Change HARP state/action semantics, policy, checkpoints, or training.
- Claim synthetic topology results are live topology-scale results.
- Claim live API admission overhead from simulator predicate timers.
- Call readiness or continuous probing to an already steered VNF a repeated admission-to-actuation lifecycle.
- Reset or reconstruct the live ledger, remove unrelated VNFs, or continue a campaign after uncertain steering or cleanup.

## Measurement design

### A. Crossed simulator matrix

- Use `src/analytics/benchmark/benchmark_algorithm/run_load_sweep.py` with `synthetic_25`, `synthetic_50`, and `synthetic_100`, each at `--active-chains 0 25 50 100` through a thin matrix launcher that invokes the existing single-occupancy CLI once per cell.
- Keep the current model/checkpoint and normalizer selected by the benchmark configuration. Use the registered matched seeds and offered trace; do not train.
- Retain per-seed records and report policy decision components plus the independent simulator admission-predicate P50/P95/P99. Report infeasible or capacity-rejected occupancy configurations instead of silently skipping cells.
- This is simulator evidence only; background chains are modeled, not live Kubernetes deployments.

### B. Live admission overhead

- Add a no-reset mode to the live concurrency runner. It must fail closed if reset is requested, migration lock is already held, inventory/ledger is inconsistent, or the chosen low-impact request profile cannot fit.
- First run a small single-worker pilot; use non-alert admission requests so the measurement isolates admission from deployment. Keep request count low, use unique flow IDs, capture `admission_validation_ms`, `server_decision_ms`, HTTP RTT, returned status/reason, and before/after state versions/inventory.
- Ensure any selection-only reservations are released by their returned exact VNF names after explicit verification they remain unactuated. If release returns 409, keep the reservation accounted and stop.
- Increase only to a bounded concurrency sweep if the pilot shows no active deployment, migration, or unknown ledger entry. Report that live validation timing is on the current 10-node testbed profile, not the synthetic 25/50/100 topology.

### C. Multi-hour lifecycle stability

- Start with a short single-lifecycle pilot. A request must be linked to one admitted realization, a successful Tekton deployment/readiness, matching controller operation and P4 readback, and a packet probe to that VNF. Store request/operation IDs, stage timestamps, response status, packet IDs, loss, and counter deltas.
- For repeated make-before-break runs, permit the next request only after the previous replacement is confirmed, the prior VNF is absent, the migration lock is idle, and VNF inventory/ledger counts return to their pre-run expected level.
- **Exact-old opt-in guard:** requests may supply `expected_old_vnf`. The request must also be alert-driven, match the service prefix, and identify an accounted Ready Deployment. DRL's feasible placement mask is restricted to that Deployment's recorded placement. The backend re-syncs and checks it again while holding the migration lock before actuation. The exact name is passed through MBB, and both the API client and Tekton pipeline check that the old Deployment exists before replacement creation. Legacy requests without the field retain prior behavior.
- A successful short exact-old pilot is required before the multi-hour run. The pilot must establish Ready replacement, matching steer confirmation, old-VNF deletion, and continuous packet receipts with zero loss.
- If the gate is satisfied, run at most three hours, sequentially at a bounded interval, in tmux. Stop on the first ambiguous operation, failed readiness/steering, stale P4 topology, missing packet receipt, inventory growth, new unknown/unaccounted VNF, non-idle migration lock, counter reset, or failure to confirm old-VNF deletion. Never use global reset to recover.
- A repeated lifecycle run measures the tested request cadence/configuration. It does not establish arbitrary multi-day stability or a universal zero-loss guarantee.

## Live-testbed safeguards

- Do not call `/api/orchestrate/reset`, edit or recreate the reservation ledger, reboot the backend/switches, or change firewall rules.
- All generated requests and evidence use unique IDs and owned output directories.
- Preserve raw evidence on any failure; failed/ambiguous outcomes remain in denominators.
- Cleanup is limited to a reservation or VNF whose request/run ID is owned by the campaign and whose lifecycle state has been positively verified.
- A safety-gate failure ends the lifecycle phase; it does not invalidate completed simulator or bounded live-admission evidence.

## Acceptance criteria

- All 12 simulator topology/occupancy cells have explicit result or explicit infeasibility outcome, matched seeds/traces, hashes, and admission timing summaries.
- Live admission pilot and bounded concurrency run report runtime admission-validation P50/P95/P99 separately from policy timing, API RTT, and throughput, with no reset and auditable reservation cleanup.
- Multi-hour lifecycle is marked complete only if the exact-replacement safety gate passes and every accepted request is correlated through packet receipt and confirmed old-instance cleanup. Otherwise it is explicitly reported as not safely executable with current API semantics, and the evidence package must not claim full P1.2 closure.
- Reconciliation and response-letter wording state the exact remaining limits and cite the new evidence artifacts.

## Completion record — 2026-11-25

- **Crossed simulator matrix:** complete. The fixed run contains 240/240 cells (3 topologies × 4 modeled occupancies × 20 matched seeds), 1,000 steps per seed, and 480 protected HARP/SAF-H policy rows. Trace pairing and finite metrics were checked; all protected runs had zero admitted hard violations. Results and cell-level mean ± sample SD of seed-level P95 are in Supplementary Table S29; raw records, CSVs, log, and manifest are under `results/rev1/p1_2_simulator/crossed_matrix_1000steps_fixed/`.
- **Live admission-only timing:** complete. Thirty no-reset selection-only requests on the 10-node profile, ten each at concurrency 1/2/4, had 30/30 verified scoped cleanups. Results are in Supplementary Table S30 and `docs/AIO-mesh-rev1/evidence/p1_2_20261124/RESULTS.md`.
- **Repeated lifecycle:** complete for the guarded scope. The three-hour exact-old vVOC campaign passed 18/18 cycles and delivered 4,952/4,952 packets. Results are in Supplementary Table S28 and `results/hil/p1_2_lifecycle_20261124/three_hour_retry/`.
- **Remaining interpretation limits:** modeled simulator occupancy is a fixed synthetic profile, live admission timing covers one 10-node testbed profile, and the repeated lifecycle covers one vVOC service/profile. These results do not establish production or multi-day stability, general zero-downtime behavior, or ordered multi-VNF forwarding. The planned evidence tasks are complete; Overleaf must confirm the final compile, table numbering, and page count before submission packaging.
