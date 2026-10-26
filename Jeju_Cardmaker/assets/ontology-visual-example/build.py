"""Build this diagram edition with the existing Cardmaker export pipeline."""
from pathlib import Path
import json
import sys
import html
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


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


rp_studio.render_card = render_learning_card
original_preview = rp_studio.preview_html


def diagram_preview(plan, paths, status, notes, digest):
    page = original_preview(plan, paths, status, notes, digest)
    page = page.replace("plan.json 수정 후 build 명령을 다시 실행하세요.",
                        "문안과 그림을 수정한 뒤 다시 제작하세요.")
    page = page.replace("로컬 제작 / 자동 게시 없음", "업무 예시와 연결 그림")
    descriptions = [
        "부서 A팀은 업무 주민설명회를 담당합니다. 주민설명회 업무는 문서 행사 안내문을 사용합니다.",
        "행사 안내문에서 연결선을 거꾸로 따라가면 이를 사용하는 주민설명회와 담당 부서 A팀을 확인합니다.",
        "부서는 일을 맡는 조직이며 이 예시에서는 A팀입니다. 업무는 수행하는 일이며 주민설명회 준비입니다. 문서는 내용을 기록한 자료이며 행사 안내문입니다.",
        "A팀에서 주민설명회로 향하는 선에는 담당합니다를, 주민설명회에서 행사 안내문으로 향하는 선에는 사용합니다를 적었습니다.",
        "위에는 부서가 업무를 담당한다는 종류와 관계를, 아래에는 A팀이 주민설명회를 담당한다는 가상 기록을 표시합니다.",
        "문서라는 큰 상자 안에 행사 안내문 상자가 있습니다. 그 안에는 이번 주민설명회 안내문이 있습니다. 따라서 이 자료도 문서입니다.",
        "담당 변경 전에는 A팀이 주민설명회를 담당합니다. 변경 후에는 B팀이 주민설명회를 담당합니다. 연결 정보도 새 담당팀에 맞게 고칩니다.",
        "우리 팀은 담당 업무를 맡고, 그 업무에서 사용 문서를 씁니다. 각 상자의 대상 종류는 부서, 업무, 문서입니다."
    ]
    segments = page.split("</details>")
    for i, description in enumerate(descriptions):
        segments[i] += "<p>그림 설명: " + html.escape(description) + "</p></details>"
    page = "".join(segments)
    return page


rp_studio.preview_html = diagram_preview
fonts = resolve_fonts(None, None, required_family="Pretendard")
assert len(read_json(PROJECT / "plan.json")["slides"]) == 8, "Adapt this renderer before changing its eight-page layout."
check_glyphs(fonts, list(strings(json.loads((PROJECT / "diagrams.json").read_text(encoding="utf-8")))))
write_json(PROJECT / "source.json", extract_document(PROJECT / "research-notes.md"))
target = args.out
rp_studio.build_project(PROJECT, target, source_path=str(PROJECT / "source.json"))
report = read_json(target / "render-report.json")
report["diagram_content"] = read_json(PROJECT / "diagrams.json")
report["renderer_sources"] = {p: sha256((PROJECT / p).read_bytes()) for p in ("build.py", "visual_renderer.py", "diagrams.json")}
write_json(target / "render-report.json", report)
about = target / "ABOUT.txt"
about.write_text(about.read_text(encoding="utf-8").replace(
    "단일 원본은 plan.json. PPTX 수정은 JSON/PNG에 역반영되지 않습니다.",
    "문안은 plan.json, 그림 원고는 render-report.json의 diagram_content에 보관합니다.\n"
    "이번 그림 판은 ontology-visual-project/build.py로 제작합니다. PPTX 수정은 JSON/PNG에 역반영되지 않습니다."), encoding="utf-8")
manifest = read_json(target / "manifest.json")
manifest["files"] = {name: sha256((target / name).read_bytes()) for name in manifest["files"]}
write_json(target / "manifest.json", manifest)
with zipfile.ZipFile(target / "cardnews.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for name in list(manifest["files"]) + ["manifest.json"]:
        archive.write(target / name, name)
print(json.dumps(rp_studio.verify_build(target), ensure_ascii=False))
