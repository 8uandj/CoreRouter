# Live changes made for the e2e HIL run (2026-11-21), all reversible

| When (UTC) | Change | Why | Rollback |
|---|---|---|---|
| 17:00 | iptables nat POSTROUTING: MASQUERADE -s 10.0.0.0/24 and -s 10.1.240.0/24 -o vxlan.calico, comment `corerouter-hil-e2e` (host 3s-com) | Pods on worker1/worker2 had no return route to the Mininet subnet | `../host_changes/ROLLBACK.sh` |
| 17:05 | Tekton Pipeline `vnf-migrate-single`: wait step passes `deploymentName=$(params.newDeployName)` | Task `kubectl-wait` requires deploymentName since 2026-11-17; every migration PipelineRun failed validation | apply `pipeline_vnf-migrate-single_before.yaml` |
| 17:07 | Backend image rebuilt (fix 1): router excludes the just-reserved VNF from "old VNF" candidates; Ready wait configurable (default 180 s) | Every first VNF of a type triggered a self-migration and a 30-s readiness timeout | `docker tag 3s-com-backend:py311-pre-e2e-20261121 3s-com-backend:py311 && ./run_backend_docker.sh run` |
| 17:29 | Backend image rebuilt (fix 2): absence-confirmation wait configurable (default 120 s); `POST /api/orchestrate/reconcile/{vnf}` releases a ledger record only when Deployment and Pods are confirmed absent | BREAK deleted the old VNF but 30-s confirmation window expired; charge leaked | previous tag `3s-com-backend:py311-e2e-fix1` |
| 17:29 | 4 leaked ledger records released through the reconcile endpoint (`reconcile_leaked.txt`) | Deployments confirmed absent by Kubernetes | none needed |
| run | Probe-time only: per-source Mininet host IPv6 address, fc00::/16 route, static neighbour, seg6 encap route, `ethtool -K hS-eth0 tx off`; all removed after each probe (audited: none left) | Linux SRv6 encapsulation from the source host | automatic teardown |
| run | ~40 VNF Deployments created via Tekton in `core-router`; P4 `routing_v6` / `srv6_end_dx4_table` entries added by the controller | the experiment itself | Deployments: `/api/vnfs/{name}` + reconcile; P4 rules persist until topology restart (no controller delete API) |

Source fix not yet live: `infrastructure/sdn/controller.py` readback comparator (compact MAC with hex letter, e.g. h10 `0a`). The controller runs inside the Mininet process; applying it requires restarting the data plane, which was not done during the run.
2026-11-21T18:25:22Z disk at 99% (2.4G free): removed own scratch git-archive (2.5G) and docker build cache unused >24h; free after: 4.8G
| 18:45 | Backend switched to corrected model (sha ea215985…, normalizer 87385923…) via run_backend_docker.sh default + read-only mount of results/models/retrain_v11_20261119_corrected; legacy long run stopped at 19 min → long_legacy_model_partial/ | user asked for long run on latest model | ROLLBACK: JO_VPPM_MODEL_PATH=results/models/v11/dgrl_v11_final_vietnam.zip JO_VPPM_SCALER_PATH=results/models/v11/vec_normalize_v11_vietnam.pkl ./run_backend_docker.sh run (legacy file still in image); script before: cluster_changes/run_backend_docker.sh.before_model_switch |
