# Realization/MSD audit after HARP merge

Scope: merged commit dd5ff67; read source, deterministic local compiler calls, unit regressions. No HIL access or deployment. Source hashes and deterministic traces: `evidence/realization/offline_pair_traces.json`.

## Confirmed behavior

1. `hybrid_decision.select_and_reserve` recognizes `source_node` or `ingress_node`. With an explicit source it calls `compile_pair_path`; otherwise it retains the synthetic SID helper.
2. The compiler uses the fixed ten-node, 11-link P4 graph, deterministic BFS from ingress to placement, reversed `fc00:<switch>::1` SIDs, exact equality of requested and materialized depth, and upper bounds for the selected routing profile and every traversed switch.
3. The route action selects a profile; BFS does not require that node as a waypoint. This differs from interpreting the action as ingress → anchor → placement.
4. `state_manager.try_reserve` checks placement CPU/RAM and per-list route MSD. CPU/RAM increments only at placement. Route MSD state is max active depth, not an additive pool. The old manuscript equation describing additive MSD and charging both nodes was incorrect and is replaced.
5. The returned admitted handle has `forwarding_sid=None`, even after path compilation. The alert-triggered DRL branch checks this field, releases the unused reservation and returns HTTP 409 before lifecycle handoff. `validate_realization_payload` also rejects handles without a forwarding SID. Path compiler success is not permission to actuate.
6. Controller rule-readback helpers and P4 contract tests exist; offline tests cannot establish live packet delivery.

## What remains unresolved

- No ordered chain of three or more VNFs is expanded into per-function placements, inter-function paths and an installed composite SID stack by this compiler. This is pair-path realization, not full-chain embedding.
- Runtime compiler, runtime profile check and simulator hop-depth approximation are distinct contracts. Existing simulator results must not be retrospectively described as evaluations of the new physical compiler.
- A supplied requested depth must equal the BFS path depth. Rejection can therefore arise from representation mismatch, not just resource exhaustion. Route-profile choice is not path routing optimization.
- Successful live forwarding requires supported handle construction, matching controller payload/readback, packet/counter evidence and release/rollback validation. These are HIL-dependent.

## Verification

`venv/bin/python -m pytest tests/rev1/test_p4_pair_realization.py tests/rev1/test_controller_rule_readback.py tests/test_hybrid_decision.py infrastructure/sdn/p4/tests/test_srv6_realization_contract.py tests/test_state_manager.py -q` → 34 passed.

Offline trace cases compile 0→2→3 at requested depth 3 and 0→5 at depth 2; wrong requested depth and coincident ingress/placement reject. These traces are code-contract examples only, not new experimental performance results.

## Next simulator work

- Existing timing columns may support descriptive cost summaries, but the concurrent sweep jobs cannot establish a controlled timing advantage. Run serialized, same-machine HARP/SAF-H timing with warm-up and hardware metadata before making a gain–cost claim.
- Missed-feasible oracle needs snapshots before each policy decision and the exact simulator admission predicate, including bandwidth and hop-dependent depth. Current seed summaries lack these snapshots; do not infer missed-feasible rates from 1 − acceptance.
- Size scaling requires size-matched checkpoints; 10/14/23-node geographic complete graphs do not substitute for 25/50/100-node controlled scaling.
