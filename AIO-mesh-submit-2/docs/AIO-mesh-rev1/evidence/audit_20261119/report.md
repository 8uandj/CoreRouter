# Evidence audit report — 2026-11-19

Audit checkout: `HARP-server`, commit `4f6b36549a14564f3220c57619b5bd2690035fe1`; Python 3.9.25, NumPy 2.0.2, PyTorch 2.7.1+cu118, SB3 2.7.1, sb3-contrib 2.7.1, Gymnasium 1.1.1, SciPy 1.13.1. The worktree had no user changes before this audit. New files and rerun outputs are isolated under `docs/AIO-mesh-rev1/evidence/audit_20261119/`, `results/evidence_audit/`, and the explicitly identified new training roots.

## Inventory and action-space verification

The host is `hanoi`: 96 logical CPUs (2 × Xeon Platinum 8160, 24 cores/socket), 251 GiB RAM, 1.6 TiB free on `/dis`, Tesla T4 with 15,360 MiB VRAM. During this audit, the shared GPU remained saturated at 100%; available VRAM fluctuated around 7.8–8.7 GiB because older synthetic HARP sessions and a separate DIPE process also use it. PyTorch reports CUDA available. Do not interpret simulator runs as HIL or packet forwarding.

Direct inspection of SB3 ZIP `data` and policy weight tensors confirms:

| Artifact family | Serialized action space / action head | Finding |
|---|---|---|
| v10 main checkpoints | `MultiDiscrete([N,N])`; action head has `2N` outputs | Vietnam 10+10, NSFNET 14+14, GEANT2 22+22 in v10 artifacts. |
| v11 main checkpoints | `MultiDiscrete([N,N])`; action head 20, 28, and 46 outputs | Vietnam N=10, NSFNET N=14, GEANT2 N=23. |
| v11 ablation full checkpoints | `Discrete(N²)`; action head 100, 196, and 529 outputs | Vietnam, NSFNET, GEANT2 respectively. All seven variants have checkpoint families, but strict per-topology normalizer pairs must be taken from actual files; the rerun manifests record the selected pairs. |
| corrected 19 Nov main retrain | `Discrete(N²)` | Corrected Vietnam, NSFNET, GEANT2 final checkpoints are the current main models. Their action spaces were rechecked on 20 Nov; hashes and normalizers are pinned in the new six-topology benchmark manifest. These are new experiments, not reproduction of the archived 2N benchmark. |

There are 133 ZIP archives under `results/models` at audit time: 75 `Discrete`, 58 `MultiDiscrete`. The machine-readable inventory is `checkpoint_action_space_inventory.csv`; hashes for ZIP, normalizer, input and retained CSV/JSON/log files are in `artifact_hashes.csv`. The old GEANT2 v10 N=22 and v11 N=23 checkpoint lineages are distinct. No N² ablation result is used to substantiate a 2N benchmark claim.

### Current primary evidence update — 2026-11-20

The six current main checkpoints (corrected Vietnam/NSFNET/GEANT2 retrains and synthetic 25/50/100 retrains) were directly inspected and all serialize `Discrete(N²)`. Existing ablation variants also use `Discrete(N²)`; no ablation retraining is required for action-space alignment. Current benchmark runs use these six N² models and their pinned normalizers. Older 2N model artifacts and training logs remain preserved but are not the primary training/evaluation evidence set. Benchmark summaries are pending completion; this update does not replace any manuscript metric.

## Manuscript result-to-source map

| Manuscript result | Best local source presently found | Evidence limitation |
|---|---|---|
| Main protected benchmark, Tables 4–6 (`rev1.tex` labels `tab:simulation_acceptance_summary`, `tab:benchmark_paired_statistics`, `tab:cspf_paired_statistics`) | `results/ablation/HARP-model/harp_ablation_{vietnam,results_nsfnet}/worker_*/benchmark_results/all_seed_summary.csv`; selected rerun in `results/evidence_audit/reruns_20261119/vietnam_bursty_s42/` | The available five-seed aggregates are not the draft's 20 matched per-seed records. Original matched benchmark and CSPF exports are unavailable. The fresh seed-42 result must not be compared to a 20-seed mean. |
| Ablation, Tables 7–8 (`tab:vietnam_ablation_summary`, `tab:timed_full_coverage`) | Five-seed historical raw summaries in `results/ablation/HARP-model/`; current retained matched-trace E3 summaries and manifests in `docs/AIO-mesh-rev1/evidence/e3/` and `results/rev1/{vietnam,nsfnet,geant2}/ablation/`; fresh NSFNET/Chaos seed-7 run in `results/evidence_audit/reruns_20261119/nsfnet_chaos_s7/` | Historical five-seed files do not prove the draft's 20-seed protocol. E3 source run raw per-request tree is absent from its indexed path, while timing reruns are available. |
| Mask/admission, Tables 9–10 (`tab:mask_admission`, `tab:proposal_violations`) | `docs/AIO-mesh-rev1/evidence/e3/{ablation_admission_summary.csv,ablation_pooled_summary.csv,manifest.json}` | Summary denominator and definitions are documented; underlying complete per-request archive is not retained, so joint mask-state/rejection reclassification is limited. |
| 12-hour control plane, Table 11 (`tab:hil_12h`) | `results/rev1/e6_12h_control_plane/runs/20261117_190242/{all_records.csv,kubernetes_readiness.csv,run_manifest.json,run_provenance.json,CONTROL_PLANE_SCOPE.json}` | This is control-plane/API evidence. It has no deployment actuation and no run-level multi-VNF packet traversal. The separate testbed source is not assumed to be on this host. |
| Offered-load sweep, Table 12 / Figure 3 (`tab:load_sweep_results`) | `docs/AIO-mesh-rev1/evidence/load_sweep/all_modes_per_seed.csv`, `mentor_b2_load_sweep_21.csv`, `mentor_d1_unprotected_load_sweep.csv`; fresh GEANT2 cell below | Combined 3,360-row per-seed CSV exists; source per-topology manifests listed in the run index are absent. |
| Oracle, Table 13 (`tab:missed_feasible_oracle`) | `results/rev1/nonhil_studies/20261117_233441/` | Present on disk; inspect its own run manifests before quoting. It is simulator oracle evidence. |
| Background chains, Table 14 (`tab:active_chain_stress`) | `results/rev1/e4_active_chains/{vietnam,nsfnet,geant2}/20261117_142126/` | Per-seed CSVs and manifests exist. These are simulator background-load results. |
| Timing/scaling, Table 15 and Figure 4 (`tab:synthetic_scalability`) | `results/rev1/nonhil_studies/20261117_235132/`, `results/rev1/e3_timed/{vietnam,nsfnet,geant2}/` | Available outputs are current revision measurements, not original historical raw timing; interpret timing components from the run-level definitions. |
| HIL forwarding claims | `results/hil/rebuild_20261117T123405Z/*.pcap`, indexed endpoint probes | No matched packet evidence shows ordered traversal and outcome through a multi-VNF chain. Do not report forwarding success, chain loss, or deployment count from these endpoint captures. |

The run-index presence check found 31 indexed entries, including 14 marked missing that currently exist. The index is stale in those cases; the generated current file hashes are provided alongside it. Conversely, paths currently absent remain explicitly marked in the CSV. `REPRODUCE.md` is therefore not treated as proof of current file presence without checking the filesystem.

## Requested single-cell reruns

Commands were run from repo root via `scripts/rerun_cell.sh`; output paths were chosen to be fresh and separate from historical results.

1. `benchmark / Vietnam / burst_surge (Bursty) / seed 42`: completed, 3,000 offered requests per algorithm. Protected safe acceptance: Greedy 58.8667%, CSPF 56.0000%, SAF-H 58.5667%, DAI 58.8667%, HARP 57.7000%; zero admitted modeled hard violations for all five. Trace hash is `27b96b2ca35c8897337c76b1eb4628c3f9dec112aed8a0cf0b62e8decae4a56a`. This one seed has no retained original row with which to compute a per-seed delta.
2. `ablation / NSFNET / Chaos / seed 7`: completed all seven variants, 3,000 steps each, with one shared trace hash `fe986a324bef21ea623619222617b8af8d96406ca4aa546b1e565b99158e3c35`. Safe acceptance: full 51.3667%, w/o GAT 52.1667%, w/o hard masking 26.0000%, w/o mask + unchecked admission 26.0000%, soft MSD penalty 39.0333%, soft MSD + runtime admission 39.0333%, w/o adaptive penalty 51.9333%. Full records 1,460 empty-mask steps and 1,459 rejections; per-request joint causes need raw `trace_records` analysis before concluding whether any rejection occurred with a nonempty mask. There are no retained historical seed-7 per-variant rows to compare.
3. `load_sweep / GEANT2 / intensity 1.2 / seed 2024`: completed using `results/models/v11/dgrl_v11_final_geant2.zip` and `results/models/v11/vec_normalize_v11_geant2.pkl`, both hashed in the audit inventory. The HARP protected row is 96.8% safe acceptance, exactly matching the retained per-seed reference; trace hashes match (`5d521711fa35dfe72befb712f281c32d66ce2c3a6d856b81bf84a2ea59aa729a`). SAF-H is 92.9667%, also matching. The retained load-sweep export contains only HARP, SAF-H, Greedy and DAI; CSPF is absent from this historic per-seed CSV, even though the single-cell runner emits a CSPF row. No delta is claimed for a missing reference row.

Full per-seed CSVs, runner manifests, summaries and logs are under `results/evidence_audit/reruns_20261119/`. No manuscript values were changed.

## Mentor-item status

| Item | Status | Evidence / outstanding gap |
|---|---|---|
| A1 | Làm được một phần | Current inventory includes commit, input and checkpoint hashes and exact rerun manifests. Some historical manifests lack original command/training environment, and original trace hashes cannot be reconstructed for missing per-seed sources. |
| A2–A3 | Làm được một phần | Existing scripts regenerate several summaries/figures from retained CSVs. No universal raw-to-all-tables generator or macro-based number ledger exists; aggregate-only/historical gaps block full generation. |
| A4 | Đã xác minh | All three requested cells ran; only GEANT2 intensity 1.2 has a true same-seed reference row and it matches. |
| A6 | Làm được một phần | Model archives, current hashes, seed/step metadata and new run commands exist. Historical training logs/config/environment/source commit are missing for some main/ablation checkpoints. |
| B1, B4, B6 | Làm được một phần | Unified-statistics scripts and load-sweep tables exist. Benchmark's missing matched 20-seed rows block re-computation of all manuscript comparisons and strongest-baseline tests. Do not infer from unpaired aggregates. |
| B5 | Thiếu artifact | Existing Bursty trace hashes show shared traces across policies; seed-dependent trace generation was not performed for this audit. |
| B7 | Làm được một phần | Oracle run directory exists and is hashable; reconcile only after inspecting its per-seed raw/manifest alongside manuscript arithmetic. |
| B8 | Đã xác minh một phần | NSFNET/Chaos seed 7 captures empty-mask counts and rejections, but broad claims require all retained per-request records and a consistent rejection taxonomy. |
| B9–B12 | Làm được một phần | Load sweep, component timing fields, SLA and ablation outputs exist. Training/revision source drift and incomplete historical raw logs limit exact attribution; lambda settings need per-run verification. |
| C1–C5 | Làm được một phần | Current protocols and checkpoint action spaces are inspected. Original training environment/hyperparameters and some topology/workload lineage are absent. |
| D1 | Đã xác minh một phần | Unprotected seed-level load sweep and current D1 table exist; source topology manifests remain absent. |
| HIL deployment/forwarding | Thiếu artifact trên máy này | The control-plane run has no actuation; endpoint pcaps do not establish multi-VNF traversal. Need the separate testbed's matched raw deployment/packet evidence or a new documented run. |

## New training sessions

The first three jobs launched at 19:49 used CUDA and were gracefully interrupted at the user's request scope after discovering their callback saved no periodic `VecNormalize`. Their interrupt model and normalizer pairs are preserved at `results/models/retrain_v11_20261119/{vietnam,nsfnet,geant2}/`; their logs are preserved. They are NEW experiments.

Corrected replacement sessions are `retrain_v11_20261119_corrected_{vietnam,nsfnet,geant2}` on tmux socket `harp_retrain_corrected_20261119`. Output is isolated under `results/models/retrain_v11_20261119_corrected/`, logs under `results/rev1/training_logs/retrain_v11_20261119_corrected/`. They use commit `4f6b36549a14564f3220c57619b5bd2690035fe1`, `Discrete(N²)`, CUDA device 0, seed 42, 4 envs, batch 32, and 100k-step periodic model+VecNormalize checkpoints; each topology has its own `command.txt`, while `source.txt` pins code and dataset hashes. At the latest check all three were alive at 2,048/2,001,920 or 3,000,320 steps each, logging about 83–84 FPS; GPU free memory was 7.7 GiB and utilization 100%. Periodic checkpoint pairs had not yet reached their first 100k step. These are new training results and must not be merged into historical manuscript tables.

## Reproduction and integrity commands

```bash
python scripts/rev1/build_evidence_audit.py
venv/bin/python scripts/rev1/summarize_audit_reruns.py
scripts/rerun_cell.sh --exp benchmark --topo vietnam --workload burst_surge --seed 42 --out results/evidence_audit/reruns_20261119/vietnam_bursty_s42
scripts/rerun_cell.sh --exp ablation --topo nsfnet --workload chaos --seed 7 --out results/evidence_audit/reruns_20261119/nsfnet_chaos_s7
scripts/rerun_cell.sh --exp load_sweep --topo geant2 --load 1.2 --seed 2024 --model results/models/v11/dgrl_v11_final_geant2.zip --normalizer results/models/v11/vec_normalize_v11_geant2.pkl --out results/evidence_audit/reruns_20261119/geant2_load12_s2024
```

The inventory command refuses neither historical data nor any model files; it reads and hashes them. It writes only the audit inventory. Re-running the three evaluation commands requires using a new, empty output path when the runner would otherwise create or overwrite files.
