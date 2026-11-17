from pathlib import Path

import pytest

from src.analytics.ablation_study import resolve_data_path as resolve_ablation_data
from src.analytics.benchmark.benchmark_algorithm.env_factory import resolve_data_path as resolve_benchmark_data


@pytest.mark.parametrize("resolver", [resolve_ablation_data, resolve_benchmark_data])
def test_missing_pinned_dataset_fails_without_substituting_repository_default(tmp_path, resolver):
    missing = tmp_path / "pinned-dataset.csv"
    with pytest.raises(FileNotFoundError, match=str(missing)):
        resolver(missing)
