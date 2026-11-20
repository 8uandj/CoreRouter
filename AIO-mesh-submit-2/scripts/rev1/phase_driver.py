#!/usr/bin/env python3
"""Plan or execute explicit revision evaluation commands after artifact preflight."""
import argparse
import json
import importlib.metadata
import re
import subprocess
import sys
from pathlib import Path


def build_commands(protocol, topology, stage, output_dir, *, steps=3000,
                   protocol_path='configs/rev1/protocol.resolved.json',
                   input_package=None, input_sha256=None):
    if stage != 'evaluate':
        raise ValueError('unsupported stage')
    if not input_package or not isinstance(input_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', input_sha256):
        raise ValueError('evaluation requires an input package and its external SHA-256')
    seeds = protocol.get('eval_seeds', [])
    scenarios = protocol.get('scenarios', [])
    if not seeds or len(set(seeds)) != len(seeds) or not scenarios or steps <= 0:
        raise ValueError('protocol needs unique seeds, scenarios and positive step count')
    artifacts = [a for a in protocol.get('artifacts', [])
                 if a.get('topology') == topology and a.get('variant') == 'main_v11']
    if len(artifacts) != 1:
        raise ValueError('exactly one main checkpoint per topology is required')
    artifact = artifacts[0]
    data = protocol['dataset']['path']
    output = Path(output_dir)
    commands = [[sys.executable, 'scripts/rev1/package_inputs.py', '--verify', str(input_package),
                 '--expected-sha256', input_sha256, '--expected-mode', 'evaluation',
                 '--execution-protocol', protocol_path],
                [sys.executable, 'scripts/rev1/check_artifacts.py', '--protocol', protocol_path,
                 '--output', str(output / 'preflight.json')]]
    for scenario in scenarios:
        commands.append([sys.executable, '-m', 'src.analytics.ablation_study', '--topology', topology,
                         '--scenario', scenario, '--steps', str(steps), '--seeds', *map(str, seeds),
                         '--data-path', data, '--output-dir', str(output / 'ablation' / scenario)])
        commands.append([sys.executable, '-m', 'src.analytics.benchmark.benchmark_algorithm.run_all',
                         '--topology', topology, '--scenario', scenario, '--steps', str(steps),
                         '--seeds', *map(str, seeds), '--data-path', data,
                         '--model-path', artifact['model_path'], '--normalizer-path', artifact['normalizer_path'],
                         '--output-dir', str(output / 'benchmark' / scenario)])
    commands.append([sys.executable, '-m', 'src.analytics.benchmark.benchmark_algorithm.run_load_sweep',
                     '--topology', topology, '--steps', str(steps), '--seeds', *map(str, seeds),
                     '--data-path', data, '--model-path', artifact['model_path'],
                     '--normalizer-path', artifact['normalizer_path'],
                     '--output-dir', str(output / 'load_sweep')])
    return commands


def build_training_commands(protocol, topology, output_dir, *, seed, main_steps,
                            ablation_steps, n_envs, rollout_steps, scenario, smoke=False):
    output = Path(output_dir)
    prefix = ('results', 'rev1', 'smoke') if smoke else ('results', 'rev1')
    if (output.is_absolute() or '..' in output.parts or output.parts[:len(prefix)] != prefix
            or len(output.parts) < len(prefix) + 1):
        raise ValueError('training output must use its isolated results/rev1 directory')
    if min(main_steps, ablation_steps, n_envs) <= 0 or rollout_steps < 2:
        raise ValueError('training budgets/env count must be positive and rollout steps >= 2')
    if smoke and max(main_steps, ablation_steps) > 1024:
        raise ValueError('smoke budget must not exceed 1024 steps per trainer')
    if scenario not in {'uniform', 'bursty', 'heavy_tail', 'chaos'}:
        raise ValueError('unsupported training scenario')
    data = protocol['dataset']['path']
    return [
        [sys.executable, '-m', 'src.analytics.training.train_v11', '--topology', topology,
         '--total-steps', str(main_steps), '--n-envs', str(n_envs), '--rollout-steps', str(rollout_steps),
         '--seed', str(seed), '--data-path', data, '--model-dir', str(output / 'models/v11')],
        [sys.executable, '-m', 'src.analytics.training.train_harp_ablation', '--topology', topology,
         '--variant', 'all', '--scenario', scenario, '--total-steps', str(ablation_steps),
         '--n-envs', str(n_envs), '--seed', str(seed), '--data-path', data,
         '--output-root', str(output / 'models/ablation')],
    ]


def build_audit_command(input_package, input_sha256, run_paths, *, steps, output):
    if not re.fullmatch(r'[0-9a-f]{64}', input_sha256):
        raise ValueError('input package SHA-256 must be a lowercase 64-character digest')
    expected = {'vietnam', 'nsfnet', 'geant2'}
    if set(run_paths) != expected:
        raise ValueError('audit requires exactly one result directory for each protocol topology')
    if steps <= 0:
        raise ValueError('audit steps must be positive')
    command = [sys.executable, 'scripts/rev1/result_coverage.py',
               '--input-package', str(input_package), '--input-sha256', input_sha256]
    for topology in ('vietnam', 'nsfnet', 'geant2'):
        command.extend(['--run', f'{topology}={run_paths[topology]}'])
    command.extend(['--steps', str(steps), '--output', str(output)])
    return command


def verify_training_inputs(protocol, root):
    try:
        from .bundle_hashes import sha256_file, sha256_paths
        from .package_inputs import relative_path
    except ImportError:
        from bundle_hashes import sha256_file, sha256_paths
        from package_inputs import relative_path
    root = Path(root).resolve()
    source_pin = protocol.get('source_sha256')
    data_pin = protocol.get('dataset', {}).get('sha256')
    if not all(isinstance(x, str) and re.fullmatch(r'[0-9a-f]{64}', x) for x in (source_pin, data_pin)):
        raise ValueError('training requires resolved source and dataset hashes')
    source = [relative_path(root, name) for name in protocol['source_paths']]
    if sha256_paths(source, root) != source_pin or sha256_file(relative_path(root, protocol['dataset']['path'])) != data_pin:
        raise ValueError('training source or dataset hash mismatch')
    for name, expected in protocol.get('runtime_versions', {}).items():
        if importlib.metadata.version(name) != expected:
            raise ValueError(f'training dependency version mismatch: {name}')


def validate_ablation_paths(protocol, topology, root):
    """Require the evaluator's first-choice paths to equal the pinned protocol."""
    keys = {'harp_full', 'harp_wo_gat', 'harp_wo_hard_masking',
            'harp_soft_msd_penalty', 'harp_wo_adaptive_penalty'}
    rows = [a for a in protocol.get('artifacts', [])
            if a.get('topology') == topology and a.get('variant') in keys]
    if len(rows) != len(keys) or {a['variant'] for a in rows} != keys:
        raise ValueError('ablation protocol lacks a unique checkpoint for each variant')
    for row in rows:
        key = row['variant']
        base = Path('results/models/ablation') / key
        model = base / f'dgrl_v11_{key}_{topology}.zip'
        normalizer = base / f'vec_normalize_v11_{key}_{topology}.pkl'
        if Path(row['model_path']) != model or Path(row['normalizer_path']) != normalizer:
            raise ValueError(f'ablation path for {key} differs from evaluator resolution')
        for shadow in (base / f'{key}_{topology}.zip', base / f'{key}_vec_normalize_{topology}.pkl'):
            if (Path(root) / shadow).exists():
                raise ValueError(f'ablation checkpoint shadowed by {shadow}')


def run_commands(commands, runner=subprocess.run):
    for command in commands:
        runner(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', default='configs/rev1/protocol.resolved.json')
    parser.add_argument('--topology', choices=['vietnam', 'nsfnet', 'geant2'])
    parser.add_argument('--output-dir')
    parser.add_argument('--stage', choices=['train', 'smoke', 'evaluate', 'audit'], default='evaluate')
    parser.add_argument('--input-package')
    parser.add_argument('--input-sha256')
    parser.add_argument('--run', action='append', default=[], metavar='TOPOLOGY=RESULT_DIR')
    parser.add_argument('--audit-output')
    parser.add_argument('--steps', type=int, default=3000)
    parser.add_argument('--train-seed', type=int)
    parser.add_argument('--main-steps', type=int)
    parser.add_argument('--ablation-steps', type=int)
    parser.add_argument('--n-envs', type=int)
    parser.add_argument('--rollout-steps', type=int)
    parser.add_argument('--train-scenario', choices=['uniform', 'bursty', 'heavy_tail', 'chaos'])
    parser.add_argument('--execute', action='store_true', help='Execute commands; default prints the plan only')
    args = parser.parse_args()
    protocol = {} if args.stage == 'audit' else json.loads(Path(args.protocol).read_text())
    if args.stage == 'audit':
        if not args.input_package or not args.input_sha256 or not args.audit_output:
            parser.error('audit requires --input-package, --input-sha256 and --audit-output')
        run_paths = {}
        for item in args.run:
            topology, separator, path = item.partition('=')
            if not separator or topology not in {'vietnam', 'nsfnet', 'geant2'} or not path or topology in run_paths:
                parser.error('--run must specify each unique topology as TOPOLOGY=RESULT_DIR')
            run_paths[topology] = path
        commands = [build_audit_command(args.input_package, args.input_sha256, run_paths,
                                        steps=args.steps, output=args.audit_output)]
    elif args.stage in {'train', 'smoke'}:
        if not args.topology or not args.output_dir:
            parser.error('train/smoke requires --topology and --output-dir')
        values = (args.train_seed, args.main_steps, args.ablation_steps, args.n_envs,
                  args.rollout_steps, args.train_scenario)
        if any(value is None for value in values):
            parser.error('train requires explicit seed, budgets, env count, rollout steps and scenario')
        commands = build_training_commands(protocol, args.topology, args.output_dir,
            seed=args.train_seed, main_steps=args.main_steps, ablation_steps=args.ablation_steps,
            n_envs=args.n_envs, rollout_steps=args.rollout_steps, scenario=args.train_scenario,
            smoke=args.stage == 'smoke')
    else:
        if not args.topology or not args.output_dir or not args.input_package or not args.input_sha256:
            parser.error('evaluate requires --topology, --output-dir, --input-package and --input-sha256')
        commands = build_commands(protocol, args.topology, 'evaluate', args.output_dir,
                                  steps=args.steps, protocol_path=args.protocol,
                                  input_package=args.input_package, input_sha256=args.input_sha256)
    print(json.dumps({'stage': args.stage, 'execute': args.execute, 'commands': commands}, indent=2), flush=True)
    if args.execute:
        if args.stage in {'train', 'smoke'}:
            verify_training_inputs(protocol, Path.cwd())
            output = Path(args.output_dir)
            allowed_root = (Path.cwd() / 'results/rev1').resolve()
            if not output.resolve().is_relative_to(allowed_root):
                raise ValueError('training output resolves outside results/rev1')
            output.mkdir(parents=True, exist_ok=False)
            with (output / 'training_plan.json').open('x') as handle:
                stage_name = 'smoke_only' if args.stage == 'smoke' else 'new_training'
                json.dump({'stage': stage_name, 'topology': args.topology,
                           'protocol': protocol, 'commands': commands}, handle, indent=2)
        elif args.stage == 'evaluate':
            validate_ablation_paths(protocol, args.topology, Path.cwd())
        run_commands(commands)


if __name__ == '__main__':
    main()
