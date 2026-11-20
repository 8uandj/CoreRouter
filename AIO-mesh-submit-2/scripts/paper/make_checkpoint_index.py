"""Record serialized metadata for main checkpoints without unpickling them."""
import json
from pathlib import Path
import zipfile

from make_evidence_index import ROOT, OUT, sha256

FIELDS = (
    "seed", "num_timesteps", "n_envs", "n_steps", "batch_size",
    "n_epochs", "gamma", "gae_lambda", "ent_coef", "vf_coef",
)


def main():
    records = []
    for checkpoint in sorted((ROOT / "results/models/v11").rglob("dgrl_v11_final_*.zip")):
        topology = checkpoint.stem.rsplit("_", 1)[1]
        normalizer = checkpoint.with_name(f"vec_normalize_v11_{topology}.pkl")
        with zipfile.ZipFile(checkpoint) as archive:
            metadata = json.loads(archive.read(next(
                name for name in archive.namelist() if name.split("/")[-1] == "data"
            )))
            version = next((name for name in archive.namelist()
                            if name.split("/")[-1] == "_stable_baselines3_version"), None)
            sb3 = archive.read(version).decode().strip() if version else None
        records.append({
            "topology": topology,
            "checkpoint": str(checkpoint.relative_to(ROOT)),
            "checkpoint_sha256": sha256(checkpoint),
            "normalizer": str(normalizer.relative_to(ROOT)),
            "normalizer_sha256": sha256(normalizer),
            "stable_baselines3_version": sb3,
            "serialized_metadata": {key: metadata[key] for key in FIELDS},
        })
    if {record["topology"] for record in records} != {"vietnam", "nsfnet", "geant2"}:
        raise ValueError("Expected three topology-specific main checkpoints")
    output = {
        "main_checkpoint_artifacts": records,
        "unavailable": ["exact training command and source commit", "training data hash",
                        "hardware and duration", "criterion used to select checkpoints",
                        "flat-action ablation checkpoint and training-log archive"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "training_metadata.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
