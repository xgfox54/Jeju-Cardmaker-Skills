"""Deterministic text-card rendering with explicit overflow and glyph checks.

This is an original adapter renderer, not a copy of the upstream renderer.
It accepts the upstream CardNewsPlan JSON contract. No network/AI calls.
"""
from __future__ import annotations

import html
import math
import os
import re
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from rp_core import (SkillError, VERSION, canonical, now, plan_hash, plan_strings,
                     read_json, require_approval, review_markdown, sha256,
                     source_summary, validate_plan, write_json)

WIDTH, HEIGHT = 1000, 1350
ROOT = Path(__file__).resolve().parents[1]


def load_profile(value: str) -> dict[str, Any]:
    path = ROOT / "assets" / "profiles" / f"{value}.json" if value in {"neutral", "jeju", "seogwipo-ai"} else Path(value).expanduser()
    data = read_json(path)
    for key in ("name", "agency", "footer", "primary", "secondary", "accent", "background", "text"):
        if not isinstance(data.get(key), str):
            raise SkillError(f"프로필의 {key} 문자열이 필요합니다.")
    for key in ("primary", "secondary", "accent", "background", "text"):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", data[key]):
            raise SkillError(f"프로필 색상 {key}는 #RRGGBB 형식이어야 합니다.")
    if len(data["agency"]) > 50 or len(data["footer"]) > 90:
        raise SkillError("프로필 기관명/푸터가 너무 깁니다.")
    if data.get("template") not in (None, "seogwipo-ai"):
        raise SkillError("지원하지 않는 프로필 템플릿입니다.")
    return data


def resolve_fonts(regular: str | None = None, bold: str | None = None,
                  required_family: str | None = None) -> tuple[Path, Path]:
    if required_family == "Pretendard":
        return resolve_pretendard(regular, bold)
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    pairs = [(windows / "malgun.ttf", windows / "malgunbd.ttf"),
             (Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"), Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")),
             (Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"), Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")),
             (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"))]
    if regular:
        rp = Path(regular).expanduser().resolve(strict=True)
        bp = Path(bold).expanduser().resolve(strict=True) if bold else rp
        if not rp.is_file() or not bp.is_file():
            raise SkillError("폰트 경로가 일반 파일이 아닙니다.")
        return rp, bp
    for rp, bp in pairs:
        if rp.is_file():
            return rp, bp if bp.is_file() else rp
    raise SkillError("한글 폰트를 찾지 못했습니다. --font로 합법적으로 설치된 TTF/OTF/TTC 경로를 지정하세요. 폰트 파일은 배포하지 않습니다.")


def resolve_pretendard(regular: str | None = None, bold: str | None = None) -> tuple[Path, Path]:
    """Use static Regular/Bold files; never silently substitute another family."""
    from fontTools.ttLib import TTFont
    if bool(regular) != bool(bold):
        raise SkillError("Pretendard Regular와 Bold를 --font 및 --bold-font로 함께 지정하세요.")
    if regular and bold:
        candidates = [(Path(regular).expanduser(), Path(bold).expanduser())]
    else:
        local_app = Path(os.environ.get("LOCALAPPDATA", str(Path.home()/"AppData/Local")))
        directories = [Path(os.environ.get("WINDIR", r"C:\Windows"))/"Fonts",
                       local_app/"Microsoft/Windows/Fonts", Path.home()/"Library/Fonts",
                       Path("/Library/Fonts"), Path.home()/".local/share/fonts",
                       Path("/usr/local/share/fonts"), Path("/usr/share/fonts")]
        candidates = []
        for directory in directories:
            if directory.is_dir():
                for rp in sorted(directory.rglob("Pretendard-Regular.*")):
                    if rp.suffix.lower() in (".ttf", ".otf"):
                        candidates.append((rp, rp.with_name("Pretendard-Bold"+rp.suffix)))
    for rp, bp in candidates:
        if not rp.is_file() or not bp.is_file():
            continue
        valid = True
        for path, weight in ((rp, 400), (bp, 700)):
            font = TTFont(str(path), lazy=True)
            try:
                family = font["name"].getDebugName(16) or font["name"].getDebugName(1)
                valid = valid and family == "Pretendard" and font["OS/2"].usWeightClass == weight and "fvar" not in font
            finally:
                font.close()
        if valid:
            return rp.resolve(), bp.resolve()
    raise SkillError("Pretendard Regular/Bold 정적 폰트가 필요합니다. 공식 배포본을 설치하거나 --font와 --bold-font 경로를 지정하세요. 다른 폰트로 대체하지 않았습니다.")


def check_glyphs(paths: tuple[Path, Path], strings: list[str]) -> None:
    from fontTools.ttLib import TTFont
    needed = {ord(c) for text in strings for c in text if not c.isspace()}
    for path in set(paths):
        font = TTFont(str(path), fontNumber=0, lazy=True)
        try:
            cmap = font.getBestCmap() or {}
            missing = needed - set(cmap)
        finally:
            font.close()
        if missing:
            chars = " ".join(chr(c) for c in sorted(missing)[:16])
            raise SkillError(f"폰트 {path.name}에 없는 글자: {chars}. 폰트를 바꾸거나 이모지를 일반 글자로 바꾸세요.")


def wrap_text(draw: Any, text: str, font: Any, width: int) -> list[str]:
    """Measured, CJK-safe wrapping. Only wrapping whitespace is discarded."""
    result: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4).split("\n"):
        if not paragraph:
            result.append("")
            continue
        line = ""
        for char in paragraph:
            if ink_width(draw, line + char, font) <= width:
                line += char
                continue
            if not line:
                raise SkillError("한 글자도 들어가지 않는 텍스트 영역입니다.")
            cut = line.rfind(" ")
            # Prefer word boundaries for Latin text, while allowing CJK line breaks.
            if cut > len(line) // 2:
                result.append(line[:cut].rstrip())
                line = line[cut + 1:] + char
            else:
                result.append(line.rstrip())
                line = char.lstrip()
            if line and ink_width(draw, line, font) > width:
                raise SkillError("텍스트 줄 너비를 초과했습니다.")
        result.append(line.rstrip())
    return result


def left_overhang(draw: Any, line: str, font: Any) -> int:
    """Pixels a line's first glyph extends left of its origin, such as a lowercase j."""
    if not line:
        return 0
    return max(0, -draw.textbbox((0, 0), line, font=font, anchor="lt")[0])


def ink_width(draw: Any, line: str, font: Any) -> float:
    """Width a line needs after it is shifted right by its left overhang."""
    if not line:
        return 0
    right = draw.textbbox((0, 0), line, font=font, anchor="lt")[2]
    return max(draw.textlength(line, font=font), right) + left_overhang(draw, line, font)


def fit_block(draw: Any, text: str, font_path: Path, width: int, height: int,
              max_size: int, min_size: int, label: str) -> dict[str, Any]:
    from PIL import ImageFont
    if not text:
        return {"lines": [], "size": max_size, "line_height": 0, "height": 0, "width": 0, "label": label}
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap_text(draw, text, font, width)
        line_height = max(math.ceil(size * 1.4), max(font.getbbox(line or "Ag가")[3] - font.getbbox(line or "Ag가")[1] for line in lines) + 5)
        actual_height = len(lines) * line_height
        if actual_height <= height and all(ink_width(draw, line, font) <= width for line in lines):
            return {"lines": lines, "size": size, "line_height": line_height,
                    "height": actual_height, "width": width, "label": label}
    raise SkillError(f"{label}: 최소 {min_size}px에서도 텍스트가 넘칩니다. 내용을 삭제하지 않았습니다. 문구를 줄이거나 페이지를 나누세요.")


def _draw_block(draw: Any, block: dict[str, Any], x: int, y: int, path: Path, color: str) -> None:
    from PIL import ImageFont
    font = ImageFont.truetype(str(path), block["size"])
    for j, line in enumerate(block["lines"]):
        draw.text((x + left_overhang(draw, line, font), y + j * block["line_height"]), line,
                  font=font, fill=color, anchor="lt")


def render_page(plan: dict[str, Any], index: int, profile: dict[str, Any], fonts: tuple[Path, Path],
                status: str, logo_path: str | None = None) -> tuple[Any, list[dict[str, Any]]]:
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (WIDTH, HEIGHT), profile["background"])
    draw = ImageDraw.Draw(image)
    regular, bold = fonts
    slide = plan["slides"][index]
    reports: list[dict[str, Any]] = []

    def block(text: str, x: int, y: int, w: int, h: int, hi: int, lo: int,
              label: str, *, strong: bool = False, color: str | None = None) -> int:
        path = bold if strong else regular
        spec = fit_block(draw, text, path, w, h, hi, lo, f"{index + 1}쪽 {label}")
        _draw_block(draw, spec, x, y, path, color or profile["text"])
        reports.append({**spec, "x": x, "y": y, "box_height": h, "overflow": False})
        return spec["height"]

    draw.rectangle((0, 0, WIDTH, 14), fill=profile["primary"])
    draw.rectangle((0, HEIGHT - 10, WIDTH // 3, HEIGHT), fill=profile["primary"])
    draw.rectangle((WIDTH // 3, HEIGHT - 10, WIDTH * 2 // 3, HEIGHT), fill=profile["secondary"])
    draw.rectangle((WIDTH * 2 // 3, HEIGHT - 10, WIDTH, HEIGHT), fill=profile["accent"])
    label = "검토용 초안" if status == "draft" else "문안 승인본"
    block(label, 64, 52, 330, 40, 24, 20, "상태", strong=True, color=profile["primary"])
    block(f"{index + 1:02d} / {len(plan['slides']):02d}", 820, 52, 120, 40, 24, 20, "쪽수")
    series_h = block(plan["series_title"], 64, 126, 872, 94, 30, 20, "시리즈명", strong=True, color=profile["primary"])
    y = max(216, 126 + series_h + 18)
    head_h = block(plan["head_copy"], 64, y, 872, 100, 28, 20, "헤드카피")
    y += max(head_h, 18) + 36
    title_h = block(slide["title"], 64, y, 872, 260, 76 if index == 0 else 64, 34, "제목", strong=True)
    y += title_h + 40
    draw.rectangle((64, y, 150, y + 7), fill=profile["accent"])
    y += 40
    bullets = slide.get("bullets", [])
    if bullets:
        body_bottom = 1140
        if body_bottom - y < 80:
            raise SkillError(f"{index + 1}쪽: 본문 공간이 부족합니다. 제목을 줄이거나 페이지를 나누세요.")
        draw.rounded_rectangle((54, y - 18, 946, body_bottom + 14), radius=22, fill="#FFFFFF", outline="#DCE2EA", width=2)
        body_text = "\n\n".join(f"• {b}" for b in bullets)
        block(body_text, 82, y, 836, body_bottom - y, 38, 27, "본문")
    if slide.get("footnote"):
        block(slide["footnote"], 64, 1176, 872, 80, 21, 16, "출처/각주")
    footer = " · ".join(x for x in (profile["agency"], profile["footer"]) if x)
    footer_width = 650 if logo_path else 872
    block(footer, 64, 1280, footer_width, 40, 19, 15, "기관/푸터")
    if logo_path:
        # Keep all colors/alpha of the supplied logo. Never remove black pixels.
        lp = Path(logo_path).expanduser().resolve(strict=True)
        if lp.stat().st_size > 10 * 1024 * 1024:
            raise SkillError("로고 파일은 10MB 이하로 지정하세요.")
        with Image.open(lp) as original:
            logo = original.convert("RGBA")
            logo.thumbnail((170, 58), Image.Resampling.LANCZOS)
            image.paste(logo, (WIDTH - 64 - logo.width, 1270), logo)
    return image, reports


def _html_preview(plan: dict[str, Any], paths: list[str], status: str) -> str:
    cards = "\n".join(f'<figure><img src="{html.escape(p, quote=True)}" alt="{html.escape(s["title"], quote=True)}"><figcaption>{i + 1}. {html.escape(s["title"])}</figcaption></figure>' for i, (p, s) in enumerate(zip(paths, plan["slides"])))
    return f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(plan['series_title'])}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1250px;margin:32px auto;padding:0 24px;background:#f1f3f5;color:#17202a}}main{{display:flex;flex-wrap:wrap;gap:24px}}figure{{margin:0;max-width:380px;flex:1 1 280px}}img{{width:100%;height:auto}}figcaption{{padding:12px 0}}.notice{{padding:16px;background:white}}</style>
<h1>{html.escape(plan['series_title'])}</h1><p class="notice">상태: {html.escape(status)} · 자동 게시하지 않음 · 카드의 모든 글자를 원문과 대조하세요.</p><main>{cards}</main></html>'''


def create_run(plan: dict[str, Any], out_dir: str | Path, profile: dict[str, Any], *,
               regular_font: str | None = None, bold_font: str | None = None, logo: str | None = None,
               source: dict[str, Any] | None = None, approval: Any = None,
               final: bool = False, locale: str = "ko") -> Path:
    plan = validate_plan(plan)
    if profile.get("template") or any("layout" in s or "takeaway" in s for s in plan["slides"]):
        raise SkillError("직원 AI 학습 템플릿과 확장 문안은 build 명령으로 제작하세요.")
    if locale not in {"ko", "en"}:
        raise SkillError("locale은 ko 또는 en이어야 합니다.")
    if final:
        if not source:
            raise SkillError("승인본에는 --source와 --approval이 필요합니다.")
        require_approval(plan, source, approval)
    status = "copy-approved" if final else "draft"
    target = Path(out_dir).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise SkillError("출력 폴더가 이미 있습니다. 기존 결과 보호를 위해 새 폴더를 지정하세요.")
    fonts = resolve_fonts(regular_font, bold_font)
    check_glyphs(fonts, plan_strings(plan) + [profile["agency"], profile["footer"], "검토용 초안 문안 승인본 • · 0123456789 / "])
    # Fit every page before creating any user-visible output.
    pages = [render_page(plan, i, profile, fonts, status, logo) for i in range(len(plan["slides"]))]
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".Jeju_Cardmaker-", dir=target.parent))
    try:
        paths: list[str] = []
        digests: dict[str, str] = {}
        reports = []
        for i, (image, blocks) in enumerate(pages):
            rel = f"jpeg/{locale}/{i + 1:02d}_{plan['slides'][i]['role']}.jpg"
            dest = stage / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            image.save(dest, format="JPEG", quality=95, optimize=True, subsampling=0)
            paths.append(rel)
            digests[rel] = sha256(dest.read_bytes())
            reports.append({"page": i + 1, "blocks": blocks, "overflow": False})
        write_json(stage / "plan.json", plan)
        write_json(stage / "profile.json", profile)
        write_json(stage / "source-summary.json", source_summary(source))
        write_json(stage / "render-report.json", {"size": [WIDTH, HEIGHT], "fonts": [p.name for p in fonts], "pages": reports})
        (stage / "review.md").write_text(review_markdown(plan, source), encoding="utf-8")
        (stage / "preview.html").write_text(_html_preview(plan, paths, status), encoding="utf-8")
        if final:
            write_json(stage / "approval.json", approval)
        write_json(stage / "manifest.json", {"version": VERSION, "engine": "local-safe", "status": status,
                   "created_at": now(), "plan_sha256": plan_hash(plan), "image_paths": paths,
                   "image_sha256": digests, "size": [WIDTH, HEIGHT], "api_calls": 0,
                   "notice": "텍스트 템플릿 렌더링입니다. 생성형 AI 일러스트와 다릅니다. 자동 게시하지 않습니다."})
        stage.rename(target)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return target


def validate_run(path: str | Path) -> tuple[Path, dict[str, Any], dict[str, Any], list[Path]]:
    root = Path(path).expanduser().resolve(strict=True)
    def confined(rel: str) -> Path:
        candidate = root / rel
        if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(root):
            raise SkillError(f"내보낼 수 없는 파일 경로: {rel}")
        # Reject parent symlinks, even if they point back into this run.
        if any(p.is_symlink() for p in candidate.parents if p != root and p.is_relative_to(root)):
            raise SkillError("결과 폴더 내부 심볼릭 링크는 내보내지 않습니다.")
        return candidate
    manifest = read_json(confined("manifest.json"))
    plan = validate_plan(read_json(confined("plan.json")))
    if manifest.get("plan_sha256") != plan_hash(plan):
        raise SkillError("렌더링 후 기획안이 변경되었습니다. 다시 렌더링하세요.")
    paths = manifest.get("image_paths")
    if not isinstance(paths, list) or len(paths) != len(plan["slides"]) or len(set(paths)) != len(paths):
        raise SkillError("이미지 수가 기획안과 다르거나 중복됩니다.")
    images = []
    for i, rel in enumerate(paths):
        if not isinstance(rel, str) or not re.fullmatch(r"jpeg/(ko|en)/\d{2}_(cover|body|closing)\.jpg", rel):
            raise SkillError("이미지 경로가 허용된 형식이 아닙니다.")
        if Path(rel).name != f"{i + 1:02d}_{plan['slides'][i]['role']}.jpg":
            raise SkillError("이미지 순서/역할이 기획안과 다릅니다.")
        image = confined(rel)
        if sha256(image.read_bytes()) != manifest.get("image_sha256", {}).get(rel):
            raise SkillError(f"이미지가 렌더링 이후 변경되었습니다: {rel}")
        images.append(image)
    return root, manifest, plan, images


def visual_pptx(images: list[Path]) -> bytes:
    """Pixel-faithful image deck, intentionally not an editable text deck."""
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    prs.slide_width = Inches(7.407407)
    prs.slide_height = Inches(10)
    for path in images:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.shapes.add_picture(str(path), 0, 0, width=prs.slide_width, height=prs.slide_height)
    stream = BytesIO()
    prs.save(stream)
    return stream.getvalue()


def package_run(path: str | Path, output: str | Path, *, include_pptx: bool = True) -> Path:
    root, manifest, plan, images = validate_run(path)
    target = Path(output).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise SkillError("ZIP 파일이 이미 있습니다. 새 파일명을 지정하세요.")
    if target.is_relative_to(root):
        raise SkillError("ZIP은 결과 폴더 밖에 저장하세요.")
    metadata = ["manifest.json", "plan.json", "profile.json", "source-summary.json", "render-report.json", "review.md", "preview.html"]
    if manifest.get("status") == "copy-approved":
        metadata.append("approval.json")
    files = images + [root / name for name in metadata]
    for file in files:
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):
            raise SkillError("ZIP에 포함할 파일이 없거나 허용된 경로 밖입니다.")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Create complete archive in memory; input sizes are bounded by the renderer.
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, file.relative_to(root).as_posix())
        if include_pptx:
            archive.writestr("cardnews-preview.pptx", visual_pptx(images))
        archive.writestr("ABOUT.txt", "Jeju_Cardmaker Codex Skill\nPPTX: 카드 이미지가 들어간 검수용 슬라이드이며 텍스트 개체는 편집되지 않습니다.\n문안 편집: plan.json / review.md\n원본 문서, API 키, 폰트 파일은 포함하지 않습니다. 자동 게시하지 않습니다.\n")
    with target.open("xb") as f:
        f.write(bio.getvalue())
    return target
