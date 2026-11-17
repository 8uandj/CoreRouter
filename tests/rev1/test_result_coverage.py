import pytest
from scripts.rev1.result_coverage import validate_matrix


def rows():
    return [{'topology': 'vietnam', 'scenario': 'chaos', 'seed': seed, 'key': key,
             'trace_steps': 10, 'trace_sha256': ('a' if seed == 1 else 'b') * 64}
            for seed in (1, 2) for key in ('full', 'baseline')]


def test_complete_matrix_requires_matching_trace_per_seed():
    validate_matrix(rows(), topology='vietnam', scenario='chaos', seeds=[1, 2],
                    policies=['full', 'baseline'], steps=10, policy_field='key')


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'wrong_trace', 'wrong_steps', 'wrong_topology'])
def test_invalid_matrix_is_rejected(mutation):
    data = rows()
    if mutation == 'missing': data.pop()
    elif mutation == 'duplicate': data.append(dict(data[0]))
    elif mutation == 'wrong_trace': data[1]['trace_sha256'] = 'c' * 64
    elif mutation == 'wrong_steps': data[0]['trace_steps'] = 9
    else: data[0]['topology'] = 'other'
    with pytest.raises(ValueError):
        validate_matrix(data, topology='vietnam', scenario='chaos', seeds=[1, 2],
                        policies=['full', 'baseline'], steps=10, policy_field='key')


def test_zero_offered_requests_are_not_accepted_as_valid_results():
    data = rows()
    for row in data:
        row['requests'] = 1
    data[0]['requests'] = 0
    with pytest.raises(ValueError, match='zero offered'):
        validate_matrix(data, topology='vietnam', scenario='chaos', seeds=[1, 2],
                        policies=['full', 'baseline'], steps=10, policy_field='key',
                        request_field='requests')


def test_ablation_manifest_rejects_wrong_model_hash():
    from scripts.rev1.result_coverage import validate_ablation_manifest
    protocol = {'dataset': {'sha256': 'd' * 64}, 'artifacts': [
        {'topology': 'vietnam', 'variant': 'harp_full', 'model_sha256': 'a' * 64,
         'normalizer_sha256': 'b' * 64}]}
    manifest = {'protocol': 'ablation-v3', 'topology': 'vietnam', 'scenario': 'chaos',
                'seeds': [1], 'steps': 10, 'data_sha256': 'd' * 64,
                'artifacts': {'harp_full': {'model_sha256': 'c' * 64, 'normalizer_sha256': 'b' * 64}}}
    with pytest.raises(ValueError, match='artifact'):
        validate_ablation_manifest(manifest, protocol, 'vietnam', 'chaos', [1], 10,
                                   {'harp_full': 'harp_full'})


def test_ablation_directory_requires_csv_and_matching_manifest(tmp_path):
    import csv
    import json
    from scripts.rev1.result_coverage import audit_ablation_directory
    data = rows()
    data = [row for row in data if row['key'] == 'full']
    for row in data:
        row['steps'] = 10
    with (tmp_path / 'harp_ablation_summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=data[0])
        writer.writeheader()
        writer.writerows(data)
    protocol = {'dataset': {'sha256': 'd' * 64}, 'artifacts': [
        {'topology': 'vietnam', 'variant': 'model', 'model_sha256': 'a' * 64,
         'normalizer_sha256': 'b' * 64}]}
    manifest = {'protocol': 'ablation-v3', 'topology': 'vietnam', 'scenario': 'chaos',
        'seeds': [1, 2], 'steps': 10, 'data_sha256': 'd' * 64,
        'artifacts': {'full': {'model_sha256': 'a' * 64, 'normalizer_sha256': 'b' * 64}}}
    (tmp_path / 'run_manifest.json').write_text(json.dumps(manifest))
    result = audit_ablation_directory(tmp_path, protocol, 'vietnam', 'chaos', [1, 2], 10,
                                       {'full': 'model'})
    assert result['rows'] == 2
    (tmp_path / 'run_manifest.json').unlink()
    with pytest.raises(FileNotFoundError):
        audit_ablation_directory(tmp_path, protocol, 'vietnam', 'chaos', [1, 2], 10,
                                 {'full': 'model'})


@pytest.mark.parametrize('kind', ['benchmark', 'load_sweep'])
def test_main_result_manifest_requires_same_dataset_seeds_and_model(kind):
    from scripts.rev1.result_coverage import validate_main_manifest
    model = {'topology': 'vietnam', 'variant': 'main_v11',
             'model_sha256': 'a' * 64, 'normalizer_sha256': 'b' * 64}
    protocol = {'dataset': {'sha256': 'd' * 64}, 'artifacts': [model]}
    manifest = {'protocol': 'benchmark-v2' if kind == 'benchmark' else 'protected-load-sweep-v2',
                'seeds': [1, 2], 'steps': 10, 'data_sha256': 'd' * 64}
    if kind == 'benchmark':
        manifest.update(topologies=['vietnam'], artifacts={'vietnam': model})
    else:
        manifest.update(topology='vietnam', model_sha256='a' * 64, normalizer_sha256='b' * 64)
    validate_main_manifest(manifest, protocol, kind, 'vietnam', [1, 2], 10)
    manifest['seeds'] = [1]
    with pytest.raises(ValueError):
        validate_main_manifest(manifest, protocol, kind, 'vietnam', [1, 2], 10)
    manifest['seeds'] = [1, 2]
    if kind == 'benchmark': manifest['artifacts']['vietnam'] = {'model_sha256': 'c' * 64, 'normalizer_sha256': 'b' * 64}
    else: manifest['model_sha256'] = 'c' * 64
    with pytest.raises(ValueError, match='artifact'):
        validate_main_manifest(manifest, protocol, kind, 'vietnam', [1, 2], 10)


def test_benchmark_directory_checks_manifest_and_policy_rows(tmp_path):
    import csv
    import json
    from scripts.rev1.result_coverage import audit_benchmark_directory
    model = {'topology': 'vietnam', 'variant': 'main_v11', 'model_sha256': 'a' * 64,
             'normalizer_sha256': 'b' * 64}
    protocol = {'dataset': {'sha256': 'd' * 64}, 'artifacts': [model]}
    manifest = {'protocol': 'benchmark-v2', 'topologies': ['vietnam'], 'seeds': [1, 2],
                'steps': 10, 'data_sha256': 'd' * 64, 'artifacts': {'vietnam': model},
                'scenario_jobs': [['chaos', 'chaos', 'stress']]}
    (tmp_path / 'run_manifest.json').write_text(json.dumps(manifest))
    directory = tmp_path / 'vietnam_chaos_stress'
    directory.mkdir()
    data = [{**row, 'algorithm': row['key'], 'requests': 1} for row in rows()]
    with (directory / 'seed_summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=data[0]); writer.writeheader(); writer.writerows(data)
    result = audit_benchmark_directory(tmp_path, protocol, 'vietnam', 'chaos', [1, 2], 10,
                                       ['full', 'baseline'])
    assert result['rows'] == 4
    manifest['scenario_jobs'] = [['uniform', 'uniform', 'stress']]
    (tmp_path / 'run_manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='scenario'):
        audit_benchmark_directory(tmp_path, protocol, 'vietnam', 'chaos', [1, 2], 10,
                                  ['full', 'baseline'])


def test_load_sweep_directory_requires_every_load_policy_and_seed(tmp_path):
    import csv
    import json
    from scripts.rev1.result_coverage import audit_load_sweep_directory
    model = {'topology': 'vietnam', 'variant': 'main_v11', 'model_sha256': 'a' * 64,
             'normalizer_sha256': 'b' * 64}
    protocol = {'dataset': {'sha256': 'd' * 64}, 'artifacts': [model]}
    manifest = {'protocol': 'protected-load-sweep-v2', 'topology': 'vietnam',
                'seeds': [1, 2], 'steps': 10, 'data_sha256': 'd' * 64,
                'model_sha256': 'a' * 64, 'normalizer_sha256': 'b' * 64,
                'loads': [0.2, 0.4], 'policies': ['full', 'baseline']}
    (tmp_path / 'vietnam_load_sweep_manifest.json').write_text(json.dumps(manifest))
    data = [{**row, 'scenario': f'load_{load:.1f}', 'load_multiplier': load,
             'algorithm': row['key'], 'requests': 1} for load in (0.2, 0.4) for row in rows()]
    path = tmp_path / 'vietnam_load_sweep_per_seed.csv'
    def write(records):
        with path.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=data[0]); writer.writeheader(); writer.writerows(records)
    write(data)
    result = audit_load_sweep_directory(tmp_path, protocol, 'vietnam', [1, 2], 10,
                                        [0.2, 0.4], ['full', 'baseline'])
    assert result['rows'] == 8
    write(data[:-1])
    with pytest.raises(ValueError, match='incomplete'):
        audit_load_sweep_directory(tmp_path, protocol, 'vietnam', [1, 2], 10,
                                   [0.2, 0.4], ['full', 'baseline'])


def test_result_source_manifest_must_match_pinned_package_sources():
    from scripts.rev1.result_coverage import validate_source_provenance
    package = {'source_files': ['src/a.py', 'src/b.py'],
               'files': {'src/a.py': 'a' * 64, 'src/b.py': 'b' * 64}}
    manifest = {'source_sha256': {'/kaggle/working/CoreRouter/src/a.py': 'a' * 64,
                                 '/kaggle/working/CoreRouter/src/b.py': 'b' * 64}}
    validate_source_provenance(manifest, package, ['src/a.py', 'src/b.py'])
    manifest['source_sha256']['/kaggle/working/CoreRouter/src/b.py'] = 'c' * 64
    with pytest.raises(ValueError, match='source'):
        validate_source_provenance(manifest, package, ['src/a.py', 'src/b.py'])
    manifest['source_sha256'].pop('/kaggle/working/CoreRouter/src/b.py')
    with pytest.raises(ValueError, match='source'):
        validate_source_provenance(manifest, package, ['src/a.py', 'src/b.py'])


def test_cross_topology_audit_rejects_missing_topology(tmp_path):
    from scripts.rev1.result_coverage import audit_revision_runs
    protocol = {'eval_seeds': [1], 'scenarios': ['chaos'], 'artifacts': [
        {'topology': name, 'variant': 'main_v11'} for name in ('vietnam', 'nsfnet', 'geant2')]}
    with pytest.raises(ValueError, match='topology'):
        audit_revision_runs(protocol, {}, {'vietnam': tmp_path}, steps=10)


def test_cross_topology_audit_visits_all_scenarios_and_pinned_sources(tmp_path, monkeypatch):
    import json
    from scripts.rev1 import result_coverage as coverage
    topologies = ['vietnam', 'nsfnet', 'geant2']
    scenarios = ['uniform', 'chaos']
    protocol = {'eval_seeds': [1], 'scenarios': scenarios, 'artifacts': [
        {'topology': name, 'variant': 'main_v11'} for name in topologies]}
    required = set(coverage.ABLATION_SOURCE + coverage.BENCHMARK_SOURCE + coverage.SWEEP_SOURCE)
    package = {'source_files': sorted(required), 'files': {name: 'a' * 64 for name in required}}
    manifest = {'source_sha256': {f'/workspace/{name}': 'a' * 64 for name in required}}
    paths = {}
    for topology in topologies:
        base = paths[topology] = tmp_path / topology
        for scenario in scenarios:
            ablation = base / 'ablation' / scenario / topology / scenario
            benchmark = base / 'benchmark' / scenario / 'one-run'
            ablation.mkdir(parents=True); benchmark.mkdir(parents=True)
            for directory in (ablation, benchmark):
                (directory / 'run_manifest.json').write_text(json.dumps(manifest))
        sweep = base / 'load_sweep'
        sweep.mkdir(parents=True)
        (sweep / f'{topology}_load_sweep_manifest.json').write_text(json.dumps(manifest))
    calls = []
    for function in ('audit_ablation_directory', 'audit_benchmark_directory', 'audit_load_sweep_directory'):
        monkeypatch.setattr(coverage, function, lambda *args, _function=function: calls.append(_function) or {'rows': 1})
    report = coverage.audit_revision_runs(protocol, package, paths, steps=3000)
    assert len(report) == 15
    assert calls.count('audit_ablation_directory') == calls.count('audit_benchmark_directory') == 6
    assert calls.count('audit_load_sweep_directory') == 3
    broken = paths['vietnam'] / 'ablation' / 'chaos' / 'vietnam' / 'chaos' / 'run_manifest.json'
    broken.write_text(json.dumps({'source_sha256': {}}))
    with pytest.raises(ValueError, match='source'):
        coverage.audit_revision_runs(protocol, package, paths, steps=3000)
