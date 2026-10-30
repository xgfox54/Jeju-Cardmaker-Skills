"""v1.1 project builder. Local-only, measured Korean text, no browser or paid API.

The plan is the single input; PNG/JPEG, HTML and both decks are built together.
The integrity manifest detects accidental edits, not malicious replacement/signatures.
"""
from __future__ import annotations

import html
import re
import shutil
import tempfile
import zipfile
from io import BytesIO
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from rp_core import (VERSION, SkillError, canonical, now, plan_hash, plan_strings,
                     read_json, require_approval, review_markdown, sha256,
                     source_summary, validate_plan, validate_source, write_json)
from rp_render import check_glyphs, fit_block, load_profile, resolve_fonts

PRESETS = {"legacy": (1000, 1350), "portrait": (1080, 1350), "portrait-2x": (2160, 2700)}
ENGINE = "Jeju_Cardmaker-studio-v1"


def citation_audit(plan: dict, notes: str | None) -> dict:
    """Check bracketed IDs exist. This is not a fact checker or URL verifier."""
    available = set(re.findall(r"(?m)^\s*(?:#{1,6}\s*)?\[(\d+)\]", notes or ""))
    used = set()
    warnings = []
    for index, slide in enumerate(plan["slides"], 1):
        footnote = slide.get("footnote") or ""
        ids = set(re.findall(r"\[(\d+)\]", footnote))
        used |= ids
        if not footnote.strip():
            warnings.append(f"{index}장: 출처/각주 없음. 사실 주장과 원문을 대조하세요.")
        if notes is not None and ids - available:
            raise SkillError(f"{index}장: SOURCES.md에 없는 출처 번호 {sorted(ids - available)}")
    if notes is None:
        warnings.append("SOURCES.md 없음: 카드별 근거 대조 기록은 사용자가 별도로 확인해야 합니다.")
    elif not used:
        warnings.append("번호형 출처 연결 없음: 서술형 출처는 자동 연결 검사를 하지 않았습니다.")
    return {"referenced_ids": sorted(used, key=int), "defined_ids": sorted(available, key=int),
            "warnings": warnings, "factual_accuracy_verified": False,
            "urls_fetched": False, "notice": "번호 연결 검사일 뿐, 주장·출처 내용의 일치 검증은 아닙니다."}


def contrast(a: str, b: str) -> float:
    def lum(value: str) -> float:
        rgb = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(x * k for x, k in zip(linear, (.2126, .7152, .0722)))
    x, y = sorted((lum(a), lum(b)))
    return (y + .05) / (x + .05)


@lru_cache(maxsize=16)
def font_family(path: Path) -> str:
    from fontTools.ttLib import TTFont
    f = TTFont(str(path), fontNumber=0, lazy=True)
    try:
        return f["name"].getDebugName(16) or f["name"].getDebugName(1) or "Malgun Gothic"
    finally:
        f.close()


def render_card(plan: dict, index: int, profile: dict, fonts: tuple[Path, Path],
                size: tuple[int, int], status: str, hide_status: bool = False,
                logo: Path | None = None) -> tuple[Any, dict]:
    if profile.get("template") == "seogwipo-ai":
        from rp_seogwipo import render_learning_card
        return render_learning_card(plan, index, profile, fonts, size, status, hide_status, logo)
    from PIL import Image, ImageDraw, ImageFont
    width, height = size
    scale = width / 1080
    logical_h = height / scale
    image = Image.new("RGB", size, profile["background"])
    draw = ImageDraw.Draw(image)
    slide = plan["slides"][index]
    blocks, shapes = [], []
    px = lambda v: round(v * scale)

    def rect(x, y, w, h, fill, radius=0):
        bounds = (px(x), px(y), px(x+w), px(y+h))
        if radius:
            draw.rounded_rectangle(bounds, radius=px(radius), fill=fill)
        else:
            draw.rectangle(bounds, fill=fill)
        shapes.append({"x": bounds[0], "y": bounds[1], "width": px(w), "height": px(h),
                       "fill": fill, "radius": px(radius)})

    def measure(text, w, h, hi, lo, strong, label):
        return fit_block(draw, text, fonts[1 if strong else 0], px(w), px(h),
                         px(hi), max(1, px(lo)), f"{index+1}장 {label}")

    def text(text_value, x, y, w, h, hi, lo, label, strong=False, color=None,
             background=None, spec=None):
        color = color or profile["text"]
        background = background or profile["background"]
        spec = spec or measure(text_value, w, h, hi, lo, strong, label)
        path = fonts[1 if strong else 0]
        font = ImageFont.truetype(str(path), spec["size"])
        glyph_bounds = []
        for j, line in enumerate(spec["lines"]):
            xx, yy = px(x), px(y) + j * spec["line_height"]
            bbox = draw.textbbox((xx, yy), line, font=font, anchor="lt")
            if bbox[0] < px(x):
                # Glyphs such as a lowercase j hang left of their origin. fit_block
                # reserved that space, so move the line right to keep the ink inside the box.
                shift = px(x) - bbox[0]
                xx += shift
                bbox = (bbox[0] + shift, bbox[1], bbox[2] + shift, bbox[3])
            if (bbox[0] < px(x) - 1 or bbox[1] < px(y) - 1 or
                    bbox[2] > px(x+w) + 1 or bbox[3] > px(y+h) + 1):
                raise SkillError(f"{index+1}장 {label}: 실제 글자 영역이 경계를 초과했습니다.")
            glyph_bounds.append(list(bbox))
            draw.text((xx, yy), line, font=font, fill=color, anchor="lt")
        blocks.append({**spec, "text": text_value, "x": px(x), "y": px(y),
                       "box_width": px(w), "box_height": px(h), "bold": strong,
                       "color": color, "background": background,
                       "contrast_ratio": round(contrast(color, background), 3),
                       "font_family": font_family(path), "glyph_bounds": glyph_bounds,
                       "overflow": False})
        return spec["height"] / scale

    rect(0, 0, 1080, 12, profile["primary"])
    for n, key in enumerate(("primary", "secondary", "accent")):
        rect(n*360, logical_h-10, 360, 10, profile[key])
    if not hide_status:
        text("검토용 초안" if status == "draft" else "문안 승인본", 64, 45, 550, 40, 24, 20,
             "상태", strong=True)
    text(f"{index+1:02d} / {len(plan['slides']):02d}", 865, 45, 151, 40, 24, 20, "쪽수")
    text(plan["series_title"], 64, 120, 952, 92, 30, 23, "시리즈", strong=True,
         color=profile["primary"] if contrast(profile["primary"], profile["background"]) >= 4.5 else profile["text"])
    y = 244
    if index == 0 and plan["head_copy"]:
        head = text(plan["head_copy"], 64, 222, 952, 90, 29, 23, "헤드카피")
        y = 222 + head + 35
    title_h = text(slide["title"], 64, y, 952, 260,
                   84 if slide["role"] in {"cover", "closing"} else 74, 42, "제목", strong=True)
    y += title_h + 28
    rect(64, y, 88, 7, profile["accent"])
    y += 42
    body_bottom = logical_h - 228
    bullets = slide.get("bullets", [])
    if bullets:
        remaining = body_bottom - y
        fits = None
        for fs in range(38, 29, -1):
            specs = [measure(b, 868, 2000, fs, fs, False, "본문") for b in bullets]
            needed = sum(s["height"]/scale + 40 for s in specs) + 16*(len(specs)-1)
            if needed <= remaining:
                fits = specs
                break
        if fits is None:
            raise SkillError(f"{index+1}장 본문: 최소 30px(1080px 기준)에서도 넘칩니다. 문장을 줄이거나 장을 나누세요.")
        for n, (bullet, spec) in enumerate(zip(bullets, fits), 1):
            box_h = spec["height"]/scale + 40
            rect(54, y, 972, box_h, "#FFFFFF", 18)
            rect(54, y+18, 5, box_h-36, profile[("primary", "secondary", "accent")[(n-1)%3]], 2)
            text(bullet, 84, y+20, 868, box_h-40, 38, 30, f"본문 {n}",
                 background="#FFFFFF", spec=spec)
            y += box_h + 16
    note = slide.get("footnote") or ""
    text(note, 64, logical_h-192, 952, 91, 23, 19, "출처/각주")
    footer = " · ".join(x for x in (profile["agency"], profile["footer"]) if x)
    text(footer, 64, logical_h-66, 730 if logo else 952, 36, 20, 16, "기관/푸터")
    logo_spec = None
    if logo:
        if logo.stat().st_size > 10*1024*1024:
            raise SkillError("로고 파일은 10MB 이하여야 합니다.")
        with Image.open(logo) as raw:
            icon = raw.convert("RGBA")
            icon.thumbnail((px(170), px(58)), Image.Resampling.LANCZOS)
            xx, yy = width-px(64)-icon.width, height-px(83)
            image.paste(icon, (xx, yy), icon)
            logo_spec = {"x": xx, "y": yy, "width": icon.width, "height": icon.height}
    warnings = [f"{index+1}장 {b['label']}: 글자 대비 {b['contrast_ratio']}" for b in blocks
                if b["text"] and b["contrast_ratio"] < 4.5]
    return image, {"page": index+1, "size": list(size), "background": profile["background"],
                   "blocks": blocks, "shapes": shapes, "logo": logo_spec,
                   "warnings": warnings, "overflow": False}


def editable_deck(reports: list[dict], size: tuple[int, int], logo: Path | None) -> bytes:
    """Native PowerPoint text/shapes, not a flattened image. Does not embed fonts."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_AUTO_SIZE, MSO_ANCHOR, PP_ALIGN
    from pptx.util import Inches, Pt
    from pptx.oxml.xmlchemy import OxmlElement
    from pptx.oxml.ns import qn
    prs = Presentation()
    w, h = size
    unit = Inches(8) / w
    prs.slide_width = Inches(8)
    prs.slide_height = round(h * unit)
    for report in reports:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string(report["background"][1:])
        for spec in report["shapes"]:
            kind = (MSO_SHAPE.OVAL if spec.get("kind") == "ellipse" else
                    MSO_SHAPE.ROUNDED_RECTANGLE if spec["radius"] else MSO_SHAPE.RECTANGLE)
            shape = slide.shapes.add_shape(kind,
                round(spec["x"]*unit), round(spec["y"]*unit), round(spec["width"]*unit), round(spec["height"]*unit))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor.from_string(spec["fill"][1:])
            shape.line.fill.background()
            shape._element.spPr.append(OxmlElement("a:effectLst"))
            style = shape._element.find(qn("p:style"))
            if style is not None:
                effect = style.find(qn("a:effectRef"))
                if effect is not None:
                    effect.set("idx", "0")
            if spec["radius"]:
                shape.adjustments[0] = min(.5, spec["radius"] / max(1, min(spec["width"], spec["height"])))
        for spec in report["blocks"]:
            if not spec["text"]:
                continue
            box = slide.shapes.add_textbox(round(spec["x"]*unit), round(spec["y"]*unit),
                round(spec["box_width"]*unit), round(spec["box_height"]*unit))
            box.name = spec["label"]
            frame = box.text_frame
            frame.clear()
            frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
            frame.auto_size = MSO_AUTO_SIZE.NONE
            frame.word_wrap = False
            frame.vertical_anchor = MSO_ANCHOR.MIDDLE if spec.get("valign") == "middle" else MSO_ANCHOR.TOP
            for n, line in enumerate(spec["lines"]):
                p = frame.paragraphs[0] if n == 0 else frame.add_paragraph()
                p.text = line
                p.alignment = PP_ALIGN.CENTER if spec.get("align") == "center" else PP_ALIGN.LEFT
                p.space_before = p.space_after = Pt(0)
                p.line_spacing = Pt(spec["line_height"] * 8 / w * 72)
                p.font.name = spec["font_family"]
                p.font.size = Pt(spec["size"] * 8 / w * 72)
                p.font.bold = spec["bold"]
                p.font.color.rgb = RGBColor.from_string(spec["color"][1:])
        if logo and report["logo"]:
            b = report["logo"]
            slide.shapes.add_picture(str(logo), round(b["x"]*unit), round(b["y"]*unit),
                width=round(b["width"]*unit), height=round(b["height"]*unit))
        for pet in report.get("pets", []):
            source = Path(__file__).resolve().parents[1] / pet["asset"]
            picture = slide.shapes.add_picture(str(source), round(pet["x"]*unit), round(pet["y"]*unit),
                width=round(pet["width"]*unit), height=round(pet["height"]*unit))
            picture.name = pet["name"]
        slide.notes_slide.notes_text_frame.text = "문안 편집용입니다. 편집 후 글자 넘침과 폰트를 재검수하세요. PNG와 자동 동기화되지 않습니다."
    stream = BytesIO()
    prs.save(stream)
    return stream.getvalue()


def image_deck(images: list[Path], size: tuple[int, int]) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    prs.slide_width = Inches(8)
    prs.slide_height = round(Inches(8) * size[1]/size[0])
    for path in images:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.shapes.add_picture(str(path), 0, 0, width=prs.slide_width, height=prs.slide_height)
    stream = BytesIO()
    prs.save(stream)
    return stream.getvalue()


def preview_html(plan: dict, paths: list[str], status: str, notes: str | None, digest: str) -> str:
    cards = []
    for i, (slide, rel) in enumerate(zip(plan["slides"], paths), 1):
        esc = html.escape
        plain = " ".join([slide["title"], *slide["bullets"], slide.get("takeaway", ""), slide.get("footnote") or ""])
        body = "".join(f"<p>{esc(t)}</p>" for t in [*slide["bullets"], slide.get("takeaway", "")] if t)
        jpg = rel.replace("png/", "jpeg/").replace(".png", ".jpg")
        cards.append(f'<article><img src="{esc(rel)}" alt="{esc(plain, quote=True)}" loading="lazy">'
                     f'<p><a download href="{esc(rel)}">{i}장 PNG</a> · <a download href="{esc(jpg)}">JPEG</a></p>'
                     f'<details><summary>{i}. {esc(slide["title"])}</summary>{body}<p>{esc(slide.get("footnote") or "")}</p></details></article>')
    safe_notes = html.escape(notes or "출처 기록 없음")
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{html.escape(plan['series_title'])}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#eef2f5;color:#172532;font-family:system-ui,sans-serif}}
header,main,aside{{max-width:1450px;margin:auto;padding:24px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}}
article{{min-width:0}}img{{width:100%;height:auto;box-shadow:0 6px 22px #0001}}p{{line-height:1.7}}details{{background:white;padding:12px}}
a{{color:#0173bc}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px}}code{{overflow-wrap:anywhere}}
</style></head><body><header><h1>{html.escape(plan['series_title'])}</h1><p>상태: {html.escape(status)} · {len(paths)}장 · 로컬 제작 / 자동 게시 없음</p>
<p><a download href="cardnews.zip">전체 ZIP</a> · <a href="review.md">문안</a> · <a href="render-report.json">검사 보고</a></p>
<p>기획안 해시: <code>{digest}</code><br>이 미리보기는 생성 당시 이미지입니다. plan.json 수정 후 build 명령을 다시 실행하세요. 브라우저에서 자동 갱신하지 않습니다.</p></header>
<main>{''.join(cards)}</main><aside><h2>출처 기록</h2><pre>{safe_notes}</pre></aside></body></html>'''


def build_project(project: str | Path, output: str | Path, *, preset: str = "portrait-2x",
                  profile_name: str = "seogwipo-ai", source_path: str | None = None,
                  approval_path: str | None = None, final: bool = False,
                  hide_status: bool = False, show_status: bool = False,
                  font: str | None = None, bold_font: str | None = None,
                  logo_path: str | None = None, pptx: bool = True) -> Path:
    project = Path(project).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise SkillError("project는 plan.json이 있는 폴더여야 합니다.")
    if preset not in PRESETS:
        raise SkillError("알 수 없는 출력 규격입니다.")
    target = Path(output).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise SkillError("결과 폴더가 이미 있습니다. 새 이름을 지정하세요.")
    # Card images carry no review stamp unless explicitly requested; manifest status still records it.
    hide_status = hide_status or not show_status
    plan = validate_plan(read_json(project/"plan.json"))
    notes_path = project/"SOURCES.md"
    notes = None
    if notes_path.exists():
        if not notes_path.is_file() or notes_path.stat().st_size > 2*1024*1024:
            raise SkillError("SOURCES.md는 2MB 이하의 텍스트여야 합니다.")
        notes = notes_path.read_text(encoding="utf-8-sig")
    audit = citation_audit(plan, notes)
    source = validate_source(read_json(source_path)) if source_path else None
    approval = read_json(approval_path) if approval_path else None
    if final:
        if source is None:
            raise SkillError("승인본에는 --source와 --approval이 필요합니다.")
        require_approval(plan, source, approval)
    status = "copy-approved" if final else "draft"
    profile = load_profile(profile_name)
    if profile.get("template") != "seogwipo-ai" and any("layout" in s or "takeaway" in s for s in plan["slides"]):
        raise SkillError("layout/takeaway 문안은 --profile seogwipo-ai로 제작하세요.")
    fonts = resolve_fonts(font, bold_font,
                          required_family="Pretendard" if profile.get("template") == "seogwipo-ai" else None)
    check_glyphs(fonts, plan_strings(plan) + [profile["agency"], profile["footer"], "검토용 초안 문안 승인본 · 0123456789 / "])
    logo = Path(logo_path).expanduser().resolve(strict=True) if logo_path else None
    size = PRESETS[preset]
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".Jeju_Cardmaker-build-", dir=target.parent))
    try:
        paths, reports = [], []
        for i, slide in enumerate(plan["slides"]):
            image, report = render_card(plan, i, profile, fonts, size, status, hide_status, logo)
            for folder, ext, kind in (("png", "png", "PNG"), ("jpeg", "jpg", "JPEG")):
                rel = f"{folder}/{i+1:02d}_{slide['role']}.{ext}"
                dest = stage/rel
                dest.parent.mkdir(exist_ok=True)
                options = {"quality": 95, "subsampling": 0, "optimize": True} if kind == "JPEG" else {"optimize": True}
                image.save(dest, format=kind, **options)
                if kind == "PNG":
                    paths.append(rel)
            image.close()
            reports.append(report)
        write_json(stage/"plan.json", plan)
        write_json(stage/"profile.json", profile)
        write_json(stage/"source-summary.json", source_summary(source))
        report = {"version": VERSION, "preset": preset, "size": list(size),
                  "fonts": [p.name for p in fonts], "pages": reports, "citations": audit,
                  "factual_accuracy_verified": False, "pptx_visual_verified": False}
        write_json(stage/"render-report.json", report)
        (stage/"review.md").write_text(review_markdown(plan, source), encoding="utf-8")
        if notes is not None:
            (stage/"SOURCES.md").write_text(notes, encoding="utf-8")
        if final:
            write_json(stage/"approval.json", approval)
        if profile.get("template") == "seogwipo-ai":
            from rp_seogwipo import PET_FILES, PET_ROOT, validate_pets
            validate_pets()
            pet_output = stage/"assets"/"jeju-pets"
            pet_output.mkdir(parents=True)
            for filename in PET_FILES:
                shutil.copyfile(PET_ROOT/filename, pet_output/filename)
        if pptx:
            (stage/"cardnews-editable.pptx").write_bytes(editable_deck(reports, size, logo))
            (stage/"cardnews-preview.pptx").write_bytes(image_deck([stage/p for p in paths], size))
        (stage/"preview.html").write_text(preview_html(plan, paths, status, notes, plan_hash(plan)), encoding="utf-8")
        (stage/"ABOUT.txt").write_text(f"Jeju_Cardmaker v{VERSION}\nPNG/JPEG: 로컬 카드 렌더링.\n"
            "cardnews-editable.pptx: 텍스트·도형 편집용. 편집/폰트 대체 후 직접 시각 검수.\n"
            "cardnews-preview.pptx: 이미지형 검토용.\n"
            "단일 원본은 plan.json. PPTX 수정은 JSON/PNG에 역반영되지 않습니다.\n"
            "검사 성공은 사실·법률·게시 승인이나 접근성 인증이 아닙니다.\n"
            "SOURCES.md는 작업자가 작성한 근거 기록이며 최신성 자동 확인은 하지 않습니다.\n"
            "폰트·원문 source.json·API 키·미승인 폴더 파일은 포함하지 않습니다.\n", encoding="utf-8")
        files = sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file())
        write_json(stage/"manifest.json", {"version": VERSION, "engine": ENGINE, "status": status,
            "created_at": now(), "preset": preset, "size": list(size), "pages": len(paths),
            "plan_sha256": plan_hash(plan), "notes_sha256": sha256(notes.encode()) if notes is not None else None,
            "files": {rel: sha256((stage/rel).read_bytes()) for rel in files},
            "api_calls": 0, "fonts_embedded": False,
            "notice": "수정 감지용 해시이며 전자서명·신원인증이 아닙니다."})
        # The manifest is not a digital signature. Only build-produced files enter the ZIP.
        with zipfile.ZipFile(stage/"cardnews.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for rel in files + ["manifest.json"]:
                z.write(stage/rel, rel)
        verify_build(stage)
        stage.rename(target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return target


def verify_build(path: str | Path) -> dict:
    """Verify all declared bytes and ZIP entries. Never export unlisted neighbors."""
    root = Path(path).expanduser().resolve(strict=True)
    def confined(rel: str) -> Path:
        part = PurePosixPath(rel)
        if part.is_absolute() or ".." in part.parts or "\\" in rel:
            raise SkillError("잘못된 산출물 경로입니다.")
        candidate = root.joinpath(*part.parts)
        if not candidate.is_file() or candidate.is_symlink() or not candidate.resolve().is_relative_to(root):
            raise SkillError(f"산출물 누락 또는 허용되지 않는 경로: {rel}")
        if any(p.is_symlink() for p in candidate.parents if p != root and p.is_relative_to(root)):
            raise SkillError("하위 심볼릭 링크는 허용하지 않습니다.")
        return candidate
    manifest_path = confined("manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("engine") != ENGINE or not isinstance(manifest.get("files"), dict):
        raise SkillError("v1.1 build 결과가 아닙니다.")
    fixed = {"plan.json", "profile.json", "source-summary.json", "render-report.json", "review.md",
             "SOURCES.md", "approval.json", "preview.html", "cardnews-editable.pptx", "cardnews-preview.pptx", "ABOUT.txt"}
    for rel, digest in manifest["files"].items():
        from rp_seogwipo import PET_FILES
        pet_files = {f"assets/jeju-pets/{n}" for n in PET_FILES}
        if rel not in fixed | pet_files and not re.fullmatch(r"(?:png/\d{2}_(?:cover|body|closing)\.png|jpeg/\d{2}_(?:cover|body|closing)\.jpg)", rel):
            raise SkillError("허용되지 않은 파일이 manifest에 있습니다.")
        if sha256(confined(rel).read_bytes()) != digest:
            raise SkillError(f"생성 후 변경된 파일: {rel}. 새 폴더로 다시 build 하세요.")
    plan = validate_plan(read_json(confined("plan.json")))
    if plan_hash(plan) != manifest.get("plan_sha256") or len(plan["slides"]) != manifest.get("pages"):
        raise SkillError("기획안/장수와 manifest 불일치")
    with zipfile.ZipFile(confined("cardnews.zip")) as z:
        expected = set(manifest["files"]) | {"manifest.json"}
        if set(z.namelist()) != expected or len(z.namelist()) != len(expected):
            raise SkillError("ZIP 파일 목록이 생성 기록과 다릅니다.")
        for rel in expected:
            if sha256(z.read(rel)) != sha256(confined(rel).read_bytes()):
                raise SkillError(f"ZIP 내용이 결과 파일과 다릅니다: {rel}")
    return {"ok": True, "pages": len(plan["slides"]), "size": manifest["size"],
            "checked_files": len(manifest["files"]), "factual_accuracy_verified": False}
