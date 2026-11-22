# Attempt 1 — invalid for admission-rate comparison (client bug)

- Started 2026-11-21 ~16:36 UTC; script `scripts/run_admission_concurrency.py` (sha256 in manifest.json `script_sha256`).
- Bug: TTL release called `POST /api/orchestrate/free` with only `vnf_name`; the backend schema
  `FreeResourceRequest` also requires `v_place, v_route, cpu_req, ram_req, msd_req`, so all 37 release
  calls returned HTTP 422 (see free_calls.csv and backend access log). The 37 admitted reservations
  (unactuated, no Deployment/PipelineRun) stayed in the live ledger and filled capacity: after seed 42,
  level C=1 every later request was rejected.
- Valid content: seed 42 / C=1 is a clean measurement up to the point capacity filled; all other levels
  measure only the rejection path under an occupied ledger (37 extra pending reservations).
- Cleanup 2026-11-21 16:43 UTC: `scripts/release_leftover_reservations.py <this dir> --apply` released
  exactly the 37 names recorded as admitted in per_request.csv (HTTP 200 x37); active VNFs back to the
  7 baseline names; ledger snapshot fields identical to ledger_before.sqlite3 except the monotonic
  state_version (15513 -> 18607). Log: leftover_release_log.json.
- Fix applied for attempt 2: full release payload + abort if any release fails or the active set
  differs from the baseline after a level.
