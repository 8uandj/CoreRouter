#!/usr/bin/env python3
"""Freeze exact revision inputs; training bundles never imply model readiness."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

try:
    from .bundle_hashes import selected_files, sha256_file, sha256_paths
except ImportError:
    from bundle_hashes import selected_files, sha256_file, sha256_paths


def relative_path(root, value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError(f'invalid package path: {value}')
    full = root / str(path)
    if any(parent.is_symlink() for parent in [full, *full.parents] if parent != root.parent):
        raise ValueError(f'symlink package path: {value}')
    if not full.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'package path escapes root: {value}')
    return full


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def check_pin(actual, expected, label):
    if expected is not None and actual != expected:
        raise ValueError(f'{label} hash mismatch')


def build_package(root, protocol_path, output, *, mode='evaluation', training_runs=None):
    root, protocol_path, output = Path(root).resolve(), Path(protocol_path).resolve(), Path(output).resolve()
    if mode not in {'training', 'evaluation'}:
        raise ValueError('mode must be training or evaluation')
    protocol = json.loads(protocol_path.read_text())
    source_paths = [relative_path(root, value) for value in protocol['source_paths']]
    if not source_paths:
        raise ValueError('source_paths must not be empty')
    if any(output == path or output.is_relative_to(path) for path in source_paths):
        raise ValueError('output path must be outside source inputs')
    sources = selected_files(source_paths, root)
    source_hash = sha256_paths(source_paths, root)
    check_pin(source_hash, protocol.get('source_sha256'), 'source')
    dataset = relative_path(root, protocol['dataset']['path'])
    if not dataset.is_file():
        raise FileNotFoundError(f'dataset missing: {dataset}')
    data_hash = sha256_file(dataset)
    check_pin(data_hash, protocol['dataset'].get('sha256'), 'dataset')
    files = dict(sources)
    files[dataset.relative_to(root).as_posix()] = dataset
    # Configuration and dependency files are covered by the full package manifest.
    config_dir = root / 'configs/rev1'
    if config_dir.is_dir():
        files.update(selected_files([config_dir], root))
    for name in ('requirements.txt', 'requirements-dev.txt'):
        if (root / name).is_file():
            files[name] = root / name
    missing, omitted = [], []
    training_runs = training_runs or {}
    if training_runs and mode != 'evaluation':
        raise ValueError('training run inputs are valid only for evaluation packages')
    if training_runs:
        topologies = {item.get('topology') for item in protocol.get('artifacts', [])}
        if set(training_runs) != topologies:
            raise ValueError('training runs must explicitly cover every protocol topology')
        for topology, run in training_runs.items():
            candidate = PurePosixPath(run)
            if candidate.parts[:2] != ('results', 'rev1') or len(candidate.parts) < 3:
                raise ValueError('training run path must be under results/rev1')
            relative_path(root, run)
            plan_path = relative_path(root, str(candidate / 'training_plan.json'))
            if not plan_path.is_file():
                raise FileNotFoundError(f'training plan missing: {plan_path}')
            plan = json.loads(plan_path.read_text())
            if (plan.get('stage') != 'new_training' or plan.get('topology') != topology
                    or plan.get('protocol', {}).get('source_sha256') != source_hash
                    or plan.get('protocol', {}).get('dataset', {}).get('sha256') != data_hash):
                raise ValueError(f'training plan source/dataset/topology mismatch: {topology}')
            files[f'provenance/training/{topology}.json'] = plan_path
    for artifact in protocol.get('artifacts', []):
        for field, hash_field in [('model_path', 'model_sha256'), ('normalizer_path', 'normalizer_sha256')]:
            target = relative_path(root, artifact[field])
            path = target
            if training_runs:
                try:
                    suffix = PurePosixPath(artifact[field]).relative_to('results/models')
                except ValueError as exc:
                    raise ValueError('artifact path must be under results/models') from exc
                path = relative_path(root, str(PurePosixPath(training_runs[artifact['topology']]) / 'models' / suffix))
            if mode == 'training':
                omitted.append(artifact[field])
                if not path.is_file():
                    missing.append(artifact[field])
                artifact[hash_field] = None
            else:
                if not path.is_file():
                    raise FileNotFoundError(f'evaluation artifact missing: {artifact[field]}')
                digest = sha256_file(path)
                check_pin(digest, artifact.get(hash_field), artifact[field])
                artifact[hash_field] = digest
                files[target.relative_to(root).as_posix()] = path
    protocol['source_sha256'] = source_hash
    protocol['dataset']['sha256'] = data_hash
    payloads = {name: path.read_bytes() for name, path in sorted(files.items())}
    digest = hashlib.sha256()
    for name in sources:
        digest.update(name.encode())
        digest.update(hashlib.sha256(payloads[name]).digest())
    if digest.hexdigest() != source_hash:
        raise RuntimeError('source changed while packaging; retry on a stable tree')
    if hashlib.sha256(payloads[dataset.relative_to(root).as_posix()]).hexdigest() != data_hash:
        raise RuntimeError('dataset changed while packaging; retry on a stable tree')
    payloads['configs/rev1/protocol.resolved.json'] = encoded(protocol)
    manifest = {'schema': 1, 'protocol_id': protocol['protocol_id'], 'mode': mode,
        'source_sha256': source_hash, 'source_files': list(sources), 'dataset_sha256': data_hash,
        'missing_artifacts': sorted(set(missing)), 'omitted_artifacts': sorted(set(omitted)),
        'training_runs': dict(sorted(training_runs.items())),
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payloads.items())}}
    payloads['package_manifest.json'] = encoded(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=output.parent, suffix='.zip.tmp')
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payloads.items()):
                info = zipfile.ZipInfo('CoreRouter/' + name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        verify_package(Path(temporary))
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return manifest


def verify_package(path, expected_sha256=None):
    if expected_sha256 is not None:
        check_pin(sha256_file(path), expected_sha256, 'archive')
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate package entry')
        for name in names:
            parts = PurePosixPath(name).parts
            if not parts or parts[0] != 'CoreRouter' or '..' in parts or '\\' in name:
                raise ValueError('unsafe package path')
        manifest = json.loads(archive.read('CoreRouter/package_manifest.json'))
        expected = {'CoreRouter/' + name for name in manifest['files']} | {'CoreRouter/package_manifest.json'}
        if set(names) != expected:
            raise ValueError('package coverage mismatch')
        for name, digest in manifest['files'].items():
            if hashlib.sha256(archive.read('CoreRouter/' + name)).hexdigest() != digest:
                raise ValueError(f'package file hash mismatch: {name}')
        resolved = json.loads(archive.read('CoreRouter/configs/rev1/protocol.resolved.json'))
        if manifest.get('schema') != 1 or manifest.get('mode') not in {'training', 'evaluation'}:
            raise ValueError('unsupported package schema or mode')
        if manifest.get('protocol_id') != resolved.get('protocol_id'):
            raise ValueError('package protocol identity mismatch')
        def require_hash(value):
            if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
                raise ValueError('resolved package requires a valid sha256 hash')
        require_hash(resolved.get('source_sha256'))
        require_hash(resolved['dataset'].get('sha256'))
        digest = hashlib.sha256()
        for name in sorted(manifest['source_files']):
            digest.update(name.encode())
            digest.update(bytes.fromhex(manifest['files'][name]))
        check_pin(digest.hexdigest(), resolved['source_sha256'], 'packaged source')
        check_pin(manifest['files'][resolved['dataset']['path']], resolved['dataset']['sha256'], 'packaged dataset')
        if manifest['mode'] == 'evaluation':
            for artifact in resolved.get('artifacts', []):
                for field, hash_field in [('model_path', 'model_sha256'), ('normalizer_path', 'normalizer_sha256')]:
                    require_hash(artifact.get(hash_field))
                    check_pin(manifest['files'][artifact[field]], artifact[hash_field], 'packaged artifact')
        if archive.testzip() is not None:
            raise ValueError('package CRC mismatch')
    return manifest


def verify_protocol_matches(package_path, protocol_path):
    """Require execution to use the exact resolved protocol stored in the archive."""
    protocol_bytes = Path(protocol_path).read_bytes()
    with zipfile.ZipFile(package_path) as archive:
        try:
            pinned_bytes = archive.read('CoreRouter/configs/rev1/protocol.resolved.json')
        except KeyError as exc:
            raise ValueError('package does not contain the resolved protocol') from exc
    if protocol_bytes != pinned_bytes:
        raise ValueError('execution protocol does not match packaged protocol')


def verify_workspace_inputs(package_path, manifest, root):
    """Ensure the frozen package describes the current code/data/config tree."""
    root = Path(root).resolve()
    with zipfile.ZipFile(package_path) as archive:
        protocol = json.loads(archive.read('CoreRouter/configs/rev1/protocol.resolved.json'))
    source_paths = [relative_path(root, item) for item in protocol.get('source_paths', [])]
    if not source_paths or sha256_paths(source_paths, root) != manifest.get('source_sha256'):
        raise ValueError('workspace source hash mismatch with package manifest')
    dataset = relative_path(root, protocol.get('dataset', {}).get('path', ''))
    if (not dataset.is_file() or sha256_file(dataset) != manifest.get('dataset_sha256')
            or manifest.get('files', {}).get(dataset.relative_to(root).as_posix()) != sha256_file(dataset)):
        raise ValueError('workspace dataset hash mismatch with package manifest')
    checked = [name for name in manifest.get('files', {})
               if (name.startswith('configs/rev1/') and name != 'configs/rev1/protocol.resolved.json')
               or name in {'requirements.txt', 'requirements-dev.txt'}]
    for name in checked:
        path = relative_path(root, name)
        if not path.is_file() or sha256_file(path) != manifest['files'][name]:
            raise ValueError('workspace configuration hash mismatch: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--protocol', type=Path, default=Path('configs/rev1/protocol.json'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', type=Path, help='Verify an existing input package instead of building one')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--expected-mode', choices=['training', 'evaluation'])
    parser.add_argument('--execution-protocol', type=Path)
    parser.add_argument('--mode', choices=['training', 'evaluation'], default='evaluation')
    parser.add_argument('--training-run', action='append', default=[], metavar='TOPOLOGY=RUN_DIR')
    args = parser.parse_args()
    if args.verify:
        if not args.expected_sha256:
            parser.error('--verify requires --expected-sha256')
        manifest = verify_package(args.verify, args.expected_sha256)
        if args.expected_mode and manifest.get('mode') != args.expected_mode:
            raise ValueError('input package mode mismatch: expected {}, got {}'.format(
                args.expected_mode, manifest.get('mode')))
        verify_workspace_inputs(args.verify, manifest, root)
        if args.execution_protocol:
            verify_protocol_matches(args.verify, args.execution_protocol)
        print(json.dumps({'status': 'verified', 'path': str(args.verify),
                          'sha256': sha256_file(args.verify), 'mode': manifest['mode']}, indent=2))
        return 0
    if not args.output:
        parser.error('--output is required when building a package')
    root = args.root.resolve()
    protocol = args.protocol if args.protocol.is_absolute() else root / args.protocol
    training_runs = {}
    for entry in args.training_run:
        topology, separator, run = entry.partition('=')
        if not separator or not topology or not run or topology in training_runs:
            parser.error('each --training-run must be a unique TOPOLOGY=RUN_DIR')
        training_runs[topology] = run
    manifest = build_package(root, protocol, args.output, mode=args.mode, training_runs=training_runs)
    print(json.dumps({'output': str(args.output), 'sha256': sha256_file(args.output),
                      'mode': args.mode, 'files': len(manifest['files']),
                      'missing_artifacts': manifest['missing_artifacts']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
