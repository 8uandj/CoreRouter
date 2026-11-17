# Pair admission → actuation source audit

Date: 2026-11-16. Static inspection only; no Kubernetes, controller or packet execution.
Source hashes: `evidence/pair_actuation_source_manifest.json`.

| Stage | Owning source / symbol | Observed behavior |
| --- | --- | --- |
| Pair realization | `services/hybrid_decision.py::generate_srv6_sids` | Produces `max(1, msd_req)` synthetic documentation-prefix SIDs; first identifies placement, remaining entries repeat routing node with different indices. No substrate-path expansion or VNF chain mapping. |
| Local admission | `services/hybrid_decision.py::select_and_reserve` | Reserves CPU/RAM and `len(sids)` under the snapshot version. This establishes the local pair predicate only. |
| API output | `routers/orchestration_router.py::orchestrate_sfc` | Returns that list as `srv6_segment_list`. It does not pass the list or routing node to the MBB service. |
| Actuation trigger | Same router | Schedules deployment/MBB only for the DRL branch with a forecast alert. Other admitted responses do not schedule deployment here. |
| Migration translation | `services/orchestration_service.py::make_before_break_sequence` | Independently constructs `target_sid` from a replacement endpoint and sends one local-SID rule plus a fixed IPv6 route on `s1`. It does not consume the admitted SID list or recheck the resulting rule set against that list's MSD profile. |
| Controller | `infrastructure/sdn/controller.py::bootstrap`, `steer` | Installs local-SID/IPv6 rules. Status now includes deployment and operation identifiers; the backend requires both to match before BREAK. Complete steering operations are serialized. This is controller confirmation, not proof that packets traversed the admitted SID list. Unknown switch names now fail the aggregate result and prevent steering confirmation/old-rule cleanup (regression-tested). A success flag still does not establish packet forwarding. |
| Alternate rule API | `routers/api_v1.py::add_p4_rule`, `src/infrastructure/sdn/p4_controller.py::inject_sfc_rule` | Separate single-SID injection entry point; does not call pair admission. The adapter's topology is explicitly mocked. Do not generalize the orchestration admission claim to every actuation endpoint. |

Service paths above are relative to `src/portal/backend/app/` unless fully qualified.

## Disposition

The source does **not** establish equality between the admitted synthetic list and an installed SRH, even for a single pair. Pair-level admission is a local resource/depth check, not demonstrated pair-to-forwarding soundness. A three-VNF chain and end-to-end enforcement remain unverified. Simulation MSD checks are checks of the supplied depth, not proof of physical realization.

Ruling: retain the existing pair simulator and narrow manuscript claims rather than invent a chain/controller mapping. Changing the mapping requires a separate validated implementation and new experiments; if this ruling is wrong, the paper understates implemented capability until correlated evidence is supplied.

Before stronger claims: carry a request-correlated immutable realization through admission and actuation; validate topology/profile mapping; confirm the exact installed rules/SRH with readback and packets; correlate steering completion to the replacement before BREAK; audit every direct actuation entry point. These are remaining requirements, not implemented features. Local unit tests cannot close this integration gap.
