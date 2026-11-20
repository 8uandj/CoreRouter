# Refreshed-model dependent reruns

This evidence set replaces the historical main-checkpoint-dependent load and
background-chain results for Vietnam, NSFNET, and GEANT2. It does not include
the separate six-topology benchmark already running under
`../multinode_benchmark_20261120_084017/`.

## Launched work

- 12 load/chain sweeps: each topology with 0, 25, 50, and 100 seeded background
  chains. Each run evaluates 20 matched seeds, 3,000 steps, seven load levels,
  five algorithms, and protected/unprotected variants.
- 3 oracle reruns: one per topology, ten seeds, 3,000 steps, stride 25,
  comparing HARP and SAF-H under the base bursty workload.
- Each process has a separate tmux session, command file, log, and output path.
  The `launch_manifest.json` pins model, normalizer, dataset, and source hashes.

## Runtime notes

The launcher found 96 logical CPUs, 251 GiB RAM, 157 GiB available memory,
and 1.6 TiB free disk after launch. All 15 Python workers were alive at the
initial verification. NVIDIA-SMI could not communicate with the driver, so
these evaluation processes run on CPU; no GPU use is claimed.

The runner emits a NetworkX duplicate-backend warning during startup. No
traceback or runner error was present in the initial log check.

To inspect sessions, use the tmux socket and names listed in
`launch_manifest.json`. Logs are in `logs/`; per-seed CSVs and run manifests
will be written beneath `load_chain/` and `oracle/` as each process completes.
