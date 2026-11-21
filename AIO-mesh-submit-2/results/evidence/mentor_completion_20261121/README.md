# Mentor simulator follow-up, 2026-11-21

Current experiments are independent of the frozen benchmark and write to this directory. Commands and logs are under `commands/` and `logs/`; jobs run in tmux socket `harp_mentor_completion_20261121` sessions `mask`, `oracle`, and `seeded_bursty`.

- `mask/`: fixed-checkpoint Bursty stress on 3 networks, 20 seeds. Counts mask emptiness and rejection intersections, and compares the pre-step mask with the counterfactual mask after the same pending TTL expiry. The actual decision and trajectory are not changed. The hypothetical post-expiry mask is not a rerun of a new policy.
- `oracle/`: 3 networks × 2 load intensities, 10 seeds, 120 sampled states per seed and policy, exhaustive pairs. Uses the refreshed-model load-sweep environment factory. Runs can take hours; manifests and logs must be checked before using the numbers.
- `seeded_bursty/`: 3 networks × 20 seeds, 5 protected algorithms. An exploratory workload varies the cyclic starting row by seed while retaining the original Bursty schedule; policies share the same trace within each seed. This does not yet cover seeded load sweep or background chains.

The GPU driver was unavailable at launch. Independent training-seed replications, sparse physical-edge topology experiments and SAF-H weight sweeps have not been completed. The bundle hash inventory is stale while output files are changing. Do not treat an active run as a completed result.

Additional jobs launched 2026-11-21:

- `seeded_load_chains`: 3 topologies; chains 0 runs 7 offered intensities and chains 25/50/100 run intensity 1.0; five protected policies, 20 evaluation seeds. Uses the same seed-specific cyclic dataset offset as `seeded_bursty`; rows are written incrementally per cell.
- `saf_sensitivity`: 3 topologies, intensities 1.2 and 1.5; baseline weights (0.5,100,5) and one-factor doubling of latency, CPU and hops, 20 seeds. These are exploratory sensitivity settings and do not change the main baseline.
- `sparse_gat_mlp`: 3 topologies, 20 seeds, existing Full/MLP checkpoints on synthetic symmetric 3-nearest-neighbour adjacency; Full's adjacency buffer is replaced after load. This is an out-of-distribution graph intervention, not training on sparse graphs, not a physical edge list, and not physical multihop routing evidence.

Independent training seeds have not been started: the NVIDIA driver is unavailable, so GPU use cannot be confirmed. Training on CPU was not substituted for the GPU training protocol. Recheck GPU and other users' load before launching training; choose separate output directories with checkpoints and normalizers.

## Supplement and independent retraining (2026-11-22)

The four original scripts imported a 10-seed evaluation list; supplementary scripts run seeds 11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192 into `supplement_10_seeds/` without overwriting the original ten. `commands/verify_supplement.py` checks the union of the two sets and paired trace hashes.

The original sandbox did not expose GPU devices; host verification confirmed a Tesla T4 and CUDA. Two additional independent Vietnam training seeds (7 and 2024) are run sequentially using the same 2,001,920 total steps, 4 environments, rollout 512 and batch size 32 recorded in the corrected seed-42 command. `independent_training/matched_seed_*` holds logs, commands, checkpoint pairs, hashes and source commit. A first short attempt used nonmatching hyperparameters and was interrupted; its artifacts are retained under `independent_training/seed_7/` and must not be pooled into the matched experiment.

`independent_eval` waits for both new final checkpoints, then evaluates training seeds 42/7/2024 over 20 matched evaluation seeds. `finalize_supp` waits for all supplement and evaluation jobs, validates expected seed files, trace matching and model/normalizer pairs, and refreshes the bundle checksum only if validation passes. Audit the completed outputs and training/environment provenance before updating paper claims.
