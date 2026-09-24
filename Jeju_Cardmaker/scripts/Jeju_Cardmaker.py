#!/usr/bin/env python3
"""Command-line entry point for the Jeju_Cardmaker Codex skill."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

from rp_core import (SkillError, VERSION, approve, extract_document, new_json,
                     read_json, require_approval, review_markdown, validate_plan, validate_source)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Jeju_Cardmaker Codex Skill: local by default; no automatic publishing.")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Read-only environment check; no secrets")
    extract = sub.add_parser("extract", help="Extract local PDF/HWPX/TXT/MD")
    extract.add_argument("--input", required=True)
    extract.add_argument("--out", required=True)
    validate = sub.add_parser("validate", help="Validate structure, not factual accuracy")
    validate.add_argument("--plan", required=True)
    validate.add_argument("--pages", type=int)
    review = sub.add_parser("review", help="Write a text review document")
    review.add_argument("--plan", required=True)
    review.add_argument("--source")
    review.add_argument("--out", required=True)
    approval = sub.add_parser("approve", help="Record actual user copy approval")
    approval.add_argument("--plan", required=True)
    approval.add_argument("--source", required=True)
    approval.add_argument("--out", required=True)
    approval.add_argument("--reviewer", required=True)
    approval.add_argument("--confirmed", action="store_true")
    render = sub.add_parser("render", help="Render deterministic local text cards")
    render.add_argument("--plan", required=True)
    render.add_argument("--source")
    render.add_argument("--out", required=True)
    render.add_argument("--profile", default="neutral")
    render.add_argument("--font")
    render.add_argument("--bold-font")
    render.add_argument("--logo")
    render.add_argument("--locale", choices=["ko", "en"], default="ko")
    render.add_argument("--final", action="store_true")
    render.add_argument("--approval")
    package = sub.add_parser("package", help="Allowlisted ZIP + optional image PPTX")
    package.add_argument("--run", required=True)
    package.add_argument("--out", required=True)
    package.add_argument("--no-pptx", action="store_true")
    build = sub.add_parser("build", help="Build PNG/JPEG/HTML/ZIP and editable/image PPTX from one project")
    build.add_argument("--project", required=True, help="Folder containing plan.json and optional SOURCES.md")
    build.add_argument("--out", required=True, help="New output folder, never overwrite")
    build.add_argument("--preset", choices=["legacy", "portrait", "portrait-2x"], default="portrait-2x")
    build.add_argument("--profile", default="jeju")
    build.add_argument("--source")
    build.add_argument("--approval")
    build.add_argument("--final", action="store_true")
    build.add_argument("--hide-status", action="store_true")
    build.add_argument("--font")
    build.add_argument("--bold-font")
    build.add_argument("--logo")
    build.add_argument("--no-pptx", action="store_true")
    verify = sub.add_parser("verify-build", help="Detect modified build outputs and ZIP mismatches")
    verify.add_argument("--run", required=True)
    check = sub.add_parser("upstream-check", help="AST-only upstream signature check")
    check.add_argument("--repo", required=True)
    original = sub.add_parser("upstream-export", help="Use original editable plan PPTX exporter")
    original.add_argument("--repo", required=True)
    original.add_argument("--run", required=True)
    original.add_argument("--out", required=True)
    original.add_argument("--trust-upstream", action="store_true")
    for name in ("api-plan", "api-render"):
        api = sub.add_parser(name, help="Optional upstream OpenAI API operation (paid)")
        api.add_argument("--repo", required=True)
        api.add_argument("--source", required=True)
        api.add_argument("--model", required=True)
        api.add_argument("--out", required=True)
        api.add_argument("--allow-paid-api", action="store_true")
        api.add_argument("--max-api-calls", type=int)
        api.add_argument("--trust-upstream", action="store_true")
        if name == "api-plan":
            api.add_argument("--pages", type=int, required=True)
        else:
            api.add_argument("--plan", required=True)
            api.add_argument("--approval", required=True)
            api.add_argument("--accept-mofe-branding", action="store_true")
            api.add_argument("--locale", choices=["ko", "en"], default="ko")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        cmd = args.command
        if cmd == "doctor":
            packages = {}
            for name in ["Pillow", "PyMuPDF", "python-pptx", "fonttools", "defusedxml", "openai", "pydantic", "PyYAML"]:
                try:
                    packages[name] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    packages[name] = None
            try:
                from rp_render import resolve_fonts
                fonts = [p.name for p in resolve_fonts()]
            except (SkillError, ImportError, OSError):
                fonts = []
            result = {"version": VERSION, "python": sys.version.split()[0], "packages": packages,
                      "fonts": fonts, "network_requested": False, "desktop_installation_verified": False}
        elif cmd == "extract":
            result = extract_document(args.input)
            new_json(args.out, result)
            result = {"output": str(Path(args.out).absolute()), "units": len(result["units"]), "warnings": result["warnings"]}
        elif cmd == "validate":
            plan = validate_plan(read_json(args.plan), args.pages)
            result = {"valid_structure": True, "pages": len(plan["slides"]), "factual_accuracy_verified": False}
        elif cmd == "review":
            plan = validate_plan(read_json(args.plan))
            source = validate_source(read_json(args.source)) if args.source else None
            dest = Path(args.out).expanduser()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("x", encoding="utf-8") as f:
                f.write(review_markdown(plan, source))
            result = {"output": str(dest.absolute())}
        elif cmd == "approve":
            result = approve(validate_plan(read_json(args.plan)), validate_source(read_json(args.source)), args.reviewer, args.confirmed)
            new_json(args.out, result)
            result = {"output": str(Path(args.out).absolute()), "copy_approved": True, "api_or_publishing_authorized": False}
        elif cmd == "render":
            from rp_render import create_run, load_profile
            output = create_run(validate_plan(read_json(args.plan)), args.out, load_profile(args.profile),
                         regular_font=args.font, bold_font=args.bold_font, logo=args.logo,
                         source=validate_source(read_json(args.source)) if args.source else None,
                         approval=read_json(args.approval) if args.approval else None,
                         final=args.final, locale=args.locale)
            result = {"output": str(output), "preview": str(output / "preview.html"), "api_calls": 0}
        elif cmd == "package":
            from rp_render import package_run
            result = {"output": str(package_run(args.run, args.out, include_pptx=not args.no_pptx))}
        elif cmd == "build":
            from rp_studio import build_project
            output = build_project(args.project, args.out, preset=args.preset, profile_name=args.profile,
                source_path=args.source, approval_path=args.approval, final=args.final, hide_status=args.hide_status,
                font=args.font, bold_font=args.bold_font, logo_path=args.logo, pptx=not args.no_pptx)
            result = {"output": str(output), "zip": str(output/"cardnews.zip"),
                      "preview": str(output/"preview.html"), "api_calls": 0,
                      "status": "copy-approved" if args.final else "draft"}
        elif cmd == "verify-build":
            from rp_studio import verify_build
            result = verify_build(args.run)
        elif cmd == "upstream-check":
            from rp_bridge import inspect_upstream
            result = inspect_upstream(args.repo)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["compatible"] else 2
        elif cmd == "upstream-export":
            from rp_bridge import original_export
            from rp_render import validate_run
            root, manifest, plan, images = validate_run(args.run)
            dest = Path(args.out).expanduser()
            if dest.exists():
                raise SkillError("기존 ZIP을 덮어쓰지 않습니다.")
            payload = original_export(args.repo, plan, images, root / "jpeg", args.trust_upstream)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("xb") as f:
                f.write(payload)
            result = {"output": str(dest.absolute()), "engine": "upstream-package-export", "notice": "원본 PPTX의 글자 넘침은 별도 시각 검수해야 합니다."}
        elif cmd == "api-plan":
            from rp_bridge import generate_upstream_plan
            if Path(args.out).exists():
                raise SkillError("출력 파일이 이미 있습니다. API를 호출하지 않았습니다.")
            plan, calls = generate_upstream_plan(args.repo, validate_source(read_json(args.source)), pages=args.pages,
                               model=args.model, trusted=args.trust_upstream, allowed=args.allow_paid_api, max_calls=args.max_api_calls)
            new_json(args.out, plan)
            result = {"output": str(Path(args.out).absolute()), "api_calls_attempted": calls, "copy_approved": False}
        elif cmd == "api-render":
            from rp_bridge import render_upstream_api
            plan = validate_plan(read_json(args.plan))
            source = validate_source(read_json(args.source))
            require_approval(plan, source, read_json(args.approval))
            images, calls = render_upstream_api(args.repo, plan, Path(args.out).expanduser(), model=args.model,
                               trusted=args.trust_upstream, allowed=args.allow_paid_api, max_calls=args.max_api_calls,
                               accept_branding=args.accept_mofe_branding, locale=args.locale)
            result = {"output": str(Path(args.out).absolute()), "images": [str(p) for p in images],
                      "api_calls_attempted": calls, "notice": "원본 API 결과입니다. 시각 검수 전 최종본으로 표시하지 마세요."}
        else:
            raise SkillError("알 수 없는 명령입니다.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (SkillError, OSError, ImportError, ValueError) as exc:
        # API SDK/upstream errors can contain server text; never dump a traceback or keys.
        message = str(exc) if isinstance(exc, SkillError) else f"{type(exc).__name__}: 입력 경로·형식·필수 패키지를 확인하세요."
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: 작업 실패. API 오류 원문과 비밀값은 출력하지 않았습니다."}, ensure_ascii=False), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
