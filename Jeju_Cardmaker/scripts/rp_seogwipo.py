"""Staff learning cards using the bundled Jeju characters and measured text."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rp_core import SkillError, read_json, sha256
from rp_render import fit_block, left_overhang

PET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "jeju-pets"
PETS = (("gyulmo", "귤귤"), ("harubang", "하르방"), ("halla", "한라"))
POSES = ("wave", "walk-right", "walk-left", "explain", "think", "cheer", "caution")
PET_FILES = ("gyulmo.png", "harubang.png", "halla.png", "manifest.json", "SOURCES.md") + tuple(
    f"{pet_id}-{pose}.png" for pet_id, _ in PETS for pose in POSES)
LABELS = {"definition": "개념 이해", "list": "업무 활용", "compare": "차이 비교",
          "steps": "따라 하기", "caution": "주의사항", "summary": "핵심 정리"}


def validate_pets() -> dict:
    """Fail on missing or changed artwork instead of drawing substitutes."""
    manifest = read_json(PET_ROOT / "manifest.json")
    for filename in PET_FILES:
        if not filename.endswith(".png"):
            continue
        path = PET_ROOT / filename
        if not path.is_file() or path.is_symlink():
            raise SkillError("제주 펫 원본 PNG를 확인하세요.")
        if sha256(path.read_bytes()) != manifest.get("sha256", {}).get(path.name):
            raise SkillError("제주 펫 원본 PNG가 배포 기록과 다릅니다.")
    return manifest


def render_learning_card(plan: dict, index: int, profile: dict, fonts: tuple[Path, Path],
                         size: tuple[int, int], status: str, hide_status: bool,
                         logo: Path | None) -> tuple[Any, dict]:
    from PIL import Image, ImageDraw, ImageFont
    from rp_studio import contrast, font_family

    validate_pets()
    width, height = size
    scale = width / 1080
    logical_h = height / scale
    px = lambda value: round(value * scale)
    image = Image.new("RGB", size, profile["background"])
    draw = ImageDraw.Draw(image)
    slide = plan["slides"][index]
    cover = slide["role"] == "cover"
    closing = slide["role"] == "closing"
    layout = slide.get("layout", "summary" if closing else "list")
    colors = (profile["accent"], profile["primary"], profile["secondary"])
    border = colors[2] if layout == "caution" else colors[index % 3]
    blocks, shapes, pets = [], [], []
    paper = "#FFFFFF"

    def rect(x, y, w, h, fill):
        draw.rectangle((px(x), px(y), px(x+w), px(y+h)), fill=fill)
        shapes.append({"x": px(x), "y": px(y), "width": px(w), "height": px(h),
                       "fill": fill, "radius": 0})

    def frame(x, y, w, h, fill, line, thickness=4):
        rect(x, y, w, h, line)
        rect(x+thickness, y+thickness, w-2*thickness, h-2*thickness, fill)

    def circle(x, y, diameter, fill):
        draw.ellipse((px(x), px(y), px(x+diameter)-1, px(y+diameter)-1), fill=fill)
        shapes.append({"kind": "ellipse", "x": px(x), "y": px(y),
                       "width": px(diameter), "height": px(diameter), "fill": fill, "radius": 0})

    def text(value, x, y, w, h, hi, lo, label, strong=False, background=paper, color=None):
        path = fonts[1 if strong else 0]
        spec = fit_block(draw, value, path, px(w), px(h), px(hi), px(lo), f"{index+1}장 {label}")
        font = ImageFont.truetype(str(path), spec["size"])
        actual_color = color or profile["text"]
        bounds = []
        for row, line in enumerate(spec["lines"]):
            xx = px(x) + left_overhang(draw, line, font)
            yy = px(y) + row * spec["line_height"]
            box = draw.textbbox((xx, yy), line, font=font, anchor="lt")
            if box[0] < px(x) or box[1] < px(y) or box[2] > px(x+w) or box[3] > px(y+h):
                raise SkillError(f"{index+1}장 {label}: 글자가 영역을 벗어납니다.")
            draw.text((xx, yy), line, font=font, fill=actual_color, anchor="lt")
            bounds.append(list(box))
        blocks.append({**spec, "text": value, "x": px(x), "y": px(y),
                       "box_width": px(w), "box_height": px(h), "bold": strong,
                       "color": actual_color, "background": background,
                       "contrast_ratio": round(contrast(actual_color, background), 3),
                       "font_family": font_family(path), "glyph_bounds": bounds, "overflow": False})
        return spec["height"] / scale

    def pet(pet_index, pose, x, bottom, max_w, max_h):
        pet_id, name = PETS[pet_index]
        filename = f"{pet_id}-{pose}.png"
        path = PET_ROOT / filename
        with Image.open(path) as original:
            character = original.convert("RGBA")
            ratio = min(px(max_w)/character.width, px(max_h)/character.height)
            character = character.resize((round(character.width*ratio), round(character.height*ratio)),
                                         Image.Resampling.NEAREST)
            xx, yy = px(x)+(px(max_w)-character.width)//2, px(bottom)-character.height
            image.paste(character, (xx, yy), character)
            pets.append({"id": pet_id, "name": name, "pose": pose, "asset": f"assets/jeju-pets/{filename}",
                         "sha256": sha256(path.read_bytes()), "x": xx, "y": yy,
                         "width": character.width, "height": character.height})

    text(plan["series_title"], 56, 42, 800, 60, 28, 23, "시리즈",
         True, profile["background"])
    text(f"{index+1:02d} / {len(plan['slides']):02d}", 888, 46, 136, 40, 25, 23, "쪽수",
         background=profile["background"])
    frame(48, 130, 984, logical_h-340, paper, border, 6)
    for n, color in enumerate((colors[2], colors[1], colors[0])):
        circle(94+n*34, 146, 18, color)
    label = "AI 기초" if cover else LABELS[layout]
    rect(94, 174, 200, 55, border)
    badge_text = "#FFFFFF" if contrast("#FFFFFF", border) >= 4.5 else profile["text"]
    text(label, 110, 186, 168, 36, 25, 23, "분류", True, border, badge_text)
    title_h = text(slide["title"], 94, 263, 892, 196, 70 if cover else 60, 44, "제목", True)
    y = 263 + title_h + 24
    if cover and plan["head_copy"]:
        y += text(plan["head_copy"], 94, y, 892, 110, 31, 28, "보조 설명") + 22

    pet_bottom = logical_h-240
    pet_h = 285 if cover else 230 if closing else 180
    pet_top = pet_bottom-pet_h
    takeaway = slide.get("takeaway", "")
    takeaway_h = 108 if takeaway else 0
    body_bottom = pet_top-54-takeaway_h
    bullets = slide.get("bullets", [])
    available = body_bottom-y
    if bullets and available < 50:
        raise SkillError(f"{index+1}장: 본문 공간이 부족합니다. 제목과 보조 설명을 줄이세요.")
    if layout == "compare" and bullets:
        for n, bullet in enumerate(bullets):
            x = 94+n*458
            frame(x, y, 434, available, paper, colors[n], 3)
            rect(x+3, y+3, 428, 9, colors[n])
            text(bullet, x+22, y+28, 390, available-50, 35, 30, f"비교 {n+1}")
    elif bullets:
        # Fit all bullets at the same size; never omit content to make room for pets.
        numbered = layout in ("steps", "summary")
        body_width = 826
        gap = 22
        chosen = None
        for fs in range(36, 29, -1):
            specs = [fit_block(draw, b, fonts[0], px(body_width), px(3000), px(fs), px(fs),
                               f"{index+1}장 본문") for b in bullets]
            if sum(s["height"]/scale for s in specs) + gap*(len(bullets)-1) <= available:
                chosen = fs, specs
                break
        if chosen is None:
            raise SkillError(f"{index+1}장: 최소 30px에서도 본문이 넘칩니다. 문장을 줄이거나 장을 나누세요.")
        fs, specs = chosen
        for n, (bullet, spec) in enumerate(zip(bullets, specs), 1):
            if numbered:
                frame(94, y, 44, 46, paper, border, 3)
                text(str(n), 104, y+5, 24, 36, 27, 25, f"순서 {n}", True)
            else:
                rect(102, y+10, 12, 12, border)
            block_h = spec["height"]/scale
            text(bullet, 152, y, body_width, block_h+1, fs, fs, f"본문 {n}")
            y += block_h + gap
    if takeaway:
        takeaway_y = pet_top-30-takeaway_h
        frame(94, takeaway_y, 892, takeaway_h, "#F4F7F6", border, 3)
        text(takeaway, 116, takeaway_y+18, 848, takeaway_h-34, 31, 28, "핵심 정리",
             True, "#F4F7F6")
    if cover or closing:
        for n in range(3):
            pose = ("wave", "explain", "wave")[n] if cover else "cheer"
            pet(n, pose, 160+n*260, pet_bottom, 240 if cover else 200, pet_h)
    else:
        pose = {"definition": "think", "compare": "explain", "steps": "walk-left",
                "caution": "caution", "summary": "cheer"}.get(layout, "explain")
        pet(index % 3, pose, 780, pet_bottom, 200, pet_h)
        text("주의사항을 확인합니다" if layout == "caution" else "한 장에 한 가지씩 익힙니다",
             94, pet_top+60, 680, 45, 25, 23, "학습 안내")
    text(slide.get("footnote") or "", 56, logical_h-174, 968, 83, 23, 19, "출처/각주",
         background=profile["background"])
    if not hide_status:
        text("검토용 초안" if status == "draft" else "문안 승인본", 56, logical_h-67, 210, 35,
             21, 19, "상태", background=profile["background"])
    footer = " · ".join(x for x in (profile["agency"], profile["footer"]) if x)
    text(footer, 280, logical_h-67, 520 if logo else 744, 42, 20, 16, "기관/푸터",
         background=profile["background"])
    logo_spec = None
    if logo:
        if logo.stat().st_size > 10*1024*1024:
            raise SkillError("로고 파일은 10MB 이하여야 합니다.")
        with Image.open(logo) as original:
            icon = original.convert("RGBA")
            icon.thumbnail((px(170), px(58)), Image.Resampling.LANCZOS)
            xx, yy = width-px(56)-icon.width, height-px(78)
            image.paste(icon, (xx, yy), icon)
            logo_spec = {"x": xx, "y": yy, "width": icon.width, "height": icon.height}
    warnings = [f"{index+1}장 {b['label']}: 글자 대비 {b['contrast_ratio']}" for b in blocks
                if b["text"] and b["contrast_ratio"] < 4.5]
    return image, {"page": index+1, "size": list(size), "background": profile["background"],
                   "template": "seogwipo-ai", "layout": layout, "border_color": border,
                   "blocks": blocks, "shapes": shapes, "pets": pets, "logo": logo_spec,
                   "warnings": warnings, "overflow": False}
