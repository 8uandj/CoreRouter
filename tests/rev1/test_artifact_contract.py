import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import torch

from scripts.rev1.check_artifacts import (
    inspect_model_artifact,
    inspect_normalizer_artifact,
    run_protocol,
)


def write_model(path: Path, *, nodes=3, architecture="gat", action_dim=None, observation_dim=None):
    obs_dim = observation_dim or nodes * 6 + 13
    action_dim = action_dim or nodes * nodes
    state = {"action_net.weight": torch.zeros(action_dim, 128)}
    if architecture == "gat":
        state["features_extractor.gat1.W.weight"] = torch.zeros(256, 6)
        state["features_extractor.fusion.0.weight"] = torch.zeros(512, 64 * nodes + 24)
    else:
        state["features_extractor.net.0.weight"] = torch.zeros(768, obs_dim)
    payload = io.BytesIO()
    torch.save(state, payload)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("policy.pth", payload.getvalue())


class ArtifactContractTests(unittest.TestCase):
    def test_gat_model_and_normalizer_match_topology_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "model.zip"
            normalizer = Path(temp) / "normalizer.npz"
            write_model(model, nodes=3)
            np.savez(normalizer, obs_mean=np.zeros(31), obs_var=np.ones(31))

            model_info = inspect_model_artifact(model, expected_nodes=3, expected_architecture="gat")
            normalizer_info = inspect_normalizer_artifact(normalizer, expected_observation_dim=31)

            self.assertEqual(model_info["action_dim"], 9)
            self.assertEqual(model_info["observation_dim"], 31)
            self.assertEqual(normalizer_info["observation_dim"], 31)

    def test_mlp_variant_is_distinguished_from_gat(self):
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "model.zip"
            write_model(model, nodes=3, architecture="mlp")
            info = inspect_model_artifact(model, expected_nodes=3, expected_architecture="mlp")
            self.assertEqual(info["architecture"], "mlp")
            with self.assertRaisesRegex(ValueError, "architecture"):
                inspect_model_artifact(model, expected_nodes=3, expected_architecture="gat")

    def test_wrong_topology_observation_and_multidiscrete_action_heads_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "model.zip"
            write_model(model, nodes=3)
            with self.assertRaisesRegex(ValueError, "topology mismatch"):
                inspect_model_artifact(model, expected_nodes=4, expected_architecture="gat")
            with self.assertRaisesRegex(ValueError, "observation"):
                inspect_model_artifact(
                    model, expected_nodes=3, expected_architecture="gat", expected_observation_dim=32
                )
            write_model(model, nodes=3, action_dim=6)
            with self.assertRaisesRegex(ValueError, "action head"):
                inspect_model_artifact(model, expected_nodes=3, expected_architecture="gat")

    def test_missing_normalizer_fails(self):
        with self.assertRaisesRegex(FileNotFoundError, "normalizer"):
            inspect_normalizer_artifact(Path("/missing/normalizer.pkl"), expected_observation_dim=31)

    def test_protocol_rejects_runtime_dependency_version_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "dataset.csv").write_text("x\n1\n", encoding="utf-8")
            (root / "source").mkdir()
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps({
                "protocol_id": "test",
                "dataset": {"path": "dataset.csv", "sha256": "0" * 64},
                "source_paths": ["source"],
                "source_sha256": "0" * 64,
                "runtime_versions": {"numpy": "0.0.0"},
                "artifacts": [],
            }), encoding="utf-8")

            result = run_protocol(protocol_path, root / "report.json", root)

            self.assertEqual(result["status"], "blocked")
            self.assertTrue(any("runtime package version mismatch for numpy" in error for error in result["errors"]))

    def test_protocol_reports_artifact_hash_even_when_model_contract_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "dataset.csv").write_text("x\n1\n", encoding="utf-8")
            (root / "source").mkdir()
            model = root / "model.zip"
            normalizer = root / "normalizer.npz"
            write_model(model, nodes=3, action_dim=6)
            np.savez(normalizer, obs_mean=np.zeros(31))
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps({
                "protocol_id": "test",
                "dataset": {"path": "dataset.csv", "sha256": "0" * 64},
                "source_paths": ["source"],
                "source_sha256": "0" * 64,
                "artifacts": [{
                    "topology": "tiny", "variant": "main", "node_count": 3,
                    "architecture": "gat", "model_path": "model.zip",
                    "normalizer_path": "normalizer.npz",
                }],
            }), encoding="utf-8")

            result = run_protocol(protocol_path, root / "report.json", root)

            artifact = result["artifacts"][0]
            self.assertIsNone(artifact["model"])
            self.assertEqual(len(artifact["model_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
