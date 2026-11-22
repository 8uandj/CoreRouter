# Journal manuscript shortening audit — 22 November 2026

The clean manuscript entry point remains `rev_clean.tex`, which inputs
`rev1.tex`. The separate supplementary entry point is `supplement.tex`.
`FGCS_overleaf_final.zip` packages both sources and the reviewer response.

## Editorial scope

- Main paper: 10 tables and 5 figures. The retained tables cover failure
  semantics, protected-policy comparison and paired inference, ablation,
  proposal violations, request-correlated HIL, BMv2 over-MSD behavior, the
  post-release three-hour HIL run, and HARP/SAF-H timing and scaling.
- Separate supplement: 22 tables and 3 figures. Detailed protocols, additional
  baselines, load/occupancy sweeps, sensitivity checks, and training variation
  remain accessible without occupying main-paper pages.
- The earlier saturated three-hour run remains in the raw archive but is
  excluded from the manuscript, supplement, generated HIL table and response.
  The reported run is `long_3h_corrected_model_released` only.
- The post-release run accepted 209/3,083 admission requests. Those requests
  were not deployed or steered by the admission workload. Its 1,800/1,800
  delivered probes targeted previously steered single VNFs.
- The response letter uses the new main-table and supplementary-table numbers.
  Reviewer comments remain verbatim.
- The author confirmed the funding identifier `KC.01.06/21-30` in this session.

## Verification and remaining gates

- `scripts/paper/check_tex_inputs.py` checks brace balance, references,
  figures and citation keys for both documents.
- `scripts/paper/package_overleaf.py` verifies the ZIP entries against the
  source bytes. `FILE_SHA256SUMS` is the bundle-wide point-in-time inventory.
- No TeX compiler is available on this host, and Docker access was not
  granted. The older `rev1.pdf` and `rev_clean.pdf` are stale 34-page builds.
  The shortened manuscript and supplement need fresh PDF compilation and
  visual inspection before submission; their current page counts are unknown.
- The separate final audit retains unresolved scientific and release limits:
  original ablation training provenance, full-chain forwarding, production or
  ASIC generalization, complete clean-machine reproduction, and immutable DOI
  deposit. These limits must stay visible in the paper and response.
