# Workspace context — 2026-11-16

## Authoritative code

User confirms `https://github.com/8uandj/CoreRouter`, branch `HARP`, is the latest code. No local-machine reconciliation is required. Workspace synchronized to `1b7ef37fb9cdce401609697307bdcc6e9bf2fe20` (2026-06-18 UTC). Git metadata restored from a fresh clone. HARP tracks origin/HARP; active server refactoring branch is now HARP-server.

At initial synchronization, verified all 290 upstream tracked files byte-for-byte; updated 25 and added 94 missing files. Subsequent HARP-server changes are described in `docs/REFACTOR_HARP_SERVER.md`. Workspace-only files retained, including revision/submitted/thesis documents, models, data and results. These retained files are not certified as part of the upstream commit; extra scripts may be older. Backup and exact inventory: `.workspace-sync/20261116T092111Z/manifest.json` and its sibling `backup/`. No training, benchmark or deployment was run during synchronization.

## Document lineage

- Original thesis: `docs/thesis_latex`, method JO-VPPM.
- Expanded submitted paper: `docs/AIO-mesh-submitted 1/submitted-1.tex`, method HARP, framework AIO-Mesh; journal Future Generation Computer Systems.
- Current major revision: `docs/AIO-mesh-rev1/review.txt`, `todo.md`, `todo-2.md`, `refs.bib`.
- Upstream historical `docs/AIO-mesh`, `docs/thesis_JOVPPM`, `docs/note` do not supersede the user-designated sources above.
- No revision manuscript `.tex` is currently present in the revision folder, despite checklist references to `AIO-Mesh.rev1.tex`.

## Reviewer priorities

Reframe novelty around the runtime admission contract and MSD-aware deployability; HARP is replaceable. Isolate runtime safety using protected baselines. Audit Elephant/Chaos generators, matched seeds, significance, acceptance accounting and ablation attribution. Clarify pair versus full-chain action semantics, SID/MSD realization, mask complexity, feature normalization, stale state, hybrid gate, latency/scalability/concurrency and conditional K-cache claims. Long-running HIL, migration and fault-injection claims require raw evidence. Review abbreviation consistency and shorten the conclusion.

## Evidence cautions

`todo.md` lists many experiments/artifacts as pending, while `todo-2.md` ticks most E1–E6 tasks complete. Reconcile these states against raw artifacts, source/config versions, seeds and logs before accepting completion. Never fabricate numbers or infer evidence from checklist ticks. Submitted results remain historical baseline until replacements have provenance.

Revision notes reference a different source state and are not proof about synchronized HARP. Example: current simulation env uses Discrete(N*N), but lists uniform/bursty/heavy_tail with no explicit chaos generator branch. Runtime contains 0.45/0.35 hybrid thresholds and try_reserve; existence alone does not establish full-chain or end-to-end safety. Re-audit source claims before editing the manuscript.

## Next task

Map reviewer concerns to synchronized source and available artifacts, reconcile both checklists, then prepare the revised manuscript and response. Synchronization does not complete revision experiments or validate reported results.

## Server refactor status

Branch `HARP-server` now separates HTTP/forecast/actuation from the hybrid selection/admission service, removes the unregistered duplicate orchestration implementation, shares runtime settings and consolidates the Docker build/dependencies. Ten redundant files were removed with reversible backups; historical research artifacts are retained. Fifteen unit/HTTP regression checks pass. Frontend build and live HIL/benchmark validation remain unperformed. This does not close reviewer experiment tasks.
