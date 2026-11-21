# Completion analysis and cell reruns

`analysis/strongest_baseline_paired.csv` compares HARP to the highest mean protected baseline per topology/workload. Baseline is selected on the same data; inference is exploratory and does not adjust for selection. Paired signed-rank, bootstrap and Holm details are in `analysis/manifest.json`.

`analysis/timing_components.csv` gives mean seed-level P95 values for instrumentation captured during the benchmark. Runs were concurrent; do not interpret as isolated hardware latency. Component P95s overlap and cannot be summed to obtain total P95.

Three cell reruns are launched by `commands/cells.sh` and write separate logs and result directories. Vietnam burst-surge seed 42: all five protected policies match original per-seed safe acceptance exactly and offered trace hashes match. Check `logs/supervisor.log` for the final status of the other cells and compare with their matching original per-seed records. Preserve any warning and record provenance before concluding reproducibility.

The bundle SHA-256 inventory is a point-in-time snapshot and must be regenerated after all live jobs finish.
