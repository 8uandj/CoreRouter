# E3 ablation evidence

`ablation_admission_summary.csv` gives all seven variants by topology. Each row aggregates 80 matched seed/workload cells (four workloads × 20 seeds), each with 3,000 offered steps. `ablation_pooled_summary.csv` gives an equal-run-weight pooled summary across all three topologies. The JSON manifest records exact inputs, hashes, definitions, coverage checks, and the source-version note.

Proposal CPU/RAM/BW/MSD violation rates can overlap. `proposed_hard_violation_rate` is their union. Primary rejection rates are non-overlapping. Admission violation rates count the union among admitted requests. Candidate pruning is a fraction of the flat `N²` actions and must not be read as wall-clock mask overhead. `avg_latency_ms` is simulator service latency. The v3 records contain no policy-compute timing or ablation training-convergence history.
