# Implementation plan: request-bound SRv6/P4 realization for HIL

> **Execution mode:** inline in the current `/home/CoreRouter` workspace. Do not create/switch branches or overwrite the pre-existing working-tree changes. No commit/push.

**Goal:** Carry an admitted request through a topology-derived SRv6 path, exact BMv2 rule installation/readback, packet/counter proof, then a safe Make-Before-Break migration.

**Approved pair-smoke contract (2026-11-17):** use `source_node` as ingress; send to a dedicated `vnf-voc` test endpoint created at `v_place`; use `v_route` as the profile whose MSD bound is checked. The smoke is pair-level. E1 separately defines and proves ordered full chains of at least three VNFs. This does not change any of the seven baseline placements or claim historical placement.

**Architecture:** The live audit shows the current P4 program is not capable of proving the target path: all ten `routing_v6` tables have only default drop; each `srv6_local_sid` has only its bootstrap `fc00:<switch>::1` entry; `srv6_advance_segment` only decrements `segmentsLeft` and does not update `ipv6.dstAddr`. Therefore a code-only alias from virtual `2001:db8` SIDs to current `fc00` entries is invalid. Correct the packet pipeline and its topology-derived forwarding rules, then bind those rules and readback to the immutable admitted realization. Keep current state fail-closed until each gate passes.

**Spec/source of truth:** `docs/AIO-mesh-rev1/SEMANTICS_CONTRACT.md`, `PAIR_ACTUATION_AUDIT.md`, `todo-2.md`, `infrastructure/sdn/topo_p4.py`, compiled BMv2 P4Info/JSON, and live BMv2 table dumps. Existing local admission semantics remain pair-level unless E1's chain work separately proves a full-chain contract. No historical placement/profile is changed.

## Evidence captured before implementation

- `live_p4_readonly_audit.txt`: read-only `show_tables`, `table_dump routing_v6`, `table_dump srv6_local_sid`, and MSD counter read across s1–s10.
- `srv6_basic.p4`: current SRH action comment calls out a missing SID index mapping; implementation decrements `segmentsLeft` only.
- `topo_p4.py`: declares the Vietnam graph and hosts, but active controller bootstrap installs SIDs only; it does not populate forwarding routes.
- `live_p4_ports_all.txt`: `show_ports` reports every declared BMv2 port UP on all ten switches. `live_host_links.txt` captures named Mininet backbone veth peer pairs and `veth-hN-k8s` bridge ports; because it includes unrelated Docker/Calico links and does not identify the active peer namespace for each Kubernetes-facing veth, it is not yet proof of the VNF endpoint path.
- `orchestration_service.py` maps each logical Vietnam node to one of three Kubernetes hosts, while `topo_p4.py` separately maps logical index `i` to switch `s{i+1}`. The configuration correspondence exists in source, but no packet endpoint contract binds `(v_place, v_route)` to an ingress host, VNF service IP, and ordered forwarding path.
- `vnf-voc.yaml` in `vnf-inputs` provides a readiness-probed HTTP endpoint (`/healthz`, `/echo`) and is a candidate bounded test workload. The default firewall template is an `echo`/`sleep` placeholder and cannot serve as an HTTP forwarding target.
- `hybrid_decision.py` ignores `SFCRequest.source_node` and `destination_node` when creating its pair-level SID list. Admission currently reserves a pair and does not trigger create/forwarding on all accepted branches.
- API smoke confirms alert requests stop before Tekton with `UNSUPPORTED_ADMITTED_REALIZATION`.

## Ordered tasks and stop gates

### Task 1 — Define packet/path contract and derive forwarding model

- Write tests first for topology graph validation, deterministic path derivation, exact SID depth/MSD, and unsupported endpoints/disconnected paths.
- Derive switch/node mapping and physical port/peer/MAC data from the active topology and Mininet/BMv2 interfaces; do not infer from switch numbering alone unless verified against live state.
- Specify wire SRH ordering, `segmentsLeft`, terminal behavior, VNF endpoint adjacency, and how the service pair maps to actual hops. A SID list may only be admitted when its exact physical path is materialized and within each involved profile's limit.

**Gate 1:** A reviewable diagram/table maps the bounded pair-level test from ingress through one `/echo` test VNF and back, with each hop mapped to switch, ingress/egress port, SID, peer MAC and P4 action using observed topology/config. `(v_place, v_route)` and `msd_req` must have a documented wire meaning, and every eligible logical node must map to the live Kubernetes endpoint path. If the current abstraction does not define this, keep admission-only behavior and stop before implementation or actuation instead of inventing the meaning. E1 separately extends this to ordered full chains.

### Task 2 — Implement correct BMv2 SRH behavior and route bootstrap

- Add failing P4/source or model tests covering valid multi-segment progression, terminal `segmentsLeft`, malformed/over-MSD rejection and unchanged source/destination at the wrong stage.
- Update `srv6_basic.p4` so each hop sets the next IPv6 destination from the parsed SRH according to the agreed wire-order contract, and updates hop limit/checksum/deparser state consistently.
- Generate `routing_v6` entries from the verified topology adjacency and live BMv2 port/MAC inventory; remove fixed s1/port/MAC assumptions.
- Compile every required MSD profile and compare resulting table/action definitions with generated P4Info/JSON. No live process restart in this task.

**Gate 2:** P4 build succeeds for all topology MSD variants; packet/model tests prove segment progression and ordinary IPv6 routing; generated routes reference actual ports and profile limits. Save source/build hashes.

### Task 3 — Transactional controller install and exact readback

- Extend the Thrift adapter with safe parsing for exact table dumps and per-switch counters; malformed/unknown output is failure, never success.
- Install new rules without deleting old rules. Read back every requested rule and compare switch/table/key/action/parameters to the admitted realization. Only a complete exact match may return correlated confirmation.
- Roll back only rules proven to belong to this operation; on uncertain install/readback, retain old path and both VNFs and journal `STEERING_UNCERTAIN`.
- Add tests for absent table entry, duplicate entry, partial install, command error text with exit 0, wrong switch/action/port, operation mismatch and rollback safety.

**Gate 3:** Unit/integration tests prove controller cannot confirm on partial or mismatched rules and cannot delete old rules before exact readback.

### Task 4 — Bind API admission to the same realization

- Replace `forwarding_sid=None`/documentation SID generation with the Task 1 path compiler output bound to request ID, operation ID, topology hash, profile hash and SID stack.
- Pass that immutable handle through create/readiness/steering; remove independent endpoint SID generation and hardcoded P4 payloads.
- Validate admission, endpoint readiness and route MSD against the same concrete path; reject unsupported paths before actuation with no PipelineRun or rule mutation.
- Preserve current ledger behavior and fail-closed reservations on uncertain deployed state.

**Gate 4:** Unit/API tests establish one-to-one identity from admission through endpoint readiness and controller payload; rejected paths leave no PipelineRun/P4 entry and release only the named unactuated reservation.

### Task 5 — Offline and live bounded forwarding smoke

- Offline: run all focused Python tests, P4 compile, controller table/parser tests, and inspect generated manifests. Review source diff with existing local edits untouched.
- Before live dataplane changes, snapshot all BMv2 rules/process/session state again and obtain a rollback bundle of current JSON, launch args, topology and controller state.
- **Live restart/mutation gate:** present the concrete compiled P4 artifacts, exact command, expected switch interruption, and rollback command for approval before stopping/restarting the shared Mininet/P4 session or changing live BMv2 rules.
- After approval: use a dedicated source/destination flow and temporary, identifiable test object; capture rules before/after, endpoint readiness, pcap at both ends, per-switch counter deltas and controller operation IDs. Clean only after confirmed absence and reconciliation.

**Gate 5:** Request-correlated packets traverse the expected hops, exact table readback matches, counters increase on those hops, and the old path remains intact on any induced failure. Inject an over-MSD packet and prove parser drop plus counter increment.

### Task 6 — Bounded migration proof

- Run one migration only after Gate 5. Correlate old/new names, request/operation IDs, admitted SID/path, Ready Pod, exact rule readback, packet continuity, counter deltas and SQLite journal state.
- Confirm BREAK occurs only after steering/readback/packet evidence; otherwise leave both sides and ledger charges for reconciliation.

**Gate 6:** Completed migration and negative/uncertain cases reconcile all resources and ledger rows. No zero-downtime claim without continuous packet evidence.

## Experiments after HIL gates

1. Finish E1 chain trace and state exactly what is pair-level versus full-chain.
2. Run E2 matched baselines/traces and acceptance accounting with raw request IDs; calculate paired bootstrap CI95, Wilcoxon, Holm and rank-biserial effect.
3. Run E3 controlled ablations on identical traces/seeds and distinguish candidate masking from runtime admission enforcement.
4. Run E4 10/25/50/100-node, arrival and concurrency sweeps; record stage timestamps and calculate decision percentiles and completed-op throughput correctly.
5. Run E5 only if the actual runtime contains the candidate-path cache; otherwise remove its claim.
6. Run E6 fault injection and 24-hour schedule only after all bounded smoke gates pass. Record actual counts rather than forcing the historical target.
7. Reconcile all raw artifacts and update manuscript/revision responses with only observed claims.

## Current stop

The read-only P4 audit has established all BMv2 launch interfaces and named backbone link peers; every expected port is UP. The active K8s bridge has ten UP `veth-hN-k8s` members, address `10.1.240.1/16`, and the Mininet return route `10.0.0.0/24 via 10.1.240.91`. Attempting to inspect the Mininet host namespace directly failed with `nsenter: cannot open /proc/<pid>/ns/net: Permission denied`; this leaves the hN-side address/route/MAC unverified from live kernel state. The source contract treats `msd_req` as exact realized SID depth. An offline deterministic minimum-hop path compiler now maps node paths to observed `fc00:<switch>::1` SIDs, rejects any path whose depth differs from `msd_req`, and checks the selected `v_route` profile limit before reservation. Focused path tests (6) and hybrid admission tests (12) pass. The compiled path remains candidate-only (`forwarding_sid=None`) because P4 rule realization/readback is not implemented. `vnf-voc` has not been created and no P4/Kubernetes live mutation has been made. Gate 1 remains incomplete until endpoint namespace routing/MAC and packet encapsulation/decapsulation contract are proven. Shared Mininet/BMv2 restart remains a separate explicit live gate.
