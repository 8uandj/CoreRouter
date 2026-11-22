# Live baseline snapshot — 2026-11-17 14:14–14:16 UTC

All commands in this snapshot were read-only. Raw CLI records are in `live_stage0_recheck.txt`, `live_switch_interface_audit.txt`, and `live_k8s_bridge_audit.txt`.

## Cluster and workloads

- Host: `3s-com`; context: `microk8s`.
- Nodes `3s-com`, `k8s-master`, `worker1`, `worker2`: all `Ready`.
- Namespace `core-router`: exactly these seven Deployments, all 1/1 Ready:
  `vnf-attack-004e219d`, `vnf-attack-0faeed9f`, `vnf-attack-228edabf`, `vnf-attack-2f0aa313`, `vnf-attack-57b6f205`, `vnf-attack-8bf0425e`, `vnf-attack-af13f6df`.
- No current Tekton `PipelineRun` has `Succeeded=Unknown`; no Kubernetes Job has active Pods. Historical Tekton runs and task Pods are preserved.
- Baseline location mapping remains the previously approved synthetic assignment; no placement was changed in this run.

## Admission and migration SQLite snapshot

Opened directly with SQLite URI `mode=ro` and `PRAGMA query_only=ON`:

- `results/rev1/runtime/reservations.sqlite3`: one durable snapshot row, schema 1, state version 24, topology hash `67131a546450606da19276263b00d23988d13fd71c17be38cb24a12637fe9f11`.
- Active records: 7, exactly the names above. Pending reservations: 0. Anonymous reservations: 0. `accounting_unknown`: 0.
- `results/rev1/runtime/migrations.sqlite3`: migration claims 0, migration events 0.
- The backend Docker mount maps `/home/CoreRouter/results/rev1/runtime` to `/app/results/rev1/runtime`; no database was replaced or written during this snapshot.

## P4 and Mininet

- `corerouter-p4` remains attached; `bmv2-s1`–`bmv2-s10` run on host networking. Their launch arguments map port IDs to the live `sN-ethM` interfaces and compiled profiles. Backbone peers match the `topo_p4.py` topology and report UP.
- `br-k8s-mn` is UP at `10.1.240.1/16`; all ten `veth-hN-k8s` members report forwarding; return route `10.0.0.0/24 via 10.1.240.91` exists.
- `nsenter` into the Mininet host namespace was denied by the CLI execution container (`/proc/<pid>/ns/net: Permission denied`), so the hN-side IP/MAC/routes remain unverified from live kernel state.
- The previously captured table audit still shows default-drop `routing_v6` tables and bootstrap-only local SID entries. No forwarding rules or packets were added.
