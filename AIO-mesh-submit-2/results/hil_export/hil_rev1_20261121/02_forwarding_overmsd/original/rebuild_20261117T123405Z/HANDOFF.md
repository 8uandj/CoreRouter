# HIL 246 recovery handoff

Updated: 2026-11-17 12:43 UTC
Run directory: `results/hil/rebuild_20261117T123405Z`

## User objective and hard limits

Recover a seven-VNF source-backed admission baseline, retire exactly the 43 names in `docs/hil/PLAN_RUN_TESTBED_246.md` only after the exact live snapshot and backups, then verify admission/create/readiness/P4 forwarding/migration. Do not use the synthetic assignment to move any retained VNF until the user confirms. Do not reset a live ledger, overwrite local changes, change network configuration, delete unrelated resources, commit, or push. Full HIL must remain blocked without verified P4 mapping, controller readback, and packet/counter evidence.

## Target and source identity

- Host hostname: `3s-com`; internal address `10.10.6.231`; Kubernetes node `3s-com` Ready. Kubernetes API, host and repo all point to the attached 246 environment after read-only commands were re-run with elevated host access.
- Repo `/home/CoreRouter`, branch `HARP`, commit `7f4a5eb50a938a0540906df32c9c4940a54e803f`.
- Preserve pre-existing local changes: modified `run_backend_docker.sh`, untracked `scripts/hil/seed_base_inventory.py`. Their origin is unknown; do not overwrite.
- Plan SHA-256 `2008dcd2565040fb4c35b60aa35e521f1822fc287c8b12d25971efe6b7faa85a`.
- Profiles SHA-256 `fc2370a51d075da2b464d855969d325299523de635689137e5600a1595d841b6`.
- Proposed assignment SHA-256 `9e3dcce9e2f1e2cc5bfde360f4a2bfa3dba7e1be6f29c95997e7eb13094c8f48`.

## Completed gates

- Phase 0: host/repo/source identified; both JSON files parse. Initial sandbox-only probe was blocked, then read-only commands succeeded on the host with elevated permissions. Initial failed probe outputs are kept in `phase0.txt`, `phase1_readonly.txt`, and `service_probes.txt` for transparency.
- Gate 1: exact 50-name comparison passed (7 retain + 43 retire), all 50 Deployments in namespace `core-router`, all 50 Ready. 305 PipelineRuns and 932 TaskRuns; zero nonterminal. `corerouter-p4` tmux session is attached and runs `sudo venv/bin/python3 infrastructure/sdn/topo_p4.py --p4` (confirmed in the prior run artifacts); preserve Mininet/P4 and do not kill it. API root/health/AI/orchestration APIs return 200; model `v11` loaded; orchestrator idle. API state says `reservation_persistence=durable` but all 50 VNFs are `accounting_unknown` and unaccounted. BMv2 Thrift ports 19091-19100 open. Controller `http://127.0.0.1:8765/health` timed out (no response). `vnf-voc-phase3-svc` is a NodePort (31656) selected by `app=vnf-voc-phase3`; preserve it unless a healthy separate support fixture replaces it.
- Gate 2: saved exact 50 Deployment YAML, services with exact app selectors, PipelineRun/TaskRun YAML, vVOC ConfigMaps, backend logs, image ID, inspect mounts, node/process/API snapshots. Backend image `3s-com-backend:py311`, image digest `sha256:c9723997fe0ed80acbbe50a5c2a8dd8936ab2602b4e4dcf6d5e45d1ead34f1f1`; no host runtime bind mount. Effective DB paths inside container: `/app/results/rev1/runtime/reservations.sqlite3` and `migrations.sqlite3`. SQLite online backups copied to this run directory; both report `PRAGMA integrity_check=ok`. SHA-256: reservations `bcb7a2321f08e7f50bc9c78d57497fe8b5fe1f83d134c4381657c4f668ce5ec6`; migration journal `329ad964a7f04c61d46599421e9f897713e3dcb2b6be4c09eec8329e0372ea7c`.

## Current state (latest)

The prior Phase 4 placement stop was repaired. All seven approved synthetic placements now have live Ready Pods on their assigned Kubernetes nodes, and Services retained their identities. The 43 exact retirement Deployments are absent. The persistent backend mount is active; the reservation DB now contains seven known source-backed records, zero unknown records, and the Vietnam topology hash matching the Python 3.11 runtime. The old ledger and migration journal are preserved under `final_preseed_backup/`.

Admission-only reserve/release passed. A bounded alert request was rejected with `UNSUPPORTED_ADMITTED_REALIZATION` before Tekton, its reservation was released, and no Deployment/PipelineRun changed. Controller health now returns HTTP 200 and BMv2 Thrift ports are reachable. P4 SID-to-forwarding mapping, controller rule readback, packet delivery, counter deltas, request-correlated create and migration remain unverified. Full HIL and benchmark are blocked.

## Next work

Do not run a load benchmark or claim full HIL. Resolve the P4 realization mapping from existing source/configuration and actual switch semantics, then independently verify controller rule readback, packet evidence, and counter delta before authorizing a request-correlated create/migration smoke. Preserve the current Mininet/P4 session. No further baseline mutation is required.

## Artifacts

- `host_phase0.txt`, `deployments.json`, `services_endpoints_pods.yaml`, `vnf_configmaps.yaml`, `tekton.yaml`, `docker_ps.txt`, `tmux.txt`, `processes.txt`, `listeners.txt`, `live_probes.txt`, API probe captures, exact Gate 1 summary, manifests, DB snapshots, checksums, and backend logs are in this directory.


## Chat continuity and Superpowers

A separate HIL handoff file has been saved so recovery does not depend on the chat transcript. Fourteen Superpowers skill folders were installed manually under `/home/dis/.codex/skills`. The official Codex plugin marketplace integration was not installed through the app UI; if its plugin hooks are needed, install it from the Plugins sidebar. Neither the skills nor plugin retain this testbed transcript; use this handoff and the run artifacts.

## Phase 4 update (2026-11-17 13:10 UTC)

User approved the proposed synthetic assignment. The backend was restarted once with a new host bind mount at `/home/CoreRouter/results/rev1/runtime`; it reopened the same 50-record, 50-unknown ledger, model v11 stayed loaded, and startup/API checks passed. The exact 43 Deployments were deleted and verified absent; 35 dedicated ClusterIP Services with exact single-app selectors were deleted. Five NodePort services remain, including `vnf-voc-phase3-svc` NodePort 31656, now with zero endpoints. All seven keep Deployments remain.

Placement reconciliation stopped after its first PipelineRun. The live prepare-vnf Task passed `nodeHostname=worker2` but then failed with `/bin/sh: line 24: python3: command not found`; because the Task shell is not fail-fast, it reported success. The apply Task logged both objects `unchanged`; the Pod stayed on `3s-com` with no nodeSelector. PipelineRun `deploy-firewall-f6baf7` is a false-positive success. No requests were sent for the other six. Do not replace the live ledger or continue placement until the Task is repaired and focused verification proves the nodeSelector reaches an existing Deployment. Full HIL remains blocked by both this Task defect and the audited P4 mapping/readback/packet gap. See `phase4_gate_failure.md` and `placement_rollouts/failed_first/` for exact evidence.


## Latest execution update (2026-11-17 13:48 UTC)

The repaired prepare Task uses shell fail-fast and awk (no Python dependency); the wait Task targets `deployment/<name>`. One initial placement readback captured an old Pod during termination; stable follow-up showed one active Ready Pod on target. The same transient old-Pod race occurred once more and was resolved by waiting for that deleting Pod to disappear. All seven final placement postconditions passed.

The active reservations DB was atomically replaced while the backend was stopped and owner lock was free. The database and migration journal were backed up first, with raw checksums preserved. Backend restart reopened the seeded database durably with seven known records and `unaccounted_vnfs=[]`. See `FINAL_REPORT.md` and `phase_status.json` for the authoritative summary.

## Context continuity skills

The 14 Superpowers skill folders from `obra/superpowers` were installed under `/home/dis/.codex/skills`. They provide workflow guidance, but they do not persist this session's transcript. Resume from this handoff and `FINAL_REPORT.md`, then inspect `phase_status.json` and linked evidence. The repository's Codex App installation instructions point to the Plugins sidebar/marketplace: https://github.com/obra/superpowers.
