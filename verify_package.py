#!/usr/bin/env python3
"""Verify declared distribution files. This is an integrity check, not a signature."""
from __future__ import annotations
import hashlib
import re
import sys
from pathlib import Path, PurePosixPath


def verify(root: Path) -> int:
    root = root.resolve(strict=True)
    listing = root / 'SHA256SUMS.txt'
    if not listing.is_file() or listing.is_symlink():
        raise ValueError('SHA256SUMS.txt is missing or is a symbolic link.')
    seen: set[str] = set()
    for line_number, line in enumerate(listing.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match:
            raise ValueError(f'Invalid manifest line {line_number}.')
        expected, name = match.groups()
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name or name in seen:
            raise ValueError(f'Unsafe or duplicate path: {name}')
        seen.add(name)
        file = root.joinpath(*rel.parts)
        if not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(root):
            raise ValueError(f'Missing or unsafe file: {name}')
        if any(parent.is_symlink() for parent in file.parents if parent != root and parent.is_relative_to(root)):
            raise ValueError(f'Symlink in file path: {name}')
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Changed file: {name}')
    if not seen:
        raise ValueError('Empty manifest.')
    print(f'OK: {len(seen)} declared files match SHA-256. Extra files are not authenticated.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(verify(Path(__file__).parent))
    except (OSError, ValueError) as exc:
        print(f'FAILED: {exc}', file=sys.stderr)
        raise SystemExit(2)
