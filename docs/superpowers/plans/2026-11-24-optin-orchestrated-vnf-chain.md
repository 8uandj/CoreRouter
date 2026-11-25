# Opt-in Orchestrated VNF Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a reproducible opt-in runner that links a successful pair-level HARP orchestration record to the existing two-Pod SRv6/P4 chain experiment without changing HARP policy or API behavior.

**Architecture:** A new HIL entry point validates a saved successful orchestration record, runs the existing uniquely named Tekton relay-chain experiment, and writes a parent manifest linking both evidence sets. Packet receipts retain their chain run/packet identity; the HARP request and operation IDs are parent metadata, not claims that HARP selected the full chain.

**Tech Stack:** Python 3.11, Kubernetes/Tekton, existing HIL JSON evidence and subprocess runner.

**Spec:** `docs/superpowers/specs/2026-11-24-hil-e2e-completion-design.md`

## Global Constraints

- Keep the existing `/api/orchestrate` contract and pair-level policy unchanged.
- Preserve existing VNFs, reservations, P4 rules, backend, Mininet, and unrelated services.
- Use separate opt-in chain resources and unique run IDs.
- Every Pod and P4 leg records the chain run ID, packet ID, and inner-packet hash; UDP handoff remains separate from P4 traversal.
- Do not claim HARP selected or admitted the full chain.
- Retain any VNF or steering state without a verified inverse-steering rollback; clean only resources uniquely owned by the opt-in chain run.

## Review Focus

- Invalid, rejected, or incomplete orchestration records must fail before creating any Kubernetes resource.
- Reused or malformed run IDs must be rejected before subprocess invocation.
- A chain-run failure must remain a failure in the parent record and must not yield a success manifest.
- Source/evidence hashes must include the upstream orchestration record and nested chain manifest.
- The parent evidence must not label pair-level realization as full-chain policy selection.

### Task 1: Opt-in HIL orchestration wrapper

**Files:**
- Create: `scripts/hil/orchestrate_vnf_pod_chain.py`
- Modify: `docs/superpowers/plans/2026-11-24-vnf-pod-srv6-chain.md`
- Evidence: `results/hil/orchestrated_vnf_chain_20261124/<run-id>/`

**Interfaces:**
- `validate_orchestration_record(record: dict) -> dict` checks HTTP 200/success, a nonempty flow ID, VNF name, admitted operation/request IDs, pair realization, and successful actuation/steering evidence. It returns normalized linkage metadata or raises `ValueError`.
- CLI requires `--record`, `--run-id`, and `--out`; `--run-id` must equal the saved request `flow_id`, must match the chain run ID format, and must not have a previous output directory. It validates the record and a fresh read-only live inventory before calling `scripts/hil/vnf_pod_chain_probe.py --run-id <run-id> --out <out>/chain`.
- The parent writes `orchestration.json` before invoking the child, then writes a final `manifest.json` only after the child exits successfully and its manifest and evidence hashes validate. On failure it records a failed status and returns nonzero.

- [x] Implement fail-closed validation for rejected/incomplete records, invalid/reused run IDs, child failure, live inventory mismatch, hash linkage, and the pair-level scope note.
- [x] Run `python3 -m py_compile scripts/hil/orchestrate_vnf_pod_chain.py` and `python3 scripts/hil/orchestrate_vnf_pod_chain.py --help`; both completed successfully.
- [x] Update the prior chain plan with the wrapper and state the linkage limitation precisely.
- [x] Run one bounded live orchestration-linked chain from the successful pair-level record, using the same flow ID as chain run ID. The runner used tmux; its initial parent-manifest path check failed after the chain child succeeded, then resume finalized the evidence without re-sending packets.
- [x] Inspect per-run Tekton, Pod, receipt, P4, and manifest evidence; verified cleanup removed only uniquely named chain resources and retained PipelineRuns for audit.

## Completion Gate

- [x] Source validation fails closed on malformed/unsuccessful records and on reused or mismatched run IDs before Kubernetes access.
- [x] The live run links a successful pair-level orchestration record to two Ready Tekton-managed relay Pods and ordered packet evidence on all three SRv6/P4 legs.
- [x] Parent and child manifests verify, including raw request/operation IDs, Pod receipts, counters, source hashes, and evidence hashes.
- [x] Final wording clearly limits HARP to pair-level selection and describes the chain as opt-in testbed orchestration.

## Execution log (2026-11-24)

- Static verification: `python3 -m py_compile scripts/hil/orchestrate_vnf_pod_chain.py` and CLI `--help` completed successfully.
- Live run: `orchchain20261124c`, linked to flow ID `orchchain20261124c`, HARP operation `7388e25f-4705-4664-833f-c0047d899565`, VNF `vnf-voc-02d52f80`, pair path s1→s2. Baseline backend digest matched; 18/18 unrelated/current VNF Deployments were Ready.
- Chain results: two relay Pods Ready on worker2; 3/3 pilot and 20/20 follow-up packets traversed two Pod receipts and egress with identical inner packet hashes. Counter deltas were s1 advance +23; s6 advance +23/terminal +23; s9 advance +23/terminal +23; s10 terminal +23; MSD-violation deltas were zero.
- Evidence: `results/hil/orchestrated_vnf_chain_20261124/orchchain20261124c/`; parent and child evidence/source hashes checked with zero mismatches. Unique run Deployments/Services, task Pods, and PVC were removed; PipelineRuns remain.
- Scope: the linked HARP decision's s1→s2 pair does not configure the measured s1→s6→s9→s10 chain path. This is a prior successful pair-level record linked to a separately configured testbed chain run, not one full-chain HARP decision or an admission-to-chain transaction. The flow ID is shared only as the correlation/run key.
- Final self-review added a label-scoped Kubernetes run-ID collision preflight before invoking the child (to prevent cleanup from targeting a resource left by a reused ID) and a graceful SIGINT timeout path so the child can run its `finally` cleanup. Final syntax/CLI checks, 127 hash checks, and `git diff --check` completed successfully.
