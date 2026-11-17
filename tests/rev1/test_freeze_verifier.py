from scripts.rev1.verify_freeze import sha256_file, verify_cli_contracts


def test_sha256_file_uses_file_bytes(tmp_path):
    item = tmp_path / "manifest.json"
    item.write_bytes(b'{"schema":1}\n')
    assert sha256_file(item) == "6b823fa123b900a4139de2101277275af8329f3a3d34c00ef3bf4fc6bf60287e"


def test_cli_contract_check_only_invokes_help_commands():
    calls = []

    class Result:
        returncode = 0
        stdout = "usage"
        stderr = ""

    def runner(command, **kwargs):
        calls.append(command)
        return Result()

    report = verify_cli_contracts("/repo", runner=runner)
    assert report["status"] == "passed"
    assert len(calls) == 3
    assert all(command[-1] == "--help" for command in calls)


def test_freeze_verification_accepts_training_package_before_checkpoints_exist():
    import pytest
    from scripts.rev1.verify_freeze import validate_input_package_mode
    assert validate_input_package_mode({"mode": "training"}) == "training"
    assert validate_input_package_mode({"mode": "evaluation"}) == "evaluation"
    with pytest.raises(ValueError, match="mode mismatch"):
        validate_input_package_mode({"mode": "training"}, "evaluation")
