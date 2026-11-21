# Revision Evidence Completion Implementation Plan

**Goal:** Resolve mentor and reviewer gaps using reproducible evidence and accurate manuscript claims.
**Architecture:** Derive tables from retained per-seed runs, link source hashes, and separately identify unavailable HIL evidence. Keep the submission bundle canonical.
**Tech Stack:** Python, CSV/JSON, LaTeX, simulator, tmux.
**Spec:** docs/AIO-mesh-rev1/comment_mentor.md and todo-2.md.

## Global Constraints

Preserve original artifacts. Do not conflate simulator with forwarding. Match checkpoints and workloads. Record uncertainty and missing evidence.

## Tasks

- [ ] Correct oracle denominators and stale prose; regenerate synthetic 25/50/100 benchmark tables.
- [ ] Reconcile statistical analyses, model provenance, manifests and generated manuscript figures.
- [ ] Complete feasible simulator experiments and cell reruns; retain logs, commands and seeds.
- [ ] Reconcile response, checklist and manuscript; identify HIL artifacts requiring the separate server.
- [ ] Verify paper build, hashes, claims, and submission bundle consistency.
