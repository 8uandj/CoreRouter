# Migration recovery records

The backend container configures a SQLite journal at
`results/rev1/runtime/migrations.sqlite3`. Override with
`CORE_ROUTER_MIGRATION_JOURNAL` pointing to a writable, persistent local volume.
A container filesystem alone does not preserve records when the container is
replaced. The journal is a local execution record, not a distributed transaction
or an automatic workflow restart engine. The service defaults to an in-memory
journal when constructed directly (unit tests); production wiring supplies the
file-backed journal explicitly.

After an orchestration response schedules migration, its `migration_result`
contains `new_vnf` and `status_path`. GET that path using the deployment's normal
API prefix, for example `/api/orchestrate/migrations/<new_vnf>`. Unknown names
return HTTP 404. A result may not exist before the background task starts.
Records survive process restart when the same journal volume is used. A saved
`running` record describes the last recorded stage; it does not prove that a
worker is still executing. Reconcile interrupted stages with Kubernetes and the
controller before any cleanup.

| Recorded outcome | Meaning |
| --- | --- |
| `MAKE_STARTED` | Recorded before invoking infrastructure MAKE. |
| `STEERING_SUBMITTING` | Operation ID and exact controller payload saved before POST. |
| `STEERING_UNCERTAIN` | No correlated confirmation. Keep old and replacement endpoints and resource charges. |
| `BREAK_REQUESTING` | Steering was confirmed for this operation; old deletion is about to be requested. |
| `BREAK_FAILED` | Old deletion request failed; migration is not complete. |
| `BREAK_UNCONFIRMED` | Delete accepted but Deployment/Pod absence was not confirmed. Old charge remains. |
| `COMPLETED` | Correlated steering confirmation followed by observed old Deployment/Pod absence; old local reservation released. This is not packet-loss evidence. |
| `MIGRATION_UNCERTAIN` | Unexpected exception or cancellation; inspect prior event history and infrastructure. No automatic destructive cleanup is performed. |

A unique replacement name is claimed transactionally in the journal before
MAKE. A duplicate name returns `MIGRATION_ALREADY_EXISTS` without another MAKE
or overwriting the existing recovery result, including when separate workers
share the journal file. Retries require an explicitly reconciled workflow and a
new replacement identity; do not delete the journal to force an uncertain
operation to execute again.

A separate durable reservation ledger now restores local resource charges and
actuation intent before production API work. It defaults to
`results/rev1/runtime/reservations.sqlite3`; override using
`CORE_ROUTER_RESERVATION_DB`. Keep it and the migration journal on the persistent
volume together. Named, pending and anonymous charges and reported resource
baselines are committed before acknowledging mutations. Restored telemetry
has no fresh ingestion timestamps and requires new samples when TTL enforcement
is enabled.

The ledger is tied to the topology's ordered names, MSD profiles, adjacency
and latency matrix. Incompatible/corrupt state fails startup. Storage failures
latch new admission closed until recovery/restart. A local file lock permits
one process owner; inherited fork managers cannot commit as the parent's owner.
Run one admission API worker per runtime; this does not implement distributed
multi-controller reservations. Do not remove owner/ledger files to bypass a
live owner or erase uncertain allocations.

Restart recovery does not resume interrupted workflows or establish equivalence
between admitted synthetic SIDs and installed paths. Such workflows remain
subject to journal and infrastructure reconciliation.
No live deployment or controller validation is implied by the journal tests.
