# 246 Testbed Recovery and HIL Execution Plan

> **For the agent on 246:** execute the phases in order. Each phase has a stop gate. Do not skip a gate because the next command appears to work.

**Goal:** Rebuild a capacity-valid seven-VNF admission baseline on server 246, retire the other 43 VNF deployments from the recorded 50-instance inventory, then run an end-to-end HIL experiment that records admission, VNF readiness, steering, migration, packet evidence, and resource counters.

**Architecture:** Use the existing MicroK8s `core-router` cluster, Tekton, backend, Mininet, BMv2 switches, and SDN controller on 246. Seed a fresh durable admission ledger from the seven recovered request profiles and the proposed rebalance file. Full HIL is gated on a verified admission-to-forwarding mapping; the current source intentionally refuses physical actuation without that mapping.

**Tech stack:** Ubuntu, Docker, MicroK8s/kubectl, Tekton, FastAPI/Python 3.11, SQLite reservation ledger, Mininet, BMv2/P4, SDN controller.

**Source inputs:**

- `configs/hil/recovered_hil_profiles.json`
- `configs/hil/base_inventory_assignment.proposed.json`
- `docs/AIO-mesh-rev1/todo-2.md` (E6)
- `docs/AIO-mesh-rev1/PAIR_ACTUATION_AUDIT.md`
- `docs/AIO-mesh-rev1/SEMANTICS_CONTRACT.md`

## Global constraints

- Target the existing testbed at `/home/CoreRouter` on 246, as requested. Do not provision a VM, change host routes/bridges/firewall rules, or run `setup_testbed.sh` on the shared host.
- This target differs from the VM-only workflow in `docs/hil/DEPLOYMENT.md`. If the owner or agent is required to enforce that VM workflow instead, stop before any mutation and report the conflict; do not silently create a VM.
- The profile values are CoreRouter modeled admission units (`cpu_req`, `ram_req`, per-request `msd_req`). They are not Kubernetes CPU/memory quantities. Do not convert 64 CPU units into `64m`, or infer MSD from Kubernetes resources.
- Each recovered profile is an accepted request from a different historical run. They are not a simultaneous historical snapshot. Use the proposed placement file only after the user approves its explicitly synthetic rebalancing.
- The 25,000-request and outcome counts in `todo-2.md` are claims to measure, not values to force or expected pass criteria. Preserve actual results even when they differ.
- Back up the live reservation DB and migration journal before any restart, delete, or ledger replacement. `run_backend_docker.sh` currently removes the old container and does not mount `/app/results/rev1/runtime`; without a persistence fix, a restart loses its SQLite state.
- Delete only the 43 exact VNF names in this plan after matching them against a fresh live snapshot. Keep the seven recovered names. Never delete all Deployments, a namespace, all Docker containers, Tekton history, or shared services by selector.
- Do not commit or push from 246 as part of this run.

## Critical source findings and stop gates

1. `NetworkStateManager.sync_with_kubernetes()` retains missing records as `presence_unconfirmed`; deleting Deployments alone does not clear old ledger entries. `/api/orchestrate/reset` refuses records with `accounting_unknown` or deployed state. Seed a new ledger only after backup and while the backend writer is stopped.
2. The admission profile builder currently sets `forwarding_sid=None` in `src/portal/backend/app/services/hybrid_decision.py`. When a DRL alert requests actuation, `orchestration_router.py` returns `409 UNSUPPORTED_ADMITTED_REALIZATION` before Tekton/Make-Before-Break. Do not call the full HIL successful until a verified realization mapping, controller readback, readiness correlation, and packet evidence pass.
3. The seven proposed placements are CPU/RAM-capacity valid in the Vietnam model and their routes meet the stated MSD limits. They are proposed assignments, not historical placements. No Kubernetes mutation may use them until the user approves `base_inventory_assignment.proposed.json`.
4. `vnf-voc-phase3` is in the 43-name retirement list, but its NodePort service was used by Phase 3 bridge validation. If Phase 3 validation is required, recreate that support service outside the admission-managed `core-router` inventory (or add an explicit, verified exclusion rule) before the phase check. A support VNF left in `core-router` will be seen as an unaccounted VNF by the current backend.

## Inputs and inventory allowlists

### Keep and rebuild/reconcile these seven profiles

```text
vnf-attack-004e219d
vnf-attack-0faeed9f
vnf-attack-228edabf
vnf-attack-2f0aa313
vnf-attack-57b6f205
vnf-attack-8bf0425e
vnf-attack-af13f6df
```

The exact request values and CSV provenance are in `configs/hil/recovered_hil_profiles.json`. The proposed placement/route assignment is in `configs/hil/base_inventory_assignment.proposed.json`.

### Retire these 43 names, only if the fresh live snapshot still matches

```text
scale-idps-42
scale-router-90
scale-router-90-mig
vnf-attack-13fca5cb
vnf-firewall-ct-04
vnf-firewall-dn-02
vnf-firewall-hcm-01
vnf-firewall-nt-03
vnf-idps-ct-01
vnf-idps-dn-03
vnf-idps-hn-01
vnf-idps-nt-02
vnf-idps-vinh-01
vnf-lb-hcm-03
vnf-lb-hp-03
vnf-lb-hue-01
vnf-mbb-src-1779442924
vnf-mbb-src-1779447740
vnf-mbb-src-1779447740-mig
vnf-nat-ct-02
vnf-nat-dn-01
vnf-nat-hcm-02
vnf-nat-hn-03
vnf-nat-hue-03
vnf-nat-nb-01
vnf-nat-nt-01
vnf-nat-qn-01
vnf-nat-vinh-02
vnf-node-1
vnf-node-hn
vnf-node-nat
vnf-router-ct-03
vnf-router-hp-02
vnf-router-hue-04
vnf-router-qn-02
vnf-router-vinh-03
vnf-test-smoke
vnf-voc-hn-02
vnf-voc-hp-01
vnf-voc-hue-02
vnf-voc-nb-02
vnf-voc-phase3
vnf-voc-qn-03
```

These lists come from the user-supplied 50-Deployment inventory snapshot. They are expected names, not proof the live cluster is unchanged.

---

## Phase 0 — Transfer and identify the target

- [ ] Copy this plan and both `configs/hil/*.json` files to `/home/CoreRouter` on 246 using the already-approved transfer method.
- [ ] On Hanoi and again on 246, run `sha256sum docs/hil/PLAN_RUN_TESTBED_246.md configs/hil/recovered_hil_profiles.json configs/hil/base_inventory_assignment.proposed.json`; compare all three hashes. On 246 also run `python3 -m json.tool` on each JSON file. Do not edit the source profiles during transfer.
- [ ] Confirm `hostname`, current UTC time, repository path, branch, commit, and `git status --short --branch`. Expected repository: `/home/CoreRouter`; expected branch family: HARP. Preserve any worktree changes. Do not checkout/reset/pull; stop before editing or rebuilding a file that overlaps an unexplained local change.
- [ ] Confirm the agent is operating on server 246 and that this is the existing MicroK8s/BMv2 testbed the user selected. Do not use the cgroup-v2 VM preflight as a gate for this existing-host plan.

## Phase 1 — Read-only preflight and evidence snapshot

- [ ] Create a restricted run directory, e.g. `results/hil/rebuild_$(date -u +%Y%m%dT%H%M%SZ)`, and record its path.
- [ ] Capture read-only snapshots of nodes, deployments, services, endpoints, pods, `vnf-inputs`/`vvoc-app` ConfigMaps, Tekton PipelineRuns/TaskRuns, Docker containers, and `tmux ls`. Do not dump Kubernetes Secrets into logs.
- [ ] Query and save `/`, `/api/health`, `/api/ai/status`, `/api/orchestrate/status`, `/api/orchestrate/state`, and `http://127.0.0.1:8765/health`. Save BMv2 reachability for Thrift ports 19091–19100.
- [ ] Check for running benchmark/HIL processes and nonterminal Tekton runs. Wait for or explicitly reconcile any active run before proceeding; do not kill an unknown tmux session.
- [ ] From the live Deployment snapshot, verify the expected 50 names exactly: seven keep names plus the 43 retirement names above. If count, names, readiness, labels, or namespace differs, save the diff and stop before deletion.
- [ ] Record `unaccounted_vnfs`, backend model status, namespace, current pipeline state, Mininet veths, BMv2 switch status, and the current `vnf-voc-phase3-svc` endpoint. A health response alone is not a forwarding check.

**Gate 1:** all services are identified; no active job is using the namespace; the 50-name diff is empty; source profile files are available and unchanged.

## Phase 2 — Backup durable state and deployment manifests

- [ ] Export current Deployment and Service YAML for all 50 VNF names into the run directory. Export relevant Tekton PipelineRuns for provenance. Preserve the original vVOC manifest/config map separately.
- [ ] Determine the backend container's effective `CORE_ROUTER_RESERVATION_DB` and `CORE_ROUTER_MIGRATION_JOURNAL` paths from its environment/defaults. Current defaults are `results/rev1/runtime/reservations.sqlite3` and `results/rev1/runtime/migrations.sqlite3`, relative to `/app` in the container.
- [ ] Copy each existing SQLite file that exists out of `3s-com-backend` into the run directory. Include checksums. Do not print environment values other than these two paths.
- [ ] Save the current Docker image tag/digest, container inspect mounts (not secrets), and backend logs around the current HIL failure.

**Gate 2:** manifests and existing DBs are backed up and checksummed. If a DB path is unknown, unwritable, locked by another process, or cannot be copied, stop.

## Phase 3 — Prepare code and offline ledger initializer before cluster changes

- [ ] Compare the HARP source on 246 with the audited files. Review `src/core/state_manager.py`, `src/portal/backend/app/containers/service_container.py`, `src/portal/backend/app/services/hybrid_decision.py`, `src/portal/backend/app/routers/orchestration_router.py`, `src/portal/backend/app/services/orchestration_service.py`, and `src/infrastructure/sdn/controller.py`.
- [ ] Update `run_backend_docker.sh` so the reservation DB and migration journal live under a host-mounted persistent directory at `/app/results/rev1/runtime`. Confirm the mount and environment paths with `docker inspect` after restart.
- [ ] Add an offline initializer at `scripts/hil/seed_base_inventory.py` with this interface: `venv/bin/python scripts/hil/seed_base_inventory.py --profiles configs/hil/recovered_hil_profiles.json --assignment configs/hil/base_inventory_assignment.proposed.json --topology vietnam --output results/hil/<run-id>/reservations.seed.sqlite3 --summary results/hil/<run-id>/seed_summary.json`. It must validate unique names, `cpu_req`/`ram_req` totals per placement node, route-node MSD capability, assignment/profile name equality, and Vietnam topology identity, then write a **new temporary** ReservationStore using `NetworkStateManager.try_reserve()` for the seven records. It must refuse to overwrite a live/locked ledger and must not call Kubernetes. Replace `<run-id>` with the run directory created in Phase 1.
- [ ] Make the initializer produce a JSON summary with source hashes, profile count 7, assignment count 7, state version, per-node CPU/RAM, route MSD maxima, and zero `accounting_unknown` records. Close/checkpoint SQLite and atomically promote the new DB only after every check passes; account for `-wal`/`-shm` sidecars and preserve the old DB backup.
- [ ] Implement the admission-to-actuation handoff end to end: preserve the admitted immutable realization from `orchestration_router.py` into `OrchestrationService.make_before_break_sequence()` and the SDN controller; derive switch/port/SID mappings from the live Vietnam `topo_p4` and loaded P4 profile; require controller operation ID and rule readback to match the request. Verify the resulting path with a packet capture and switch counter delta. Reject on topology hash/profile mismatch, missing mapping, or readback mismatch. Do not fill `forwarding_sid` or any controller SID with an invented constant. Keep an explicit test showing unsupported realizations are rejected before Tekton creates resources.
- [ ] Ensure deployment readiness is tied to the same admitted request/new VNF, and Make-Before-Break does not delete the old VNF until steering confirmation and packet/readback checks pass. Keep failed or uncertain operations charged for reconciliation.
- [ ] Verify the support-only vVOC handling: either move its Phase 3 fixture into a separate namespace or implement a narrowly scoped, tested exclusion from admission synchronization. Do not leave it as an unknown Deployment in `core-router`.
- [ ] Add/run focused verification for the initializer, restart persistence, unknown-inventory fail-closed behavior, and API/actuation rejection/success gates. Run `bash test/test_phases.sh phase3` and `phase5` only after the app/support changes are built; record raw outputs.

**Gate 3:** verified P4 realization and the offline initializer are ready; all focused checks pass. If the mapping cannot be proven against actual switch/port/SID behavior, stop at limited admission testing; do not start or label the run full HIL.

## Phase 4 — Controlled retirement and baseline rebuild

- [ ] Obtain approval for the proposed placement assignment file before changing the seven current VNF locations. Do not use the historical placements as a simultaneous assignment.
- [ ] Pause all `/api/orchestrate` traffic and scenario runners. Backups from Phase 2 must exist before replacing the backend container.
- [ ] Add the host bind mount for `/app/results/rev1/runtime` to `run_backend_docker.sh`, copy the existing DB/journal into that directory, then restart the backend once and verify it reopened the same old ledger. This validates persistence before retirement.
- [ ] Re-run the exact 50-name comparison immediately before deletion. Generate a 43-line removal file from the names in this plan; never derive deletion targets from a broad label selector.
- [ ] Delete only the 43 named Deployments with wait-for-absence. Delete a corresponding `<deployment>-svc` only when a live Service has selector exactly `app=<deployment>` and the service is not a shared/NodePort dependency. Preserve PipelineRun history. Do not remove `vnf-voc-phase3-svc` until its support replacement is healthy.
- [ ] Verify all 43 Deployments and their selected Pods are absent; inspect any replacement/migration PipelineRun before continuing. Keep the seven recovered names running until their approved placement update is ready.
- [ ] If retaining Phase 3 NodePort validation, recreate `vnf-voc-phase3` as test-support in a separate namespace outside the admission manager's `core-router` scope and verify `NodePort 31656`/`/healthz`; update the Phase 3 check to use that namespace. Otherwise mark Phase 3 bridge validation as intentionally unavailable for this HIL run. Do not leave an unaccounted support Deployment in `core-router`.
- [ ] Reconcile the seven retained Deployments to the approved assignment. Before applying anything, inspect the generated manifest from the actual `vnf-inputs` ConfigMap and the live `vnf-lcm-fast` Pipeline/Tasks. Confirm the operation is idempotent for an existing Deployment, preserves the VNF name/labels/service, and maps the requested physical node correctly. `POST /api/deploy` only accepts `name`, `type`, `profile`, and `location`; it does not carry the recovered CPU/RAM/MSD accounting profile, and its template defaults may replace fields. Do not use it for these existing VNFs unless a dry-run/export proves the resulting YAML preserves required fields and selects the intended K8s worker. If that cannot be proven, stop and report the exact mismatch before changing locations. Wait for each PipelineRun and Deployment rollout; do not change recovered CPU/RAM/MSD profile values in the ledger.
- [ ] Stop `3s-com-backend` after all seven rollouts complete. Build a fresh temporary ledger from the seven profiles, confirm its summary, then atomically replace the active reservation DB while preserving the old DB backup. Start the backend from the reviewed image with the persistent mount.
- [ ] Query `/api/orchestrate/state`; require exactly seven admission-managed baseline VNFs, all Ready, all profiles known, `unaccounted_vnfs=[]`, `reservation_persistence="durable"`, and no extra VNF Deployment in the managed namespace. Verify model remains loaded and backend logs have no startup/SQLite errors.

**Gate 4:** seven baseline VNFs are Ready, ledger matches the assignment, 43 retired names are absent, and the support service is either separately healthy or explicitly out of scope.

## Phase 5 — Single-request create and migration smoke

- [ ] Before load generation, submit one controlled request with a unique request ID and a profile that fits current capacity/MSD. Save request JSON and response.
- [ ] Verify the matching ledger reservation, Tekton PipelineRun, new Deployment, Pod readiness, exact operation ID, controller rule readback, packet capture/forwarding, and per-switch MSD counter delta. Verify the previous VNF remains until the new path is confirmed, then verify old-resource teardown.
- [ ] Inject one over-MSD request and verify rejection before actuation; confirm no Deployment, PipelineRun, or P4 rule was created for it.
- [ ] Run one controlled migration and verify old/new names, placement, SID list, controller operation ID, readiness, rule readback, packet evidence, and completed BREAK in the migration journal.
- [ ] Reconcile and clean smoke-test VNFs through the lifecycle API only after confirmed absence; do not call `/api/orchestrate/reset` while any deployed reservation remains.

For the first bounded live-runner check, only after Gate 5's single-request checks pass, run from `/home/CoreRouter` with the persistent backend and verified SDN controller:

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "results/hil/${RUN_ID}/smoke"
set -o pipefail
venv/bin/python -m src.analytics.benchmark.benchmark_testbed.run_all_scenarios \
  --api-base-url http://127.0.0.1:8000/api \
  --sdn-base-url http://127.0.0.1:8765 \
  --scenario ddos_mbb \
  --steps 20 \
  --request-interval-s 10 \
  --seed 246 \
  --no-reset \
  --no-baselines \
  --output-dir "results/hil/${RUN_ID}/smoke" \
  2>&1 | tee "results/hil/${RUN_ID}/smoke/run.log"
```

The runner creates its own timestamped child directory. Keep the backend baseline intact; inspect the generated `preflight.json`, `summary.csv`, `all_records.csv`, JSON outputs, and backend/controller logs before extending duration. If this smoke run does not produce request-correlated readiness, steering/readback, and packet evidence, stop; do not launch the 24-hour job.

**Gate 5:** both accepted create/migration and rejected over-MSD cases have request-correlated evidence, and all resources/ledger entries reconcile. Any 409 `UNSUPPORTED_ADMITTED_REALIZATION`, missing packet, missing readback, or ambiguous cleanup blocks the full run.

## Phase 6 — HIL load and stability run

- [ ] Run a short bounded scenario first, using the live runner with `--no-reset` because seven deployed baseline VNFs are present. Do not use concurrency runner defaults that reset the live ledger.
- [ ] Confirm the short run records offered/admitted/rejected/deployed/migrated counts separately, request IDs, CPU/RAM/MSD rejection reasons, decision timing, deployment/readiness timing, steering timing, and packet/counter evidence.
- [ ] For E6 stability, use a deterministic 24-hour request schedule if the protocol requires an exact offered-request count. The existing `normal_load` generator intentionally emits a request on only about 20% of iterations; do not assume `--steps 25000` means 25,000 offered requests. Record actual offered requests and use a paced schedule rather than forcing the historical target outcomes.
- [ ] Capture per-hour logs, resource and load context, workload seed/trace hash, source/model/config hashes, Tekton failures, controller errors, readiness timeouts, migrations, packet captures, MSD counter deltas, and full raw CSV/JSON outputs under `results/hil/<run-id>`.
- [ ] Do not claim the `todo-2.md` target counts were reproduced unless the raw run proves them. Limit the result to the actual software/BMv2 environment.

## Phase 7 — Final reconciliation and evidence handoff

- [ ] Re-export Deployment/Service/Pod/Tekton/ledger state and compare with the Phase 2 snapshot.
- [ ] Confirm the seven baseline VNF records plus any intentionally retained new test VNFs all have known profiles; no unexplained reservation, active operation, PipelineRun, Pod, Service endpoint, or P4 rule remains.
- [ ] Keep the persistent ledger and HIL results. Do not delete the 43-name backup, old SQLite backup, logs, Pcaps, or run manifests.
- [ ] Produce a short report with pass/fail for each gate, exact command transcript, run directory, hashes, and unresolved failures. Do not commit or push.

## Final success criteria

The testbed is ready for a full HIL claim only if all of the following hold:

- Seven recovered profiles are loaded and capacity-valid under the approved new placement.
- The other 43 exact old VNF Deployments are absent; no unaccounted VNF remains in the admission-managed namespace.
- The reservation DB survives backend restart and its topology hash matches the Vietnam topology.
- A new request demonstrably creates a ready VNF through the HIL path.
- A migration demonstrably preserves the old instance until the new path is ready and verified, then completes steering/readback and cleanup.
- An over-MSD request is rejected before deployment/actuation.
- Request-correlated API, Kubernetes/Tekton, controller/readback, packet, counter, timing, and run-manifest evidence is saved.

If the actuation or packet-evidence gate fails, report **“baseline rebuilt; full HIL blocked”** and preserve the evidence. Do not report the testbed as ready for full HIL.
