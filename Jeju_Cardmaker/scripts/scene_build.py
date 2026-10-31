"""Build scene-based staff AI cards from plan.json and diagrams.json in one project folder.

python scene_build.py --project <PROJECT> --out <NEW_FOLDER> [--source source.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from card_scenes import ENGINE_VERSION, diagram_strings, make_preview, make_renderer  # noqa: E402
from rp_core import SkillError, read_json, sha256, validate_plan  # noqa: E402
from rp_render import check_glyphs, resolve_fonts  # noqa: E402
from rp_studio import PRESETS, build_project, verify_build  # noqa: E402

SKILL = SCRIPTS.parent


def build_scenes(project: str | Path, out: str | Path, *, source: str | None = None,
                 preset: str = "portrait-2x", show_status: bool = False, pptx: bool = True,
                 approval: str | None = None, final: bool = False) -> Path:
    project = Path(project).expanduser().resolve(strict=True)
    target = Path(out).expanduser().absolute()
    if project.is_relative_to(SKILL) or target.is_relative_to(SKILL):
        raise SkillError("프로젝트와 결과 폴더는 스킬 밖에 두세요.")
    plan = validate_plan(read_json(project / "plan.json"))
    diagrams_path = project / "diagrams.json"
    if not diagrams_path.is_file():
        raise SkillError("diagrams.json이 필요해요. references/scene-types.md를 참고하세요.")
    diagrams = read_json(diagrams_path)
    renderer = make_renderer(plan, diagrams)
    check_glyphs(resolve_fonts(None, None, required_family="Pretendard"), diagram_strings(diagrams))
    if source is None and (project / "source.json").is_file():
        source = str(project / "source.json")
    return build_project(
        project, target, preset=preset, profile_name="seogwipo-ai", source_path=source,
        approval_path=approval, final=final, show_status=show_status, pptx=pptx,
        card_renderer=renderer, preview_builder=make_preview(plan, diagrams, renderer.reports),
        report_extra={"scene_engine": ENGINE_VERSION, "diagram_content": diagrams,
                      "renderer_sources": {"diagrams.json": sha256(diagrams_path.read_bytes())},
                      "character_plan": renderer.characters},
        about_note="그림 원고는 diagrams.json이며 render-report.json의 diagram_content에 보관합니다. "
                   "scripts/scene_build.py로 제작합니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description="장 유형(scene) 카드뉴스 제작")
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--source")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="portrait-2x")
    parser.add_argument("--show-status", action="store_true", help="카드에 검토 상태 글자 표시")
    parser.add_argument("--no-pptx", action="store_true")
    parser.add_argument("--approval")
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    try:
        output = build_scenes(args.project, args.out, source=args.source, preset=args.preset,
                               show_status=args.show_status, pptx=not args.no_pptx,
                               approval=args.approval, final=args.final)
        print(json.dumps(verify_build(output), ensure_ascii=False))
        return 0
    except (SkillError, OSError, ValueError) as error:
        print(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
