#!/usr/bin/env python3
"""Install only this skill; never install packages, clone repositories or call APIs."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EXCLUDED = {'.venv', '__pycache__', '.git', 'runtime', 'outputs', '.pytest_cache'}
# Releases before v1.1.1 installed this skill as skills/releasepick.
LEGACY_NAMES = ('releasepick',)


def install(source: Path, base: Path, *, replace: bool = False) -> dict:
    source = source.resolve(strict=True)
    if not (source / 'SKILL.md').is_file():
        raise ValueError('The package is missing Jeju_Cardmaker/SKILL.md.')
    base = base.expanduser().absolute()
    if base.is_symlink() or any(p.is_symlink() for p in base.parents):
        raise ValueError('Install location must not traverse symbolic links.')
    target = base / 'skills' / 'Jeju_Cardmaker'
    if target.is_symlink():
        raise ValueError('Refusing to replace a symbolic link.')
    if target.exists() and not replace:
        raise FileExistsError('Jeju_Cardmaker already exists. Use --replace to back it up first.')
    if target.exists() and not target.is_dir():
        raise ValueError('Install target is not a directory.')
    legacy = [base / 'skills' / name for name in LEGACY_NAMES]
    legacy = [p for p in legacy if p.exists() or p.is_symlink()]
    if any(p.is_symlink() or not p.is_dir() for p in legacy):
        raise ValueError('An earlier ReleasePick install is not a regular directory. Check it manually.')
    if legacy and not replace:
        raise FileExistsError('An earlier ReleasePick install exists. Use --replace (UPDATE.cmd) to back it up first.')
    for root, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = [d for d in dirs if d not in EXCLUDED]
        for name in dirs + files:
            if (Path(root) / name).is_symlink():
                raise ValueError('The skill package contains a symbolic link.')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink():
        raise ValueError('The skills directory must not be a symbolic link.')
    stage = Path(tempfile.mkdtemp(prefix='.Jeju_Cardmaker-install-', dir=base))
    backup = None
    moved: list[tuple[Path, Path]] = []
    try:
        shutil.copytree(source, stage / 'Jeju_Cardmaker', ignore=shutil.ignore_patterns(*EXCLUDED, '*.pyc'))
        if target.exists() or legacy:
            backup_root = base / 'skill-backups'
            if backup_root.is_symlink():
                raise ValueError('Backup directory must not be a symbolic link.')
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        try:
            if target.exists():
                backup = backup_root / ('Jeju_Cardmaker-' + stamp)
                target.rename(backup)
            for old in legacy:
                # Move the earlier install out of skills/ so Codex does not list two copies.
                dest = backup_root / ('Jeju_Cardmaker-legacy-' + stamp)
                old.rename(dest)
                moved.append((old, dest))
            (stage / 'Jeju_Cardmaker').rename(target)
        except BaseException:
            if backup is not None and not target.exists():
                backup.rename(target)
            for old, dest in reversed(moved):
                if not old.exists():
                    dest.rename(old)
            raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return {'installed': str(target), 'backup': str(backup) if backup else None,
            'legacy_backups': [str(dest) for _, dest in moved],
            'runtime_installed': False, 'upstream_downloaded': False, 'api_calls': 0}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', help='Existing project directory, instead of user-wide installation')
    p.add_argument('--replace', action='store_true', help='Back up an existing skill outside the skills directory')
    args = p.parse_args(argv)
    try:
        if sys.version_info < (3, 11):
            raise ValueError('Python 3.11 or newer is required. Python 3.11/3.12 is recommended for upstream.')
        if args.project:
            root = Path(args.project).expanduser().resolve(strict=True)
            if not root.is_dir():
                raise ValueError('--project must name an existing directory.')
            base = root / '.agents'
        else:
            base = Path.home() / '.agents'
        print(json.dumps(install(Path(__file__).parent / 'Jeju_Cardmaker', base, replace=args.replace), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
