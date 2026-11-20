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

## Evidence status at packaging

The benchmark sessions and model-refresh reruns were active at package time.
Their log files were moved without stopping the processes; subsequent CSV,
JSON, and manifest writes are directed into this bundle through the workspace
compatibility symlink. Regenerate the hash inventory after all sessions finish
with `python3 scripts/rev1/refresh_submission_manifest.py`.

The HIL/testbed machine is separate. No HIL logs or measurements are claimed
or included as if they were present on this server. Unrelated repository utilities, old manuscript snapshots, generated
`node_modules`/virtualenvs/caches, and local Kaggle configuration are excluded.
Legacy pre-correction main-model training and benchmark archives are also
excluded; the current main models are under `results/models/retrain_v11_20261119_corrected/`.
