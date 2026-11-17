# E1 admission and state semantics

The production selector and the Gym environment select one placement node and
one routing node per request. They do not realize a general multi VNF chain.

| Quantity | Accounting rule |
| --- | --- |
| CPU and RAM | Charged only to the placement node. |
| MSD / SID depth | Checked independently for each request's realized SID list against the routing node's limit. Concurrent flows do not add their SID depths together. |
| State column `MSD_used` | Maximum active SID-list depth observed on each routing node. It is an observation/accounting summary, not consumable capacity. |
| Environment path depth | The realized request-level SID-list length (`msd_req`) is checked against the selected routing node's MSD limit. The pair-level simulator does not materialize transit SIDs or add a hop contribution. |
| Release | Remove only a tracked named or anonymous reservation. Recompute the maximum remaining per-list depth when a reservation is removed. |
| Mask exhaustion | An all-false mask stays all false. It means no candidate passed the current feasibility predicate and must not be turned into unrestricted actions. |

The current Gym environment and runtime inference use flat `Discrete(N²)`
actions, encoded as `v_place * N + v_route`. The runtime mask has N² entries
and marks a pair only when placement CPU/RAM and route MSD pass; atomic
admission rechecks those constraints before reservation. Recovered main v11
checkpoints were trained with `MultiDiscrete([N,N])` and a `2N`-logit head.
The inference adapter sums placement and route logits for each pair before
applying the N² mask. This preserves the unmasked factorized distribution;
the original training mask and any revised pair-mask outcome are separate
provenance questions. The checkpoint and normalizer are not changed.

The in-process lock makes local admission and release updates atomic within one
`NetworkStateManager`; it does not provide a transaction across Kubernetes,
the API process, or the forwarding plane. A successful reservation is not proof
that deployment, steering, or packet forwarding completed.

## Hybrid decision gate

`NetworkStateManager.choose_mode()` uses the current snapshot's
`global_utilization = max(mean(node CPU utilization), mean(node MSD utilization))`.
There is no rolling window or duration requirement:

- In heuristic mode, engage DRL when utilization is strictly above `0.45`
  (float32 epsilon is used at the comparison boundary) or when a forecast alert
  is active.
- In DRL mode, return to heuristic only when utilization is strictly below
  `0.35` (with the same boundary epsilon) and no forecast alert is active.
- Otherwise, retain the current mode.

Per-node CPU `alert` flags above 80% are exposed in the snapshot but do not by
themselves engage DRL. Forecast alerts come from the telemetry/forecast path or
the request's alert, DDoS, or `Attack` fields. The orchestration router starts
the MBB/deployment handoff only when the selected branch is DRL and that
request-level `forecast_alert` predicate is true. There is no separate
migration cooldown/window in this gate.

Historical model compatibility remains a separate gate. Changes to feature,
action, or normalization representations require a model compatibility check
or retraining and validation before using a checkpoint for new measurements.

## Realization boundary found in the source audit

`generate_srv6_sids` produces a synthetic pair list for local admission and API
output. The migration service independently creates an endpoint SID; the admitted
list is not passed into its steering payload. Thus even pair-to-forwarding
correspondence is not established. Only the DRL-plus-forecast-alert branch of
`/orchestrate` schedules lifecycle work. The separate `/p4/rules` entry point
does not invoke pair admission. Controller steering status carries the deployment and operation identifiers;
the migration service requires both to match before removing the old VNF. See `PAIR_ACTUATION_AUDIT.md` and its source-hash manifest.

Safety statements apply to the local selection/reservation boundary, not to all
actuation entry points or installed packet paths. No live forwarding evidence
was produced by this audit.

## Uncertain migration and reservation retention

After a steering submission attempt, a lost response or non-202 response does
not establish that switch rules are unchanged. The service polls the same
operation and only proceeds to BREAK on correlated confirmation. Without it,
it returns `STEERING_UNCERTAIN`, operation ID and submission status, logs both
VNF names, and retains both endpoints and their reservations. This state needs
reconciliation; it is not successful migration or verified rollback.

Kubernetes list reconciliation no longer expires pending reservations at 60
seconds or silently drops an existing reservation when its list entry vanishes.
Anonymous reservations also remain charged during sync. Explicit lifecycle
cleanup must confirm absence before releasing a failed replacement. This can
retain capacity during unresolved failures; freeing it by timeout would risk
overbooking while deployments/Pods/forwarding still exist.

Migration results now persist in the production SQLite event journal and are
retrievable by replacement name. Duplicate replacement claims cannot reexecute
MAKE. Old-resource release requires confirmed old Deployment/Pod absence after
correlated steering; failed/unconfirmed BREAK is a recovery state, not completion.
See `RUNTIME_RECOVERY.md` for persistence configuration and restart limits.

## Observed utilization and local resource charges

Kubernetes sync no longer invents time-varying CPU/RAM baseline load or clears
reported MSD. The state uses reported CPU/RAM utilization plus locally tracked
charges. Repeated syncs do not add charges twice. A telemetry update cannot erase
pending reservations. Because measurements do not identify which local charges
are already included, this accounting can double-count measured deployed load;
it is conservative, not an exact occupancy estimator. Do not treat it as the
Gym simulator's observed workload or silently reuse its live acceptance rates.

A previously untracked deployment has unknown CPU/RAM/SID requirements; the
manager records `accounting_unknown` instead of inventing 10/5/2 defaults. New
admission rejects with `untracked_deployment_resources` while such records remain;
`unaccounted_vnfs` exposes them for reconciliation. A missing deployment list entry
does not resolve this uncertainty. Restart recovery must restore verified
reservation profiles before admission can safely resume.

Optional telemetry TTL now uses the oldest of separate CPU/RAM/MSD local-ingestion
timestamps. A missing field remains stale; MSD-only updates cannot mark missing
CPU/RAM observations fresh. Nonfinite/negative resources and invalid node IDs
are rejected before any state mutation. Upstream measurement time is still
unverified, and TTL remains opt-in.

## Named request expiry and live HIL readiness

`/orchestrate/free` accepts an optional `vnf_name`. A named selection-only
reservation is released by identity and repeated release is idempotent; another
request with the same CPU/RAM/depth tuple is unaffected. Legacy tuple-only
release remains limited to anonymous reservations.

The orchestration router marks actuation intent before scheduling background
work. TTL release rejects those records, observed deployments and unknown
profiles with `lifecycle_cleanup_required`. Their resources require the verified
lifecycle cleanup path, not a timer. Kubernetes sync preserves this intent.
Reset also rejects records tied to live/unresolved actuation or deployment.

The HIL runner sends request identity, retries unconfirmed TTL releases and no
longer resets the local ledger after scenario cleanup. A refused initial reset
stops the run. It counts deployment only after `deployment_ready` is explicitly
true from positive ready/desired replica counts on an HTTP 200 state response;
merely appearing in the deployment list is insufficient. A missing deployment
entry clears readiness while retaining its allocation.

This does not implement de-steering/deletion for deployed TTL expiry. Such
allocations remain held pending a verified teardown workflow. HIL migration
completion must still be correlated to the migration journal rather than a
global latest-pipeline success flag.

## Durable local admission state

Production container initialization restores a topology-bound SQLite admission
ledger before exposing infrastructure integrations. Each reservation, release,
actuation-intent, resource-sync and telemetry mutation is checkpointed under the
local admission lock before successful return. A failed write latches admission
closed. Named/pending/anonymous charges and reported resources survive restart;
ingestion timestamps do not, so strict freshness requires new samples.

Exclusive local ownership rejects a second process on the same ledger; a fork
cannot write through its parent's manager. This is a single-process local
contract, not distributed reservation. It adds synchronous storage overhead to
runtime decisions and must be present in measured runtime latency. Benchmarks
using the Gym simulator do not include that cost. See `RUNTIME_RECOVERY.md`.
