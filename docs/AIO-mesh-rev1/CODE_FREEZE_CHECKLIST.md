# Code freeze gate (before research execution)

This gate tracks implementation readiness, separately from the E1–E6 research evidence gate. The code is frozen for this revision with explicit fail-closed restrictions on unsupported physical operations. This is not research evidence or HIL actuation approval. The user will execute training, research benchmarks and HIL; no such phase is run during this work.

- [x] Local pair admission, action/normalizer compatibility, deterministic trace/accounting/statistics tests exist and passed in the 89-test regression run recorded in `REVISION_STATUS.md`.
- [x] HTTP regression checks execute with optional dependencies installed.
- [x] Controller unknown-switch/empty-rule/install-error outcomes cannot confirm successful steering.
- [x] Migration BREAK requires replacement and operation IDs matching the submitted steering command; controller operations are serialized.
- [x] Bind a supported admitted realization to its controller payload, or fail explicitly when no supported realization exists; never silently steer a different SID/path. Immutable request/operation/topology/profile identity, exact payload/SID validation, endpoint mismatch rejection, and pre-actuation HTTP 409 are regression-tested. No verified physical profile is configured, so actuation is intentionally disabled until an end-to-end mapping is validated.
- [x] Background migration outcomes are journaled and retrievable; duplicate replacement execution is blocked. BREAK failure and unconfirmed deletion retain old resource charges. See `RUNTIME_RECOVERY.md` and the 104-test run.
- [x] Restore named/pending/anonymous charges and actuation intent from a topology-bound durable reservation ledger; startup rejects corrupted/incompatible profiles and another ledger owner. Crash and storage-failure tests pass (140-test suite).
- [x] Enforce safe lifecycle behavior: MAKE/readiness/steering/BREAK retention, real-telemetry sync, named selection-only TTL release, replica readiness and reset guards are tested. Deployed TTL returns `DEPLOYED_TTL_TEARDOWN_REQUIRED` and retains its ledger charge. Correlated P4 de-steer/rule-delete/readback is deliberately unsupported until a verified physical mapping exists; deployed TTL cleanup must not be treated as available.
- [x] Remove synthetic resource reconstruction; preserve telemetry and local charges; unknown deployment profiles fail explicitly. Conservative accounting and per-field freshness documented in `SEMANTICS_CONTRACT.md`.
- [x] Validate benchmark/ablation/protocol consistency and deterministic source/data/model packaging. Evaluation verifies package SHA/mode/protocol identity, preflight pins required checkpoints/dataset, phase execution stops on failed preflight, missing datasets do not substitute a default file, and cross-topology/source-lineage audit is callable as `--stage audit`. `--stage smoke` uses a distinct output tree and `smoke_only` plans are rejected by evaluation packaging. Focused command/package tests pass.
- [x] Supply and run the freeze verifier, environment report, source manifest and runbook. `verify_freeze.py` and `FREEZE_MANIFEST.md` provide the workflow; final clean-commit verification is recorded in `REVISION_STATUS.md`.
- [x] Run final unit/regression and command-contract checks after the final changes; provide executable smoke/experiment entry points for the user without executing those phases. Current code-only suite: 195 passed, 14 third-party deprecation warnings; changed sources compile, CLI help contracts and `git diff --check` pass. The final clean-commit verifier remains pending. Testbed/configuration limits are recorded.

Research training, pre-registered 20-seed evaluation, topology/load/concurrency measurement and live HIL/packet evidence run after code readiness. Their absence must not be disguised by unit-test success.

## Restrictions carried into phase execution

- Physical steering remains fail-closed with HTTP 409 until a tested switch/SID/port profile is supplied.
- Deployed TTL teardown remains unavailable. Keep its reservation charged until correlated controller readback verifies rule deletion.
- The current training input package lists missing ablation checkpoints. Evaluation packaging and preflight must stop until compatible trained artifacts are supplied.
