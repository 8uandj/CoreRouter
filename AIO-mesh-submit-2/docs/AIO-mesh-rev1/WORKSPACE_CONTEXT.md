# Current context override — 2026-11-16

Người dùng làm rõ chronology: `todo.md` là yêu cầu ban đầu; draft `rev1.tex` từng nhận số liệu không có nguồn và đã được khôi phục/audit; mentor sau đó đưa `todo-2.md`. Không coi số liệu cũ trong draft hoặc completion ticks là evidence. Người dùng xác nhận bộ kết quả chính từ nay là các retrain mới và benchmark mới; log training bản cũ không cần làm dữ liệu chính. Ablation hiện có được giữ vì các biến thể đã dùng action space flat N²; không cần retrain chỉ để đồng bộ action space. HIL ở server khác. Tình trạng hiện tại: sáu checkpoint retrain mới đã xác minh là `Discrete(N²)`, benchmark sáu topology đang chạy, chưa có tổng hợp hoàn tất. Các checkpoint main cũ 2N vẫn được giữ làm artifact lịch sử/compatibility, không trộn vào bộ kết quả chính mới. Chi tiết ở `REVISION_STATUS.md`, `SEMANTICS_CONTRACT.md`, và evidence dưới `results/evidence/multinode_benchmark_20261120_084017/`.

---

# Workspace context — 2026-11-16

## Authoritative code

User confirms `https://github.com/8uandj/CoreRouter`, branch `HARP`, is the latest code. No local-machine reconciliation is required. Workspace synchronized to `1b7ef37fb9cdce401609697307bdcc6e9bf2fe20` (2026-06-18 UTC). Git metadata restored from a fresh clone. HARP tracks origin/HARP; active server refactoring branch is now HARP-server.

At initial synchronization, verified all 290 upstream tracked files byte-for-byte; updated 25 and added 94 missing files. Subsequent HARP-server changes are described in `docs/REFACTOR_HARP_SERVER.md`. Workspace-only files retained, including revision/submitted/thesis documents, models, data and results. These retained files are not certified as part of the upstream commit; extra scripts may be older. Backup and exact inventory: `.workspace-sync/20261116T092111Z/manifest.json` and its sibling `backup/`. No training, benchmark or deployment was run during synchronization.

## Document lineage

- Original thesis: `docs/thesis_JOVPPM`, method JO-VPPM (user-designated canonical origin, confirmed 2026-11-16). `docs/thesis_latex` is retained historical material.
- Expanded submitted paper: `docs/AIO-mesh-submitted 1/submitted-1.tex`, method HARP, framework AIO-Mesh; journal Future Generation Computer Systems.
- Current major revision: `docs/AIO-mesh-rev1/review.txt`, `todo.md`, `todo-2.md`, `refs.bib`.
- `docs/AIO-mesh` and `docs/note` remain historical references; use the user-designated thesis → submitted → Rev1 lineage above.
- No revision manuscript `.tex` is currently present in the revision folder, despite checklist references to `AIO-Mesh.rev1.tex`.

## Reviewer priorities

Reframe novelty around the runtime admission contract and MSD-aware deployability; HARP is replaceable. Isolate runtime safety using protected baselines. Audit Elephant/Chaos generators, matched seeds, significance, acceptance accounting and ablation attribution. Clarify pair versus full-chain action semantics, SID/MSD realization, mask complexity, feature normalization, stale state, hybrid gate, latency/scalability/concurrency and conditional K-cache claims. Long-running HIL, migration and fault-injection claims require raw evidence. Review abbreviation consistency and shorten the conclusion.

## Evidence cautions

`todo.md` lists many experiments/artifacts as pending, while `todo-2.md` ticks most E1–E6 tasks complete. Reconcile these states against raw artifacts, source/config versions, seeds and logs before accepting completion. Never fabricate numbers or infer evidence from checklist ticks. Submitted results remain historical baseline until replacements have provenance.

Revision notes reference a different source state and are not proof about synchronized HARP. Example: current simulation env uses Discrete(N*N), but lists uniform/bursty/heavy_tail with no explicit chaos generator branch. Runtime contains 0.45/0.35 hybrid thresholds and try_reserve; existence alone does not establish full-chain or end-to-end safety. Re-audit source claims before editing the manuscript.

## Next task

Map reviewer concerns to synchronized source and available artifacts, reconcile both checklists, then prepare the revised manuscript and response. Synchronization does not complete revision experiments or validate reported results.

## Server refactor status

Branch `HARP-server` now separates HTTP/forecast/actuation from the hybrid selection/admission service, removes the unregistered duplicate orchestration implementation, shares runtime settings and consolidates the Docker build/dependencies. Ten redundant files were removed with reversible backups; historical research artifacts are retained. Fifteen unit/HTTP regression checks pass. Frontend build and live HIL/benchmark validation remain unperformed. This does not close reviewer experiment tasks.

## HARP-model artifact recovery — 2026-11-16

Fetched `origin/HARP-model` at `19534b0489c532be46bd4fb540acf83019ac3c8d`. Full 749-file historical snapshot retained under `results/historical/HARP-model/19534b0489c5/snapshot/`. Restored all 160 files from its `CoreRouter/results/` to workspace `results/`, with 38 differing local files backed up. See `HARP_MODEL_ARTIFACT_AUDIT.md` and `HARP_MODEL_ARTIFACT_MANIFEST.json`. This recovers historical evidence; it does not establish runtime compatibility or complete reviewer experiments.

## Source comparison and latest artifact update

Latest fetched HARP-model commit: `1badfd486d5d303ecdeba2f04cd7626163b3a8bd`; adds Vietnam ablation results (66 files). Latest full snapshot: `results/historical/HARP-model/1badfd486d5d/snapshot/` (815 files). All top-level ablation result folders are accessible under `results/ablation/HARP-model/`. GEANT2/Vietnam evaluation outputs exist; their ablation training checkpoints are not present in the fetched tree. Main source comparison: 138 identical, 12 different, 12 current-only, 4 snapshot-only files in the stated code/config scope. Bundled `kaggle_harp_update/src` is a different source version (68 identical, 7 different mapped Python files), including model selection and metric accounting differences. See `HARP_MODEL_CODE_AUDIT.md` and machine-readable comparison before deciding which source produced submitted results.

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
