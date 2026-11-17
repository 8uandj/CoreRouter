import json
import zipfile
from pathlib import Path
import pytest
from scripts.rev1.package_inputs import build_package, verify_package


def fixture_root(root):
    (root / 'src').mkdir()
    (root / 'src/main.py').write_text('print("research")\n')
    (root / 'src/env').mkdir()
    (root / 'src/env/secret.txt').write_text('excluded virtual environment')
    (root / 'data').mkdir()
    (root / 'data/input.csv').write_text('x\n1\n')
    (root / 'configs/rev1').mkdir(parents=True)
    path = root / 'configs/rev1/protocol.json'
    path.write_text(json.dumps({'protocol_id': 'test', 'source_paths': ['src'],
        'dataset': {'path': 'data/input.csv', 'sha256': None}, 'source_sha256': None,
        'artifacts': [{'model_path': 'results/model.zip', 'normalizer_path': 'results/norm.pkl'}]}))
    return path


def test_training_package_is_deterministic_and_records_missing_models(tmp_path):
    protocol = fixture_root(tmp_path)
    first, second = tmp_path / 'one.zip', tmp_path / 'two.zip'
    build_package(tmp_path, protocol, first, mode='training')
    build_package(tmp_path, protocol, second, mode='training')
    assert first.read_bytes() == second.read_bytes()
    manifest = verify_package(first)
    assert manifest['mode'] == 'training'
    assert len(manifest['missing_artifacts']) == 2
    assert 'src/env/secret.txt' not in manifest['files']
    with zipfile.ZipFile(first) as archive:
        resolved = json.loads(archive.read('CoreRouter/configs/rev1/protocol.resolved.json'))
    assert resolved['dataset']['sha256']
    assert resolved['source_sha256']


def test_evaluation_package_rejects_missing_checkpoints(tmp_path):
    protocol = fixture_root(tmp_path)
    with pytest.raises(FileNotFoundError, match='artifact'):
        build_package(tmp_path, protocol, tmp_path / 'eval.zip', mode='evaluation')
    assert not (tmp_path / 'eval.zip').exists()


def test_changed_archive_bytes_and_traversal_paths_are_rejected(tmp_path):
    protocol = fixture_root(tmp_path)
    target = tmp_path / 'one.zip'
    build_package(tmp_path, protocol, target, mode='training')
    with zipfile.ZipFile(target, 'a') as archive:
        archive.writestr('CoreRouter/src/unlisted.py', 'injected')
    with pytest.raises(ValueError, match='coverage'):
        verify_package(target)
    config = json.loads(protocol.read_text())
    config['dataset']['path'] = '../outside.csv'
    protocol.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='path'):
        build_package(tmp_path, protocol, tmp_path / 'bad.zip', mode='training')


def test_evaluation_bundle_pins_models_and_checker_hashes_same_source(tmp_path):
    from scripts.rev1.check_artifacts import sha256_paths
    protocol = fixture_root(tmp_path)
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results/model.zip').write_bytes(b'checkpoint fixture; packaging does not certify spaces')
    (tmp_path / 'results/norm.pkl').write_bytes(b'normalizer fixture')
    target = tmp_path / 'evaluation.zip'
    manifest = build_package(tmp_path, protocol, target, mode='evaluation')
    assert manifest['missing_artifacts'] == []
    with zipfile.ZipFile(target) as archive:
        resolved = json.loads(archive.read('CoreRouter/configs/rev1/protocol.resolved.json'))
    assert resolved['source_sha256'] == sha256_paths([tmp_path / 'src'], tmp_path)
    assert resolved['artifacts'][0]['model_sha256']
    assert 'results/model.zip' in manifest['files']


def test_pinned_input_changes_and_symlinks_are_rejected(tmp_path):
    protocol = fixture_root(tmp_path)
    config = json.loads(protocol.read_text())
    config['dataset']['sha256'] = '0' * 64
    protocol.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='dataset hash mismatch'):
        build_package(tmp_path, protocol, tmp_path / 'wrong.zip', mode='training')
    config['dataset']['sha256'] = None
    protocol.write_text(json.dumps(config))
    (tmp_path / 'src/link.py').symlink_to(tmp_path / 'data/input.csv')
    with pytest.raises(ValueError, match='symlink'):
        build_package(tmp_path, protocol, tmp_path / 'linked.zip', mode='training')


def test_evaluation_archive_requires_nonempty_artifact_hashes(tmp_path):
    import hashlib
    protocol = fixture_root(tmp_path)
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results/model.zip').write_bytes(b'model')
    (tmp_path / 'results/norm.pkl').write_bytes(b'normalizer')
    target = tmp_path / 'eval.zip'
    build_package(tmp_path, protocol, target, mode='evaluation')
    with zipfile.ZipFile(target) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    key = 'CoreRouter/configs/rev1/protocol.resolved.json'
    resolved = json.loads(entries[key])
    resolved['artifacts'][0]['model_sha256'] = None
    entries[key] = json.dumps(resolved).encode()
    manifest_key = 'CoreRouter/package_manifest.json'
    manifest = json.loads(entries[manifest_key])
    manifest['files']['configs/rev1/protocol.resolved.json'] = hashlib.sha256(entries[key]).hexdigest()
    entries[manifest_key] = json.dumps(manifest).encode()
    with zipfile.ZipFile(target, 'w') as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    with pytest.raises(ValueError, match='hash'):
        verify_package(target)


def test_evaluation_bundle_can_take_models_from_explicit_training_run(tmp_path):
    protocol = fixture_root(tmp_path)
    config = json.loads(protocol.read_text())
    config['artifacts'] = [{'topology': 'vietnam', 'model_path': 'results/models/v11/main.zip',
                            'normalizer_path': 'results/models/v11/norm.pkl'}]
    protocol.write_text(json.dumps(config))
    trained = tmp_path / 'results/rev1/run-a/models/v11'
    trained.mkdir(parents=True)
    (trained / 'main.zip').write_bytes(b'newly trained model')
    (trained / 'norm.pkl').write_bytes(b'new normalizer')
    from scripts.rev1.bundle_hashes import sha256_file, sha256_paths
    plan = {'stage': 'new_training', 'topology': 'vietnam', 'protocol': {
        'source_sha256': sha256_paths([tmp_path / 'src'], tmp_path),
        'dataset': {'sha256': sha256_file(tmp_path / 'data/input.csv')}}}
    (trained.parent.parent / 'training_plan.json').write_text(json.dumps(plan))
    target = tmp_path / 'evaluation.zip'
    build_package(tmp_path, protocol, target, mode='evaluation',
                  training_runs={'vietnam': 'results/rev1/run-a'})
    with zipfile.ZipFile(target) as archive:
        assert archive.read('CoreRouter/results/models/v11/main.zip') == b'newly trained model'
    assert verify_package(target)['mode'] == 'evaluation'
    assert not (tmp_path / 'results/models').exists()


def test_evaluation_rejects_training_run_from_different_source(tmp_path):
    protocol = fixture_root(tmp_path)
    config = json.loads(protocol.read_text())
    config['artifacts'] = [{'topology': 'vietnam', 'model_path': 'results/models/v11/main.zip',
                            'normalizer_path': 'results/models/v11/norm.pkl'}]
    protocol.write_text(json.dumps(config))
    run = tmp_path / 'results/rev1/run-a'
    run.mkdir(parents=True)
    (run / 'training_plan.json').write_text(json.dumps({'stage': 'new_training', 'topology': 'vietnam',
        'protocol': {'source_sha256': '0' * 64, 'dataset': {'sha256': '0' * 64}}}))
    with pytest.raises(ValueError, match='training.*source'):
        build_package(tmp_path, protocol, tmp_path / 'evaluation.zip', mode='evaluation',
                      training_runs={'vietnam': 'results/rev1/run-a'})


def test_execution_protocol_must_match_pinned_archive_protocol(tmp_path):
    from scripts.rev1.package_inputs import verify_protocol_matches
    bundle = tmp_path / 'inputs.zip'
    protocol = tmp_path / 'protocol.resolved.json'
    protocol.write_text('{"protocol_id":"different"}')
    with zipfile.ZipFile(bundle, 'w') as archive:
        archive.writestr('CoreRouter/configs/rev1/protocol.resolved.json', '{"protocol_id":"pinned"}')
    with pytest.raises(ValueError, match='does not match packaged protocol'):
        verify_protocol_matches(bundle, protocol)


def test_smoke_only_checkpoints_cannot_be_packaged_for_evaluation(tmp_path):
    protocol = fixture_root(tmp_path)
    config = json.loads(protocol.read_text())
    config['artifacts'] = [{'topology': 'vietnam', 'model_path': 'results/models/v11/main.zip',
                            'normalizer_path': 'results/models/v11/norm.pkl'}]
    protocol.write_text(json.dumps(config))
    run = tmp_path / 'results/rev1/smoke/check-1'
    run.mkdir(parents=True)
    (run / 'training_plan.json').write_text(json.dumps({
        'stage': 'smoke_only', 'topology': 'vietnam', 'protocol': {
            'source_sha256': '0' * 64, 'dataset': {'sha256': '0' * 64}}}))
    with pytest.raises(ValueError, match='training plan source/dataset/topology mismatch'):
        build_package(tmp_path, protocol, tmp_path / 'evaluation.zip', mode='evaluation',
                      training_runs={'vietnam': 'results/rev1/smoke/check-1'})


def test_package_source_manifest_must_match_current_workspace(tmp_path):
    from scripts.rev1.package_inputs import verify_workspace_inputs
    protocol = fixture_root(tmp_path)
    target = tmp_path / 'training.zip'
    manifest = build_package(tmp_path, protocol, target, mode='training')
    verify_workspace_inputs(target, manifest, tmp_path)
    (tmp_path / 'src/main.py').write_text('changed after packaging\n')
    with pytest.raises(ValueError, match='workspace source hash mismatch'):
        verify_workspace_inputs(target, manifest, tmp_path)
