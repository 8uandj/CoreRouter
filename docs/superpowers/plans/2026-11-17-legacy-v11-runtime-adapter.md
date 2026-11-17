# Legacy v11 Runtime Adapter Implementation Plan

> **For agentic workers:** Use the existing session to implement and verify each step.

**Goal:** Run the saved v11 `MultiDiscrete([N,N])` policy through a pair mask without retraining, and describe its provenance accurately in the revision.

**Architecture:** Reuse the offline additive head conversion in runtime inference. Load the original policy weights into a flat `Discrete(N²)` policy; the original checkpoint and normalizer remain immutable. Expose the detected source encoding through the status API.

**Tech Stack:** Python, PyTorch, sb3-contrib, Gymnasium, pytest, LaTeX.

**Spec:** The user's choice in this conversation and `docs/AIO-mesh-rev1/FREEZE_MANIFEST.md`.

## Global Constraints

- Keep the legacy checkpoint and its normalizer unchanged.
- Reject unsupported dimensions and missing normalization statistics.
- Retain historical result tables as historical, with no invented adapter measurements.

## Review Focus

- An unsupported policy head must fail loading.
- A missing normalizer must fail loading.
- The loaded policy must accept an N² pair mask and select a valid pair.
- The API must distinguish a converted legacy policy from a native flat policy.
- The paper must distinguish training action encoding from runtime pair encoding.

## Tasks

### Task 1: Runtime loading

- [ ] Add a failing test that loads the recovered Vietnam checkpoint with its normalizer and predicts under a one-pair mask.
- [ ] Run the test and observe the expected load failure.
- [ ] Load and validate `policy.pth`, convert its 2N head with the existing additive transform, and construct the flat inference policy.
- [ ] Run the focused test and revision tests.

### Task 2: Diagnostics and paper

- [ ] Add a failing status test for the source encoding.
- [ ] Add the encoding to runtime status.
- [ ] Update semantics and paper text to state 2N training and N² runtime scoring, keeping historic results marked as such.
- [ ] Run relevant tests, LaTeX checks if available, and `git diff --check`.
