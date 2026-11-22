# 246 full-HIL execution plan

## Goal

Reach an evidence-backed path from source-backed admission through VNF creation/readiness, BMv2 P4 forwarding and Make-Before-Break migration, then run only the experiments whose prerequisites have passed. Preserve the seven-VNF baseline and all existing safety gates.

## Current evidence

Latest read-only BMv2 table audit is in `live_p4_readonly_audit.txt`: across all ten switches, `routing_v6` contains only default drop; each `srv6_local_sid` contains only `fc00:<switch>::1`; all sampled MSD-drop counters are zero. In `srv6_basic.p4`, `srv6_advance_segment` decrements `segmentsLeft` but does not set the next IPv6 destination. The current program/controller therefore cannot prove multi-hop forwarding. See `P4_REALIZATION_IMPLEMENTATION_PLAN.md` for the revised, gated implementation plan.

- The seven baseline VNF records are durable and known; all seven Deployments are Ready at the approved synthetic placements; the retired 43 Deployments are absent.
- Admission-only reserve/release passes. Alert actuation is rejected with `UNSUPPORTED_ADMITTED_REALIZATION` before Tekton.
- `hybrid_decision.py` creates virtual SIDs and sets `forwarding_sid=None`.
- `topo_p4.py` describes ten Mininet switches/hosts and known backbone links. Controller bootstrap entries include `fc00:<switch>::1`; the current orchestration path instead hardcodes switch `s1`, a route, MACs/port, and derives a separate endpoint SID.
- Controller health and BMv2 Thrift connectivity do not prove table contents or packet forwarding. No request-correlated readback/packet/counter/migration evidence exists yet.

## Approaches considered

1. **Use the existing ten-switch BMv2 topology as the physical substrate (chosen).** The captured BMv2 port tables show all declared ports UP. The captured host link snapshot also shows the named backbone veth peers. This is enough to map backbone port identities when reconciled against `topo_p4.py`, but does not yet establish the service endpoint path through `hN`/Kubernetes. Build a deterministic route from verified substrate edges, then add exact rule readback and preserve old rules until packet evidence confirms the replacement.
2. **Correct the P4 pipeline/runtime where the source audit requires it.** Current admitted documentation-prefix SIDs are not the live `fc00:` local SIDs; the pipeline also does not advance IPv6 destination across SRH segments, while all routing tables currently default-drop. A translation-only change is invalid. Any compiled pipeline or bootstrap change remains offline until its live restart gate.

No SID, port, MAC, switch mapping, resource value or placement will be inferred from a label or invented. The implementation remains fail-closed until a mapping is derived and verified.

## Stages and stop gates

### 0. Protect and snapshot

Reconfirm the HIL baseline, `corerouter-p4` session, controller, BMv2 containers, repo status and existing uncommitted changes. Capture source/config hashes and current rules before experiments. Never rebuild/restart Mininet or alter host networking as an audit shortcut.

**Gate:** exactly seven known/Ready records, no unknown inventory, no active migration/PipelineRun, baseline and controller state captured.

### 1. P4 realization audit (read-only)

Read P4 table/action definitions, compiled P4Info/JSON, live switch table dumps/counters, topology links, ports/MACs, bootstrap rules, and actual Mininet↔Kubernetes attachment. Determine whether the P4 program really advances a segment list or only forwards IPv6 destinations. Produce a request-level virtual-to-physical trace with MSD accounting and identify the destination VNF endpoint semantics.

**Gate:** one concrete supported path and actual rule schema can be derived from current artifacts and live state. Otherwise stop and report the missing source evidence; do not inject rules.

### 2. Admission-to-realization design and implementation

Bind one immutable operation/request identity, topology hash, admitted profile, SID/path and physical rules. Make path selection verify every hop and per-list MSD. Reject before reservation/actuation when mapping is unsupported. Remove hardcoded `s1`/port/MAC/endpoint-SID assumptions. Add controller rule readback and verify the complete new rules before reporting steer confirmation. Do not delete old rules on partial install, mismatched readback, timeout or uncertain response.

**Gate:** focused tests cover valid mapping, topology/profile mismatch, missing hop, MSD rejection, stale operation IDs, partial install/readback and no-BREAK-on-uncertainty; source review and preflight pass.

### 3. Bounded dataplane proof

Use a dedicated test flow with known source/destination and capture points. Record baseline and post-flow packet/counter values, exact request/operation IDs, rules before/after, packet capture, and switch route. First test a non-migration create: admission → Tekton → Ready endpoint → steering → packet delivery. Do not use a baseline VNF as a disposable target.

**Gate:** request-correlated rule readback and packets traverse the intended path; counter deltas agree; an over-MSD request creates no reservation/workload/rule.

### 4. Make-Before-Break proof

Run one bounded migration between known endpoints. Require new endpoint readiness, successful exact rule readback and packet continuity before BREAK. If steering or readback is uncertain, retain both VNFs/reservations and record a recoverable journal state. Verify completed journal, old endpoint absence only after confirmation, and resource reconciliation.

**Gate:** one accepted create and one migration complete with correlated API/Kubernetes/Tekton/controller/pcap/counter/journal evidence; negative case rejects before actuation; no orphan or unknown records.

### 5. Todo experiments, in order

- **E1:** finish pair-to-path-to-SID-to-MSD-to-admission trace; state pair-level versus full-chain guarantees.
- **E2:** matched traces/baselines, acceptance accounting and statistical analysis from raw data.
- **E3:** controlled ablations and safety attribution on matched seeds/traces.
- **E4:** topology/concurrency/latency sweeps with per-request stage timestamps and correct percentile/throughput definitions.
- **E5:** run only if a candidate-path cache exists in the final runtime; otherwise document removal from scope.
- **E6:** only after Stages 3–4 pass, run fault injection and then the 24-hour schedule. Record actual offered/admitted/deployed/rejected counts; do not force historical target counts.

### 6. Manuscript and final reconciliation

Regenerate only claims supported by raw artifacts, complete revision status/response items, preserve all source traces and hashes, and report software/BMv2 limitations. Do not claim ASIC/carrier-grade or zero downtime without evidence.

## Immediate next action

Stage 1 has verified that all BMv2 ports are UP and the saved host snapshot includes named backbone veth peer pairs. It has not verified the active `hN` attachment through to a Ready VNF endpoint, nor established a sound mapping from the model's `(v_place, v_route)` to the testbed's ten city/switch nodes. This is now the concrete stop: keep the existing 7-VNF baseline intact, finish the source/topology contract offline, and implement a bounded explicit realization model with fail-closed behavior. The live P4 program has only default-drop IPv6 routes and incomplete SRH progression. No live P4 mutation or shared Mininet restart until compiled artifacts, a dedicated endpoint, expected interruption and rollback steps are reviewed at the live gate.
