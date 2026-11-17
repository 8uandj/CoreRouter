import pytest
from scripts.rev1.phase_driver import build_commands, run_commands


def test_evaluation_commands_use_protocol_seeds_data_and_pinned_model():
    protocol = {'dataset': {'path': 'data/input.csv'}, 'eval_seeds': [42, 100],
                'scenarios': ['chaos'], 'artifacts': [{'topology': 'vietnam',
                'variant': 'main_v11', 'model_path': 'models/main.zip',
                'normalizer_path': 'models/norm.pkl'}]}
    commands = build_commands(protocol, 'vietnam', 'evaluate', 'results/rev1/run',
                              input_package='inputs.zip', input_sha256='a' * 64)
    assert commands[0][1:3] == ['scripts/rev1/package_inputs.py', '--verify']
    assert commands[0][commands[0].index('--expected-sha256') + 1] == 'a' * 64
    ablation = next(c for c in commands if 'src.analytics.ablation_study' in c)
    sweep = next(c for c in commands if 'src.analytics.benchmark.benchmark_algorithm.run_load_sweep' in c)
    assert ablation[ablation.index('--seeds') + 1:][:2] == ['42', '100']
    assert sweep[sweep.index('--seeds') + 1:][:2] == ['42', '100']
    assert 'data/input.csv' in ablation and 'models/main.zip' in sweep


def test_driver_stops_on_preflight_failure_without_running_experiments():
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        raise RuntimeError('preflight failed')
    with pytest.raises(RuntimeError, match='preflight'):
        run_commands([['python', 'check_artifacts.py'], ['python', '-m', 'experiment']], execute)
    assert len(calls) == 1


def test_evaluation_refuses_ablation_paths_that_could_select_unpinned_models(tmp_path):
    from scripts.rev1.phase_driver import validate_ablation_paths
    protocol = {'artifacts': [{'topology': 'vietnam', 'variant': 'harp_full',
                               'model_path': 'other/model.zip', 'normalizer_path': 'other/norm.pkl'}]}
    with pytest.raises(ValueError, match='ablation'):
        validate_ablation_paths(protocol, 'vietnam', tmp_path)


def test_main_benchmark_uses_same_explicit_protocol_seeds():
    from src.analytics.benchmark.benchmark_algorithm.config import AlgorithmBenchmarkConfig
    config = AlgorithmBenchmarkConfig(seed_override=(42, 100))
    assert config.seeds == [42, 100]
    protocol = {'dataset': {'path': 'data/input.csv'}, 'eval_seeds': [42, 100],
                'scenarios': ['chaos'], 'artifacts': [{'topology': 'vietnam', 'variant': 'main_v11',
                'model_path': 'models/main.zip', 'normalizer_path': 'models/norm.pkl'}]}
    commands = build_commands(protocol, 'vietnam', 'evaluate', 'results/rev1/run',
                              input_package='inputs.zip', input_sha256='a' * 64)
    benchmark = next(c for c in commands if 'src.analytics.benchmark.benchmark_algorithm.run_all' in c)
    assert benchmark[benchmark.index('--seeds') + 1:][:2] == ['42', '100']
    assert 'models/main.zip' in benchmark and 'models/norm.pkl' in benchmark


def test_benchmark_rejects_duplicate_or_conflicting_seed_options():
    from src.analytics.benchmark.benchmark_algorithm.config import AlgorithmBenchmarkConfig
    with pytest.raises(ValueError):
        AlgorithmBenchmarkConfig(seed_override=(42, 42))
    with pytest.raises(ValueError):
        AlgorithmBenchmarkConfig(single_seed=True, seed_override=(42, 100))


def test_training_plan_uses_explicit_independent_budgets_and_isolated_outputs():
    from scripts.rev1.phase_driver import build_training_commands
    protocol = {'dataset': {'path': 'data/input.csv'}}
    commands = build_training_commands(protocol, 'vietnam', 'results/rev1/train-1',
        seed=17, main_steps=800, ablation_steps=400, n_envs=2, rollout_steps=64, scenario='chaos')
    main, ablation = commands
    assert main[main.index('--total-steps') + 1] == '800'
    assert ablation[ablation.index('--total-steps') + 1] == '400'
    assert main[main.index('--seed') + 1] == ablation[ablation.index('--seed') + 1] == '17'
    assert main[main.index('--model-dir') + 1] == 'results/rev1/train-1/models/v11'
    assert ablation[ablation.index('--output-root') + 1] == 'results/rev1/train-1/models/ablation'


def test_training_plan_rejects_invalid_budgets_and_output_paths():
    from scripts.rev1.phase_driver import build_training_commands
    protocol = {'dataset': {'path': 'data/input.csv'}}
    with pytest.raises(ValueError):
        build_training_commands(protocol, 'vietnam', '../outside', seed=1, main_steps=10,
                                ablation_steps=10, n_envs=1, rollout_steps=2, scenario='chaos')
    with pytest.raises(ValueError):
        build_training_commands(protocol, 'vietnam', 'results/rev1/run', seed=1, main_steps=0,
                                ablation_steps=10, n_envs=1, rollout_steps=2, scenario='chaos')


def test_smoke_training_has_separate_output_and_small_explicit_budget():
    from scripts.rev1.phase_driver import build_training_commands
    protocol = {'dataset': {'path': 'data/input.csv'}}
    commands = build_training_commands(protocol, 'vietnam', 'results/rev1/smoke/check-1',
        seed=17, main_steps=512, ablation_steps=512, n_envs=1, rollout_steps=512,
        scenario='chaos', smoke=True)
    assert 'results/rev1/smoke/check-1/models/v11' in commands[0]
    with pytest.raises(ValueError, match='smoke budget'):
        build_training_commands(protocol, 'vietnam', 'results/rev1/smoke/check-2',
            seed=17, main_steps=3000, ablation_steps=512, n_envs=1, rollout_steps=512,
            scenario='chaos', smoke=True)


def test_audit_stage_builds_explicit_cross_topology_coverage_command():
    from scripts.rev1.phase_driver import build_audit_command
    command = build_audit_command(
        'results/rev1/evaluation.zip', 'a' * 64,
        {'vietnam': 'results/rev1/vietnam', 'nsfnet': 'results/rev1/nsfnet',
         'geant2': 'results/rev1/geant2'},
        steps=3000, output='results/rev1/coverage.json')
    assert command[:3] == [__import__('sys').executable, 'scripts/rev1/result_coverage.py',
                           '--input-package']
    assert command.count('--run') == 3
    assert 'vietnam=results/rev1/vietnam' in command
    assert command[command.index('--output') + 1] == 'results/rev1/coverage.json'


def test_audit_plan_does_not_require_external_resolved_protocol(monkeypatch, tmp_path, capsys):
    import sys
    from scripts.rev1 import phase_driver
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', [
        'phase_driver.py', '--stage', 'audit', '--input-package', 'inputs.zip',
        '--input-sha256', 'a' * 64, '--run', 'vietnam=v', '--run', 'nsfnet=n',
        '--run', 'geant2=g', '--steps', '3000', '--audit-output', 'coverage.json'])

    phase_driver.main()

    assert 'scripts/rev1/result_coverage.py' in capsys.readouterr().out


def test_checked_in_protocol_pre_registers_exactly_twenty_unique_evaluation_seeds():
    import json
    from pathlib import Path
    protocol = json.loads(Path('configs/rev1/protocol.json').read_text())
    assert protocol['eval_seeds'] == [
        42, 100, 2024, 8888, 9999, 7, 17, 73, 314, 2718,
        11, 23, 47, 89, 101, 211, 512, 1024, 4096, 8192,
    ]
    assert len(set(protocol['eval_seeds'])) == 20
