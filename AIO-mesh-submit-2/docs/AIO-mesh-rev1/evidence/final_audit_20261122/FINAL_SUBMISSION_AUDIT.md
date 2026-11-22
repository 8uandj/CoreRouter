# Final-submission audit — 22 November 2026

Sources reviewed: `comment_mentor.md`, `todo.md`, `todo-2.md`, `review.txt`, the manuscript and reviewer response. This report supersedes historical completion ticks; it does not certify reviewer acceptance.

## Evidence checked in this pass

- 53/53 referenced input/output/source SHA-256 values match for the main benchmark/sweeps generator manifest, HIL table generator, and arrival-rate paired statistics. See `source_hash_checks.json`.
- HIL tables regenerated from campaign, fault-injection and both long-run summaries.
- LaTeX static checker resolves manuscript inputs, labels, figures and bibliography keys. PDF compilation and page/float inspection require a TeX environment.
- Final Vietnam checkpoints for training seeds 42, 7 and 2024 contain 2,002,944 transitions each. Old evaluation metadata incorrectly used the target 2,001,920 for seeds 42/7; final evaluation reads actual counts from checkpoint metadata.
- Seeds 42/7 retain their identical model/normalizer hashes; their 40 evaluations are reused with corrected step metadata. Seed 2024 is evaluated afresh over 20 matched seeds under `evaluation_2m`. The 800k results remain archived separately.

## Mentor acceptance criteria

| Criteria | Disposition and evidence |
|---|---|
| A1–A3 | Partial. Main benchmark, sweeps, HIL and arrival-rate have manifests/generators and verified hashes. Not every number in prose is generated; a clean-machine full reproduction has not been demonstrated. |
| A4 | Three selected-cell reruns retained in `mentor_completion_20261121/cell_rerun_comparison.csv`; acceptance and trace equality established, not equality of timings. |
| A5 | HIL request/readiness/campaign/packet/counter records retained. Original control-plane run lacks full HTTP error bodies; later e2e campaign has separate request correlation. |
| A6 | Main checkpoint provenance retained. Original training archives for every ablation variant remain incomplete. |
| A7 | Repository identified; immutable DOI deposit not established. Requires author/release action. |
| B1–B6 | Paired statistics, Holm families, sample SD, denominators, trace repetition and strongest-baseline/Greedy–DAI audit presented; strongest-baseline selection remains exploratory. |
| B7–B9 | Pair oracle and TTL/mask intervention presented with experiment scope. Timed ablation contains ten conditions; it does not represent full twelve-condition timing coverage. |
| B10 | Simulator timing and benchmark components presented. Shared-host HARP timings are not isolated; finer cause of SAF-H 100-node tail is not identified. |
| B11–B12 | QoS table covers HARP and SAF-H; the requested complete five-policy QoS and original final adaptive-penalty histories are not fully supplied. No universal adaptive-penalty benefit is claimed. |
| B13 | Control-plane HIL workload, labels, denominators and latency boundaries distinguished from e2e campaign. |
| C1 | Partial. Main configuration and policy architecture documented; full historical ablation training provenance remains incomplete. |
| C2–C7 | Flat pair-action interface, variants, workload/substrate construction, local depth check and bandwidth predicates described. Full-chain formulation is a system objective; pair actions do not realize arbitrary chains. |
| C8–C12 | Notation/reward/fallback/Hybrid and state consistency described. Distributed atomicity, arbitrary full-chain soundness and Hybrid transition performance are outside the measured contract. |
| D1–D2 | Unprotected simulator rates and BMv2 depth-fault packet/counter evidence reported. Each deployed request addresses one VNF. |
| E1–E5, E7–E8 | Runtime contribution and completed evidence foregrounded; drafting status language removed. Benefits scoped by workload, graph construction and target. |
| E6, E9–E11 | Source-level terminology/reference checks performed. Final typography, float placement, bibliography warnings and clean/marked PDF equivalence require compilation. |
| F1–F6 | Figures/tables available and inputs resolve. Full final-size visual inspection remains a PDF gate. |
| G1–G2 | Editor and five reviewers have response sections; selected stale table locations corrected. Final cross-reference/page validation requires compiled PDFs. |
| G3 | Author confirmation required: submitted funding KC-4.0-56/19-30 versus revision KC.01.06/21-30. Do not infer a grant code from experimental records. |
| P1-1, P1-7 | Physical-edge experiments not established. Sparse adjacency sensitivity is derived from latency and must not be described as verified physical topology. |
| P1-2–P1-3 | Completed within single-VNF BMv2 scope: deployment/readback/steering/probes, make-before-break order, two 3h occupancy runs and over-MSD injection. |
| P1-4–P1-6 | Size-matched HARP/synthetic, background occupancy, seed-offset sensitivity and CSPF sweeps presented. Live API concurrency is distinct from actuation burst queue measurements. |
| P1-8–P1-9 | Hybrid branch and mask/TTL sensitivity scoped. Neither Hybrid switching benefit nor a deployed post-expiry-mask improvement is claimed. |
| P2-1 | Final 2M evaluation and three-training-seed table generated in this pass; only three Vietnam models and one evaluation workload. |
| P2-2–P2-3 | Additional pair oracles and SAF-H weight sensitivity retained in supplementary evidence. |
| P2-4 | Ordered multi-VNF simulator/forwarding experiment not established. |

## Reviewer concerns

R1: distinguishes runtime enforcement from masking; updates superseded numerical claims. R2.1/R3: runtime is the contribution, established GAT/PPO/masking are policy components. R2.2: common protected heuristics and admission bypass establish attribution. R2.3: paired statistics, workload-dependent outcomes and cost presented. R2.4: five-policy arrival study, occupancy and oracle clarify saturation. R2.5: pair action, no candidate-path cache, quadratic mask, Hybrid predicate and end-to-end latency scoped. R4: larger synthetic substrates and terminology included, final PDF check pending. R5.1–R5.4: MSD failure mode, local predicates, safe-RL positioning, normalization and state freshness documented. R5.5: separate simulator/control-plane/e2e/stability evidence; no production or ASIC claim. R5.6: conclusion remains two paragraphs.

## Release decision

The source is prepared for final editorial review. The mentor's strict definition of “all P0 complete” is not yet satisfied. Remaining author/release gates are grant confirmation, DOI/repository availability, original ablation provenance or explicit PI acceptance of that limitation, complete numerical-generation coverage, clean-machine reproduction, and compiled PDF inspection. These gates must not be converted into scientific completion claims by deleting their audit record.
