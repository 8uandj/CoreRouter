# Code Freeze Gate Implementation Plan

> **For agentic workers:** Execute tasks inline in order. Each code change starts with a regression test that fails for the expected reason.

**Goal:** Close the code-only freeze gates while keeping research execution opt-in and outside this work.

**Architecture:** Preserve pair-level admission claims unless an explicitly supported realization can be carried unchanged to the controller. Fail closed where deployed teardown cannot be confirmed. Integrate existing package, artifact and result checks into a plan-first phase driver, then add a read-only freeze verifier and modular runbook.

**Tech Stack:** Python 3.9, pytest, FastAPI, SQLite reservation journal, JSON protocol/package manifests, shell/Python CLI.

**Spec:** `docs/AIO-mesh-rev1/CODE_FREEZE_CHECKLIST.md` and the user-provided five-item freeze plan.

## Global Constraints

- Do not run training, benchmark data collection, HIL, or live infrastructure commands.
- Existing CLI defaults stay plan/preflight only; executing work requires an explicit flag.
- Missing or mismatched realization, checkpoints, protocol inputs, or deployment confirmation fails closed.
- Never release a deployed reservation before correlated deletion/de-steering confirmation.
- Do not claim freeze readiness until final code-only regression and command-contract checks pass.

## Review Focus

- Admission and actuation payload cannot diverge silently; mismatch must produce explicit failure.
- Ambiguous deployment teardown retains ledger charges and reports a recoverable state.
- Existing users of plan-only and explicit execution CLI modes retain their contract.
- Package/protocol provenance covers every topology, scenario, checkpoint and result archive.
- Freeze verification reports unavailable optional/runtime dependencies without activating services.

### Task 1: Bind admitted realization to actuation

**Files:** `src/portal/backend/app/services/hybrid_decision.py`, `src/portal/backend/app/routers/orchestration_router.py`, `src/portal/backend/app/services/orchestration_service.py`, related tests.

- [x] Add regression coverage for immutable admission identity and exact payload SID matching.
- [x] Add regression coverage for missing/changed realization and prove actuation is rejected before scheduling/submission.
- [x] Implement fail-closed pair-level realization contract; current topology data has no verified forwarding profile, so physical realization remains unsupported.
- [x] Focused tests pass. End-to-end supported mapping remains a freeze blocker.

### Task 2: Deployed lifecycle and reconciliation

**Files:** `src/portal/backend/app/services/orchestration_service.py`, `src/core/state_manager.py`, API schemas/routes and lifecycle tests.

- [ ] Add failing teardown tests for confirmed deletion, failed deletion, lost confirmation, and retry/idempotency.
- [ ] Add failing reset/reload reconciliation tests for dangling reservations, leftover rules and running replicas.
- [ ] Implement operation-correlated teardown; retain reservations until absence and rule deletion are verified. Keep selection-only TTL semantics distinct.
- [ ] Verify focused tests.

### Task 3: Phase and artifact contracts

**Files:** `scripts/rev1/phase_driver.py`, `scripts/rev1/result_coverage.py`, `scripts/rev1/package_inputs.py`, notebook and tests.

- [x] Add failing command-contract tests for missing dataset/checkpoint, source mismatch, all-topology coverage and archive output.
- [x] Integrate package/hash/protocol preflight and cross-topology audit into explicit driver stages without executing experimental commands by default.
- [x] Add separate smoke-only artifact paths; reject dataset fallback and smoke checkpoint reuse for evaluation.
- [x] Mocked command/package tests pass.

### Task 4: Freeze verifier and modular runbook

**Files:** `scripts/rev1/verify_freeze.py`, `docs/AIO-mesh-rev1/FREEZE_MANIFEST.md`, `docs/AIO-mesh-rev1/PHASE_INPUTS.md`, tests.

- [x] Test read-only reporting helpers and CLI contracts.
- [x] Implement verifier that never starts infrastructure or workloads and reports optional `p4runtime-shell` status.
- [x] Document independent Simulation, Kaggle/Server, and HIL phases with inputs, outputs and explicit user activation.
- [x] Verify helper tests and run against a temporary training package; final report blocks on dirty worktree.

### Task 5: Final code-only verification and checklist

**Files:** `docs/AIO-mesh-rev1/CODE_FREEZE_CHECKLIST.md`, `docs/AIO-mesh-rev1/REVISION_STATUS.md`.

- [x] Run the complete regression suite and command-contract tests after all changes; 195 passed with 14 third-party deprecation warnings.
- [x] Run syntax and diff checks; no training, benchmark, simulation collection, or HIL was run.
- [x] Mark only gates proven by these checks; infrastructure-dependent teardown/forwarding claims remain open.
