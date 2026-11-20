# New six-topology HARP benchmarks

This is the new primary benchmark experiment set using the final `Discrete(N^2)` checkpoints from the completed six trainings. It is separate from archived benchmark results and prior main-model training logs.

Protocol: benchmark-v2; Elephant/Heavy-tail, Bursty, and Chaos stress workloads; 20 fixed evaluation seeds; 3,000 offered steps per seed/workload; 10 policy modes from the runner (protected and unprotected); exhaustive upper-bound policy skipped. Six independent tmux sessions run one seed worker each.

- `launch_manifest.json` pins training checkpoint and VecNormalize hashes, input data hash, code commit, seeds, and protocol.
- `action_space_verification.json` records direct checks of each SB3 archive's serialized action-space cardinality and `action_net` output width; both equal N² for the six benchmark checkpoints and all 18 pinned main/ablation artifacts in `configs/rev1/protocol.json`.
- `commands/` records each exact command.
- `logs/` records live progress and errors.
- Each topology's output folder will contain its run manifest, per-seed CSV, aggregate summaries, paired statistics, and plots.
- After all six complete, run `venv/bin/python scripts/rev1/summarize_multinode_benchmark_evidence.py results/evidence/multinode_benchmark_20261120_084017` to produce a combined per-seed table, mean/sample-SD tables, paired HARP-versus-SAF-H and HARP-versus-strongest-protected-baseline tests, exact Wilcoxon, paired bootstrap CIs, and Holm correction.

The benchmark remains in progress, so no manuscript metric has been replaced yet. Once complete, its seed-level outputs supersede the archived benchmark metrics for the primary result set. Keep the archived results and old main-training logs as preserved legacy records; do not mix their rows with these N² runs.

Synthetic-100 needed a retry because 10,000-class FP32 softmax output missed PyTorch's default simplex validation tolerance by roughly 5e-6 on the first state. The failed attempt and traceback remain in its timestamped output and `logs/synthetic_100.log`. Before retrying, an isolated check confirmed finite model output and identical deterministic action (4301) between raw-logit argmax and `MaskablePPO.predict`; the retry disables PyTorch distribution argument validation for this process only. See `synthetic_100_retry_manifest.json`, exact retry command, and retry log. This workaround is recorded as an evaluation runtime detail.
