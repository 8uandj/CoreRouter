# E1 chain, SID, MSD, and forwarding boundary audit

Audit date: 2026-11-17. This is a static audit of the current source. It did
not inject packets or verify end-to-end forwarding. File hashes are recorded
in `evidence/pair_actuation_source_manifest.json`.

## Current source contract

| Stage | Source | What the code establishes |
| --- | --- | --- |
| Decision unit | `services/hybrid_decision.py::select_and_reserve` | Selects one placement node and one route-profile node per request. It does not expand a request into a general chain of three or more VNFs. |
| Physical path candidate | `services/p4_pair_realization.py::compile_pair_path` | When an ingress/source node is supplied, computes a shortest path from ingress to placement over the compiled P4 topology. The route node selects the MSD profile; it is not necessarily a transit node in that path. |
| SID stack | `compile_pair_path`, `infrastructure/sdn/p4_topology.py::compile_p4_forwarding_rules` | Builds the switch SID stack from the reverse of the source-to-placement switch path. The controller later derives per-hop IPv6 rules and a terminal End.DX4 rule from the admitted path and its observed port map. |
| MSD checks | `compile_pair_path`, `NetworkStateManager.try_reserve` | With a physical path, `msd_req` must equal the materialized switch-SID count, fit the selected route-profile limit, and fit every switch limit on the path. Admission then reserves placement CPU/RAM and checks that path depth against the selected route node. This is pair/path-candidate accounting, not a general multi-VNF chain check. |
| Missing ingress | `generate_srv6_sids` | Without a source/ingress node, constructs documentation-prefix `2001:db8::/32` SIDs from the pair and requested depth. This profile has no forwarding SID and is not a physical path. |
| Admission identity | `services/realization.py::AdmittedRealization` | Carries immutable request/operation IDs, topology/profile identity, SID stack, switch path, and optional P4 topology hash. The payload validator rejects a steering payload that differs from this admitted identity. |
| Actuation gate | `routers/orchestration_router.py::orchestrate_sfc` | Only the DRL plus forecast-alert branch schedules deployment/steering. If that decision has no supported forwarding SID, the router releases the unactuated reservation and returns `UNSUPPORTED_ADMITTED_REALIZATION`. |
| Kubernetes and controller | `services/orchestration_service.py::_execute_make_before_break`, `infrastructure/sdn/controller.py::steer` | The backend requests deployment, waits for a ready endpoint, submits the admitted path and correlated IDs/hashes, and waits for matching controller status before BREAK. The controller compiles rules against its observed live port map and requires installation success. This confirms control-plane rule installation/status; it does not show that a packet traversed the intended path. |

## E1 disposition

The source now defines a pair-level physical path candidate when the request
contains ingress information and the live P4 topology/profile can be read.
Without ingress, the admitted SID list remains synthetic. In both cases, the
decision model still chooses one placement/route pair; it does not produce a
multi-VNF chain of length three or greater.

The physical path, SID stack, MSD predicates, admission handle, and controller
payload are source-bound for the supported pair path. This closes the source
definition/audit portion of E1 only. It does not close the `→ forwarding`
evidence requirement: the current evidence set has no request-correlated packet
capture proving that packets traverse the installed SID list. Controller rule
installation or a positive steer status is not packet-forwarding evidence.

Keep claims limited to pair-level path compilation, per-list MSD checks,
admission, and controller-visible rule installation. Do not claim general
multi-VNF-chain soundness, packet delivery, forwarding stability, or zero
downtime until packet evidence is collected for the same request and admitted
realization. The 24-hour E6 run is control-plane-only and cannot close this gap.
