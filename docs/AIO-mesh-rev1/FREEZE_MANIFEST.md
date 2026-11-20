# Code freeze verification and phase runbook

This document covers code and input reproducibility. The verifier does not
start controllers, Kubernetes, training, simulation workloads, benchmarks, or
HIL. A clean verifier report is a precondition for execution, not research
evidence or proof that forwarding works on a testbed.

## Freeze verification

After all source edits are reviewed and committed, build a new training input
package (before checkpoints exist) or evaluation package (after compatible
checkpoints exist) and record its SHA-256 outside the archive. Then run:

```sh
python scripts/rev1/verify_freeze.py \
  --root . \
  --input-package /path/to/rev1-training-inputs.zip \
  --input-sha256 <external-sha256> \
  --expected-mode training \
  --output results/rev1/freeze-verification.json
```

The report records the Git commit, dirty paths, Python and dependency versions,
protocol hash, package mode/manifest/hash, and `--help` command contracts for the
phase, package, and coverage CLIs. It reports the optional `p4runtime-shell`
dependency even when that package is absent. A dirty tree, missing required
dependency, package/protocol/source/data/config mismatch, or failed command
contract blocks the report. A training package validates source/data before new models exist; after
training, verify a separate evaluation package before benchmark execution. This
command reads repository/package metadata; `--output` only writes the requested
report file.

## Simulation phase

Use the resolved protocol's pinned dataset, checkpoints, scenarios, and
pre-registered 20-seed list:

```text
[42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
 11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192]
```

The first 10 preserve the prior revision proposal; the added 10 are fixed in
`configs/rev1/protocol.json`. Do not alter this list after result collection
starts. Plan each topology separately (default is plan-only):

The current primary main checkpoints are the corrected retrains under
`results/models/retrain_v11_20261119_corrected/`. They use flat
`Discrete(N²)` action heads: Vietnam N=10, NSFNET N=14, GEANT2 N=23. The
synthetic 25/50/100-node checkpoints used by the new benchmark also use
`Discrete(N²)`. Existing ablation variants use the same flat action interface
and remain valid without retraining for action-space compatibility. Archived
pre-retrain main v10/v11 checkpoints retain their historical factorized
`MultiDiscrete([N,N])` / `2N` heads; the legacy loader still supports them, but
they are not the current primary model inputs. The benchmark launch manifest
pins all six current model and normalizer hashes. The new benchmark is still
running, so its numerical outputs are not yet complete.

```sh
python scripts/rev1/phase_driver.py --stage evaluate --topology vietnam \
  --protocol configs/rev1/protocol.resolved.json --output-dir results/rev1/vietnam \
  --input-package /path/to/rev1-evaluation-inputs.zip --input-sha256 <external-sha256>
```

The user explicitly adds `--execute` after the input preflight, freeze report,
and protocol review. Repeat for NSFNET and GEANT2. After all result directories
are complete, audit the package lineage and full topology/scenario matrix:

```sh
python scripts/rev1/phase_driver.py --stage audit \
  --input-package /path/to/rev1-evaluation-inputs.zip \
  --input-sha256 <external-sha256> \
  --run vietnam=results/rev1/vietnam \
  --run nsfnet=results/rev1/nsfnet \
  --run geant2=results/rev1/geant2 \
  --steps 3000 --audit-output results/rev1/coverage.json
```

Audit mode validates completed outputs; it does not launch experiment commands.

## Kaggle / server phase

Build a deterministic training input package from the reviewed source and
pinned dataset. On Kaggle/server, train into a new `results/rev1` run directory
using `--stage train` with explicit seed, main/ablation budgets, environment
count, rollout size, and scenario. The command is plan-only unless the user
adds `--execute`. Preserve `training_plan.json`, logs, checkpoints, and hashes.
Then package the completed topology training runs in evaluation mode and run
artifact preflight before simulation evaluation. Training completion is not
evaluation evidence.

For code-path smoke training only, use `--stage smoke` and an output directory
under `results/rev1/smoke/<run-id>`. Explicit main/ablation budgets are capped
at 1,024 steps each. The default remains plan-only; this mode is never accepted
as a new-training run by evaluation packaging, and its checkpoints cannot
silently become benchmark inputs. Smoke outputs are not research results.

## HIL physical phase

HIL is a separate, user-operated phase on a verified testbed. Before enabling
actuation, provide a supported mapping from admitted realization/profile to
switch, SID and port, and a controller operation that can de-steer/delete and
confirm rule removal. The current implementation rejects actuation when that
mapping is missing. Use request-correlated migration journal records, preserve
raw request/counter logs, and retain reservations whenever deletion or absence
cannot be confirmed. Deployed TTL teardown/readback is not implemented: expiry
returns `DEPLOYED_TTL_TEARDOWN_REQUIRED`, and the durable reservation ledger
must remain charged until a correlated P4 rule-delete readback confirms
success. An HTTP acceptance alone is not deletion evidence. No freeze verifier
or simulation command starts HIL.
