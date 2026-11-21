# AIO-Mesh revision submission bundle

Canonical folder for the current paper revision source and evidence. The
`results/evidence` directory here is the physical home of all live benchmark,
load/chain, and oracle evidence. The workspace path `results/evidence`
is a compatibility symlink to this directory, so existing tmux jobs continue
writing here after this package was created.

## Contents

- `src/`, `configs/rev1/`, `scripts/rev1/`, `scripts/paper/`, `notebook/`,
  `data/`: current simulator, training/evaluation, paper-table/figure code, and
  required inputs for reruns.
- `docs/AIO-mesh-rev1/` and `docs/response_rev1.tex`: current revision and
  mentor-response material, including prior audit evidence.
- `results/models/`: corrected Vietnam/NSFNET/GEANT2 main retrains, synthetic
  25/50/100-node models, all paired normalizers/checkpoints, and current
  ablation models.
- `results/rev1/training_logs/`: corrected main-retrain logs and latest
  synthetic batch32 training logs.
- `results/rev1/e3_*` and topology `ablation/`: retained N^2 ablation records.
- `results/evidence/`: live six-topology benchmark and refreshed-model
  load/background-chain/oracle reruns, with logs, commands, manifests, and
  generated CSV/JSON/plots.
- `provenance/`: source commit/branch/dirty-state, included-file index, current
  source diff, Python/runtime package versions, and package lock.

## Refreshed evidence status

The six-topology N² stress benchmarks and the refreshed-model load, background-
chain, and pair-oracle reruns are complete. Manuscript-facing tables and figures
were regenerated from the retained per-seed CSVs by
`python3 scripts/rev1/summarize_model_refresh_evidence.py`,
`python3 scripts/rev1/plot_manuscript_benchmark.py`, and
`python3 scripts/rev1/plot_manuscript_load_sweeps.py`. Source CSV hashes are
recorded under `docs/AIO-mesh-rev1/evidence/model_refresh_20261120/`; run
manifests retain checkpoint and normalizer hashes and run commands. The
dedicated serialized decision-cost paragraph is explicitly identified in the
manuscript as a separate measurement that was not rerun with the corrected
checkpoints. HIL remains on the separate testbed and has not been refreshed by
these simulator jobs.

Refresh `FILE_SHA256SUMS` after evidence changes with
`python3 scripts/rev1/refresh_submission_manifest.py`.

The HIL/testbed machine is separate. No HIL logs or measurements are claimed
or included as if they were present on this server. Unrelated repository utilities, old manuscript snapshots, generated
`node_modules`/virtualenvs/caches, and local Kaggle configuration are excluded.
Legacy pre-correction main-model training and benchmark archives are also
excluded; the current main models are under `results/models/retrain_v11_20261119_corrected/`.
