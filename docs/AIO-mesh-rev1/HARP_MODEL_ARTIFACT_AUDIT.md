# HARP-model artifact recovery

Source: `origin/HARP-model`, commit `19534b0489c532be46bd4fb540acf83019ac3c8d`.
Recovered on 2026-11-16; working branch remains `HARP-server`.

## Document lineage

User-confirmed origin: `docs/thesis_JOVPPM` → `docs/AIO-mesh-submitted 1/submitted-1.tex` → revision in `docs/AIO-mesh-rev1`.
No manuscript or experiment implementation was changed in this recovery.

## Locations and coverage

- Complete historical branch snapshot: `results/historical/HARP-model/19534b0489c5/snapshot/` (749 files, 590,527,313 bytes). Includes historical source/config/data alongside artifacts for provenance inspection; it is not merged into the current source.
- Main v11 models: `results/models/v11/`, including Vietnam, NSFNET, GEANT2 ZIPs, matching PKL normalizers, Vietnam NPZ and expanded model files.
- Ablation models: `results/models/ablation/`. Five NSFNET variants: full, without GAT, without hard masking, without adaptive penalty, soft MSD penalty. Each has final ZIP + normalizer + eight checkpoints at 250k through 2M steps: 40 intermediate checkpoints total.
- Three-topology 5-seed ablation summaries: `results/ablation/5 seeds/`, 18 rows per topology.
- Historical benchmark: `results/benchmark_algorithm/20260617_201432/`; combined CSV has 60 NSFNET rows. Testbed artifacts: `results/benchmark_testbed/20260517_201632/`.
- Additional raw ablation, figures and benchmark outputs remain in snapshot top-level `harp_ablation/`, `harp_ablation_results_nsfnet/`, `harp_ablation_geant2/`, and `harp_ablation_results_nsfnet.zip`. NSFNET raw CSV has 90 rows (3 workloads × 6 variants × 5 seeds). Duplicate copies are retained with original paths; do not count duplicates as independent runs.
- Historical paper CSVs: snapshot `CoreRouter/docs/AIO-mesh/results/`.

All 160 source `CoreRouter/results/` files were mapped to their normal workspace paths: 110 added, 12 identical, 38 replaced after backup. Backups: `results/historical/HARP-model/19534b0489c5/backup/`. In particular the local Vietnam model ZIP differed and was backed up before replacement; its normalizers were identical. The manifest records every source blob, SHA-256, size, destination and applicable backup path.

## Evidence limits before revision

- Recovered main model ZIP metadata identifies MultiDiscrete action spaces. The current trainer and benchmark use flat `Discrete(N²)`, and the production adapter has now been aligned to that interface with a flat N² pair mask/action decoder. The recovered MultiDiscrete checkpoints remain incompatible and require retraining; Vietnam model reports SB3 2.8.0 and 2,001,920 timesteps, while NSFNET and GEANT2 report SB3 2.3.2 and 3,000,320 timesteps.
- Branch contains no Vietnam/GEANT2 ablation training checkpoint sets corresponding to the NSFNET set. Three-topology aggregate CSVs do not replace those missing checkpoints or raw per-seed results. No separate trained checkpoint for unchecked/no-migration variants was found in the ablation model directory.
- Vietnam Full safe acceptance summary rounds to the submitted values: uniform 18.90, bursty 18.74, heavy-tail 17.89. Fresh comparison also confirms heavy-tail MLP 16.57 ± 0.53, latency 3.29 ± 0.19, and NoAdapt 16.06 ± 0.43. This checks selected aggregate values, not every manuscript cell or the underlying provenance.
- GEANT2 `chaos` and `heavyTail` JSON results in the snapshot share the same Git blob; this is duplicate evidence requiring workload/provenance audit.
- No training, benchmark, inference, or HIL run was executed. Checklists do not certify these recovered historical results as revised experiments.

`results/` is Git-ignored. The audit/context/manifest are reviewable documentation; binary artifacts remain local and on the source branch unless explicitly packaged later.

## Integrity verification

Verified all 749 snapshot files and all 160 installed result files (909 copies) against manifest SHA-256 and sizes. All 49 source ZIP archives passed CRC checks. All 38 backup paths exist. Runtime compatibility remains untested.

## Update: latest remote and Vietnam recovery

Remote advanced from `19534b0` to `1badfd486d5d303ecdeba2f04cd7626163b3a8bd`, adding exactly 66 files under `harp_ablation_vietnam/`. All previous branch files are unchanged. Latest full snapshot contains 815 files (596,254,415 bytes), at `results/historical/HARP-model/1badfd486d5d/snapshot/`. The previous snapshot and its recovery manifest/backups remain intact.

Both `harp_ablation_geant2` and `harp_ablation_vietnam` contain evaluation artifacts. Accessible copies of all top-level ablation folders/archive are now under `results/ablation/HARP-model/`, preserving original folder names. Vietnam contains 90 raw ablation rows across 3 scenarios × 6 variants × 5 seeds, plus 60 benchmark rows; GEANT2 contains 17 CSV/JSON/figure artifacts, without a raw 5-seed CSV in that folder. Neither folder contains model ZIP/PKL/PTH checkpoints. The absence claim above concerns training checkpoints for those topologies, not the presence of ablation results. Earlier wording must not be interpreted as saying those result folders are absent.

The latest manifest supersedes the initial file inventory; the initial backup mapping is retained at `results/historical/HARP-model/19534b0489c5/manifest.json`. Main `CoreRouter/results/` was unchanged in the update, so its 160 destination files were already identical. See `HARP_MODEL_CODE_AUDIT.md` for the source comparison, including the separate bundled Kaggle source.

## User-confirmed Kaggle source package for Vietnam

On 2026-11-16 the user confirmed that the source package attached to the Vietnam Kaggle run was the `CoreRouter/` folder on branch `HARP-model`. Combined with the earlier confirmation, the historical experiment lineage is: `notebook/vietnam.ipynb` → `HARP-model:CoreRouter/` → Vietnam outputs recovered under `harp_ablation_vietnam/`. This resolves the package-selection uncertainty above at the folder level. Use the main `CoreRouter/src` tree as the historical source reference, rather than treating `CoreRouter/kaggle_harp_update/src` as an equally likely source. The notebook's module commands execute from `/kaggle/working/CoreRouter`, consistent with that main source tree.

The latest recovered reference is commit `1badfd486d5d303ecdeba2f04cd7626163b3a8bd`; its `CoreRouter/` tree is unchanged from the previously recovered `19534b0489c532be46bd4fb540acf83019ac3c8d`. The user confirmed the folder/branch, not an immutable historical Kaggle dataset version or commit. Do not claim the latest reference commit was necessarily the exact run-time commit. Missing exported ablation checkpoints remain a separate artifact gap. Existing code comparison against `CoreRouter/` is the relevant comparison for this confirmed package. No source, notebook, or experiment result was changed.

## User-confirmed shared experiment pipeline across three topologies

The user clarified on 2026-11-16 that Vietnam, NSFNET and GEANT2 runs all used the same source package (`CoreRouter/` on `HARP-model`) and the same notebook workflow, with only a few topology-specific configuration changes. `notebook/vietnam.ipynb` is the supplied representative notebook for this shared workflow; do not limit its provenance to Vietnam or infer separate source implementations from the names of result folders. Historical main `CoreRouter/src` is the common reference for all three topologies.

Exact per-topology configuration differences have not yet been enumerated by the user or fully recovered from run metadata. The inspected Vietnam values (including 500,000 training steps) must not automatically be assigned to NSFNET/GEANT2. Compare available configs/artifacts to establish the actual topology, training budget, seeds and other overrides for each run. This clarification establishes common source/workflow lineage, not identical configuration values or complete checkpoint availability. No code, notebook or numerical result was modified.
