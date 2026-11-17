# Reproducible phase inputs

This prepares code/data/model bundles only. It does not run training,
benchmark evaluation, Kaggle or HIL and is not a code-freeze approval.

Build a training input snapshot, deliberately omitting old checkpoint inputs:

```sh
python scripts/rev1/package_inputs.py --mode training --output /tmp/rev1-training-inputs.zip
```

Build an evaluation input snapshot after new checkpoints have been produced:

```sh
python scripts/rev1/package_inputs.py --mode evaluation --output /tmp/rev1-evaluation-inputs.zip
```

Evaluation mode requires every protocol model and normalizer file. Packaging
pins file hashes but does not certify action spaces or compatibility. Run the
artifact checker on the extracted resolved protocol before evaluation:

```sh
python scripts/rev1/check_artifacts.py --protocol configs/rev1/protocol.resolved.json --output results/rev1/preflight.json
```

Each archive contains `CoreRouter/package_manifest.json` and
`CoreRouter/configs/rev1/protocol.resolved.json`. The latter pins source, data
and evaluation-artifact hashes. Training mode explicitly records omitted and
missing artifacts; it is not an evaluation-ready package. New training outputs
must receive new hashes before evaluation packaging.

The builder sorts paths and fixes ZIP metadata. Identical stable inputs give
identical archive bytes on the same toolchain. It excludes virtual environments,
caches, hidden directories, node_modules and compiled build trees. It rejects
symlinks, escaping paths, pinned-hash mismatches, missing evaluation inputs,
changed inputs during packaging, duplicate/extra archive entries and invalid
CRC/content hashes. Bundle validation also checks the resolved protocol against
archived source/data/model bytes. Keep the printed archive SHA-256 outside the
archive and verify it before extraction on Kaggle.

Canonical source hashing is shared with the artifact checker. It includes the
protocol's explicit source paths, filters out the excluded local/generated
files and hashes each sorted relative path followed by its file SHA-256 bytes.
Configuration/dependency files are additionally covered by the full manifest.
Any subsequent code change requires rebuilding the input snapshot.

The representative historical `notebook/vietnam.ipynb` remains historical.
The older ablation Python notebook export still uses package discovery. The
dedicated `notebook/rev1-benchmark-ablation-kaggle.ipynb` uses an explicit
package path and externally recorded SHA-256, validates the archive before
using it, refuses to overwrite its work root and defaults to plan-only. No
package is uploaded by these commands.

A protocol-driven phase driver is available. It prints the exact commands by
default and performs no execution:

```sh
python scripts/rev1/phase_driver.py --topology vietnam --output-dir results/rev1/example \
  --input-package /tmp/rev1-evaluation-inputs.zip --input-sha256 <external-sha256>
```

The user may later add `--execute` to run preflight followed by the protocol's
ablation scenarios, the main benchmark for each scenario, and the load sweep.
Execution checks that each ablation path is canonical and has no
higher-priority shadow file. Missing pinned datasets fail instead of silently
substituting a repository default. The separate `--stage audit` command plans
or runs cross-topology coverage and source-lineage validation for completed
results; it does not launch training or benchmark workloads. See
`FREEZE_MANIFEST.md` for the phase runbook and read-only freeze verifier.

Training can also be planned explicitly with `--stage train` and the required
`--train-seed`, `--main-steps`, `--ablation-steps`, `--n-envs`,
`--rollout-steps` and `--train-scenario` options. No historical budget is
inferred. Default is plan-only. If the user later selects `--execute`, source,
dataset and pinned dependencies are verified first; an unused isolated
`results/rev1` output directory and `training_plan.json` are created before
new training starts. PPO rollout rounding can make actual trained steps exceed
the requested budget; the ablation trainer currently uses 512 rollout steps.
Training outputs still need compatible evaluation packaging and preflight.

Code-path smoke training uses `--stage smoke` with an output under
`results/rev1/smoke/<run-id>` and explicit budgets no greater than 1,024 steps
per trainer. It is plan-only unless `--execute` is supplied. Its
`smoke_only` training plan is rejected by evaluation packaging, so these
checkpoints cannot be mistaken for research-training inputs.

After the user has produced and copied all three new-training run directories
into the same revision workspace, build an evaluation package without copying
models into the historical `results/models` tree:

```sh
python scripts/rev1/package_inputs.py --mode evaluation --output /tmp/rev1-evaluation-inputs.zip \
  --training-run vietnam=results/rev1/vietnam-run \
  --training-run nsfnet=results/rev1/nsfnet-run \
  --training-run geant2=results/rev1/geant2-run
```

Every protocol topology must be specified. Each run must contain the driver's
`training_plan.json` with matching source and dataset hashes and topology; the
plan is included in the evaluation bundle. Models are stored under their
canonical archive paths and individually hashed. This lineage check does not
certify that training completed correctly or that model spaces match: evaluation
preflight remains mandatory.
