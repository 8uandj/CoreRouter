"""Validate one policy-by-seed result matrix without manufacturing missing rows."""
import re


def validate_matrix(rows, *, topology, scenario, seeds, policies, steps, policy_field,
                    request_field=None):
    if not seeds or not policies or steps <= 0 or len(set(seeds)) != len(seeds) or len(set(policies)) != len(policies):
        raise ValueError('expected seeds, policies and steps must be unique and nonempty')
    expected = {(str(policy), int(seed)) for policy in policies for seed in seeds}
    seen = set()
    traces = {}
    for row in rows:
        try:
            key = (str(row[policy_field]), int(row['seed']))
            trace_steps = int(row['trace_steps'])
            trace_hash = row['trace_sha256']
            if request_field is not None and int(row[request_field]) <= 0:
                raise ValueError('zero offered requests')
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'invalid result row: {exc}') from exc
        if row.get('topology') != topology or row.get('scenario') != scenario:
            raise ValueError('unexpected topology or scenario')
        if key in seen or key not in expected:
            raise ValueError(f'duplicate or unexpected policy/seed: {key}')
        if trace_steps != steps or not isinstance(trace_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', trace_hash):
            raise ValueError(f'invalid trace for policy/seed: {key}')
        seen.add(key)
        traces.setdefault(key[1], set()).add(trace_hash)
    if seen != expected:
        raise ValueError(f'incomplete result matrix: missing={sorted(expected - seen)}')
    if any(len(hashes) != 1 for hashes in traces.values()):
        raise ValueError('offered trace mismatch between policies')
    return {'topology': topology, 'scenario': scenario, 'seeds': len(seeds),
            'policies': len(policies), 'rows': len(seen), 'trace_steps': steps}


def validate_ablation_manifest(manifest, protocol, topology, scenario, seeds, steps, variant_models):
    if (manifest.get('protocol') != 'ablation-v3' or manifest.get('topology') != topology
            or manifest.get('scenario') != scenario or manifest.get('seeds') != seeds
            or manifest.get('steps') != steps or not protocol.get('dataset', {}).get('sha256')
            or manifest.get('data_sha256') != protocol['dataset']['sha256']):
        raise ValueError('ablation manifest protocol, workload or data mismatch')
    actual = manifest.get('artifacts', {})
    if set(actual) != set(variant_models):
        raise ValueError('ablation artifact coverage mismatch')
    for variant, model_key in variant_models.items():
        matches = [item for item in protocol.get('artifacts', [])
                   if item.get('topology') == topology and item.get('variant') == model_key]
        if len(matches) != 1:
            raise ValueError(f'ablation artifact protocol missing or duplicated: {model_key}')
        for field in ('model_sha256', 'normalizer_sha256'):
            expected = matches[0].get(field)
            if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected) or actual[variant].get(field) != expected:
                raise ValueError(f'ablation artifact hash mismatch: {variant} {field}')


def audit_ablation_directory(directory, protocol, topology, scenario, seeds, steps, variant_models):
    """Check one ablation CSV and manifest; this does not certify scientific validity."""
    import csv
    import json
    from pathlib import Path
    directory = Path(directory)
    manifest = json.loads((directory / 'run_manifest.json').read_text())
    validate_ablation_manifest(manifest, protocol, topology, scenario, seeds, steps, variant_models)
    with (directory / 'harp_ablation_summary.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    return validate_matrix(rows, topology=topology, scenario=scenario, seeds=seeds,
                           policies=list(variant_models), steps=steps, policy_field='key',
                           request_field='steps')


def validate_main_manifest(manifest, protocol, kind, topology, seeds, steps):
    versions = {'benchmark': 'benchmark-v2', 'load_sweep': 'protected-load-sweep-v2'}
    if kind not in versions:
        raise ValueError('unsupported main result type')
    correct_topology = (manifest.get('topologies') == [topology] if kind == 'benchmark'
                        else manifest.get('topology') == topology)
    dataset_hash = protocol.get('dataset', {}).get('sha256')
    if (manifest.get('protocol') != versions[kind] or not correct_topology
            or manifest.get('seeds') != seeds or manifest.get('steps') != steps
            or not isinstance(dataset_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', dataset_hash)
            or manifest.get('data_sha256') != dataset_hash):
        raise ValueError('main result manifest workload or data mismatch')
    matches = [item for item in protocol.get('artifacts', [])
               if item.get('topology') == topology and item.get('variant') == 'main_v11']
    if len(matches) != 1:
        raise ValueError('main artifact protocol missing or duplicated')
    actual = manifest.get('artifacts', {}).get(topology, {}) if kind == 'benchmark' else manifest
    for field in ('model_sha256', 'normalizer_sha256'):
        expected = matches[0].get(field)
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected) or actual.get(field) != expected:
            raise ValueError(f'main artifact hash mismatch: {field}')


def audit_benchmark_directory(directory, protocol, topology, scenario, seeds, steps, policies):
    """Check a single scenario's benchmark manifest and seed summary."""
    import csv
    import json
    from pathlib import Path
    directory = Path(directory)
    manifest = json.loads((directory / 'run_manifest.json').read_text())
    validate_main_manifest(manifest, protocol, 'benchmark', topology, seeds, steps)
    if manifest.get('scenario_jobs') != [[scenario, scenario, 'stress']]:
        raise ValueError('benchmark scenario or load mismatch')
    summary = directory / f'{topology}_{scenario}_stress' / 'seed_summary.csv'
    with summary.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    return validate_matrix(rows, topology=topology, scenario=scenario, seeds=seeds,
                           policies=policies, steps=steps, policy_field='algorithm',
                           request_field='requests')


def audit_load_sweep_directory(directory, protocol, topology, seeds, steps, loads, policies):
    """Validate the complete load × policy × seed matrix for one topology."""
    import csv
    import json
    import math
    from pathlib import Path
    directory = Path(directory)
    manifest = json.loads((directory / f'{topology}_load_sweep_manifest.json').read_text())
    validate_main_manifest(manifest, protocol, 'load_sweep', topology, seeds, steps)
    if not loads or len(set(loads)) != len(loads) or manifest.get('loads') != loads or manifest.get('policies') != policies:
        raise ValueError('load sweep workload or policy coverage mismatch')
    with (directory / f'{topology}_load_sweep_per_seed.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    groups = {load: [] for load in loads}
    for row in rows:
        try:
            load = float(row['load_multiplier'])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError('invalid load multiplier') from exc
        if not math.isfinite(load) or load not in groups:
            raise ValueError('unexpected load multiplier')
        groups[load].append(row)
    results = [validate_matrix(groups[load], topology=topology, scenario=f'load_{load:.1f}',
                               seeds=seeds, policies=policies, steps=steps,
                               policy_field='algorithm', request_field='requests') for load in loads]
    return {'topology': topology, 'loads': len(loads), 'rows': sum(item['rows'] for item in results)}


def validate_source_provenance(manifest, package_manifest, required_paths):
    """Match run-time source hashes to selected files in the pinned input package."""
    hashes = manifest.get('source_sha256')
    package_files = package_manifest.get('files', {})
    selected = package_manifest.get('source_files', [])
    if not isinstance(hashes, dict) or not required_paths or len(set(required_paths)) != len(required_paths):
        raise ValueError('missing or invalid source provenance')
    for relative in required_paths:
        matches = [value for name, value in hashes.items()
                   if isinstance(name, str) and (name == relative or name.endswith('/' + relative))]
        expected = package_files.get(relative)
        if (relative not in selected or len(matches) != 1 or not isinstance(expected, str)
                or not re.fullmatch(r'[0-9a-f]{64}', expected) or matches[0] != expected):
            raise ValueError(f'source provenance missing or mismatched: {relative}')


VARIANT_MODELS = {
    'harp_full': 'harp_full', 'harp_wo_gat': 'harp_wo_gat',
    'harp_wo_hard_masking': 'harp_wo_hard_masking',
    'harp_wo_mask_unchecked': 'harp_wo_hard_masking',
    'harp_soft_msd_penalty': 'harp_soft_msd_penalty',
    'harp_soft_msd_admission': 'harp_soft_msd_penalty',
    'harp_wo_adaptive_penalty': 'harp_wo_adaptive_penalty',
}
BASE_POLICIES = [f'{policy}_{mode}' for mode in ('protected', 'unprotected')
                 for policy in ('harp', 'saf_h', 'traditional_greedy', 'decoupled_ai')]
LOADS = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5]
COMMON_SOURCE = ['src/orchestration/jo_vdpr/env.py', 'src/orchestration/jo_vdpr/topology.py']
ABLATION_SOURCE = COMMON_SOURCE + ['src/analytics/ablation_study.py',
    'src/analytics/training/train_harp_ablation.py', 'src/orchestration/jo_vdpr/rewards.py']
BENCHMARK_SOURCE = COMMON_SOURCE + [f'src/analytics/benchmark/benchmark_algorithm/{name}.py'
    for name in ('run_all', 'algorithms', 'metrics', 'model_loader')]
SWEEP_SOURCE = COMMON_SOURCE + [f'src/analytics/benchmark/benchmark_algorithm/{name}.py'
    for name in ('run_load_sweep', 'algorithms', 'config')]


def audit_revision_runs(protocol, package_manifest, run_paths, *, steps):
    import json
    from pathlib import Path
    topology_rows = [item['topology'] for item in protocol.get('artifacts', [])
                     if item.get('variant') == 'main_v11']
    if len(topology_rows) != len(set(topology_rows)) or set(run_paths) != set(topology_rows) or not topology_rows:
        raise ValueError('run paths must cover every protocol topology exactly once')
    seeds, scenarios = protocol['eval_seeds'], protocol['scenarios']
    report = []
    for topology in topology_rows:
        base = Path(run_paths[topology])
        for scenario in scenarios:
            ablation = base / 'ablation' / scenario / topology / scenario
            benchmark_parent = base / 'benchmark' / scenario
            candidates = [p for p in benchmark_parent.iterdir() if p.is_dir() and (p / 'run_manifest.json').is_file()]
            if len(candidates) != 1:
                raise ValueError(f'benchmark run directory missing or ambiguous: {topology}/{scenario}')
            benchmark = candidates[0]
            policies = list(BASE_POLICIES)
            if steps <= 1000:
                policies.extend(['exhaustive_pair_search_protected', 'exhaustive_pair_search_unprotected'])
            for directory, required in ((ablation, ABLATION_SOURCE), (benchmark, BENCHMARK_SOURCE)):
                manifest = json.loads((directory / 'run_manifest.json').read_text())
                validate_source_provenance(manifest, package_manifest, required)
            report.append({'kind': 'ablation', **audit_ablation_directory(
                ablation, protocol, topology, scenario, seeds, steps, VARIANT_MODELS)})
            report.append({'kind': 'benchmark', **audit_benchmark_directory(
                benchmark, protocol, topology, scenario, seeds, steps, policies)})
        sweep = base / 'load_sweep'
        manifest = json.loads((sweep / f'{topology}_load_sweep_manifest.json').read_text())
        validate_source_provenance(manifest, package_manifest, SWEEP_SOURCE)
        report.append({'kind': 'load_sweep', **audit_load_sweep_directory(
            sweep, protocol, topology, seeds, steps, LOADS, BASE_POLICIES)})
    return report


def main():
    import argparse
    import json
    import zipfile
    from pathlib import Path
    try:
        from .package_inputs import verify_package
    except ImportError:
        from package_inputs import verify_package
    parser = argparse.ArgumentParser(description='Audit completed revision result matrices against a pinned input package')
    parser.add_argument('--input-package', required=True, type=Path)
    parser.add_argument('--input-sha256', required=True)
    parser.add_argument('--run', action='append', required=True, metavar='TOPOLOGY=RESULT_DIR')
    parser.add_argument('--steps', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{64}', args.input_sha256):
        parser.error('input SHA-256 must be a lowercase 64-character digest')
    manifest = verify_package(args.input_package, args.input_sha256)
    if manifest.get('mode') != 'evaluation':
        raise ValueError('result audit requires an evaluation input package')
    with zipfile.ZipFile(args.input_package) as archive:
        protocol = json.loads(archive.read('CoreRouter/configs/rev1/protocol.resolved.json'))
    runs = {}
    for item in args.run:
        topology, separator, path = item.partition('=')
        if not separator or not topology or not path or topology in runs:
            parser.error('each run must be a unique TOPOLOGY=RESULT_DIR')
        runs[topology] = Path(path)
    report = audit_revision_runs(protocol, manifest, runs, steps=args.steps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump({'status': 'coverage_and_lineage_checked', 'input_sha256': args.input_sha256,
                   'steps': args.steps, 'results': report}, handle, indent=2)
    print(f'Checked {len(report)} result groups; report: {args.output}')


if __name__ == '__main__':
    main()
