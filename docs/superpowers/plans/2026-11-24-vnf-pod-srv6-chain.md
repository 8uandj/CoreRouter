# VNF Pod SRv6 Chain and Orchestration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the bounded multi-hop SRv6/P4 probe to Kubernetes VNF Pods, then correlate an admitted orchestration request through Tekton deployment, readiness, steering, readback, and packet receipts.

**Architecture:** Each P4 leg decapsulates at a node-side gateway. The gateway sends the unchanged inner packet bytes in a bounded UDP envelope to the next ordinary CNI relay Pod; the Pod records its ID/hash and returns the bytes to the gateway, which emits the next independent SRv6/P4 leg. Report and instrument this UDP handoff separately from P4 legs. Then correlate the chain with the existing admission/deployment/steering path. This does not change the pair-level policy action.

**Tech Stack:** Python 3.11, Kubernetes, Tekton, Mininet, BMv2 P4, SRv6, Scapy.

**Spec:** `docs/superpowers/specs/2026-11-24-hil-e2e-completion-design.md`

## Global Constraints

- Preserve current VNFs, reservations, P4 rules, backend, Mininet, and unrelated services.
- Use separate opt-in template/configuration and unique names; do not edit shared live ConfigMaps during the first pilot.
- Every Pod and P4 leg must record the same run ID, packet ID, and inner-packet hash; gateway UDP handoffs are separate evidence.
- Every leg must fit the configured MSD on every traversed switch.
- Do not claim HARP selected/admitted the full chain; the current policy action remains a pair.
- First live run is one chain with at most 3 packets; increase to 20 only after inspecting the pilot evidence.

## Review Focus

- Missing or duplicate packet IDs must fail the run.
- A Pod receipt must match the original full inner-packet hash.
- Controller readback alone does not prove packet traversal.
- The UDP handoff between the node-side gateway and a Pod must not be mistaken for the measured SRv6/P4 leg.
- CNI, host routing, and node placement can change whether the packet reaches the Pod; capture both sides of each boundary.

### Task 1: Opt-in VNF Pod relay

**Files:** Create `infrastructure/k8s/manifests/templates/vnf-chain-relay.yaml`, `infrastructure/k8s/manifests/chain-relay-app.yaml`, and `scripts/hil/vnf_chain_relay.py`.

**Interfaces:** The Pod receives a bounded UDP envelope from the node-side gateway, validates run/stage/packet identity and the complete inner IPv4 SHA-256, writes JSONL, and returns the unchanged IP bytes to the gateway. The template has readiness/liveness endpoints, resource limits, a unique UDP port, and no host networking. `CAP_NET_RAW` is not needed by this gateway-handoff implementation.

- [x] Implement the Pod UDP-envelope receiver, run/stage/packet marker parser, SHA-256 check, health endpoints, and byte-identical echo.
- [x] Add a dedicated app ConfigMap, template ConfigMap key, Task, and Pipeline without changing `vnf-inputs` or current templates.
- [x] Add explicit rollback instructions; live Deployments and Services were uniquely named and removed after evidence capture.

### Task 2: Mininet gateway and Pod-to-P4 chain probe

**Files:** Create `scripts/hil/vnf_chain_gateway.py`, `scripts/hil/vnf_pod_chain_probe.py`, and `scripts/hil/analyze_vnf_pod_chain.py`; write evidence under `results/hil/vnf_pod_chain_20261124/`.

**Interfaces:** The gateway accepts the first P4-decapsulated packet and Pod handoff receipts for configured run/stage/packet IDs, verifies the inner hash and order, and emits the exact inner IPv4 bytes over the next independently compiled SRv6/P4 leg. On each P4 decapsulation it forwards the bytes to the next Pod. The runner fails on missing/duplicate/reordered receipts or a mismatched hash and captures PCAP/counter deltas.

- [x] Compile/use each leg from the live table readbacks and observed switch host ports; all three paths have SID depth 2 within physical MSD.
- [x] Start two uniquely named relay Pods through Tekton and save PipelineRuns and Ready conditions.
- [x] Run the 3-packet pilot; validate gateway input/output captures, Pod receipts, egress, and exact switch counter deltas.
- [x] After pilot acceptance, run 20 more packets and write a hash-verified manifest and summary.

### Task 3: Correlate an orchestrated VNF with dataplane evidence

**Files:** Create `scripts/hil/orchestrated_vnf_chain.py`; reuse `scripts/hil/live_inventory.py` and the chain analyzer.

**Interfaces:** One request record correlates `/api/orchestrate` request/operation IDs, reservation, Tekton run, Pod readiness, each P4 rule readback, steering confirmation, and packet receipts. The runner starts probes only after the admitted realization and all endpoints are verified. This validates current single-VNF pair-level actuation; it does not assert that policy selected the two-Pod relay chain.

- [x] Capture fresh baseline, state snapshot, admitted topology/profile hashes, and per-probe P4 counters.
- [x] Submit one bounded alert-mode request with a source node and unique service identity.
- [x] Correlate the admitted realization, reservation, Tekton run, Ready Pod, controller operation, P4 readback, HTTP responses, and counter deltas.
- [x] Run 3 requests first, review the HTTP 200 pilot, then run 20; write a manifest with source and evidence hashes.
- [ ] Remove the uniquely owned VNF only after an inverse steering/rollback path exists. It remains deployed and steered so the active route does not point to a deleted endpoint.

## Completion gate

- [x] In the separate two-Pod relay run, each packet is received by both requested Pods in order with unchanged inner bytes/hash.
- [x] Each P4 leg in that relay run has captures and exact counter deltas with no new MSD violation; the single-VNF campaign separately records its exact counter deltas and broad captures.
- [x] One orchestration request is correlated through deployment, readiness, readback, steering, and 23 HTTP 200 responses.
- [x] Report the remaining pair-level policy limitation separately from testbed chain evidence.

## Execution log (2026-11-24)

- **Ruling:** Keep the inner IPv4 bytes, including destination IP, unchanged. Use the existing Mininet hosts `h6` and `h9` as per-stage gateways to CNI relay Pods; after byte/hash verification and Pod echo, each gateway sends the next P4 leg. The UDP handoff is instrumented separately and is not counted as P4 traversal. This uses the observed Mininet-to-Pod route while avoiding the impossible requirement to route one unchanged destination IP to two Pod IPs. Cost if wrong: a packet receipt could be mistaken for direct P4 delivery to the Pod; the evidence therefore records each boundary and makes only the relay-chain claim.
- Read-only live inventory showed the Mininet/P4 bridge on `3s-com`, worker2 Pod-CIDR reachability from h6/h9, and existing active routes for s1→s6, s6→s9, and s9→s10. The required MACs and table entries were read back before sending.
- Task 1 and Task 2 completed using run `podchain20261124b`: two relay Pods were Ready through Tekton; pilot 3/3 and follow-up 20/20 matched at both Pod stages and egress; all hashes matched; expected P4 counter deltas were observed on s1/s6/s9/s10, with no new MSD violation. Artifacts: `results/hil/vnf_pod_chain_20261124/podchain20261124b/`.
- Cleanup removed both run-specific Deployments/Services and the workspace PVC after deleting only completed task Pods labeled for this run. The pipeline records and static opt-in Task/Pipeline/ConfigMaps remain. Post-run inventory returned to 17 VNF Deployments.
- Rollback of the reusable opt-in support objects: `kubectl -n core-router delete pipeline/vnf-chain-deploy task/prepare-vnf-chain configmap/vnf-chain-inputs configmap/vnf-chain-relay-app`. Per-run resources are removed by the probe runner; if interrupted, delete only `deployment/vnf-chain-<run>-s1`, `service/vnf-chain-<run>-s1`, `deployment/vnf-chain-<run>-s2`, `service/vnf-chain-<run>-s2`, the labeled `tekton.dev/pipeline=vnf-chain-deploy,core-router/chain-run=<run>` task Pods, and `pvc/chain-ws-<run>`.
- Task 3 pair-level realization completed as run `orchchain20261124c`: one request correlated to `vnf-voc-02d52f80`, a succeeded `vnf-lcm-fast` PipelineRun, Ready Pod on `k8s-master`, controller confirmation, s1→s2 readback, pilot 3/3 and follow-up 20/20 HTTP 200 responses. Counter deltas were +15 and +100 per switch respectively (TCP frames per HTTP transaction), with zero new MSD violations. Report and hash manifest: `results/hil/orchestrated_chain_20261124/run03/`.
- The request did not select or instantiate the two-Pod relay chain; policy remains pair-level. The newly steered VNF is intentionally retained because no verified inverse-steering cleanup path exists. Inventory is 18/18 Ready (17 baseline plus this experiment VNF). Chain selection and safe removal remain open.

## Opt-in orchestration linkage (2026-11-24)

- Added `scripts/hil/orchestrate_vnf_pod_chain.py`, which requires a completed, correlated pair-level orchestration record, checks a fresh read-only inventory against its backend image, and invokes the existing two-Pod Tekton/SRv6/P4 probe using the same `flow_id` as the chain run ID. The parent manifest hashes the upstream record and all child evidence. A failed finalization can resume from an already successful child manifest without re-sending packets.
- Live run `orchchain20261124c` links the prior successful pair-level operation `7388e25f-4705-4664-833f-c0047d899565` to two Ready relay Pods on worker2. The chain delivered 3/3 pilot and 20/20 follow-up packets in order through both Pod receipts and egress; all inner-packet hashes matched. P4 counter deltas were +23 advance on s1, +23 advance/+23 terminal on s6, +23 advance/+23 terminal on s9, and +23 terminal on s10; new MSD violations were zero.
- The first parent-manifest finalization detected a verifier path-base mismatch after the child run had already succeeded. The verifier was corrected to resolve child-manifest paths from the repository root and restrict them to the run directory; resume finalized the parent manifest without re-running the chain. Parent and child evidence/source hashes then verified with zero mismatches. Per-run Deployments, Services, task Pods, and PVC were removed; the two successful PipelineRuns remain for audit.
- This links a recorded pair-level HARP operation to a separate opt-in testbed chain experiment. It still does not mean HARP selected the two-VNF chain; the pair selected in the linked request is s1→s2, while the measured chain uses the separately specified h1→s6→s9→s10 SRv6/P4 legs. The evidence supports testbed chain traversal under the recorded run, not full-chain policy selection or direct traffic steering through the linked single-VNF Pod.
