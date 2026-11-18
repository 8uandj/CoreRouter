# E1 chain, SID, MSD, and forwarding boundary audit

Audit date: 2026-11-17. This is a static audit of the current source. It did
not inject packets or verify end-to-end forwarding. File hashes are recorded
in `evidence/pair_actuation_source_manifest.json`.

## Current source contract

| Stage | Source | What the code establishes |
| --- | --- | --- |
| Decision unit | `models/schemas.py::SFCRequest`, `services/hybrid_decision.py::select_and_reserve` | The current `/orchestrate` request carries one `service_type`; the policy selects one placement node and one route-profile node per request. This is the current API/policy contract, not a claim that the testbed cannot deploy multiple VNFs or that an earlier manually assembled chain was never run. |
| Physical path candidate | `services/p4_pair_realization.py::compile_pair_path` | When an ingress/source node is supplied, computes a shortest path from ingress to placement over the compiled P4 topology. The route node selects the MSD profile; it is not necessarily a transit node in that path. |
| SID stack | `compile_pair_path`, `infrastructure/sdn/p4_topology.py::compile_p4_forwarding_rules` | Builds the switch SID stack from the reverse of the source-to-placement switch path. The controller later derives per-hop IPv6 rules and a terminal End.DX4 rule from the admitted path and its observed port map. |
| MSD checks | `compile_pair_path`, `NetworkStateManager.try_reserve` | With a physical path, `msd_req` must equal the materialized switch-SID count, fit the selected route-profile limit, and fit every switch limit on the path. Admission then reserves placement CPU/RAM and checks that path depth against the selected route node. This is pair/path-candidate accounting, not a general multi-VNF chain check. |
| Mask vs path validation | `NetworkStateManager.action_mask`, `select_and_reserve` | The N² mask screens placement CPU/RAM and route-profile MSD per pair. It does not compile every ingress-specific physical path. The chosen candidate's concrete path/depth is checked before reservation; a path mismatch can reject that candidate and cause the heuristic-to-DRL fallback or a final rejection. Thus the pair mask is a prefilter, not an exact physical-path feasibility mask. |
| Missing ingress | `generate_srv6_sids` | Without a source/ingress node, constructs documentation-prefix `2001:db8::/32` SIDs from the pair and requested depth. This profile has no forwarding SID and is not a physical path. |
| Admission identity | `services/realization.py::AdmittedRealization` | Carries immutable request/operation IDs, topology/profile identity, SID stack, switch path, and optional P4 topology hash. The payload validator rejects a steering payload that differs from this admitted identity. |
| Actuation gate | `routers/orchestration_router.py::orchestrate_sfc` | Only the DRL plus forecast-alert branch schedules deployment/steering. If that decision has no supported forwarding SID, the router releases the unactuated reservation and returns `UNSUPPORTED_ADMITTED_REALIZATION`. |
| Kubernetes and controller | `services/orchestration_service.py::_execute_make_before_break`, `infrastructure/sdn/controller.py::steer` | The backend requests deployment, waits for a ready endpoint, submits the admitted path and correlated IDs/hashes, and waits for matching controller status before BREAK. The controller compiles rules against its observed live port map and requires installation success. This confirms control-plane rule installation/status; it does not show that a packet traversed the intended path. |

## E1 disposition

The source now defines a pair-level physical path candidate when the request
contains ingress information and the live P4 topology/profile can be read.
Without ingress, the admitted SID list remains synthetic. The current
`/orchestrate` schema and policy decision are per service request and do not
accept or expand an ordered chain of VNF functions. This source finding is
about the current policy-controlled request path; it does not mean that the
Kubernetes testbed cannot host many VNF instances or that a prior manually
assembled chain could not have been demonstrated.

The authors report that an earlier testbed experiment deployed an ordered
chain comprising multiple VNFs and observed packets traverse its VNFs
sequentially. The run plan `results/hil/rebuild_20261117T123405Z/FULL_HIL_EXECUTION_PLAN.md`
also lists an ordered chain of at least three VNFs as a later E1 activity; the
plan is evidence of intent, not execution. Other historical artifacts record
a 50-Deployment inventory with all 50 Ready at one snapshot, followed by a
reduced seven-Deployment baseline. Separate packet captures record a probe
reaching a Mininet host and the Kubernetes overlay toward one target Pod. The
target Pod at that time ran `alpine` with `sleep infinity` and had no
application listener. The reviewed archive does not retain the request
manifest, function order, endpoint trace, or packet captures for the reported
multi-VNF run; those artifacts should be recovered before making a
request-correlated quantitative forwarding claim. This archive gap does not
invalidate the authors' report or the separate source finding that the current
policy API is pair-level.

The physical path, SID stack, MSD predicates, admission handle, and controller
payload are source-bound for the supported pair path. This closes the source
definition/audit portion of E1 only. It does not close the `→ forwarding`
evidence requirement: the current evidence set has no request-correlated packet
capture proving that packets traverse the installed SID list. Controller rule
installation or a positive steer status is not packet-forwarding evidence.

The action mask is also weaker than the later ingress-specific path check: it
does not enumerate the concrete physical path for every placement/route pair.
The final chosen realization is checked before admission, but candidate pruning
and the physical-path feasibility set are not identical. This must be stated
when describing masking and candidate quality.

Keep claims limited to pair-level path compilation, per-list MSD checks,
admission, and controller-visible rule installation. Do not claim general
multi-VNF-chain soundness, packet delivery, forwarding stability, or zero
downtime until packet evidence is collected for the same request and admitted
realization. The 12-hour E6 run is control-plane-only and cannot close this gap.
