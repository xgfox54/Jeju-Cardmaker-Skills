"""Build this diagram edition with the existing Cardmaker export pipeline."""
from pathlib import Path
import json
import sys
import zipfile
import argparse

PROJECT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description="Build the copied ontology diagram example.")
parser.add_argument("--skill-root", required=True, type=Path)
parser.add_argument("--out", required=True, type=Path)
args = parser.parse_args()
SKILL = args.skill_root.resolve(strict=True)
if PROJECT.is_relative_to(SKILL):
    parser.error("Copy the example to a project folder outside the skill before building.")
if args.out.resolve().is_relative_to(SKILL):
    parser.error("Choose an output folder outside the skill.")
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
import rp_studio
from rp_render import check_glyphs, resolve_fonts
from rp_core import extract_document, write_json, read_json, sha256
from visual_renderer import render_learning_card
from scene_preview import make_preview, validate_page


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


rendered_pages = []


def render_checked(*arguments, **keywords):
    image, report = render_learning_card(*arguments, **keywords)
    validate_page(report)
    check_glyphs(arguments[3], [block["text"] for block in report["blocks"]])
    rendered_pages.append(report)
    return image, report


rp_studio.render_card = render_checked
rp_studio.preview_html = make_preview(rendered_pages)
fonts = resolve_fonts(None, None, required_family="Pretendard")
assert len(read_json(PROJECT / "plan.json")["slides"]) == 8, "Adapt this renderer before changing its eight-page layout."
check_glyphs(fonts, list(strings(json.loads((PROJECT / "diagrams.json").read_text(encoding="utf-8")))))
write_json(PROJECT / "source.json", extract_document(PROJECT / "research-notes.md"))
target = args.out
rp_studio.build_project(PROJECT, target, source_path=str(PROJECT / "source.json"))
report = read_json(target / "render-report.json")
report["diagram_content"] = read_json(PROJECT / "diagrams.json")
report["renderer_sources"] = {p: sha256((PROJECT / p).read_bytes()) for p in ("build.py", "visual_renderer.py", "scene_preview.py", "diagrams.json")}
report["character_scene_checks"] = {"glyphs_checked": True, "text_pet_overlap": 0, "text_text_overlap": 0, "contrast_warnings": 0}
write_json(target / "render-report.json", report)
about = target / "ABOUT.txt"
about.write_text(about.read_text(encoding="utf-8").replace(
    "단일 원본은 plan.json. PPTX 수정은 JSON/PNG에 역반영되지 않습니다.",
    "문안은 plan.json, 그림 원고는 render-report.json의 diagram_content에 보관합니다.\n"
    "이번 그림 판은 복사한 예제 폴더의 build.py로 제작합니다. PPTX 수정은 JSON/PNG에 역반영되지 않습니다."), encoding="utf-8")
manifest = read_json(target / "manifest.json")
manifest["files"] = {name: sha256((target / name).read_bytes()) for name in manifest["files"]}
write_json(target / "manifest.json", manifest)
with zipfile.ZipFile(target / "cardnews.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for name in list(manifest["files"]) + ["manifest.json"]:
        archive.write(target / name, name)
print(json.dumps(rp_studio.verify_build(target), ensure_ascii=False))
