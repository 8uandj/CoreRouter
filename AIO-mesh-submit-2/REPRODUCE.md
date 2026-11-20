# AIO-Mesh revision evidence and reproduction

The manuscript is in [docs/AIO-mesh-rev1](docs/AIO-mesh-rev1). From the repository root, run `make paper-data` with Python, NumPy, and Matplotlib installed to regenerate the outputs that have accessible input records. Run `python3 scripts/paper/check_tex_inputs.py` for the source, figure, reference, and citation checks. The strict hash check is `python3 scripts/check_manifest.py`. The `--allow-missing` form also prints unavailable paths and exits successfully only if every accessible file matches. It does not certify missing evidence.

The [run index](docs/AIO-mesh-rev1/evidence/run_index) inventories all ten requested experiments and the three available main checkpoint archives. It distinguishes an original file hash recorded by an earlier export from a hash computed for an accessible file now. Index entries identify evidence and gaps. They do not reconstruct the original execution command or assert a git revision where neither was preserved.

| Manuscript result | Generator or check | Available data and remaining gap |
|---|---|---|
| Tables 4–6, Appendix Figure A.1 | `scripts/rev1/plot_manuscript_benchmark.py` | HARP/SAF-H aggregates and figure are retained. Original matched per-seed benchmark and CSPF exports are missing. The published-in-draft paired results remain archived statistics, pending recalculation under one procedure. |
| Tables 7–8, Appendix Figures A.2–A.3 | `scripts/rev1/plot_manuscript_ablation.py` | Matched-trace summaries and source metadata are under `evidence/e3/`. Original records, timed records and ablation checkpoint/normalizer pairs are unavailable here. |
| Tables 9–10 | `scripts/paper/make_ablation_tables.py` | Generated from the preserved E3 equal-weight CSV summaries. The original per-request archive is still needed for a joint mask-state and rejection analysis. |
| Table 11 | `scripts/paper/make_table11.py` | `results/rev1/e6_12h_control_plane/runs/20261117_190242`. Includes the 12,325 request records, 720 readiness records, hourly summary and run metadata. |
| Table 12, Figure 3, Appendix Tables A.1–A.4 | `scripts/paper/make_load_sweep_figure.py`, `scripts/rev1/summarize_mentor_statistics.py` | The combined per-seed export is under `evidence/load_sweep/`. It has 3,360 rows and paired trace hashes. The original per-topology directories/manifests are missing. The generated artifacts cover the appendix tests and Figure 3. Table 12 reads the previously generated protected-policy rows. |
| Tables 13–15, Figure 4 | `scripts/rev1/run_nonhil_studies.py`, `scripts/rev1/plot_nonhil_studies.py` | The manuscript and revision notes preserve aggregate results. The original oracle, occupancy, and timing outputs are missing or incomplete. Figure 4 was redrawn from the reported aggregates. Recover the per-seed files before dispersion and confidence interval or tail-cause verification. |
| Figures 1–2 | `scripts/paper/make_architecture_figures.py` | Architecture illustrations. |
| Appendix Table A.5 | scripts/paper/make_qos_table.py | HARP/SAF-H service outcomes from the retained 18-cell benchmark aggregate. Evidence for all five policies requires recovery of the per-seed records. |
| Shared numerical macros | `scripts/paper/make_numbers.py` | The HIL request total and load-contrast ranges are generated in `generated/numbers.tex` and `generated/numbers.json`. Other prose values still require the archives and generators described above. |
| Checkpoint metadata | `scripts/paper/make_checkpoint_index.py` | Main checkpoint ZIPs and associated normalizers. The original training log, training dataset identity, hardware, run command, checkpoint-selection rule and ablation training artifacts are missing. |

## Testbed source records

The HIL table uses `all_records.csv`, `kubernetes_readiness.csv`, `run_manifest.json` and `CONTROL_PLANE_SCOPE.json`. Its JSON output preserves source hashes, per-hour admission rates and response percentiles. API records preserve request fields and outcome classifications. They do not preserve the original HTTP bodies and error messages in full. The measurement has no run-level packet counter series. The 50-Deployment inventory discussed in earlier drafts is a separate snapshot and does not enter Table 11.

The available endpoint captures are indexed under `evidence/run_index/forwarding.json`. They show an endpoint probe. No matched packet record identifies the ordered traversal and outcomes of a multi-VNF chain. Recover the historical packet and deployment logs or run a new documented forwarding experiment before reporting chain length, SID stack, loss, or repetition count.

## Single-cell reruns

See [the November 19 rerun report](docs/AIO-mesh-rev1/evidence/rerun_report.md). The runner defaults to the local `venv/bin/python`. Set `AIOMESH_PYTHON` to the interpreter from the archived experiment when its dependencies differ. A rerun emits fresh results and does not replace the archived records.

## Overleaf

Upload the contents of `docs/AIO-mesh-rev1/` preserving `figs/`, `generated/` and `evidence/load_sweep/`. Select `rev1.tex` for the green-marked manuscript or `rev_clean.tex` for the clean manuscript. For the response letter, include the same `generated/numbers.tex` alongside the letter under `generated/`. The shared preamble also supports the repository layout with the response in `docs/`. These instructions leave PDF generation to Overleaf. No DOI deposit has been made. The current [FGCS author guide](https://www.sciencedirect.com/journal/future-generation-computer-systems/publish/guide-for-authors) returned HTTP 403 during inspection and should be confirmed from the submission portal.
