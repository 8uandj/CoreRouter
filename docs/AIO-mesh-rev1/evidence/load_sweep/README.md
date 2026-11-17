# Current-code load sweep

Source: `results/rev1/load_sweep/current_code_20261117/`, Vietnam/NSFNET/GEANT2. Each topology has 1,120 rows: 20 seeds × 7 intensities × 8 modes. Source hashes, coverage and policy-paired offered trace hashes were checked before manuscript insertion. All protected admitted hard-violation rates are zero.

`all_modes_per_seed.csv` retains every protected and unprotected trial. `all_modes_summary.csv` summarizes safe acceptance, candidate infeasibility, primary rejection categories and admitted hard violations for all 168 topology/intensity/mode groups. `paired_statistics_21.json` retains original bootstrap CIs, Wilcoxon p-values and rank-biserial effects, adding `holm_p_21` corrected across all 21 topology/intensity comparisons. Original per-file `holm_p` fields are not a correction across this full family.

Reproduce with `venv/bin/python scripts/rev1/summarize_manuscript_load_sweeps.py` and `venv/bin/python scripts/rev1/plot_manuscript_load_sweeps.py`.

The sweep uses arrival probability min(1, intensity), topology-scaled base TTL 15–60 steps multiplied by scale 1.0/1.4/2.3 with integer rounding, then longer TTL above intensity 1.0. CPU/RAM demand and requested SID depth also scale above intensity 1.0. Different TTLs prevent direct pooling with the long-lived benchmark stress conditions. CI and SD describe evaluation variation at fixed checkpoints; repeated Bursty offered traces do not represent independent traffic realizations.

Upload `figs/load_sweep_three_topologies.pdf` to the manuscript's Overleaf `figs/` directory. Individual `vietnam_load_sweep.pdf`, `nsfnet_load_sweep.pdf`, and `geant2_load_sweep.pdf` are also exported for optional separate presentation. The combined figure is the one referenced by `rev1.tex`.
