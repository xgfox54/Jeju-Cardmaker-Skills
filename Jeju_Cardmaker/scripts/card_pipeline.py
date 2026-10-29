"""Inspect existing card builds and package reviewed drafts without approving copy."""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final, TypedDict

from rp_core import SkillError, canonical, plan_hash, read_json, sha256, write_json
from rp_studio import contrast, verify_build

SKILL: Final = Path(__file__).resolve().parent.parent
POLICY: Final = SKILL / "references/quality-policy.json"
REVIEW_FIELDS: Final = ("visual_checked", "copy_checked", "diagram_checked",
                        "character_checked", "spacing_checked")


class Block(TypedDict):
    text: str
    label: str
    x: float
    y: float
    box_width: float
    box_height: float
    size: float
    font_family: str
    color: str
    background: str
    glyph_bounds: list[list[float]]
    overflow: bool
    align: str
    valign: str


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    detail: str
    page: int = 0


@dataclass(frozen=True, slots=True)
class PageImage:
    page: int
    image: str
    sha256: str


@dataclass(slots=True)
class Gate:
    run_id: str = ""
    status: str = "draft"
    pages: list[PageImage] = field(default_factory=list)
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.run_id and self.pages) and not self.errors


def confined(root: Path, relative: str) -> Path:
    """Accept only regular files beneath the given input root."""
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or "\\" in relative or ":" in relative:
        raise SkillError("허용되지 않는 입력 경로입니다.")
    path = root.joinpath(*rel.parts)
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise SkillError("입력 파일이 없거나 프로젝트 범위를 벗어납니다.")
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root and p.is_relative_to(root)):
        raise SkillError("입력의 심볼릭 링크는 허용하지 않습니다.")
    return path


def box(x: float, y: float, width: float, height: float) -> list[float]:
    return [x, y, x + width, y + height]


def overlaps(a: list[float], b: list[float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def inside(inner: list[float], outer: list[float], slack: float = 1) -> bool:
    return (all(math.isfinite(v) for v in inner + outer) and
            inner[2] >= inner[0] and inner[3] >= inner[1] and
            inner[0] >= outer[0]-slack and inner[1] >= outer[1]-slack and
            inner[2] <= outer[2]+slack and inner[3] <= outer[3]+slack)


def inspect_run(project: Path, run: Path) -> Gate:
    """Recompute the inspection from input files and exported artifacts."""
    from PIL import Image
    from pptx import Presentation

    result = Gate()
    project, run = project.resolve(strict=True), run.resolve(strict=True)
    try:
        verify_build(run)
        manifest = read_json(confined(run, "manifest.json"))
        report = read_json(confined(run, "render-report.json"))
        plan = read_json(confined(project, "plan.json"))
        policy = read_json(POLICY)
        source_inputs = {"plan.json": sha256(confined(project, "plan.json").read_bytes())}
        if plan_hash(plan) != manifest["plan_sha256"]:
            result.errors.append(Issue("INPUT", "현재 기획안과 제작 결과가 다릅니다."))
        notes = confined(project, "SOURCES.md").read_text(encoding="utf-8")
        if notes != confined(run, "SOURCES.md").read_text(encoding="utf-8"):
            result.errors.append(Issue("INPUT", "현재 출처 기록과 제작 결과가 다릅니다."))
        source_inputs["SOURCES.md"] = sha256(notes.encode())
        if (project / "source.json").exists():
            source_inputs["source.json"] = sha256(confined(project, "source.json").read_bytes())
        for name, expected in report.get("renderer_sources", {}).items():
            actual = sha256(confined(project, name).read_bytes())
            source_inputs[name] = actual
            if actual != expected:
                result.errors.append(Issue("INPUT", "제작 코드 또는 그림 원고가 변경됐습니다."))
        if (project / "visual_renderer.py").exists() and not report.get("renderer_sources"):
            result.errors.append(Issue("INPUT", "주제별 렌더러의 제작 해시 기록이 없습니다."))
        fingerprint = {"manifest": sha256((run/"manifest.json").read_bytes()),
                       "policy": sha256(POLICY.read_bytes()), "inputs": source_inputs,
                       "inspector": sha256(Path(__file__).read_bytes())}
        result.run_id = sha256(canonical(fingerprint))
        result.status = manifest["status"]
        width, height = manifest["size"]
        scale = width / policy["logical_width"]
        if abs(width/height-policy["aspect_ratio"]) > 0.001:
            result.errors.append(Issue("SIZE", "직원 AI 카드의 4:5 규격이 아닙니다."))
        pages = report["pages"]
        pngs = sorted(name for name in manifest["files"] if name.startswith("png/"))
        if len(pngs) != len(plan["slides"]) or len(pages) != len(pngs):
            raise SkillError("기획안·이미지·검사 기록의 장수가 다릅니다.")
        deck = Presentation(confined(run, "cardnews-editable.pptx"))
        if len(deck.slides) != len(pages):
            raise SkillError("PPTX 장수가 이미지와 다릅니다.")
        if abs(deck.slide_width/deck.slide_height-width/height) > 0.001:
            result.errors.append(Issue("PPTX", "PPTX 판형이 이미지와 다릅니다."))
        for number, (page, image_name, slide) in enumerate(zip(pages, pngs, deck.slides), 1):
            image_path = confined(run, image_name)
            result.pages.append(PageImage(number, image_name, sha256(image_path.read_bytes())))
            if page["page"] != number or page["size"] != [width, height]:
                result.errors.append(Issue("SIZE", "페이지 번호 또는 크기 기록이 다릅니다.", number))
            with Image.open(image_path) as image:
                if image.format != "PNG" or image.size != (width, height):
                    result.errors.append(Issue("SIZE", "PNG 형식 또는 크기가 다릅니다.", number))
                for x, color in zip(policy["dots"]["x"], policy["dot_colors"]):
                    center = (round((x+10)*scale), round((policy["dots"]["y"]+10)*scale))
                    expected = tuple(int(color[j:j+2], 16) for j in (1,3,5))
                    if image.convert("RGB").getpixel(center) != expected:
                        result.errors.append(Issue("DOTS", "상자 밖 원의 위치 또는 색이 다릅니다.", number))
            if page.get("border_color") not in policy["border_colors"]:
                result.errors.append(Issue("STYLE", "제주 테두리 색을 확인하세요.", number))
            if page.get("overflow") or page.get("warnings"):
                result.errors.append(Issue("RENDER", "렌더러의 미해결 경고가 있습니다.", number))
            blocks: list[Block] = page["blocks"]
            glyphs = []
            for block in blocks:
                if not block["text"]:
                    continue
                if not block["glyph_bounds"] or block["overflow"]:
                    result.errors.append(Issue("TEXT", "글자 실측 기록이 없거나 넘침이 있습니다.", number))
                if not block["font_family"].startswith(policy["font_family"]):
                    result.errors.append(Issue("FONT", "Pretendard 사용 여부를 확인하세요.", number))
                if contrast(block["color"], block["background"])+0.001 < policy["contrast_min"]:
                    result.errors.append(Issue("CONTRAST", "글자 대비가 기준보다 낮습니다.", number))
                minimum = 0
                if "본문" in block["label"]:
                    minimum = policy["body_min_px"]
                elif any(word in block["label"] for word in ("그림", "캐릭터", "요청문")):
                    minimum = policy["diagram_min_px"]
                if block["size"]/scale+0.01 < minimum:
                    result.errors.append(Issue("FONT", "본문 또는 그림 글자가 기준보다 작습니다.", number))
                if "분류" in block["label"] and (block.get("align") != "center" or block.get("valign") != "middle"):
                    result.errors.append(Issue("LABEL", "분류 라벨이 가운데 정렬되지 않았습니다.", number))
                if re.search(r"(?:합니다|봅니다|입니다|습니다|습니까)[.!?。]?", block["text"]):
                    result.warnings.append(Issue("TONE", "합니다체 또는 인용문 종결을 문맥에서 확인하세요.", number))
                bounds = box(block["x"], block["y"], block["box_width"], block["box_height"])
                for glyph in block["glyph_bounds"]:
                    if not inside(glyph, bounds) or not inside(glyph, [0,0,width,height]):
                        result.errors.append(Issue("TEXT", "실제 글자가 배정 영역을 벗어납니다.", number))
                    glyphs.append(glyph)
            for i, glyph in enumerate(glyphs):
                if any(overlaps(glyph, other) for other in glyphs[i+1:]):
                    result.errors.append(Issue("OVERLAP", "글자끼리 겹칩니다.", number))
                    break
            pets = page.get("pets", [])
            if not pets or (number in (1,len(pages)) and set(p["id"] for p in pets) != set(policy["pet_ids"])):
                result.errors.append(Issue("PETS", "캐릭터 수 또는 표지·마지막 장의 3종을 확인하세요.", number))
            originals = read_json(SKILL / "assets/jeju-pets/manifest.json")["sha256"]
            for pet in pets:
                pet_box = box(pet["x"], pet["y"], pet["width"], pet["height"])
                if not inside(pet_box,[0,0,width,height]) or any(overlaps(pet_box,g) for g in glyphs):
                    result.errors.append(Issue("PETS", "캐릭터가 글자를 가리거나 화면을 벗어납니다.", number))
                asset = confined(run, pet["asset"])
                if sha256(asset.read_bytes()) != originals.get(asset.name) or pet["sha256"] != originals.get(asset.name):
                    result.errors.append(Issue("PETS", "배포된 캐릭터 원본과 다릅니다.", number))
            normalize = lambda value: re.sub(r"\s+", "", value)
            expected_text = [normalize(b["text"]) for b in blocks if b["text"]]
            actual_text = [normalize(shape.text) for shape in slide.shapes if shape.has_text_frame and shape.text]
            if expected_text != actual_text or len([s for s in slide.shapes if s.shape_type == 13]) != len(pets):
                result.errors.append(Issue("PPTX", "편집형 PPTX의 문구 또는 캐릭터 수가 다릅니다.", number))
            rendered = "".join(expected_text)
            planned = plan["slides"][number-1]
            if any(normalize(value) not in rendered for value in [planned["title"],*planned["bullets"]]):
                result.errors.append(Issue("COPY", "제목 또는 본문이 제작 기록에서 누락됐습니다.", number))
        for warning in report.get("citations", {}).get("warnings", []):
            result.warnings.append(Issue("SOURCE", warning))
    except (SkillError, OSError, KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        result.errors.append(Issue("STRUCTURE", f"입력·산출물 구조를 확인하세요: {type(error).__name__}"))
    return result


def init_project(project: Path, topic: str, mode: str, pages: int) -> Path:
    """Create an incomplete plan that cannot accidentally pass the normal build."""
    if not 1 <= pages <= 12 or not topic.strip() or mode not in ("topic","manuscript","revision"):
        raise SkillError("주제와 1~12장의 분량을 지정하세요.")
    project = project.resolve()
    if project.exists() or project.is_relative_to(SKILL):
        raise SkillError("스킬 밖의 새 작업 폴더를 지정하세요.")
    project.mkdir(parents=True)
    write_json(project/"brief.json", {"mode":mode,"topic":topic,"audience":"서귀포시 직원",
               "learning_goal":"","work_example":"","pages":pages,"style":"seogwipo-ai"})
    slides = [{"role":"cover" if i==0 else "closing" if i==pages-1 else "body",
               "title":"","bullets":[],"footnote":None} for i in range(pages)]
    write_json(project/"plan.json", {"series_title":f"오늘의 주제: {topic.strip()}","head_copy":"","slides":slides})
    (project/"storyboard.md").write_text("# 장별 기획\n\n| 장 | 전달할 내용 | 그림 | 캐릭터 역할 | 근거 |\n|---|---|---|---|---|\n" +
                 "".join(f"| {i} | | | | |\n" for i in range(1,pages+1)),encoding="utf-8")
    (project/"SOURCES.md").write_text("# 출처와 대조 기록\n\n출처별 확인일·위치와 카드별 대응을 작성함. 가상 예시와 제작자 제안을 구분함.\n",encoding="utf-8")
    return project


def inspect_to_folder(project: Path, run: Path, output: Path) -> Gate:
    """Write an inspection plus uncompleted review and every-page contact sheets."""
    from PIL import Image, ImageDraw, ImageOps

    if output.exists() or output.is_symlink():
        raise SkillError("검사 결과 폴더는 새 이름을 사용하세요.")
    if output.resolve().is_relative_to(SKILL) or output.resolve().is_relative_to(run.resolve()):
        raise SkillError("스킬과 초안 밖의 검사 폴더를 사용하세요.")
    result = inspect_run(project, run)
    output.mkdir(parents=True)
    write_json(output/"gate-report.json", {**asdict(result),"passed":result.passed})
    review = {"version":1,"run_id":result.run_id,"reviewer":"","sources_checked":False,
              "warning_notes":"","pages":[{"page":p.page,"png_sha256":p.sha256,
                      **{key:False for key in REVIEW_FIELDS}} for p in result.pages]}
    write_json(output/"review.json", review)
    mobile_width = read_json(POLICY)["mobile_width"]
    mobile_height = round(mobile_width / read_json(POLICY)["aspect_ratio"])
    previews = []
    for page in result.pages:
        with Image.open(confined(run.resolve(),page.image)) as image:
            mobile = ImageOps.contain(image.convert("RGB"),(mobile_width,mobile_height))
            mobile.save(output/f"page-{page.page:02d}.png")
            previews.append(mobile)
    for start in range(0,len(previews),4):
        sheet = Image.new("RGB",(mobile_width*2,(mobile_height+24)*2),"#eef3f1")
        draw = ImageDraw.Draw(sheet)
        for index, image in enumerate(previews[start:start+4]):
            x,y = (index%2)*mobile_width,(index//2)*(mobile_height+24)
            sheet.paste(image,(x,y+24))
            draw.text((x+8,y+6),str(start+index+1),fill="#172532")
        sheet.save(output/f"contact-{start//4+1:02d}.png")
    return result


def deliver(project: Path, run: Path, review_file: Path, output: Path) -> Path:
    """Copy only verified build files after current, complete review records."""
    if output.exists() or output.is_symlink():
        raise SkillError("전달 폴더는 새 이름을 사용하세요.")
    result = inspect_run(project,run)
    if not result.passed:
        raise SkillError("자동 검사 실패: 전달 폴더를 만들지 않았습니다.")
    review = read_json(review_file)
    allowed = {"version","run_id","reviewer","sources_checked","warning_notes","pages"}
    if not isinstance(review,dict) or set(review) != allowed:
        raise SkillError("검수 기록의 필드가 올바르지 않습니다.")
    if (review.get("version") != 1 or review.get("run_id") != result.run_id or
            not isinstance(review.get("reviewer"),str) or not review["reviewer"].strip() or
            review.get("sources_checked") is not True):
        raise SkillError("현재 초안의 출처 검수와 검수자 기록이 필요합니다.")
    if result.warnings and (not isinstance(review.get("warning_notes"),str) or not review["warning_notes"].strip()):
        raise SkillError("경고의 문맥 검토 결과를 기록하세요.")
    recorded = review.get("pages",[])
    if not isinstance(recorded,list) or len(recorded) != len(result.pages):
        raise SkillError("모든 장의 검수 기록이 필요합니다.")
    for expected, actual in zip(result.pages,recorded):
        if not isinstance(actual,dict) or set(actual) != {"page","png_sha256",*REVIEW_FIELDS}:
            raise SkillError("페이지 검수 기록의 필드가 올바르지 않습니다.")
        if (actual.get("page") != expected.page or actual.get("png_sha256") != expected.sha256 or
                any(actual.get(key) is not True for key in REVIEW_FIELDS)):
            raise SkillError("페이지 순서·해시·검수 완료 항목을 확인하세요.")
    output = output.resolve()
    if output.is_relative_to(SKILL) or output.is_relative_to(run.resolve()):
        raise SkillError("스킬과 초안 밖의 전달 폴더를 사용하세요.")
    output.parent.mkdir(parents=True,exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".card-delivery-",dir=output.parent)).resolve()
    if stage.parent != output.parent:
        raise SkillError("전달 준비 폴더의 위치가 다릅니다.")
    cards = stage/"cards"
    cards.mkdir()
    manifest = read_json(confined(run.resolve(),"manifest.json"))
    for name in [*manifest["files"],"manifest.json","cardnews.zip"]:
        destination = cards / name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(confined(run.resolve(),name),destination)
    verify_build(cards)
    qc = stage/"qc"
    qc.mkdir()
    write_json(qc/"gate-report.json",{**asdict(result),"passed":True})
    write_json(qc/"review.json",review)
    stage.rename(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="카드뉴스 기획·검사·전달 도구")
    commands = parser.add_subparsers(dest="command",required=True)
    init = commands.add_parser("init")
    init.add_argument("--project",type=Path,required=True)
    init.add_argument("--topic",required=True)
    init.add_argument("--mode",choices=("topic","manuscript","revision"),default="topic")
    init.add_argument("--pages",type=int,default=8)
    for name in ("inspect","deliver"):
        command = commands.add_parser(name)
        command.add_argument("--project",type=Path,required=True)
        command.add_argument("--run",type=Path,required=True)
        command.add_argument("--out",type=Path,required=True)
        if name == "deliver":
            command.add_argument("--review",type=Path,required=True)
    args = parser.parse_args()
    try:
        match args.command:
            case "init":
                output = init_project(args.project,args.topic,args.mode,args.pages)
            case "inspect":
                result = inspect_to_folder(args.project,args.run,args.out)
                print(json.dumps({"passed":result.passed,"errors":len(result.errors),
                                  "warnings":len(result.warnings),"pages":len(result.pages)},ensure_ascii=False))
                return 0 if result.passed else 1
            case "deliver":
                output = deliver(args.project,args.run,args.review,args.out)
        print(json.dumps({"output":str(output)},ensure_ascii=False))
        return 0
    except (SkillError,OSError,KeyError,TypeError,ValueError) as error:
        print(str(error) if isinstance(error,SkillError) else "입력 파일이나 폴더를 확인하세요.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
