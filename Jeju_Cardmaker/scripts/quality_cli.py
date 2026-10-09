#!/usr/bin/env python3
"""Checked wrapper; preserves the existing Jeju_Cardmaker.py commands and outputs."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from rp_quality import (QualityError, attach_approval, decode_json, normalized_plan,
                        policy, postflight, preflight, require_quality_approval,
                        safe_file, seal_checked_build, validate_source,
                        verify_checked, write_json_new)
from rp_core import SkillError


def read_bundle(project: str | Path) -> tuple[Path, dict, dict, str, dict]:
    root = Path(project).expanduser().absolute()
    if not root.is_dir():
        raise QualityError("plan.json 등이 있는 프로젝트 폴더가 필요합니다.")
    plan = normalized_plan(decode_json(safe_file(root, "plan.json", 2*1024*1024).read_bytes()))
    source = validate_source(decode_json(safe_file(root, "source.json", 2*1024*1024).read_bytes()))
    notes = safe_file(root, "SOURCES.md", 2*1024*1024).read_text(encoding="utf-8-sig")
    evidence = decode_json(safe_file(root, "evidence.json", 2*1024*1024).read_bytes())
    return root, plan, source, notes, evidence


def approval_record(path: str | Path) -> dict:
    value = Path(path).expanduser().absolute()
    return decode_json(safe_file(value.parent, value.name, 2*1024*1024).read_bytes())


def checked_build(project: str | Path, output: str | Path, *, as_of: str,
                  max_age_days: int = 30, preset: str = "portrait-2x",
                  profile_name: str = "jeju", approval_path: str | None = None,
                  final: bool = False, hide_status: bool = False,
                  font: str | None = None, bold_font: str | None = None,
                  logo_path: str | None = None, pptx: bool = True,
                  _engine=None, _verifier=None) -> Path:
    """No user-visible destination is published until all checks pass.

    _engine/_verifier are explicit dependency injection points for integration tests,
    never command-line switches and never loaded from content documents.
    """
    root, plan, source, notes, evidence = read_bundle(project)
    rules = policy(as_of, max_age_days)
    pre = preflight(plan, source, notes, evidence, rules)
    target = Path(output).expanduser().absolute()
    if target == root or root.is_relative_to(target) or target.is_relative_to(root):
        raise QualityError("출력은 원문 프로젝트와 별도 폴더로 지정하세요.")
    if target.exists() or target.is_symlink() or any(p.is_symlink() for p in target.parents):
        raise QualityError("기존 출력 또는 심볼릭 링크 위치에는 저장하지 않습니다.")
    if hide_status and not final:
        raise QualityError("초안의 상태 표시는 제거할 수 없습니다.")
    approval = approval_record(approval_path) if approval_path else None
    if final:
        require_quality_approval(approval, pre)
    if _engine is None:
        from rp_studio import build_project, verify_build
        from rp_render import load_profile
        _engine, _verifier = build_project, verify_build
        profile = load_profile(profile_name)
    else:
        profile = None  # Tests supply a local fake engine, not real rendering.
    if _verifier is None:
        raise QualityError("기존 빌드의 무결성 검증기가 필요합니다.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".Jeju_Cardmaker-quality-", dir=target.parent))
    try:
        snapshot = temporary/"inputs"
        snapshot.mkdir()
        for name, obj in (("plan.json", plan), ("source.json", source), ("evidence.json", evidence)):
            write_json_new(snapshot/name, obj)
        (snapshot/"SOURCES.md").write_text(notes, encoding="utf-8")
        if approval is not None:
            write_json_new(snapshot/"approval.json", approval)
        if profile is not None:
            write_json_new(snapshot/"profile.json", profile)
            profile_name = str(snapshot/"profile.json")
        if logo_path:
            original_logo = Path(logo_path).expanduser().absolute()
            logo_bytes = safe_file(original_logo.parent, original_logo.name, 10*1024*1024).read_bytes()
            logo = snapshot/("logo"+original_logo.suffix)
            logo.write_bytes(logo_bytes)
            logo_path = str(logo)
        candidate = temporary/"result"
        result = Path(_engine(snapshot, candidate, preset=preset, profile_name=profile_name,
                              source_path=str(snapshot/"source.json"),
                              approval_path=str(snapshot/"approval.json") if approval is not None else None,
                              final=final, hide_status=hide_status, font=font, bold_font=bold_font,
                              logo_path=logo_path, pptx=pptx))
        if result.absolute() != candidate.absolute():
            raise QualityError("렌더러가 예약한 임시 출력 외의 경로를 반환했습니다.")
        integrity = _verifier(candidate)
        if not isinstance(integrity, dict) or integrity.get("ok") is not True:
            raise QualityError("기존 산출물 무결성 검사가 통과하지 않았습니다.")
        post = postflight(candidate, plan, rules)
        _, p2, s2, n2, e2 = read_bundle(root)
        after = preflight(p2, s2, n2, e2, rules)
        if pre["binding"] != after["binding"]:
            raise QualityError("제작 중 입력이 변경되었습니다. 변경된 문안으로 다시 실행하세요.")
        seal_checked_build(candidate, pre, post)
        if target.exists() or target.is_symlink():
            raise QualityError("제작 중 출력 경로가 생성되었습니다. 덮어쓰지 않습니다.")
        candidate.rename(target)
    finally:
        # Only the wrapper's own temporary directory is removed; never user inputs.
        shutil.rmtree(temporary, ignore_errors=True)
    return target


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    sub = command.add_subparsers(dest="command", required=True)
    for name in ("preflight", "approve", "build"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--as-of", required=True, help="검토 기준일 YYYY-MM-DD; 자동 최신성 확인이 아닙니다.")
        p.add_argument("--max-age-days", type=int, default=30)
        p.add_argument("--out", required=name != "preflight")
        if name == "approve":
            p.add_argument("--reviewer", required=True)
            p.add_argument("--confirmed", action="store_true")
        if name == "build":
            p.add_argument("--preset", choices=("legacy", "portrait", "portrait-2x"), default="portrait-2x")
            p.add_argument("--profile", default="jeju")
            p.add_argument("--approval")
            p.add_argument("--final", action="store_true")
            p.add_argument("--hide-status", action="store_true")
            p.add_argument("--font")
            p.add_argument("--bold-font")
            p.add_argument("--logo")
            p.add_argument("--no-pptx", action="store_true")
    p = sub.add_parser("verify")
    p.add_argument("--run", required=True)
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "verify":
            from rp_studio import verify_build
            root = Path(args.run).expanduser().absolute()
            verify_build(root)
            result = verify_checked(root)
        elif args.command == "build":
            out = checked_build(args.project, args.out, as_of=args.as_of, max_age_days=args.max_age_days,
                                preset=args.preset, profile_name=args.profile, approval_path=args.approval,
                                final=args.final, hide_status=args.hide_status, font=args.font,
                                bold_font=args.bold_font, logo_path=args.logo, pptx=not args.no_pptx)
            result = {"ok": True, "output": str(out), "zip": str(out/"cardnews-checked.zip"),
                      "api_calls": 0, "publishing_authorized": False}
        else:
            _, plan, source, notes, evidence = read_bundle(args.project)
            result = preflight(plan, source, notes, evidence, policy(args.as_of, args.max_age_days))
            if args.command == "approve":
                # Existing core records approval; no flags inferred from the source or a passing gate.
                from rp_core import approve
                result = attach_approval(approve(plan, source, args.reviewer, args.confirmed), result)
            if args.out:
                dest = Path(args.out).expanduser().absolute()
                if dest.is_symlink() or any(p.is_symlink() for p in dest.parents):
                    raise QualityError("출력 경로의 심볼릭 링크는 허용하지 않습니다.")
                dest.parent.mkdir(parents=True, exist_ok=True)
                write_json_new(dest, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (QualityError, OSError, ValueError, ImportError) as exc:
        # SkillError messages from the existing core are user-actionable and never contain secrets.
        message = str(exc) if isinstance(exc, (QualityError, SkillError)) else f"{type(exc).__name__}: 입력/승인/필수 패키지를 확인하세요."
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: 검사 실패. 내부 오류 원문은 출력하지 않았습니다."}, ensure_ascii=False), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
