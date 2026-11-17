# Manuscript reconciliation — 2026-11-17

## Sources and editorial rule

`rev1_data_simualator.tex` supplies the outline and mentor revisions, not numerical evidence. `rev1.tex` uses retained artifacts. Reviewer requirements are taken jointly from `review.txt`, `todo.md`, and `todo-2.md`. Internal checklist labels belong in this document, not in submission prose. Mentor revisions that qualify safety, paired-state effects, runtime novelty, and timing boundaries are retained in substance; unsupported example results are not restored. New prose and captions are green.

## Coverage against both checklists

| Checklist scope | Evidence and manuscript treatment | Remaining requirement |
|---|---|---|
| P0.1 / E2 workload audit | Current GEANT2 benchmark: `results/rev1/geant2/benchmark/current_code_three_workloads/20261117_205637`; Vietnam/NSFNET scenario outputs. Nine acceptance rows and paired comparisons retained. Bursty repeated trace across seeds disclosed. | Final independent reproducibility audit. |
| P0.2 / E2 common admission | Four protected algorithms, all nine conditions; zero admitted modeled hard violations. Policy-independent enforcement stated explicitly. | Per-request deployment accounting requires HIL. |
| P0.3 / E2 significance | 20 evaluation seeds, paired percentile-bootstrap CI, Wilcoxon, Holm across nine comparisons. Figure shows all effects including unfavorable results. | Rank-biserial effects are now included in the main nine-condition statistical table. |
| P0.4 / E1 action realization | Architecture and limitations restrict demonstrated scope to placement–routing pairs and local predicates. | Full chain → installed SID path → forwarding evidence is not established. |
| P0.5 / E4 latency | Timing ablation table and figure include measurement boundary and sample SD. Active-chain occupancy table retained separately. | Controller handoff, actuation, larger topology, live concurrency, warm-up/hardware metadata and throughput analysis. |
| P0.6 / E5 cache | No K-cache sensitivity claims or plots; cache not implemented. | None unless runtime introduces a cache. |
| P0.7 / E1 hybrid gate | Existing architecture retains gate and limitations. | Live hybrid results require request-correlated evidence. |
| P0.8 / E1 state | Existing feature normalization, mask and freshness/consistency limitations retained. | Complete telemetry/version/actuation contract evidence. |
| P1.1 / E2 load sweep | All three current-code sweeps completed; 3,360 seed records validated. Main figure and all 21 protected-policy table rows inserted; all eight modes retained in evidence/load_sweep. | Load-sweep Holm correction covers all 21 topology/intensity comparisons; HIL remains separate. |
| P1.2 / E4 topology scale | Actual networks have 10/14/23 nodes; no synthetic 50/100-node result asserted. | Size-matched models and controlled runs. |
| P1.3 / E4 chains | 0/25/50/100 background chains on three topologies retained as a distinct protocol. | Live request concurrency is separate and unmeasured. |
| P1.4–P1.5 / E6 HIL | Original HIL subsection position retained; unsupported ten-run/24h/over-depth counts excluded. | Correlated admission/deployment/forwarding logs and packet/counter evidence. |
| P1.6 / E3 masking | Seven variants, three topologies, four workloads; proposal union and individual constraints; admission on/off diagnostic; pruning and timing plots. | Training convergence history unavailable; do not infer causal mask effect from distinct policies. |
| P1.7 abbreviations | Existing expansions retained; submission proofreading still required. | Final abbreviation pass with compiled manuscript. |

## Figures delivered

- `figs/benchmark_paired_effects.pdf`: all nine HARP–SAF-H comparisons, from paired JSON; script `scripts/rev1/plot_manuscript_benchmark.py` records source paths.
- `figs/ablation_mask_admission.pdf`: Full/NoMask pruning and safe acceptance from evidence/e3 aggregate; SD across 80 seed–workload cells.
- `figs/ablation_compute_cost.pdf`: Full/MLP acceptance and per-seed decision p95 from Vietnam Uniform/Bursty timed CSVs; mean and sample SD.
- `figs/load_sweep_three_topologies.pdf` now reports the completed current-code sweep with bootstrap CI and runtime rejection. Individual topology PDFs are also exported. Overview/testbed diagrams remain checklist work; current figures do not imply an operational testbed measurement.

## Insertion points for later evidence

- Load sweep: Scalability and Online Processing Overhead subsection; replace protocol-only paragraph with validated figure and quantitative interpretation. Preserve the actual combined arrival/demand/TTL definition.
- HIL: Hardware-in-the-Loop Testbed Validation subsection, before scalability as in mentor outline. Add verified admission/deployment counts, duration and timing, then packet/counter outcomes separately.
- Revisit Abstract and Conclusion only when those results are validated. Favorable active-chain results use a different protocol and must not be presented as overturning unfavorable stress benchmarks.

## Limits of this editing pass

No LaTeX engine is installed in the checked environment. Figures and reference targets can be checked locally, but PDF pagination and float placement still require compilation in Overleaf. This is an evidence-based working revision, not a declaration that every reviewer requirement is complete.
