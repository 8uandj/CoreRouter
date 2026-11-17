# No-P4 Revision Work Plan

**Goal:** Complete the revision tasks that can be supported by simulation, source/config audit, and control-plane HIL without claiming P4 packet forwarding.

**Approach:** Reconcile provenance and current source first; then run only experiments whose model/checkpoint/data preflight passes. Keep simulation, control-plane HIL, and data-plane HIL results separate. No P4 traffic, live routing mutation, migration zero-downtime claim, or P4 over-MSD claim is in scope.

**Scope from:** `docs/AIO-mesh-rev1/todo.md` and `todo-2.md`.

## Phases

1. **Evidence and workload audit:** P0.1, P1.1, E2. Reconcile historical aliases, configs, seeds, traces, source/model/data hashes, denominators and manifests. Change generator/config only when source evidence identifies a defect; rerun matched traces after preflight.
2. **Protection and ablation evidence:** P0.2, P0.3, P1.6, E3. Use common admission boundary and matched offered traces. Separate policy proposal, runtime rejection, admission, and deployment. Run paired inference only with compatible, pinned artifacts; report CI, exact paired tests, effect size and rejection accounting.
3. **Semantics and implementation audit:** P0.4, P0.7, P0.8, E1. Define the supported pair-level action, hybrid thresholds, state/features, normalization, mask behavior, freshness and atomicity from current source. Keep chain/forwarding claims open where implementation does not establish them.
4. **Decision-stage performance:** P0.5, P1.2, P1.3, E4. Measure only decision-stage code and explicitly separate state, mask, inference, admission and controller handoff. Use synthetic topology/active-chain/concurrency controls where available; don't label modeled/service latency as packet latency.
5. **Conditional cache item:** E5/P0.6. Verify whether candidate-path cache exists in the evaluated runtime. If absent, remove cache claims and skip K-sensitivity experiments.
6. **Control-plane stability:** E6 first item only. A bounded/long control-plane HIL run may count API outcomes, Kubernetes readiness and control-plane migration states. It cannot claim packet forwarding, zero downtime, or BMv2 enforcement. Full E6 remains open.
7. **Manuscript cleanup:** P1.7 abbreviations and update prose/tables only from audited evidence; update TODO/status/ledger after each evidence-backed phase.

## Constraints

- Preserve all pre-existing user worktree changes; no reset, checkout, clean, commit, or push.
- Do not run P4 packet traffic or alter the live Mininet/BMv2 tables under this scope.
- Do not convert missing/unsupported artifacts into numbers; stop an experiment when preflight fails and record the gap.
- User selected inline execution by asking to proceed directly.

## Current baseline evidence

- `REVISION_STATUS.md` reports implementation support for protected/unprotected comparisons, ablations, load sweep, concurrency, synthetic topologies and corrected latency accounting, but says research-scale matched experiments remain unrun.
- `EVIDENCE_LEDGER.csv` withdraws the submitted HIL table from revised claims and flags historical HIL provenance as needing audit.
- The latest live benchmark artifact from 2026-11-17 had 11 requests, 0 accepted/deployed/actuated; its HTTP decision latency is not forwarding latency.
