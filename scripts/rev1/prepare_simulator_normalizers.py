#!/usr/bin/env python3
"""Stage saved VecNormalize statistics for the pinned NumPy 1.24 runner.

The source pickle remains untouched. The generated NPZ contains only the
observation-normalization statistics consumed by this repository's NpzNormalizer.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pickle
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


class _IgnoredGeneratorState:
    """The evaluation normalizer needs observation statistics, not its RNG."""

    def __setstate__(self, state):
        del state


class _CompatUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        if module == "numpy.random._pickle" and name in (
            "__generator_ctor", "__bit_generator_ctor"
        ):
            return lambda *args, **kwargs: _IgnoredGeneratorState()
        return super().find_class(module, name)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_saved_normalizer(path: Path):
    # NumPy 2 pickles renamed numpy.core to numpy._core. Alias only for reading
    # the archived artifact; the live benchmark continues using pinned NumPy.
    for name in (
        "numpy._core", "numpy._core.multiarray", "numpy._core._multiarray_umath",
        "numpy._core.numeric", "numpy._core.numerictypes",
    ):
        try:
            sys.modules[name] = importlib.import_module(
                name.replace("numpy._core", "numpy.core")
            )
        except ImportError:
            pass
    with path.open("rb") as handle:
        return _CompatUnpickler(handle).load()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-model-root", type=Path,
                        default=Path("AIO-mesh-submit-2/results/models"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results/rev1/p1_2_simulator/normalizers"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for topology in ("synthetic_25", "synthetic_50", "synthetic_100"):
        source_dir = args.source_model_root / f"v11_{topology}"
        source_pkl = source_dir / f"vec_normalize_v11_{topology}.pkl"
        if not source_pkl.is_file():
            raise FileNotFoundError(source_pkl)
        obj = load_saved_normalizer(source_pkl)
        stats = obj.obs_rms
        staged_pkl = args.output_dir / source_pkl.name
        shutil.copy2(source_pkl, staged_pkl)
        npz_path = staged_pkl.with_suffix(".npz")
        np.savez_compressed(
            npz_path,
            obs_mean=np.asarray(stats.mean, dtype=np.float32),
            obs_var=np.asarray(stats.var, dtype=np.float32),
            clip_obs=np.asarray(float(obj.clip_obs), dtype=np.float64),
            epsilon=np.asarray(float(obj.epsilon), dtype=np.float64),
            norm_obs=np.asarray(bool(obj.norm_obs), dtype=np.bool_),
        )
        entries.append({
            "topology": topology,
            "source_pickle": str(source_pkl),
            "source_pickle_sha256": sha256(source_pkl),
            "staged_pickle": str(staged_pkl),
            "staged_pickle_sha256": sha256(staged_pkl),
            "npz_sidecar": str(npz_path),
            "npz_sidecar_sha256": sha256(npz_path),
            "observation_shape": list(stats.mean.shape),
            "clip_obs": float(obj.clip_obs),
            "epsilon": float(obj.epsilon),
            "norm_obs": bool(obj.norm_obs),
        })
    manifest = {
        "protocol": "saved-vecnormalize-npz-compatibility-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "numpy": np.__version__,
        "rng_state_used_for_normalization": False,
        "entries": entries,
    }
    output = args.output_dir / "normalizer_conversion_manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
