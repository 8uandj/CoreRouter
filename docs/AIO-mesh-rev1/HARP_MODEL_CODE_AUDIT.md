# Source comparison against HARP-model

Reference commit: `1badfd486d5d303ecdeba2f04cd7626163b3a8bd`.
Current branch: `HARP-server`, HEAD `0329531b8fe150a8f707e149115f9a1f69f91079`; compared actual workspace bytes.

## Scope and result

Main historical tree: `results/historical/HARP-model/1badfd486d5d/snapshot/CoreRouter/`. Compare tracked current files with source/config in historical `src/`, `scripts/`, tests and root scripts/config. Exclude generated assets/caches, documentation, data/results and bundled Kaggle copy from the main count.

| Status | Files |
| --- | ---: |
| identical | 138 |
| only_current | 12 |
| different | 12 |
| only_snapshot | 4 |

The trees are not identical. This is a byte comparison, not a runtime equivalence test. Full per-file SHA-256 values are in `HARP_MODEL_CODE_COMPARISON.json`; unified differences of common changed text files are in `HARP_MODEL_CODE_DIFF.patch`.

## Research-critical findings

- `train_v11.py`, `train_harp_ablation.py`, `ablation_study.py`, `gnn_policy.py`, `dgrl_agent.py`, `state_manager.py`, and root `requirements.txt` are byte-identical. Topology/reward modules and main benchmark algorithms/config/metrics/model loader are also identical according to the manifest.
- `src/orchestration/jo_vdpr/env.py` differs: current code exposes the previously fixed CPU alert threshold as `alert_cpu_threshold=0.80` and adds optional `inference_sla_threshold=None`, which rejects above-threshold latency when enabled. Defaults preserve those particular conditions; changing the thresholds can change observations, admission and results. Both trees already declare flat `Discrete(N*N)`; this recovery did not convert either action space.
- `kaggle_harp_ablation_cells.py` differs substantially: historical notebook evaluates three scenarios across five seeds, load sweep and algorithm benchmark. Current notebook calls `ablation_parameter_sweep` for heavy-tail and five seeds. It must not be treated as the exact historical experiment driver.
- `kaggle_notebook_cells.py` differs: historical file is Vietnam benchmark-only; current file trains NSFNET/GEANT2 and benchmarks. Historical `kaggle_train_benchmark_v11_cells.py` exists only in snapshot.
- Main `run_load_sweep.py` only differs by suppressing the plot title. The README adds HARP naming/SAF-H and a caveat that Chaos and Elephant resolve to the same heavy-tail generator; main benchmark logic matches the historical tree.
- Backend differences follow the server refactor: selection/reservation extracted into `app/services/hybrid_decision.py`, duplicate unregistered router removed from `ai.py`, shared settings centralized, Dockerfile/dependencies consolidated. Main agent and state-manager files still match, but this does not prove identical HTTP/HIL behavior.

## Bundled Kaggle source is a separate version

Snapshot also includes `CoreRouter/kaggle_harp_update/src`. Mapped to current `src`, 68 Python files are identical and 7 differ. This bundle must not be silently treated as the main `CoreRouter/src`.

- Bundled benchmark `algorithms.py` lacks SAF-H, labels the learned method `jo_vppm` rather than `harp`, and returns empty metrics on missing model instead of raising the main-tree error.
- Bundled `config.py` selects main v11 models directly; main/current code prefers `models/ablation/harp_full` where available. Restoring the NSFNET ablation model can therefore change which checkpoint an otherwise unchanged benchmark selects.
- Bundled `metrics.py` reads `msd_violation`; main/current reads `admitted_msd_violation`. These are different accounting choices.
- Bundled `run_all.py` has the older algorithm list without SAF-H. Env, shared config and load-sweep file also differ.
- Matching source files do not establish which of these copies actually generated each CSV. Record the experiment entry point, resolved model path, seed/config and source hash before interpreting results.

## Data check

`data/real_telecom_combined.csv`, `data/telecom_trace.csv` and `data/dataset_summary.json` are byte-identical between current workspace and the historical main tree. No dataset was replaced.

## Non-identical paths

- `convert_to_figma_svg.py` — only_current
- `deploy_helper.sh` — only_current
- `harp_benchmark_full.py` — only_current
- `kaggle_harp_ablation_cells.py` — different
- `kaggle_notebook_cells.py` — different
- `kaggle_train_benchmark_v11_cells.py` — only_snapshot
- `plot_pareto_design_space.py` — only_current
- `requirements-dev.txt` — only_current
- `run_backend_docker.sh` — different
- `run_simulation.sh` — only_current
- `src/analytics/ablation_parameter_sweep.py` — only_current
- `src/analytics/benchmark/benchmark_algorithm/README.md` — different
- `src/analytics/benchmark/benchmark_algorithm/run_load_sweep.py` — different
- `src/analytics/benchmark_eval.py` — only_current
- `src/analytics/dataset_generator.py` — only_current
- `src/orchestration/jo_vdpr/env.py` — different
- `src/portal/backend/Dockerfile` — different
- `src/portal/backend/Dockerfile.py311` — only_snapshot
- `src/portal/backend/app/core/config.py` — different
- `src/portal/backend/app/routers/ai.py` — different
- `src/portal/backend/app/routers/orchestration_router.py` — different
- `src/portal/backend/app/services/hybrid_decision.py` — only_current
- `src/portal/backend/requirements.txt` — different
- `src/portal/frontend/src/assets/react.svg` — only_snapshot
- `src/portal/frontend/src/views/Monitoring.jsx` — only_snapshot
- `src/shared/config.py` — different
- `tests/test_hybrid_decision.py` — only_current
- `tests/test_orchestration_api.py` — only_current

No source file was overwritten or merged during this comparison. No training, inference, benchmark, or HIL run was performed.

## User-confirmed Vietnam experiment notebook

On 2026-11-16 the user identified `notebook/vietnam.ipynb` as the notebook used on Kaggle to generate Vietnam results. SHA-256 at inspection: `2871629c634807ceeb69457c356764866578ab0fd91e3e22460c71daa4770f8a`. This supersedes inference from similarly named root Python notebook exports when identifying the Vietnam experiment driver.

Inspected configuration: `WORKER_TOPOLOGY="vietnam"`; ablation evaluation 3,000 steps for uniform/bursty/heavy_tail and seeds 42, 100, 2024, 8888, 9999. Training command calls `train_harp_ablation --variant all --scenario heavy_tail --total-steps 500000 --n-envs 4 --seed 42`, unless its existing-model compatibility check skips training. Cell 5 computes per-scenario/per-variant mean and pandas sample standard deviation across evaluation seeds. Cells 6 and 7 call the load sweep and algorithm benchmark respectively; the latter uses CLI defaults for steps/seeds rather than forwarding ablation STEPS/SEEDS. Cell 8 packages worker results, benchmark CSVs and load-sweep outputs, without explicitly exporting `results/models/ablation` checkpoints. Thus downloaded result folders need not contain trained checkpoints.

User-confirmed historical usage is recorded separately from executable evidence: the supplied notebook has no execution counts or saved cell outputs. It selects the first matching attached source package and can merge missing files from other attached result folders; dependencies are unpinned. The exact Kaggle input dataset/version and resolved source/checkpoint hashes remain to be established. The notebook establishes the intended driver/protocol, but by itself does not choose between historical `CoreRouter/src` and `CoreRouter/kaggle_harp_update/src` or certify the exact checkpoints used. No notebook cells were executed or modified during inspection.

## User-confirmed Kaggle source package for Vietnam

On 2026-11-16 the user confirmed that the source package attached to the Vietnam Kaggle run was the `CoreRouter/` folder on branch `HARP-model`. Combined with the earlier confirmation, the historical experiment lineage is: `notebook/vietnam.ipynb` → `HARP-model:CoreRouter/` → Vietnam outputs recovered under `harp_ablation_vietnam/`. This resolves the package-selection uncertainty above at the folder level. Use the main `CoreRouter/src` tree as the historical source reference, rather than treating `CoreRouter/kaggle_harp_update/src` as an equally likely source. The notebook's module commands execute from `/kaggle/working/CoreRouter`, consistent with that main source tree.

The latest recovered reference is commit `1badfd486d5d303ecdeba2f04cd7626163b3a8bd`; its `CoreRouter/` tree is unchanged from the previously recovered `19534b0489c532be46bd4fb540acf83019ac3c8d`. The user confirmed the folder/branch, not an immutable historical Kaggle dataset version or commit. Do not claim the latest reference commit was necessarily the exact run-time commit. Missing exported ablation checkpoints remain a separate artifact gap. Existing code comparison against `CoreRouter/` is the relevant comparison for this confirmed package. No source, notebook, or experiment result was changed.

## User-confirmed shared experiment pipeline across three topologies

The user clarified on 2026-11-16 that Vietnam, NSFNET and GEANT2 runs all used the same source package (`CoreRouter/` on `HARP-model`) and the same notebook workflow, with only a few topology-specific configuration changes. `notebook/vietnam.ipynb` is the supplied representative notebook for this shared workflow; do not limit its provenance to Vietnam or infer separate source implementations from the names of result folders. Historical main `CoreRouter/src` is the common reference for all three topologies.

Exact per-topology configuration differences have not yet been enumerated by the user or fully recovered from run metadata. The inspected Vietnam values (including 500,000 training steps) must not automatically be assigned to NSFNET/GEANT2. Compare available configs/artifacts to establish the actual topology, training budget, seeds and other overrides for each run. This clarification establishes common source/workflow lineage, not identical configuration values or complete checkpoint availability. No code, notebook or numerical result was modified.
