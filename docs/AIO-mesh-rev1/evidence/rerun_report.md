# Single-cell rerun report (2026-11-19)

Source checkout: `7035b43bd91b9042b2417623362c868d547017df`. The benchmark implementation was unchanged. Run outputs are under `results/rerun/`.

| Requested cell | Outcome | Comparison to original |
|---|---|---|
| Vietnam / Burst surge / seed 42 | Completed, 3,000 requests for each of the five protected policies. Safe acceptance in percent: Greedy 58.9333, DAI 59.2333, SAF-H 58.7000, CSPF 56.0000, HARP 57.7000. Zero admitted modeled hard violations in all five. | The five rerun policies shared offered trace SHA-256 `27b96b2ca35c8897337c76b1eb4628c3f9dec112aed8a0cf0b62e8decae4a56a`. The archived original row is unavailable. A difference against the published 20-seed mean would not test replication. |
| NSFNET / Chaos / seed 7 | Preflight failed before evaluation. The strict Full ablation checkpoint and corresponding normalizer were missing. | Requires the original checkpoint pairs and per-seed records. |
| GEANT2 / intensity 1.2 / seed 2024 | HARP normalizer could not be loaded. The current NumPy 1.x runtime does not contain the `numpy._core` modules referenced by the normalizer. Mapping the missing module names in an isolated diagnostic process was insufficient. | Requires the NumPy 2.x experiment environment or a validated portable export of the archived normalization state. The retained sweep CSV contains the reference cell. |

Commands used from repository root:

```bash
scripts/rerun_cell.sh --exp benchmark --topo vietnam --workload burst_surge --seed 42
scripts/rerun_cell.sh --exp ablation --topo nsfnet --workload chaos --seed 7
scripts/rerun_cell.sh --exp load_sweep --topo geant2 --load 1.2 --seed 2024 \
  --model results/models/v11/v11_nsfnet_geant22/dgrl_v11_final_geant2.zip \
  --normalizer results/models/v11/v11_nsfnet_geant22/vec_normalize_v11_geant2.pkl
```
