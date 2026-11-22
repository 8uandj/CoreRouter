# Server 246 HIL recovery — final status

Run artifacts: `results/hil/rebuild_20261117T123405Z/`.

## Gates

- **Phase 0–2: pass.** Server/repository/source identity and original 50-name inventory were recorded. Backups include the original database, a final byte-for-byte pre-replacement reservation database, and the migration journal.
- **Phase 3: partial; full P4 gate blocked.** The admission baseline seed is valid, but source still has no verified mapping from admitted SID stack to a P4 forwarding profile. No controller rule readback, packet delivery, or switch counter delta proves forwarding.
- **Phase 4: pass.** Exactly the 43 named Deployments are absent; only the seven approved names remain. Seven Pods are Ready at the synthetic approved placement. The repaired Tekton tasks fail fast, patch the nodeSelector, and wait for the exact Deployment. Existing Service identity/ClusterIP was preserved for each VNF.
- **Live ledger: pass.** SQLite is healthy and durable at `/home/CoreRouter/results/rev1/runtime/reservations.sqlite3`; it contains the seven recovered, source-backed profiles, the approved synthetic assignment and zero `accounting_unknown`. The active topology hash is `67131a546450606da19276263b00d23988d13fd71c17be38cb24a12637fe9f11`. Migration journal integrity is `ok` and its pre-run contents were empty.
- **Admission-only smoke: pass.** One heuristic request returned HTTP 200, reserved its resource tuple, created no Deployment/PipelineRun, then was released via `/api/orchestrate/free`; ledger returned to exactly seven records and zero unknown.
- **Unsupported-realization negative smoke: pass.** One alert request returned HTTP 409 `UNSUPPORTED_ADMITTED_REALIZATION`, released the reservation, and left Deployment/PipelineRun sets unchanged. Alert state was cleared afterward.
- **Phase 5 create-through-admission/migration: blocked/not run.** Direct `/api/deploy` was used only to reconcile the seven baseline placements; no new admitted request was allowed to create or migrate a workload without proven P4 realization.
- **Phase 6 load/benchmark: not run.** Controller health returned HTTP 200 and all BMv2 Thrift ports 19091–19100 were reachable, but reachability is not forwarding evidence. No long benchmark was run.
- **Phase 7: baseline/inventory reconciliation pass; end-to-end forwarding/migration reconciliation remains blocked.** The `corerouter-p4` Mininet/P4 tmux session was preserved.

**Conclusion: baseline rebuilt; full HIL blocked.** Do not interpret the recovered admission profiles or approved placement as historical co-resident state or historical placement.

## Placement outcome

| Name | Synthetic location | K8s node | Result |
|---|---|---|---|
| `vnf-attack-004e219d` | HoChiMinh | `worker2` | Ready |
| `vnf-attack-0faeed9f` | Hanoi | `k8s-master` | Ready |
| `vnf-attack-228edabf` | HaiPhong | `k8s-master` | Ready |
| `vnf-attack-2f0aa313` | NinhBinh | `k8s-master` | Ready |
| `vnf-attack-57b6f205` | Vinh | `worker1` | Ready |
| `vnf-attack-8bf0425e` | DaNang | `worker1` | Ready |
| `vnf-attack-af13f6df` | CanTho | `worker2` | Ready |

## Important artifacts

- `phase_status.json`, `phase7_final_summary.json`, `phase4_final_inventory_gate.json`
- `seed_summary.json`, `final_api_state.json`, `phase4_ledger_gate.json`
- `admission_smoke_{request,response,summary}.json` and `unsupported_smoke_{request,response,summary}.json`
- `phase4_placement_rollouts_after_taskfix_last4.log` and `placement_rollouts/` (including first failed Task evidence and subsequent successful postconditions)
- `phase4_taskfix_live_tasks_after.yaml`, `phase4_taskfix_live_pipeline_after.yaml`, and `taskfix_first_manifest.server-dryrun.yaml`
- `final_preseed_backup/` (old reservations and journal; exact raw pre-replace copies)
- `final_controller_health.txt`, `phase7_final_pipelineruns.json`, `phase7_final_taskruns.json`, `phase7_final_deployments.json`
- `P4_mapping_audit.md` from the preceding run plus this run's controller reachability evidence

The first Python 3.8 seed attempt was rejected because its topology serialization differed from the active Python 3.11 ledger. The successful seed was built inside the backend's Python 3.11 runtime; its source hashes match the repository inputs. An ownership operation on the runtime-created file was denied, so no replacement occurred in that attempt; the seed was copied back as a host-owned file and then replaced only after backend stop and lock verification.

## Context continuity

The Superpowers skill set was installed under `/home/dis/.codex/skills` (14 skills). Skills provide workflow instructions but do not retain a conversation transcript. Use `HANDOFF.md`, `FINAL_REPORT.md`, and the evidence files in this run directory to resume after a chat/session interruption. The Superpowers repository documents Codex App installation through its Plugins marketplace: https://github.com/obra/superpowers.
