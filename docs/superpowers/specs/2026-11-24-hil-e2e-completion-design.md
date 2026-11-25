# HIL E2E completion design (proposed)

## Intent

Produce reproducible, request-correlated evidence for the paper's testbed claims. The current runtime admits a placement–routing pair and the 2026-11-21 campaign proves deployment, rule readback, steering, and delivery to one VNF. It does not prove ordered traversal of a service chain or continuity during migration.

## Approaches

1. **Complete the existing live testbed (chosen).** Keep the currently running Kubernetes, backend, Mininet, and BMv2 instance; add preflight and focused experiments. This avoids rebuilding the environment but requires careful ownership checks because other services share the host.
2. **Move to the previously specified isolated VM.** Provision and validate a fresh bounded guest before repeating the experiments. This improves isolation but requires hypervisor access, recreation of Kubernetes/Tekton/Mininet, and a new evidence baseline.
3. **Extend HARP to full-chain actions.** Change the policy action, admission predicate, and training/evaluation protocol. This is a separate research change, not a prerequisite for measuring a testbed service chain; existing pair-level benchmark results cannot establish the new policy's performance.

## Proposed implementation for approach 1

1. Record read-only snapshots of backend image, Kubernetes readiness, topology/controller version, P4 profiles and rule counters, firewall/VXLAN configuration, ledger, and host capacity. Use an owned evidence directory and hash inputs. Fail preflight if required state differs from the recorded experiment configuration.
2. Make required network and controller fixes reproducible at startup with explicit status and rollback. Validate them after restart before any campaign. Do not alter unrelated services or purge existing VNFs/rules.
3. Build a bounded chain experiment with at least two distinct VNFs. Give each probe a request ID and packet sequence; capture receipt at ingress, each VNF, and egress. Verify exact order, packet counts, SID list and per-switch MSD against the realized path. Distinguish controller readback from packet traversal.
   The user confirmed that each leg must traverse SRv6/P4 and carry the same inner flow identity. A proxy at each VNF must process the inner packet and re-encapsulate it toward the next VNF over an independently admitted SRv6 leg. The final result must include evidence at every VNF and on every P4 leg; an application-only HTTP relay does not meet this requirement.
4. Build a separate continuous-flow migration experiment. Record send/receive sequence numbers and timestamps before, during and after make-before-break, alongside Pod readiness, steering confirmation, old Pod deletion, and resource ledger state. Report observed loss and interruption; claim zero downtime only if the measured definition and all repetitions support it.
5. Run a request-correlated, bounded long-run campaign that records admission through packet receipt for each accepted request. Keep a separate admission-only run for comparison. Export raw logs, PCAPs, manifests, checksums, and table-generation inputs. Update the manuscript only after the evidence is reviewed.

## Selected near-term chain orchestration design (2026-11-24)

- **Approaches considered:** (1) add a separate opt-in HIL runner over the existing Tekton relay-chain pipeline and probe, linked to a recorded successful pair-level request; selected because it reuses the verified chain and leaves HARP stable. (2) add a new backend/API chain endpoint, which would add runtime/API surface without changing the policy's pair action. (3) change HARP's action to choose full chains, which is a separate model and evaluation project.
- Keep the existing `/api/orchestrate` request and pair-level policy unchanged. A previously recorded successful pair-level request is a fail-closed correlation prerequisite for a separate opt-in two-Pod chain experiment; it does not select or install the chain path.
- Add a dedicated HIL runner that accepts a unique run ID and an already captured successful orchestration record, validates the request/operation and live baseline, then invokes the existing chain relay Tekton/Pipeline and bounded SRv6/P4 probe using the same flow ID as the chain run identity. The operation's pair path and the experiment's separately configured chain legs remain distinct evidence.
- Preserve the existing relay architecture: Mininet gateways hand the unchanged inner packet to two ordinary CNI relay Pods and emit the next independently compiled P4/SRv6 leg. Instrument the UDP handoff separately from P4 traversal.
- The resulting manifest links the orchestration request/operation, chain PipelineRuns, Ready Pod identities, each P4 leg and readback, Pod receipts, exact packet hashes, counter deltas, and source/evidence hashes. The chain packet stage remains bounded at 3-packet pilot then 20 packets after inspection.
- This demonstrates a testbed chain experiment linked to a successful pair-level orchestration record. It is not one HARP admission-to-chain actuation transaction, does not establish full-chain policy selection, and does not change the meaning of existing HARP benchmark results.
- Retain any VNF or steering state without a verified inverse-steering rollback; clean only resources uniquely owned by the opt-in chain run.

## Constraints and acceptance

- Preserve existing workloads and evidence; no broad cleanup or ledger reset.
- Do not conflate simulator pair-level safety, single-VNF delivery, ordered chain traversal, or migration continuity.
- Use bounded runs and preflight/rollback for live changes; stop if ownership or recovery is uncertain.
- Completion requires repeatable post-restart smoke, packet-correlated chain order, measured migration continuity, and a long-run per-request admission-to-delivery record. Any unsupported claim remains explicitly limited in the paper.

## Current verified baseline

- On 2026-11-24, read-only `kubectl` showed 17 Ready VNF Deployments. `docker ps` showed the CoreRouter backend and ten BMv2 containers running; the backend image digest matched the 2026-11-21 HIL summary.
- Corrected-model campaign: 398 offered, 69 admitted/steered with rule readback, 64 in-campaign probes with 20/20 delivery; 57 migration orders were confirmed. Two three-hour runs each delivered 1,800/1,800 probes to previously steered VNFs. Their accepted admissions were not actuated in those long runs.
- The recorded k8s-master VXLAN firewall fix was runtime-only, and the controller's s10 readback source correction was not live during the 2026-11-21 runs.
- Source inspection on 2026-11-24 found that the current runtime action and P4 realization target one placement VNF. The firewall and IDPS ConfigMap templates start `sleep infinity`; they do not forward packets to a next VNF. An ordered multi-VNF packet experiment therefore requires a real forwarding service/proxy and a defined handoff between functions before a live probe can support that claim. A receipt analyzer alone cannot close this gap.
- A bounded four-stage Mininet-host proxy experiment now shows packet-correlated traversal over five SRv6/P4 legs. It is a forwarding-plane component experiment. The full design remains open until equivalent ordered traversal is connected to Kubernetes VNF Pods and the admission/Tekton lifecycle path.
- **Architecture ruling, 2026-11-24:** With an unchanged inner IPv4 packet, its destination IP cannot identify two different Pod IPs. Use the Mininet hosts at the P4 leg endpoints as per-stage gateways. Each gateway sends the complete unchanged inner bytes in a bounded UDP envelope to an ordinary CNI relay Pod; the Pod validates, records, and echoes the envelope, then the gateway verifies exact-byte identity and emits the next independently compiled SRv6/P4 leg. The UDP handoff is instrumented and reported separately; it is not counted as an SRv6/P4 leg. Keep all chain resources uniquely named and opt-in.
- **Live evidence, 2026-11-24:** Two relay Pods were deployed through a dedicated Tekton Pipeline on worker2. Run `podchain20261124b` achieved 3/3 pilot and 20/20 follow-up delivery through two Pod receipts and egress, with matching inner hashes and expected counter deltas on the three P4 legs. The static opt-in Task/Pipeline/ConfigMaps remain; per-run workloads and workspace PVC were removed. Evidence is under `results/hil/vnf_pod_chain_20261124/podchain20261124b/`.
