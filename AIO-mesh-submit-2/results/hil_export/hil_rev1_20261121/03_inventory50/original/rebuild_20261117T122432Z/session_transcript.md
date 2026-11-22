# HIL 246 recovery transcript

Run: `rebuild_20261117T122432Z`  
Start target time: `2026-11-17T12:24:32Z`  
Repository: `/home/CoreRouter`  
Host: operator-confirmed server 246; `hostname=3s-com`, Kubernetes node address `10.10.6.231`.

## Phase 0 — identity and inputs

Commands: `hostname; date -u +%Y-%m-%dT%H:%M:%SZ; pwd; git branch --show-current; git rev-parse HEAD; git status --short --branch; sha256sum docs/hil/PLAN_RUN_TESTBED_246.md configs/hil/recovered_hil_profiles.json configs/hil/base_inventory_assignment.proposed.json; python3 -m json.tool ...`.

Results: repo `/home/CoreRouter`, branch `HARP`, commit `7f4a5eb50a938a0540906df32c9c4940a54e803f`; worktree clean before changes. Both JSON files parse. Source hashes are saved in `source_hashes.sha256` and `source_hashes_after.sha256`; profile and assignment hashes remained unchanged. Hanoi-side comparison was not run in this shell.

## Phase 1 — read-only preflight

Commands: `microk8s status --wait-ready`; `kubectl get nodes -o wide`; `kubectl -n core-router get deployments/services/endpoints/pods`; `kubectl -n core-router get pipelineruns,taskruns`; `docker ps --no-trunc`; `tmux ls`; `ps -eo pid,ppid,etime,args`; `curl http://127.0.0.1:8000/{,api/health,api/ai/status,api/orchestrate/status,api/orchestrate/state}`; `curl http://127.0.0.1:8765/health`; Thrift TCP probes on 19091–19100.

Results: exact expected inventory names matched (50/50; 7 keep + 43 retire), every Deployment was `1/1 Ready`, 304 PipelineRuns and 932 TaskRuns were terminal. `corerouter-p4` is the active Mininet/P4 `topo_p4.py` console and is not a benchmark runner; no benchmark/HIL process or active Tekton run was found. Backend API returned 200, AI model loaded, orchestration idle, reservation persistence reported durable, and `unaccounted_vnfs` contained all 50 Deployment names. Controller `/health` initially exceeded a 5-second client timeout; retry returned HTTP 200 after about 5 seconds and all ten BMv2 switches were reachable. Current `vnf-voc-phase3-svc` endpoint was `10.1.235.184:8000`.

## Phase 2 — backups

Commands: export all 50 Deployment YAMLs, namespace Services YAML, PipelineRun YAML, `vvoc-app` ConfigMap YAML; inspect backend image/mounts and only the two reservation DB paths; use Python `sqlite3.Connection.backup()` from the running backend to snapshot both DBs; `PRAGMA quick_check`; SHA-256 the exports and backups.

Results: backend paths were `/app/results/rev1/runtime/reservations.sqlite3` and `/app/results/rev1/runtime/migrations.sqlite3`; no persistent runtime bind mount existed. Both online SQLite copies passed `quick_check=ok`. The reservation snapshot contains 50 active records, 50 `accounting_unknown`, 0 pending, 0 anonymous, state version 16. Migration journal tables had zero rows. Checksums are in `manifest_hashes.sha256` and `sqlite_backup_hashes.sha256`.

## Phase 3 — source preparation and focused checks

Changes prepared locally: `run_backend_docker.sh` now adds a host bind mount at `/app/results/rev1/runtime` and sets explicit DB/journal paths. Added `scripts/hil/seed_base_inventory.py`; it validates profile provenance, unique/equal name sets, Vietnam node labels, per-node CPU/RAM, route MSD, uses `NetworkStateManager.try_reserve()`, refuses overwrite and checks expected topology identity before promotion.

Commands/checks: host `venv/bin/python` seed; backend-container Python 3.11 seed against the read-only active-ledger topology identity; reopen the offline seed twice; run `tests.test_hybrid_decision` with Python 3.11; direct `OrchestrationService.make_before_break_sequence` negative check; `bash -n run_backend_docker.sh`; `git diff --check`.

Results: the 7-profile seed passed with CPU/RAM assignments under 100, route MSD maxima 3→4, 5→8, 8→6, state version 8 and zero unknown records. Runtime-matching seed is `reservations.seed.py311.checked.sqlite3`; reopening it yielded 7 records, zero unknown and durable persistence. The Python 3.8.10/NumPy 1.24.4 host seed hash (`3013…`) did not match backend Python 3.11.18/NumPy 2.4.6 and was explicitly rejected; it is retained for diagnosis and must not be applied. Runtime/backend hash is `67131a…`, matching active ledger. Nine hybrid-decision unittests passed. Direct service check returned `UNSUPPORTED_ADMITTED_REALIZATION` before the fake Tekton orchestrator was called.

`pytest` could not run because neither host Python environment nor backend image has pytest. `tests.test_orchestration_api` could not import its `TestClient` because the image lacks `httpx2`. The test file itself contains a pre-actuation rejection check; the direct service check was run instead.

## Gate 3 P4 audit

Commands: inspect `infrastructure/sdn/topo_p4.py`, `infrastructure/sdn/controller.py`, `src/portal/backend/app/services/hybrid_decision.py`, `src/portal/backend/app/services/orchestration_service.py`; query `/health`, `/steer/status`, `/stats/msd_drops`; inspect all ten BMv2 container commands/mounts and loaded profile hashes.

Result: **Gate 3 full-actuation requirement failed.** Live P4 profiles and links are present and controller/counter endpoints respond. However, admissions create `2001:db8:*` SIDs while topology bootstrap installs `fc00:*`; orchestration hard-codes `s1`, port 1 and MAC values; controller status only reports an operation ID/boolean after `table_add` and provides no exact rule readback. No request-correlated packet evidence or forwarding counter delta exists. Current MSD-drop counters are all zero. Full HIL is blocked.

## Stop point

No Kubernetes object was changed, no container was restarted, no ledger was replaced, no 7 VNF location was changed, and no benchmark was run. Current 7 retained VNF Pods are all on Kubernetes node `3s-com`; the proposed assignment spreads them over `k8s-master`, `worker1`, `worker2`. The next baseline mutation requires approval to use that synthetic assignment. The 43 exact retire names still match the live snapshot and their manifests are backed up.

## Proposed placement preflight (read-only)

Commands: export live node labels/taints/allocatable; capture the seven retained Pods' node names; read the live `vnf-inputs` ConfigMap, `vnf-lcm-fast` Pipeline and Tasks; render the exact seven Deployment/Service pairs using the live `prepare-vnf` behavior; `kubectl -n core-router apply --dry-run=server -f proposed_baseline_generated.yaml`.

Results: all seven current Pods are Ready on `3s-com`. Proposed assignment targets `k8s-master`, `worker1`, and `worker2`; all three target nodes are Ready and schedulable. `k8s-master` has `dedicated=core-router:NoSchedule`; live `prepare-vnf` injects the matching toleration plus node-role tolerations and the exact hostname nodeSelector. The generated Deployments preserve VNF names, `app=<name>` selectors/labels and Services. Server dry-run returned configured for the seven Deployments and unchanged for all seven Services. This would roll the seven Pods to the proposed nodes, so no apply was made pending explicit user approval.
