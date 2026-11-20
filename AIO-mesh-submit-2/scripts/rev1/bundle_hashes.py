"""Canonical source selection shared by packaging and artifact preflight."""
import hashlib
from pathlib import Path

EXCLUDED = {'env', 'venv', '.venv', '__pycache__', '.pytest_cache', 'node_modules',
            '.git', '.aws', '.codex', '.agents', 'dist', 'build', 'site-packages'}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def selected_files(paths, root):
    root = root.resolve()
    found = {}
    for candidate in paths:
        if not candidate.exists():
            raise FileNotFoundError(f'source input missing: {candidate}')
        files = candidate.rglob('*') if candidate.is_dir() else [candidate]
        for path in files:
            relative = path.relative_to(root)
            if any(part in EXCLUDED or part.startswith('.') for part in relative.parts):
                continue
            if path.suffix in {'.pyc', '.pyo'}:
                continue
            if path.is_symlink():
                raise ValueError(f'source symlink is not a frozen input: {relative}')
            if path.is_file():
                found[relative.as_posix()] = path
    return dict(sorted(found.items()))


def sha256_paths(paths, root):
    digest = hashlib.sha256()
    for relative, path in selected_files(paths, root).items():
        digest.update(relative.encode('utf-8'))
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()
