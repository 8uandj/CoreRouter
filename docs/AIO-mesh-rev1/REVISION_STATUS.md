# Revision status

Updated: 2026-11-17

## Integrity recovery

- Removed unsupported invented manuscript results and rebuilt descriptive historical Vietnam/NSFNET summaries from available per-seed files. Historical lineage checks remain incomplete; see `INTEGRITY_RECOVERY.md` and `EVIDENCE_LEDGER.csv`.
- Captured HARP-model source/artifact audit records. The HARP-model runtime model interface is not established as compatible with the flat-action benchmark environment.

## E3 matched-trace ablation results

- Completed the registered 20-seed, 3,000-step-per-seed ablation evaluation for Vietnam, NSFNET, and GEANT2 across Uniform, Bursty, Heavy-tail, and distinct Chaos workloads. Each topology/workload contains 20 seeds × 7 variants, and trace hashes match across variants within each seed.
- Recomputed candidate-mask pruning, runtime rejection, admitted hard-violation, and safe-acceptance metrics. The aggregated table uses 80 seed/workload cells per topology (mean ± sample SD); this is evaluation variation, not independent training uncertainty.
- Updated `rev1.tex` with all seven registered variants, per-topology admission outcomes, and pooled CPU/RAM/BW/MSD proposal violation rates with overlap semantics. Reproducible aggregates and source/checkpoint/normalizer/trace hashes are in `evidence/e3/manifest.json` and `ablation_admission_summary.csv`. Admission outcomes are simulator evidence for modeled predicates, not full-chain deployment or forwarding evidence. The retained training artifacts contain no convergence history, so no convergence result is claimed; the timing rerun measures local simulator policy-decision components, not external controller/deployment latency.
- The 20-seed algorithm benchmark reruns for Vietnam and NSFNET completed at 19:43 and 19:45 on 2026-11-17; logs are `/tmp/rev1-benchfix-vietnam.log` and `/tmp/rev1-benchfix-nsfnet.log`. The E3 compute-overhead rerun is now running sequentially in tmux (`e3-ablation-timed`) so timing is not collected concurrently with those benchmarks.

## Code work in progress: E1 admission contract

- `NetworkStateManager` now charges CPU/RAM to placement only, checks each list's SID depth against the routing node limit, tracks anonymous TTL reservations, rejects malformed or duplicate named reservations, and reconstructs per-node MSD state as maximum active depth.
- Heuristic feasibility, Gym policies, SAF-H candidate generation, and the testbed baseline predicate now use the same per-list MSD interpretation. Environment action decoding rejects malformed/out-of-range values and an empty action mask stays empty.
- The production DRL runtime now accepts the recovered main v11 `MultiDiscrete([N,N])` checkpoints by converting their factorized `2N` action heads into additive `N²` pair logits before applying the runtime pair mask. The current trainer still declares flat `Discrete(N²)`. Historical training provenance and revised runtime results must be reported separately.
- DRL inference no longer reports a heuristic shadow choice as a loaded model. Missing or unreadable normalizer statistics fail model loading, and checkpoint space mismatches use an explicit safe-search fallback.
- Chaos is now an independently seeded two-state Markov demand profile with documented transition and demand parameters; historical records remain untouched.
- The Gym simulator now checks exactly the SID-list depth emitted by the runtime pair-level realization; it no longer adds an unmaterialized hop count. The implementation and evidence explicitly remain pair-level and do not claim full multi-VNF-chain validation.
- The runtime reservation contract now uses a monotonically increasing state version. A policy decision is admitted only if its snapshot version still matches under the reservation lock; stale decisions fail closed. Resource telemetry ages are exposed, and strict TTL enforcement can be enabled with `CORE_ROUTER_TELEMETRY_TTL_S`.
- Hysteresis keeps strict `>45%` engage and `<35%` release semantics despite float32 rounding; exact-boundary regression tests cover both thresholds.
- The strict ablation evaluator supports multi-seed runs, preflights all variant artifacts/spaces, uses the registered no-GAT extractor when loading MLP checkpoints, and rejects missing/duplicate/incomplete variant-seed output coverage or per-seed trace mismatches. It includes a paired SoftMSD policy evaluation with the MSD admission boundary enabled/disabled, reusing the same trained checkpoint; a negative MSD reward is now applied to rejected candidates as well as admitted soft-constraint candidates. Ablation output reports overlapping proposed CPU/RAM/BW/MSD rates, unique proposed/admitted hard-violation rates, and non-overlapping primary rejection rates. The v3 run manifest includes accounting definitions and source/artifact hashes. The Kaggle notebook derives row coverage from the registered variant list and displays these fields. A 2-step NSFNET/Chaos smoke completed all seven variants with one shared trace hash; this verifies runner coverage only, not scientific outcomes.
- Benchmark preflight validates dataset, checkpoint, normalizer and spaces before evaluation. The comparison runner now checks protected/unprotected coverage, reports candidate/admission and non-overlapping primary rejection rates, handles mask exhaustion through the shared admission boundary, and tracks mask candidate pruning. It reports measured per-request decision P50/P95/P99, state/mask/inference/admission components, and real elapsed throughput. A fresh 2-step NSFNET/Chaos smoke covered all eight protected/unprotected policy modes.
- Workload/arrival sampling now uses an RNG stream isolated from TTL/lifecycle randomness, so policy-dependent admissions do not alter future offered traffic for the same seed. Per-run benchmark and ablation summaries record trace hashes and trace-step counts.
- Benchmark seed/policy coverage is validated before export, including exact requested seed sets, policy matrix, offered-step count, nonzero request counts, and matched trace hashes. Empty/missing trace records are now rejected explicitly; paired inference also rejects duplicate, incomplete, or trace-mismatched pairs.
- Load-sweep runner now evaluates HARP, SAF-H, Greedy and DAI on the same offered trace at each load and seed; exports per-seed rows, paired HARP-vs-SAF-H tests, bootstrap intervals, trace/model/data hashes and a multi-policy figure. It rejects zero-offered rows rather than interpreting them as 0% acceptance. A 40-step single-seed smoke produced 28 policy/load rows with matching trace hashes and at least seven offered requests per load.
- Kaggle ablation notebook now trains missing/incompatible model sets after strict preflight, evaluates Elephant/heavy-tail and Chaos over ten seeds, verifies variant/seed coverage and matched trace hashes, then runs multi-policy load sweep and benchmark. Notebook JSON and every code cell parse; actual Kaggle execution remains pending.
- Kaggle setup now pins the current validated Python dependency versions rather than installing latest packages. Model manifests record the actual runtime dependency versions.
- Exhaustive search now restores lifecycle/workload RNGs and all mutable environment state between counterfactual actions. The expected coverage matrix includes both protection modes.
- The HIL runner now records admission separately from confirmed deployment, waits for a replacement VNF to appear non-pending before counting it deployed, exports component timing and hourly summaries, and supports wall-clock-duration runs. A separate matched concurrency harness replays one trace at bounded client worker levels and computes throughput from completed calls / measured wall time. Neither has been run against a live testbed here.
- Added deterministic `synthetic_25`, `synthetic_50`, and `synthetic_100` grid topologies with stable node profiles and connected grid adjacency. The benchmark and v11/ablation training CLIs accept these sizes; benchmark manifests now record node/edge counts and synthetic status, and exhaustive pair search is disabled on synthetic sweeps. The synthetic graph supports topology-size measurement in the current pair-level simulator; it does not add full-chain routing semantics. No synthetic model has been trained or evaluated yet.
- The load-sweep runner can now seed fixed-profile active background chains after every matched reset, independently from offered arrival rate and live API concurrency. It supports repeatable 0/25/50/100 chain conditions, records the seeded population/profile, and rejects populations that exceed per-node CPU/RAM capacity. This is a simulation workload control; no active-chain sweep has been run yet.
- Replaced the old P4 MSD script, which only compared SID counts in Python while claiming switch enforcement, with an actual BMv2 packet harness. It injects an over-depth packet and a boundary-depth packet, checks egress capture and the existing violation counter, and writes PCAPs plus a JSON record including compiled JSON/source hashes and verifies the compiled SID-stack size matches the requested MSD. It states that runtime admission is outside this data-plane test. The harness syntax/profile were checked, but no live BMv2 packet run has occurred. Run instructions and evidence limits are in `infrastructure/sdn/p4/README.md`.
- Migration rollback now releases a replacement's local resource reservation only after the terminate request is followed by an explicit Kubernetes observation that both its Deployment and matching Pods are absent. Failed/unavailable termination or inconclusive Kubernetes state retains the reservation. A MAKE-start failure uses the same absence check. Unit tests cover confirmed deletion and inconclusive presence.
- Earlier checks (before the legacy adapter): 57 revision tests passed; the old Vietnam preflight rejected the recovered main checkpoint because the `2N` and `N²` heads differed. The later offline loader and current runtime adapter resolve that shape mismatch. These earlier test counts and missing-artifact observations are historical and do not describe the current checkout. The short NSFNET smokes were code checks, not experimental results.

## Still open before E1 can close

- Measure MBB peak occupancy and verify deployment failure/rollback against a live Kubernetes testbed; local tests now check reservation release only after confirmed absence and retention when state is inconclusive.
- Audit full pair → SID generation → P4/controller realization and topology-specific MSD meaning; current contract is pair-level and does not claim full chain realization.
- Evaluate the three retained main v11 checkpoints through the validated factorized-to-pair adapter, with pinned model and normalizer hashes. The `train_v11 --topology all` option remains available but is not part of the chosen no-retraining path.
- Pin and preflight the retained ablation checkpoints for Vietnam, NSFNET and GEANT2; distinguish any absent variant from a compatible retained artifact.
- Run the matched evaluation protocol with retained checkpoints under the corrected evaluator and label results as legacy-policy evaluation. The changed MSD semantics mean these runs cannot be described as training under the corrected semantics.
- Pass the ten-seed primary protocol end-to-end without a training stage, then decide which manuscript claims the resulting evidence actually supports.
- Run the topology-size (10/25/50/100 nodes) sweeps after training size-matched checkpoints; verify normalized offered load and report node/edge count, memory and timing. Run the active-chain-count sweep on matched traces separately from live concurrent API load. The live concurrency harness covers simultaneous API requests, while decision-stage timing instrumentation exists for the current supported topology/policy runners.
- Add a K-sensitivity runner only if a candidate-path cache is introduced; no such cache exists in the current runtime.
- Complete controlled over-MSD/P4 evidence, MBB steering confirmation/rollback checks, and run the multi-hour/24-hour HIL protocol. Harness support is present, but these require the deployment/testbed and cannot be replaced by Gym smoke runs.
- Add distinct telemetry-source timestamps/versions if upstream telemetry timestamps are available; current optional TTL measures time since local ingestion and the default remains disabled.
- Run API tests in an environment with its optional dependencies and execute the remaining requirements in `todo.md` before marking tasks complete.

Only short smoke runs were performed. No research-scale revision experiment, Kaggle run, HIL run, commit, or push has been performed in this continuation.

## Continuation: pair-to-actuation audit — 2026-11-16

- Added `PAIR_ACTUATION_AUDIT.md` and a SHA-256 source manifest. The admitted synthetic SID list is returned in the API but not handed to migration steering, which builds a different endpoint SID. Pair-to-forwarding soundness remains unverified.
- Recorded conditional actuation (DRL plus forecast alert), the direct P4 rule endpoint outside pair admission, and uncorrelated controller confirmation. Updated manuscript scope and the local version-check description accordingly.
- Ruling: retain pair-level scope rather than implement an unvalidated controller/chain mapping. Cost if wrong: understating capability until correlated evidence exists. E1/E6 remain open; no training or live experiment was run.

### Controller fail-closed correction

- Fixed `SDNController.bootstrap`: unknown switches now make the install fail, so `steer` cannot confirm success or remove old rules in that case.
- Regression test reproduced false success before the fix; `python -m unittest discover -s tests/rev1 -p test_controller_steering.py -v` passes both unknown-switch and successful-install cases after the fix. `git diff --check` passes.
- Attempt to run admission/hybrid pytest checks with `src/portal/backend/env/bin/python` could not start: that interpreter lacks pytest. No full-suite pass is claimed for this continuation.
- Code freeze is not ready: admitted-list/steering correspondence and request-correlated confirmation still need implementation/verification before stronger runtime claims.

## Continuation: migration confirmation hardening — 2026-11-16

- Controller status now includes replacement name and operation ID; the migration service generates a fresh UUID and requires an HTTP 200 plus matching identifiers and a boolean confirmation before BREAK. Legacy/global or unrelated confirmations are ignored.
- Serialized complete steering operations using a separate execution lock while keeping status reads available. Empty steering rule sets, unknown switches and installation exceptions fail closed.
- Replaced import-time asyncio migration lock with a lock created in the serving event loop; enabled HTTP regression tests exposed the Python 3.9 import failure after an earlier loop had closed.
- Removed unmeasured zero-loss/nanosecond statements from migration logs/comments. Success output includes the steering operation ID.
- RED→GREEN evidence: correlation test initially consumed the first stale response; now consumes all four responses before BREAK. Concurrent controller test initially installed the second operation during the first; now serializes. Empty-rules and installation-exception tests initially failed; now reject.
- Verification: `venv/bin/python -m pytest tests/rev1 tests/test_state_manager.py tests/test_hybrid_decision.py tests/test_orchestration_api.py -q` outside sandbox: 89 passed, no skips, 14 third-party matplotlib/pyparsing warnings. Sandbox TestClient stalled in cross-thread event-loop wakeup; those runs were interrupted and the same suite completed outside sandbox.
- Installed pytest 8.4.2, FastAPI 0.115.12 and httpx 0.28.1 in the existing repository venv for verification. No live testbed or long experiment was run.
- Still open: admitted realization vs steering payload; uncertain steering timeout/rollback; input packaging/protocol and freeze gate. A controller success flag is not packet evidence.

## Continuation: uncertain steering and reservation lifetime — 2026-11-16

- Removed destructive rollback on steering POST timeout/exception and non-202 response. These responses can follow partial or completed installation. The service now polls the same operation and preserves both endpoints unless correlated confirmation authorizes BREAK.
- Unconfirmed outcomes return/log `STEERING_UNCERTAIN`, replacement/old names, operation ID, elapsed time and submission state. The background workflow's returned recovery record still needs durable retrieval/integration before this recovery interface is considered complete.
- Kubernetes sync no longer discards pending reservations after 60 seconds, drops charges on a transient missing deployment entry, or forgets anonymous reservations during resource rebuild.
- Ruling: retain unconfirmed allocations until explicit confirmed cleanup rather than expire them. Cost: stranded capacity needs reconciliation; automatic expiry could overbook a still-live replacement.
- Six new regressions were observed failing before their fixes (three steering submission outcomes, pending expiry, anonymous retention and disappearing deployment entry). Full verification outside sandbox: `venv/bin/python -m pytest tests/rev1 tests/test_state_manager.py tests/test_hybrid_decision.py tests/test_orchestration_api.py -q` → 95 passed, no skips, 14 third-party warnings.
- No live steering, packets, long experiment or code freeze occurred. Remaining code work includes durable recovery records, BREAK failure handling, removing synthetic resource-state reconstruction, admitted-realization binding, packaging/protocol and final freeze validation.

## Continuation: durable recovery and BREAK verification — 2026-11-16

- Added a SQLite migration event journal; production container wiring uses `CORE_ROUTER_MIGRATION_JOURNAL` or `results/rev1/runtime/migrations.sqlite3`. Writes are committed before MAKE and steering submission. A persistent volume is required across container replacement.
- Added `GET /orchestrate/migrations/{replacement}` and a status path in scheduled migration responses. Terminal/background outcomes, controller payload and operation IDs can now be recovered after reopening the journal. Recorded running stages are not proof of a live process.
- Journal transactionally claims each replacement once; repeated requests, including separate workers on the same database, do not repeat MAKE or overwrite an earlier recovery record. Storage failure before MAKE prevents infrastructure mutation.
- BREAK failure now reports `BREAK_FAILED`; accepted deletion without confirmed Deployment/Pod absence reports `BREAK_UNCONFIRMED`. Only confirmed old absence releases the old local reservation and reports COMPLETED. Unexpected errors/cancellation are journaled as uncertain without destructive cleanup.
- RED→GREEN: duplicate execution test initially ran MAKE twice; BREAK error/absence tests initially reported success and never released confirmed-old reservations. Tests now pass. Reopen/copy isolation, two-worker claim, storage-failure and HTTP lookup checks are included.
- Final suite outside sandbox: `venv/bin/python -m pytest tests/rev1 tests/test_state_manager.py tests/test_hybrid_decision.py tests/test_orchestration_api.py -q` → 104 passed, no skips, 14 third-party warnings. Changed Python files compile; `git diff --check` passes.
- Read `RUNTIME_RECOVERY.md` for semantics and limits. Journal recovery does not yet restore local reservations after restart, nor establish admitted-SID/steering equivalence. Synthetic resource reconstruction and protocol/packaging/freeze checks remain open. No live testbed or code freeze performed.

## Continuation: real resource reconciliation — 2026-11-16

- Removed sin/cos fake resource load from runtime Kubernetes sync and stopped erasing observed MSD. CPU/RAM now conservatively combine measured utilization and tracked local charges; sync and fresh telemetry preserve pending and anonymous charges.
- Replaced fabricated 10 CPU / 5 RAM / 2 SID defaults for unknown deployments with explicit unknown accounting. Admission rejects unresolved profiles and public state exposes `unaccounted_vnfs`.
- Ruling: observations plus local charges until source telemetry can identify included allocations. Cost: deployed load can be counted twice and acceptance can be conservative. Do not represent this as exact live occupancy or simulation equivalence.
- TTL freshness is per CPU/RAM/MSD field; a missing field is stale. Invalid/nonfinite/negative resource samples and invalid node IDs are rejected atomically.
- Six new regressions were observed failing before implementation, including telemetry erasure, invented load, erased reservations, fabricated unknown profiles, partial telemetry freshness and invalid sample mutation. Updated obsolete tests that expected fake background utilization.
- Verification outside sandbox: full revision/state/hybrid/HTTP suite → 110 passed, no skips, 14 third-party warnings; `py_compile` and `git diff --check` pass.
- Next source gaps include durable restoration/reconciliation of reservation profiles, named TTL release/HIL lifecycle accounting, realized steering binding and deterministic phase packaging/freeze validation. No long experiment or code freeze was performed.

## Continuation: named TTL and HIL lifecycle accounting — 2026-11-16

- Added optional request identity to expiry API; selection-only reservations release by name idempotently, without affecting another same-tuple request. Actuation intent is marked before background scheduling and blocks unverified TTL release; sync preserves that marker.
- HIL runner includes identity and retains/retries failed expiry requests rather than forgetting them. Removed post-cleanup ledger reset. Reset refuses unresolved actuation/deployment records and the runner stops on refused/unavailable initial reset.
- Runtime sync now exposes positive replica-based deployment readiness. HIL no longer treats `is_pending=False` (object observed) as deployment success. Missing observations clear readiness while retaining allocation.
- RED→GREEN: named HTTP expiry previously released nothing; actuation marker did not exist; HIL forgot rejected releases; readiness counted pending deployment; reset cleared actuation charges. New regressions cover these failures plus marker/readiness preservation through sync.
- Verification: full revision/state/hybrid/HTTP suite outside sandbox → 116 passed, no skips, 14 third-party warnings. Changed Python files compile and `git diff --check` passes.
- Remaining lifecycle work: correlate HIL migration completion with journal, verify deployed TTL teardown/de-steering, restore reservation profiles after process restart, and finish admitted-realization binding. No live testbed, long training or code freeze occurred.

## Continuation: journal-correlated HIL and counter integrity — 2026-11-16

- HIL now polls `/orchestrate/migrations/{replacement}` instead of the global latest pipeline. Completed migration requires matching old/new names, a nonempty consistent operation ID, success, CONFIRMED steering and COMPLETED recovery state. Recovery outcomes and journal timeout are exported separately. Fresh deployment is no longer counted as a migration trigger.
- Added per-request migration completion/operation/recovery fields and `completed_migrations` summary. Legacy `successful_migration_pipelines` now mirrors verified completed migrations for compatibility; it no longer interprets arbitrary pipeline success as migration evidence.
- Thrift counter failure/unparseable output now returns unavailable (`null`), not zero. HIL rejects missing/invalid/empty counter snapshots, endpoint failures and decreased/reset totals. Raw request/hourly CSVs are written before the final counter validation, preserving evidence if the final read fails.
- RED→GREEN: unrelated latest pipeline previously counted as completed; migration journal waiter did not exist; fresh deployment counted as migration; nine failed counter cases previously yielded numeric evidence. The regressions now pass.
- Full suite outside sandbox: 133 passed, no skips, 14 third-party warnings. One additional raw-preservation test was then added; the counter evidence file passes all 13 cases including it. Changed Python files compile and `git diff --check` passes.
- Remaining before freeze: restart reservation recovery, deployed TTL teardown/realization binding, phase packaging/protocol and final review/smokes. No live controller/HIL experiment or freeze was performed.

## Continuation: durable reservation restart recovery — 2026-11-16

- Added `ReservationStore` with atomic SQLite snapshots and exclusive local process ownership. Production container restores it via `CORE_ROUTER_RESERVATION_DB` (default `results/rev1/runtime/reservations.sqlite3`) before infrastructure integrations. Direct test/simulation managers remain in-memory unless configured.
- Snapshots bind topology names/MSD/adjacency/latency and preserve named, pending, anonymous, actuation-intent and observed resource records. Resource rebuild is deterministic; fresh telemetry timestamps are intentionally not restored.
- All state-version mutations checkpoint before acknowledgment. Write failure latches new admission closed and is exposed in public state; restart uses the last committed conservative ledger. Duplicate process ownership, corrupt/incompatible profiles and inherited fork writes fail.
- RED→GREEN: constructor/restart/owner/storage-failure tests initially failed because persistence was absent; inherited-owner write test then reproduced fork access before the PID guard. Additional tests verify abrupt subprocess exit recovery and corrupt-profile startup rejection.
- Ruling: one local admission owner per persistent ledger, rather than claim multiworker/distributed atomicity. Cost: one admission worker and synchronous durable-write overhead; include that overhead in live runtime measurements.
- Verification: full revision/state/hybrid/HTTP suite outside sandbox → 140 passed, no skips, 14 third-party warnings; changed source compiles and `git diff --check` passes. No live testbed or code freeze performed.
- Remaining code gates: deployed TTL teardown and admitted realization ↔ forwarding binding; deterministic protocol/source/data/model phase packaging, final review and smoke verification.

## Continuation: explicit phase inputs and code-only scope

- User clarified: finish code only; user will execute experimental phases. Do not start training, research benchmarks, live testbed services or HIL. Regression tests and mocked command/model tests remain authorized.
- Added deterministic `package_inputs.py` and shared canonical source hashing. Training bundles explicitly omit checkpoint inputs; evaluation bundles require all declared model/normalizer files and pin hashes. Verification rejects missing/extra/duplicate entries, path traversal/symlinks, input hash mismatch, changed input bytes and invalid archive contents.
- Artifact checker now uses the same source-selection/hash contract, excluding venvs, caches, hidden directories and compiled build outputs. Protocol source paths include SDN source and regression coverage; torch version is pinned to the inspected runtime.
- Two packaging-only snapshots from an unchanged source state produced byte-identical 181-file archives; later source edits mean that snapshot is not the eventual frozen package. Five package tests cover deterministic behavior, training/evaluation distinction, missing models, tampering, traversal, symlinks and canonical source agreement. No experiment was executed.
- Main v11 trainer now accepts explicit budget, env count, rollout size, seed, dataset and model output. One-env mode uses DummyVecEnv; resources close after training, and interruption is not reported as successful completion. Controls are checked with a mocked PPO/environment, not real training.
- Server read-only inspection is recorded in `SERVER_CONFIG_AUDIT.md`: current account cannot inspect Docker containers, no usable local kubeconfig/standard MicroK8s installation was found, and expected controller/Thrift listeners were absent. Repository topology definitions remain candidate configuration, not proof of instantiated infrastructure. No services were started or modified.
- Verification: full revision/state/hybrid/HTTP suite → 146 passed, no skips, 14 third-party warnings. Changed code compiles and `git diff --check` passes. Input packaging runbook: `PHASE_INPUTS.md`.
- Still required for code freeze: dedicated explicit-input notebook/phase driver, protocol CLI consistency, realization/teardown binding, final review and code-only verification. No code freeze claimed.

## Continuation: per-switch counter coverage

- HIL counter validation now compares the exact switch set and each switch's counter before/after a run. A reset on one switch can no longer be concealed by an increase on another; a disappeared switch invalidates the measurement. Raw request CSV remains available when validation fails.
- Two regression cases reproduced both failures before the fix. `venv/bin/python -m pytest tests/rev1/test_msd_counter_evidence.py tests/rev1/test_testbed_accounting.py -q` → 20 passed. `git diff --check` passed. These are mocked tests; no research experiment or HIL run was performed.
- Code freeze remains open for the explicit phase driver/notebook, realization/teardown binding, protocol consistency and final review.

## Continuation: evaluation package verification

- Verification now requires valid SHA-256 pins for source, dataset and every evaluation model/normalizer, and checks package schema, mode and protocol identity. Previously a null artifact hash could bypass the resolved-protocol check even when archive coverage was valid.
- Regression reproduced the null-hash acceptance before the fix. `venv/bin/python -m pytest tests/rev1/test_input_package.py tests/rev1/test_artifact_contract.py -q` passed 12 tests. No training or experiment was run.
- Freeze remains open for the phase driver/notebook, realization/teardown, protocol consistency and final review.

## Continuation: partial evaluation driver

- Added an explicit protocol-driven command planner for ablation and load sweep. Default behavior only prints commands; `--execute` is opt-in and stops on preflight failure. The driver checks canonical ablation paths and rejects higher-priority shadow files before execution.
- Mocked command tests passed: `venv/bin/python -m pytest tests/rev1/test_phase_driver.py -q` → 3 passed. No training, benchmark or HIL was run.
- This is partial: main comparison benchmark, training orchestration, all-topology coverage, archival, notebook integration and realization/teardown remain open before freeze.

## Continuation: protocol seeds for main benchmark

- Main benchmark accepts explicit unique seed lists; the phase driver now passes the protocol seeds, dataset and pinned main model/normalizer to each scenario benchmark as well as ablation/load sweep. Duplicate seeds and conflicting single-seed options fail before a run.
- `venv/bin/python -m pytest tests/rev1/test_phase_driver.py tests/rev1/test_benchmark_coverage.py -q` → 9 passed. Tests do not execute training, benchmarks or HIL. `git diff --check` passed.
- Training orchestration, cross-topology coverage, archival, notebook integration and realization/teardown remain open.

## Continuation: explicit training command plan

- Phase driver now plans main and ablation new-training commands with separate required budgets, training seed, environment count, rollout size, scenario and isolated revision output. Default remains plan-only. Opt-in execution verifies pinned source/data/dependencies, requires a new output directory and saves the full command/protocol plan first.
- Seven phase-driver tests pass; `py_compile` and `git diff --check` pass. No training or experimental phase was executed. PPO rollout rounding and the ablation trainer's fixed 512-step rollout remain explicit in the runbook.
- Notebook integration, result coverage/archival, realization/teardown and final review remain open.

## Continuation: explicit-input revision notebook

- Added `notebook/rev1-benchmark-ablation-kaggle.ipynb`: the user supplies the exact archive path and external SHA-256; archive paths, package mode and full manifest are verified before moving into a new work root. No auto-discovery or destructive work-root reset. `RUN_PHASE` defaults false, and training requires explicit settings.
- The notebook itself is included in protocol source hashing. The driver still lacks all-topology coverage checks, result archival and the realization/teardown integration; the notebook does not claim those are complete.
- `venv/bin/python -m pytest tests/rev1/test_revision_notebook.py tests/rev1/test_phase_driver.py -q` → 8 passed; notebook cells parse and have no execution counts or outputs. `git diff --check` passed. Notebook, training and experiments were not executed.

## Continuation: new-training outputs to evaluation package

- Evaluation packaging accepts an explicit training run for every protocol topology. It reads checkpoints from each isolated `results/rev1/<run>/models` directory, embeds them at canonical archive paths, and preserves the training plans in the package without altering historical models.
- Training plans now record topology. Packaging rejects absent plans and source/dataset/topology mismatches; individual model hashes and later compatibility preflight remain required.
- `venv/bin/python -m pytest tests/rev1/test_input_package.py tests/rev1/test_phase_driver.py -q` → 15 passed. These are fixture/mocked checks; no training or experiment was run. Coverage/archival validation and realization/teardown remain open before freeze.

## Continuation: result matrix validation primitive

- Added a reusable validator for exact policy × seed coverage within one topology/scenario. It rejects missing, duplicate or unexpected rows, mismatched traces, invalid trace lengths/hashes and zero offered requests when that field is specified.
- `venv/bin/python -m pytest tests/rev1/test_result_coverage.py -q` → 7 passed; `py_compile` and `git diff --check` passed. Tests use fixtures only; no experimental phase was executed.
- This is a validation primitive, not yet the complete cross-topology artifact/manifest audit or result archiver. Those remain open along with realization/teardown and final review.

## Continuation: ablation artifact lineage validation

- Added an ablation-manifest validator that compares topology, scenario, seeds, steps, dataset hash and each variant's pinned model/normalizer hashes against the resolved protocol. Missing, duplicate or mismatched artifacts fail rather than certify coverage.
- `venv/bin/python -m pytest tests/rev1/test_result_coverage.py -q` → 8 passed; `git diff --check` passed. No experimental run occurred.
- The validator still needs integration into a complete cross-topology audit/archiver, alongside benchmark and load-sweep manifest checks. Realization/teardown and final review remain open.

## Continuation: ablation directory validation

- Connected the matrix and lineage validators to the actual `harp_ablation_summary.csv` and `run_manifest.json` filenames. Missing files, zero-offered rows, trace mismatches and pinned dataset/model mismatches fail the audit.
- `venv/bin/python -m pytest tests/rev1/test_result_coverage.py -q` → 9 passed; `git diff --check` passed. Fixtures only; no experiment was run.
- This validates one ablation directory, not the complete cross-topology benchmark/load-sweep audit or archival. Those and realization/teardown remain open.

## Continuation: main result manifest validation

- Added checks for benchmark and load-sweep manifest versions, topology, seeds, steps, dataset hash and pinned main model/normalizer hashes. Unsupported or mismatched metadata fails explicitly.
- `venv/bin/python -m pytest tests/rev1/test_result_coverage.py -q` → 11 passed; `git diff --check` passed. No research experiment was executed.
- File-level matrix integration, cross-topology audit/archival, source provenance and realization/teardown remain open.

## Continuation: benchmark file-level audit

- Added a benchmark-directory audit connecting `run_manifest.json` with the scenario `seed_summary.csv`. It checks the expected workload, model/data hashes and exact policy × seed matrix with matched traces and nonzero requests.
- `venv/bin/python -m pytest tests/rev1/test_result_coverage.py -q` → 12 passed; `git diff --check` passed. Fixtures only; no experiment was run.
- Load-sweep file integration, cross-topology audit, source provenance, archival and realization/teardown remain open.

## Continuation: load-sweep file-level audit

- Added validation of load-sweep manifest and per-seed CSV against the expected load × policy × seed matrix, including matched traces and nonzero offered requests. Unexpected loads or missing rows fail.
- `venv/bin/python -m pytest tests/rev1/test_result_coverage.py -q` → 13 passed; `git diff --check` passed. Fixture checks only; no experiment was run.
- A cross-topology orchestrator/archiver and source-provenance validation remain to be connected, along with realization/teardown and final review.

## Continuation: freeze-gate hardening

- Added immutable `AdmittedRealization` identity (request, operation, topology hash, profile, SID stack) to admission results. The current pair-level profile deliberately has no physical forwarding SID. Alert-triggered actuation now returns an explicit 409 and releases only its still-unactuated reservation; the migration service independently rejects missing realization before MAKE. For supported handles, it checks the resolved endpoint SID and validates controller identity plus the exact admitted SID stack before POST. Mismatch initiates guarded replacement cleanup and does not submit steering.
- Named expiry of an observed deployment now reports `DEPLOYED_TTL_TEARDOWN_REQUIRED` and retains the ledger charge. P4 rule de-steer/delete/readback is still unavailable without a verified switch/profile mapping; this is a fail-closed limitation, not completed deployed teardown.
- Removed dataset resolver fallback from ablation and benchmark paths. Missing pinned data now raises a path-specific `FileNotFoundError`; revised the exhaustive fixture to point directly to the dataset it uses. Evaluation still runs artifact/dataset preflight before any benchmark command.
- Connected cross-topology coverage and source-lineage audit to `phase_driver.py --stage audit`; the stage plans by default and executes only the audit CLI when explicitly requested.
- Added read-only `verify_freeze.py` to report commit/dirty state, Python and dependency versions (including optional `p4runtime-shell`), protocol/package hashes and CLI `--help` contracts. Added the phase runbook in `FREEZE_MANIFEST.md`. Protocol now pre-registers 20 unique evaluation seeds; no 20-seed results are claimed.
- Evaluation now requires the external input archive SHA-256, evaluation package mode, and byte-identical resolved protocol before artifact preflight. The Kaggle notebook passes the same archive/hash through the driver. Added `--stage smoke` with separate `results/rev1/smoke/<run>` outputs, a 1,024-step cap and `smoke_only` provenance; evaluation packaging rejects these runs.
- RED→GREEN focused verification: realization contract/admission 15 passed; migration lifecycle regression 10 passed; unresolved-realization HTTP rejection 1 passed outside sandbox; phase driver, dataset input and lifecycle subset 24 passed; freeze verifier 2 passed. Existing matplotlib/pyparsing deprecation warnings remain. No training, benchmark, simulation data collection, server provisioning or HIL was run.
- Code freeze now uses fail-closed restrictions for unsupported physical operations. Positive forwarding-profile support and deployed P4 teardown/readback remain unavailable and must stay disabled.

### Final code-only check for this continuation

- `venv/bin/python -m pytest tests/rev1 tests/test_state_manager.py tests/test_hybrid_decision.py tests/test_orchestration_api.py -q` → 196 passed, 14 matplotlib/pyparsing deprecation warnings.
- Changed Python sources compile; `git diff --check` passes; phase, package and freeze-verifier `--help` command contracts return successfully.
- Committed all workspace changes as a code-freeze snapshot. Built a fresh training package and ran `verify_freeze.py`; result `ready`, clean tree, package/source/data/config and CLI checks passed. Training package mode intentionally omits missing model checkpoints; no evaluation package or research evidence is claimed.
- No simulation data collection, training, benchmark, server provisioning, controller actuation, or HIL was run. Positive physical steering and deployed TTL teardown remain disabled pending a verified profile and readback workflow.

## Continuation: legacy main-checkpoint action compatibility

- The three retained `main_v11` checkpoints have factorized `2N` action heads, while the current benchmark environment uses flat `N²` placement/route pair actions. The benchmark loader now converts the two N-way linear heads into additive pair logits (`place[p] + route[r]`) before loading, so the existing weights and matching normalizers can be evaluated without retraining. Pair-level action masks still apply after conversion.
- `configs/rev1/protocol.json` declares `factorized_2n` only for `main_v11`; the 15 ablation checkpoints remain explicitly `flat_n2`. Artifact preflight checks the declared encoding and rejects any other dimension. `FREEZE_MANIFEST.md` now lists the present full and ablation artifacts accurately.
- Verification: focused artifact-contract suite 8 passed; 188 tests passed when excluding the HTTP API module. The full 198-test command stalls on the first `TestClient` request; a minimal FastAPI/TestClient request also stalls in this environment, so the 10 HTTP tests could not be verified here. Evaluation package assembled with all 18 model/normalizer pairs and no missing artifacts; artifact preflight reported `ready` with 0 issues; one masked inference from each of the three actual main checkpoints loaded and returned an action inside the N² mask. After commit `42f1c1427397b0731924dadaf11ad404c6c04df4`, `verify_freeze.py` reported `ready`, clean worktree, and passed all CLI contracts.
- No training, ablation run, benchmark collection, simulation result collection, or HIL was run. Evaluation package SHA-256 from this dirty draft is temporary and must be regenerated after the final reviewed commit.

## Continuation: evaluation package verify CLI and phase plans

- Fixed `package_inputs.py --verify`: it now resolves the requested workspace root before validating package inputs. Added a regression for the CLI path that previously raised `UnboundLocalError`.
- The focused artifact/package tests pass (20 passed), and artifact preflight reports `ready` (18 artifacts, 0 issues). All 15 unique ablation checkpoint/normalizer pairs loaded through the exact ablation preflight path; the three main checkpoints also loaded and produced mask-valid pair actions. These checks do not call `env.step` or collect results.
- Created an evaluation bundle at `results/rev1/inputs/rev1-evaluation-inputs.zip` with the extracted resolved protocol alongside it. The archive SHA-256 is `086d6ab67ad714de60bb9ec67a03dd2a255c53d0be92b878f55dba0ffc43deb0`; package CLI verification and exact protocol matching pass. Plan-only driver commands for Vietnam, NSFNET, and GEANT2 each produced 11 commands with `execute=false`.
- Full regression caveat remains: 188 tests pass without `tests/test_orchestration_api.py`; the first HTTP test stalls in this runtime, and a minimal FastAPI/TestClient request reproduces the stall. No training, ablation results, benchmark results, or HIL were run.

## Completed current-code load sweep — 2026-11-17

Vietnam, NSFNET and GEANT2 completed in separate tmux sessions. Validated 1,120 rows per topology, all 7 intensities and 8 policy modes, 20 seeds per group, paired trace hashes and current source hashes. Updated rev1.tex with a three-topology figure, all 21 protected-policy summary rows, family-wide Holm statistics and scoped Abstract/Conclusion findings. Reproducible scripts: scripts/rev1/plot_manuscript_load_sweeps.py and summarize_manuscript_load_sweeps.py. All-mode evidence: evidence/load_sweep/. No LaTeX compilation performed.

## Editorial refinement after load sweep

Rewrote evaluation framing, policy-regime interpretation, computation discussion and two-paragraph conclusion; consolidated limitations and removed audit-style completion/archive wording. Preserved numerical tables, the four single-column table layouts, and existing Overleaf overview/testbed paths. HARP–SAF-H timing benefit remains unestablished under controlled matched execution; no favorable cost claim added. Static TeX reference/environment checks and git diff --check passed; no PDF compilation performed.
