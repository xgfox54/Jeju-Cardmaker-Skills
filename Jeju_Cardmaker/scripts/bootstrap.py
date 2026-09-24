#!/usr/bin/env python3
"""Explicit network opt-in for a skill-local virtualenv and optional upstream."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from rp_core import SkillError, now, write_json
from rp_bridge import UPSTREAM_URL, inspect_upstream

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path | None = None) -> None:
    # Do not print environment variables or credentials. No shell evaluation.
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode:
        raise SkillError(f'설치 명령이 종료 코드 {result.returncode}로 실패했습니다. 기존 자료는 삭제하지 않았습니다.')


def venv_python(venv: Path) -> Path:
    return venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def ensure_venv() -> Path:
    target = ROOT / '.venv'
    python = venv_python(target)
    if target.is_symlink():
        raise SkillError('가상환경 심볼릭 링크는 허용하지 않습니다.')
    if target.exists():
        if not (target / 'pyvenv.cfg').is_file() or not python.is_file():
            raise SkillError('기존 .venv가 정상 가상환경이 아닙니다. 자동 삭제하지 않습니다.')
    else:
        run([sys.executable, '-m', 'venv', str(target)])
    return python


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('core', 'upstream'):
        c = sub.add_parser(command)
        c.add_argument('--allow-network', action='store_true')
        if command == 'upstream':
            c.add_argument('--dest', help='Optional new clone destination')
            c.add_argument('--ref', default='main', help='Git branch or tag; full commit recorded after cloning')
            c.add_argument('--install-deps', action='store_true', help='Install reviewed upstream dependencies in skill .venv')
    args = p.parse_args(argv)
    try:
        if sys.version_info < (3, 11):
            raise SkillError('Python 3.11 이상이 필요합니다. 원본은 3.11/3.12를 권장합니다.')
        if not args.allow_network:
            raise SkillError('다운로드에는 --allow-network를 명시하세요. 네트워크 작업을 실행하지 않았습니다.')
        if args.command == 'core':
            python = ensure_venv()
            run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(ROOT / 'requirements-core.txt')])
            result = {'runtime_python': str(python), 'api_calls': 0}
        else:
            if not shutil.which('git'):
                raise SkillError('Git 실행 파일을 찾지 못했습니다.')
            if not args.ref or args.ref.startswith('-') or any(c in args.ref for c in '\r\n'):
                raise SkillError('유효한 브랜치/태그 이름을 지정하세요.')
            target = Path(args.dest).expanduser().absolute() if args.dest else ROOT / 'runtime' / 'Jeju_Cardmaker'
            if target.exists() or target.is_symlink():
                raise SkillError('원본 저장소 대상이 이미 있습니다. 자동 갱신·덮어쓰기하지 않습니다. upstream-check로 확인하세요.')
            target.parent.mkdir(parents=True, exist_ok=True)
            # The upstream is not included in this package. It is fetched only now.
            run(['git', 'clone', '--depth', '1', '--branch', args.ref, '--', UPSTREAM_URL, str(target)])
            report = inspect_upstream(target)
            (ROOT / 'runtime').mkdir(parents=True, exist_ok=True)
            write_json(ROOT / 'runtime' / 'upstream.json', {'downloaded_at': now(), 'url': UPSTREAM_URL, 'ref': args.ref, **report})
            if not report['compatible']:
                raise SkillError('다운로드는 되었으나 원본 함수 계약이 달라졌습니다. 의존성 설치/실행을 중단했습니다. runtime/upstream.json을 확인하세요.')
            if args.install_deps:
                # Fixed allowlist: reject options, URLs and editable/VCS requirements.
                allowed = {'streamlit', 'python-dotenv', 'pymupdf', 'pillow', 'openai', 'pydantic', 'pyyaml', 'python-pptx', 'requests', 'beautifulsoup4'}
                import re
                requirements = target / 'requirements.txt'
                for line in requirements.read_text(encoding='utf-8-sig').splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    match = re.fullmatch(r'([A-Za-z0-9_-]+)\s*(?:[<>=!~]{1,2}[0-9][A-Za-z0-9.*+-]*(?:\s*,\s*[<>=!~]{1,2}[0-9][A-Za-z0-9.*+-]*)*)?', line)
                    if not match or match.group(1).lower() not in allowed:
                        raise SkillError('원본 requirements.txt에 확인되지 않은 항목이 있습니다. 수동 검토 후 설치하세요.')
                python = ensure_venv()
                run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(requirements)])
            result = {'upstream': str(target), 'commit': report['commit'], 'compatible': report['compatible'], 'api_calls': 0,
                      'notice': '소스 함수 계약 검사입니다. 실제 API 동작/라이선스 적합성을 보증하지 않습니다.'}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        message = str(exc) if isinstance(exc, SkillError) else f'{type(exc).__name__}: 설치 경로 및 환경을 확인하세요.'
        print(json.dumps({'ok': False, 'error': message}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
