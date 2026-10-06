#!/usr/bin/env python3
"""Check publication size limits and excluded files without changing the index."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def publication_files():
    listing = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT)
    return sorted(set(path.decode('utf-8') for path in listing.split(b'\0') if path))


def main():
    paths = publication_files()
    total = 0
    maximum = 0
    for name in paths:
        path = ROOT / name
        if not path.exists():
            continue
        assert not path.is_symlink(), f'Unexpected publication symlink: {name}'
        assert not name.endswith('.log') or name == 'results/tests.log', f'Unexpected log: {name}'
        assert not any(part in ('.agents', '.codex', 'node_modules', '__pycache__') for part in path.relative_to(ROOT).parts), name
        size = path.stat().st_size
        assert size <= 10 * 1048576, f'File exceeds 10 MiB: {name}'
        total += size
        maximum = max(maximum, size)
    assert len(paths) <= 1000, 'Tree exceeds 1,000 files'
    assert total <= 32 * 1048576, 'Tree exceeds 32 MiB'
    print(json.dumps({'files': len(paths), 'total_bytes': total, 'largest_file_bytes': maximum, 'limits_passed': True}))


if __name__ == '__main__':
    main()
