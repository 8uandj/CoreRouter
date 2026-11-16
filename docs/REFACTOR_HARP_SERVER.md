# HARP-server refactor — 2026-11-16

Baseline: `HARP` at `1b7ef37fb9cdce401609697307bdcc6e9bf2fe20`.
Working branch: `HARP-server`. This is a structural cleanup, not the major-review experiment implementation.

## Runtime ownership

- `routers/ai.py`: simulation replay and AI/model status only. Its unregistered orchestration router and stale implementation were removed; `main.py` never included that router.
- `routers/orchestration_router.py`: the registered HTTP API, telemetry/forecast updates and background actuation.
- `services/hybrid_decision.py`: heuristic/DRL selection, existing pair-level SID realization and tracked local admission. Keeps heuristic failure and concurrent-capacity fallback order; unexpected errors propagate. HardConstraintError now maps to HTTP 409 NO_SAFE_ACTION consistently, including exhausted DRL search (previously a generic handler returned 500).
- `src/shared/config.py`: canonical settings. Backend `app/core/config.py` re-exports the same object. Existing JO_VPPM environment names and checkpoint/module paths remain compatible. Configuration no longer overwrites GOOGLE_APPLICATION_CREDENTIALS on import.

No changes were made to training rewards, workload distributions, model weights, action space, telemetry freshness semantics or make-before-break ordering. Local admission remains pair-level and does not establish full-chain safety.

## Build and dependencies

The existing Python 3.11 Dockerfile was consolidated from `Dockerfile.py311` into the formerly empty `Dockerfile`. The Docker helper now references this canonical path. Docker and local backend setup use the same backend requirements, which include root research dependencies plus FastAPI, Uvicorn, Kubernetes, requests and torch-geometric. The unused Google AI SDK dependency was removed; no source imports it. Build caches and cleanup backups are excluded from Git/Docker contexts.

## Removed files and recovery

Ten files were removed from active paths with full copies retained under `.workspace-sync/refactor-HARP-server/removed/`. Exact paths, reasons, original SHA-256 and byte sizes are in `removed-files.json` there:

- Incomplete archive `zi3ZoVE6` and packaged source snapshot `kaggle_harp_update.zip`.
- Superseded `Dockerfile.py311` after consolidation.
- Historical editor backup `docs/thesis_JOVPPM/myThesis.tex.bak`.
- Unreferenced legacy `Monitoring.jsx` and unused React starter SVG.
- Four exact duplicates: root status/context/benchmark notes (canonical copies in `docs/note/`) and `docs/CoreRouter.pdf` (canonical `docs/Related/CoreRouter.pdf`).

Removed active files total 99,101,427 bytes. Backups still occupy disk intentionally and are ignored by Git/Docker. Before-images of modified runtime/config files are in the sibling `before/` directory. Git also preserves upstream tracked files.

Historical training versions, benchmark runners, P4 build profiles, thesis variants, submitted/revision documents, models, datasets and results are retained: no evidence establishes they are redundant. Keep old JO-VPPM/jo_vdpr identifiers where required by checkpoint loading or historical scripts.

## Verification

- 15 unit/HTTP tests pass: state manager, hybrid selection, heuristic and capacity fallback, reservation tracking, SID depth/order, fail-closed rejection, HTTP response compatibility, 409/422 and unexpected-error 500.
- HTTP checks use mocked Kubernetes/model/forecast integrations; no live testbed calls or deployments.
- All existing registered orchestration endpoint decorators match the baseline.
- Python AST syntax checks pass for tracked sources and new service/tests; shell syntax checks pass for the Docker helper and simulation launcher; `git diff --check` passes.
- FastAPI/httpx test dependencies were installed under `/tmp/harp-server-check-deps`, leaving the project's existing venv unchanged. Core suite: `venv/bin/python -m unittest discover -s tests -v`. Full HTTP suite in this session: `PYTHONPATH=/tmp/harp-server-check-deps:. venv/bin/python -m unittest discover -s tests -v` (run outside restricted event-loop sandbox). After normal backend setup, install `requirements-dev.txt` to enable HTTP tests.
- Frontend build/lint not run: Node/npm unavailable. Docker image not built. HIL/training/benchmark results are not validated by these checks.

## Remaining review work

`chaos` still aliases `heavy_tail` in algorithm benchmark configuration; historical notebooks and source notes disagree with this baseline. The two revision checklists disagree about experimental completion. These are documented in WORKSPACE_CONTEXT.md; changing experimental protocols or claims is a separate task requiring artifact audit and reruns.
