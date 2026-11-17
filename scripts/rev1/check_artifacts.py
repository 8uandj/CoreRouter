#!/usr/bin/env python3
"""Preflight pinned revision checkpoints and normalizers before long runs.

The checker reads policy tensors with PyTorch's weights-only loader. SB3
VecNormalize files are trusted local pickle artifacts produced by this repo's
training code; never point the protocol at untrusted pickle files.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import pickle
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import torch


try:
    from .bundle_hashes import sha256_file, sha256_paths
except ImportError:
    from bundle_hashes import sha256_file, sha256_paths


def inspect_model_artifact(
    model_path: Path,
    *,
    expected_nodes: int,
    expected_architecture: str,
    expected_observation_dim: int | None = None,
    action_encoding: str = "flat_n2",
) -> dict[str, Any]:
    if expected_architecture not in {"gat", "mlp"}:
        raise ValueError(f"Unsupported expected architecture: {expected_architecture}")
    if not model_path.is_file():
        raise FileNotFoundError(f"model checkpoint missing: {model_path}")
    try:
        with zipfile.ZipFile(model_path) as archive:
            policy_bytes = archive.read("policy.pth")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"invalid SB3 policy archive {model_path}: {exc}") from exc

    try:
        state = torch.load(io.BytesIO(policy_bytes), map_location="cpu", weights_only=True)
    except TypeError as exc:
        raise RuntimeError("Artifact preflight requires PyTorch with weights_only loading support") from exc
    if not isinstance(state, dict):
        raise ValueError(f"policy weights are not a state dictionary: {model_path}")

    action_weight = state.get("action_net.weight")
    if action_weight is None or len(action_weight.shape) != 2:
        raise ValueError(f"missing linear action head in {model_path}")
    action_dim = int(action_weight.shape[0])

    gat_weight = state.get("features_extractor.gat1.W.weight")
    gat_fusion = state.get("features_extractor.fusion.0.weight")
    mlp_input = state.get("features_extractor.net.0.weight")
    if gat_weight is not None and gat_fusion is not None:
        architecture = "gat"
        if len(gat_weight.shape) != 2 or int(gat_weight.shape[1]) != 6:
            raise ValueError(f"GAT node feature width mismatch in {model_path}")
        fusion_width = int(gat_fusion.shape[1])
        inferred_nodes, remainder = divmod(fusion_width - 24, 64)
        if remainder != 0:
            raise ValueError(f"cannot infer GAT topology size from feature tensor in {model_path}")
        observation_dim = inferred_nodes * 6 + 13
    elif mlp_input is not None:
        architecture = "mlp"
        observation_dim = int(mlp_input.shape[1])
        inferred_nodes, remainder = divmod(observation_dim - 13, 6)
        if remainder != 0:
            raise ValueError(f"cannot infer MLP topology size from observation tensor in {model_path}")
    else:
        raise ValueError(f"unrecognized GAT/MLP feature extractor in {model_path}")

    if architecture != expected_architecture:
        raise ValueError(
            f"architecture mismatch for {model_path}: expected {expected_architecture}, got {architecture}"
        )
    if inferred_nodes != expected_nodes:
        raise ValueError(
            f"topology mismatch for {model_path}: expected {expected_nodes} nodes, got {inferred_nodes}"
        )
    expected_obs = expected_observation_dim or (6 * expected_nodes + 13)
    if observation_dim != expected_obs:
        raise ValueError(
            f"observation dimension mismatch for {model_path}: expected {expected_obs}, got {observation_dim}"
        )
    expected_actions = expected_nodes * expected_nodes
    allowed_actions = {
        "flat_n2": expected_actions,
        "factorized_2n": 2 * expected_nodes,
    }
    if action_encoding not in allowed_actions:
        raise ValueError(f"unsupported action encoding in protocol: {action_encoding}")
    if action_dim != allowed_actions[action_encoding]:
        raise ValueError(
            f"action head mismatch for {model_path}: expected {action_encoding} "
            f"({allowed_actions[action_encoding]} logits), got {action_dim} logits"
        )

    return {
        "path": str(model_path),
        "sha256": sha256_file(model_path),
        "topology_nodes": inferred_nodes,
        "observation_dim": observation_dim,
        "action_space": f"Discrete({expected_actions})",
        "action_dim": action_dim,
        "action_encoding": action_encoding,
        "architecture": architecture,
    }


def inspect_normalizer_artifact(
    normalizer_path: Path, *, expected_observation_dim: int
) -> dict[str, Any]:
    if not normalizer_path.is_file():
        raise FileNotFoundError(f"normalizer missing: {normalizer_path}")
    try:
        if normalizer_path.suffix == ".npz":
            with np.load(normalizer_path) as stats:
                mean = stats["obs_mean"] if "obs_mean" in stats else stats["mean"]
        else:
            with normalizer_path.open("rb") as handle:
                normalizer = pickle.load(handle)
            mean = normalizer.obs_rms.mean
    except Exception as exc:
        raise ValueError(f"cannot read normalizer observation statistics {normalizer_path}: {exc}") from exc
    observation_dim = int(np.asarray(mean).size)
    if observation_dim != expected_observation_dim:
        raise ValueError(
            f"normalizer observation dimension mismatch for {normalizer_path}: "
            f"expected {expected_observation_dim}, got {observation_dim}"
        )
    return {
        "path": str(normalizer_path),
        "sha256": sha256_file(normalizer_path),
        "observation_dim": observation_dim,
    }


def _resolve(root: Path, relative_path: str) -> Path:
    resolved = (root / relative_path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"protocol path escapes repository root: {relative_path}") from exc
    return resolved


def _check_pinned_hash(label: str, actual: str, expected: str | None, errors: list[str]) -> None:
    if not expected:
        errors.append(f"{label}: expected SHA-256 is not pinned in protocol")
    elif actual.lower() != expected.lower():
        errors.append(f"{label}: SHA-256 mismatch (expected {expected}, got {actual})")


def run_protocol(protocol_path: Path, output_path: Path, root: Path) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    artifacts: list[dict[str, Any]] = []

    dataset = protocol.get("dataset", {})
    dataset_path = _resolve(root, dataset.get("path", ""))
    if not dataset_path.is_file():
        errors.append(f"dataset missing: {dataset_path}")
        dataset_hash = None
    else:
        dataset_hash = sha256_file(dataset_path)
        _check_pinned_hash("dataset", dataset_hash, dataset.get("sha256"), errors)

    source_paths = [_resolve(root, item) for item in protocol.get("source_paths", [])]
    missing_sources = [str(path) for path in source_paths if not path.exists()]
    errors.extend(f"source path missing: {path}" for path in missing_sources)
    source_hash = sha256_paths([path for path in source_paths if path.exists()], root)
    _check_pinned_hash("source tree", source_hash, protocol.get("source_sha256"), errors)

    for item in protocol.get("artifacts", []):
        label = f"{item.get('topology')}/{item.get('variant')}"
        nodes = int(item["node_count"])
        obs_dim = int(item.get("observation_dim", nodes * 6 + 13))
        record: dict[str, Any] = {
            "topology": item["topology"],
            "variant": item["variant"],
            "model": None,
            "model_sha256": None,
            "normalizer": None,
            "normalizer_sha256": None,
            "errors": [],
        }
        model_path = _resolve(root, item["model_path"])
        normalizer_path = _resolve(root, item["normalizer_path"])
        if model_path.is_file():
            record["model_sha256"] = sha256_file(model_path)
            _check_pinned_hash(
                f"{label} model", record["model_sha256"], item.get("model_sha256"), record["errors"]
            )
        try:
            model = inspect_model_artifact(
                model_path,
                expected_nodes=nodes,
                expected_architecture=item["architecture"],
                expected_observation_dim=obs_dim,
                action_encoding=item.get("action_encoding", "flat_n2"),
            )
            record["model"] = model
        except Exception as exc:
            record["errors"].append(f"model: {type(exc).__name__}: {exc}")
        if normalizer_path.is_file():
            record["normalizer_sha256"] = sha256_file(normalizer_path)
            _check_pinned_hash(
                f"{label} normalizer", record["normalizer_sha256"],
                item.get("normalizer_sha256"), record["errors"]
            )
        try:
            normalizer = inspect_normalizer_artifact(normalizer_path, expected_observation_dim=obs_dim)
            record["normalizer"] = normalizer
        except Exception as exc:
            record["errors"].append(f"normalizer: {type(exc).__name__}: {exc}")
        errors.extend(f"{label}: {message}" for message in record["errors"])
        artifacts.append(record)

    try:
        versions = {
            name: importlib.metadata.version(name)
            for name in (
                "numpy", "gymnasium", "stable-baselines3", "sb3-contrib", "torch",
                "shimmy", "matplotlib", "pandas", "networkx", "scipy",
            )
        }
    except importlib.metadata.PackageNotFoundError as exc:
        versions = {"error": str(exc)}
        errors.append(f"runtime package version unavailable: {exc}")
    for name, expected in protocol.get("runtime_versions", {}).items():
        actual = versions.get(name)
        if actual is None:
            errors.append(f"runtime package version unavailable for pinned package {name}")
        elif actual != str(expected):
            errors.append(f"runtime package version mismatch for {name}: expected {expected}, got {actual}")

    result = {
        "protocol_id": protocol.get("protocol_id"),
        "status": "ready" if not errors else "blocked",
        "dataset": {"path": str(dataset_path), "sha256": dataset_hash},
        "source_sha256": source_hash,
        "runtime_versions": versions,
        "eval_seeds": protocol.get("eval_seeds", []),
        "scenarios": protocol.get("scenarios", []),
        "artifacts": artifacts,
        "errors": errors,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    protocol_path = args.protocol if args.protocol.is_absolute() else args.root / args.protocol
    output_path = args.output if args.output.is_absolute() else args.root / args.output
    result = run_protocol(protocol_path, output_path, args.root.resolve())
    print(f"artifact preflight: {result['status']} ({len(result['errors'])} issue(s))")
    for error in result["errors"]:
        print(f"- {error}")
    print(f"report: {output_path}")
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
