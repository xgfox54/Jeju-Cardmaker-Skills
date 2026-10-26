"""Staff learning cards using the bundled Jeju characters and measured text."""
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Any

from rp_core import SkillError, read_json, sha256
from rp_render import fit_block, left_overhang

fit_learning_block = partial(fit_block, prefer_words=True)

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
    obstacles = []
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

    def text(value, x, y, w, h, hi, lo, label, strong=False, background=paper, color=None,
             align="left", valign="top", leading=1.4):
        path = fonts[1 if strong else 0]
        spec = fit_learning_block(draw, value, path, px(w), px(h), px(hi), px(lo), f"{index+1}장 {label}")
        font = ImageFont.truetype(str(path), spec["size"])
        metrics = [draw.textbbox((0, 0), line, font=font, anchor="lt") for line in spec["lines"]]
        spec["line_height"] = max(round(spec["size"]*leading),
                                  max((b[3]-b[1]+4 for b in metrics), default=0))
        ink_height = ((len(metrics)-1)*spec["line_height"] + metrics[-1][3]) if metrics else 0
        spec["height"] = ink_height
        offset_y = (px(h)-ink_height)//2 if valign == "middle" else 0
        actual_color = color or profile["text"]
        bounds = []
        for row, line in enumerate(spec["lines"]):
            metric = metrics[row]
            xx = (px(x)+(px(w)-(metric[2]-metric[0]))//2-metric[0] if align == "center"
                  else px(x) + left_overhang(draw, line, font))
            yy = px(y) + offset_y + row * spec["line_height"]
            box = draw.textbbox((xx, yy), line, font=font, anchor="lt")
            if box[0] < px(x) or box[1] < px(y) or box[2] > px(x+w) or box[3] > px(y+h):
                raise SkillError(f"{index+1}장 {label}: 글자가 영역을 벗어납니다.")
            draw.text((xx, yy), line, font=font, fill=actual_color, anchor="lt")
            bounds.append(list(box))
        blocks.append({**spec, "text": value, "x": px(x), "y": px(y),
                       "box_width": px(w), "box_height": px(h), "bold": strong,
                       "align": align, "valign": valign,
                       "color": actual_color, "background": background,
                       "contrast_ratio": round(contrast(actual_color, background), 3),
                       "font_family": font_family(path), "glyph_bounds": bounds, "overflow": False})
        return spec["height"] / scale

    def pet(pet_index, pose, x, bottom, max_w, max_h, placement="group"):
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
            pets.append({"id": pet_id, "name": name, "pose": pose, "placement": placement,
                         "asset": f"assets/jeju-pets/{filename}",
                         "sha256": sha256(path.read_bytes()), "x": xx, "y": yy,
                         "width": character.width, "height": character.height})

    text(plan["series_title"], 56, 42, 800, 60, 28, 23, "시리즈",
         True, profile["background"])
    text(f"{index+1:02d} / {len(plan['slides']):02d}", 888, 46, 136, 40, 25, 23, "쪽수",
         background=profile["background"])
    frame(48, 130, 984, logical_h-340, paper, border, 6)
    for n, color in enumerate((colors[2], colors[1], colors[0])):
        circle(48+n*34, 96, 20, color)
    label = "AI 기초" if cover else LABELS[layout]
    rect(104, 178, 176, 48, border)
    badge_text = "#FFFFFF" if contrast("#FFFFFF", border) >= 4.5 else profile["text"]
    text(label, 104, 178, 176, 48, 24, 23, "분류", True, border, badge_text,
         align="center", valign="middle")
    title_h = text(slide["title"], 104, 264, 872, 190, 70 if cover else 54, 44, "제목", True,
                   leading=1.22)
    y = 264 + title_h + 44
    if cover and plan["head_copy"]:
        y += text(plan["head_copy"], 104, y, 872, 110, 30, 28, "보조 설명") + 32

    content_bottom = logical_h-266
    pet_h = 260 if cover else 210 if closing else 176
    takeaway = slide.get("takeaway", "")
    takeaway_spec = fit_learning_block(draw, takeaway, fonts[1], px(820), px(160), px(30), px(28), "핵심 정리")
    takeaway_h = max(88, takeaway_spec["height"]/scale+36) if takeaway else 0
    body_bottom = content_bottom-pet_h-44-(takeaway_h+36 if takeaway else 0)
    bullets = slide.get("bullets", [])
    available = body_bottom-y
    if bullets and available < 50:
        raise SkillError(f"{index+1}장: 본문 공간이 부족합니다. 제목과 보조 설명을 줄이세요.")
    if layout == "compare" and bullets:
        panels = []
        for bullet in bullets:
            heading, separator, body = bullet.partition("\n\n")
            if not separator:
                heading, body = "", bullet
            head_spec = fit_learning_block(draw, heading, fonts[1], px(374), px(3000), px(32), px(32), "비교 제목")
            body_spec = fit_learning_block(draw, body, fonts[0], px(374), px(3000), px(32), px(32), "비교 본문")
            panels.append((heading, body, head_spec, body_spec))
        panel_h = max((p[2]["height"]+p[3]["height"])/scale+80 for p in panels)
        if panel_h > available:
            raise SkillError(f"{index+1}장: 비교 문장을 줄이거나 장을 나누세요.")
        for n, bullet in enumerate(bullets):
            x = 104+n*450
            frame(x, y, 422, panel_h, paper, "#D7E2DF", 2)
            rect(x+2, y+2, 418, 5, colors[n])
            heading, body, head_spec, body_spec = panels[n]
            head_h = text(heading, x+24, y+28, 374, head_spec["height"]/scale+1,
                          32, 32, f"비교 제목 {n+1}", True)
            text(body, x+24, y+28+head_h+(24 if heading else 0), 374,
                 body_spec["height"]/scale+1, 32, 32, f"비교 {n+1}")
            obstacles.append([px(x), px(y), px(x+422), px(y+panel_h)])
        y += panel_h
    elif bullets:
        # Fit all bullets at the same size; never omit content to make room for pets.
        numbered = layout in ("steps", "summary")
        body_x = 164 if numbered else 138
        body_width = 976-body_x
        gap = 40 if numbered else 32
        chosen = None
        for fs in range(34, 29, -1):
            specs = [fit_learning_block(draw, b, fonts[0], px(body_width), px(3000), px(fs), px(fs),
                               f"{index+1}장 본문") for b in bullets]
            if sum(s["height"]/scale for s in specs) + gap*(len(bullets)-1) <= available:
                chosen = fs, specs
                break
        if chosen is None:
            raise SkillError(f"{index+1}장: 최소 30px에서도 본문이 넘칩니다. 문장을 줄이거나 장을 나누세요.")
        fs, specs = chosen
        for n, (bullet, spec) in enumerate(zip(bullets, specs), 1):
            if numbered:
                rect(104, y-5, 40, 40, "#EEF3F1")
                text(str(n), 104, y-5, 40, 40, 24, 24, f"순서 {n}", True,
                     background="#EEF3F1", align="center", valign="middle")
            else:
                rect(108, y+12, 8, 8, border)
            block_h = spec["height"]/scale
            used_h = text(bullet, body_x, y, body_width, block_h+1, fs, fs, f"본문 {n}")
            y += used_h + gap
        y -= gap
    if takeaway:
        takeaway_y = y+36
        rect(104, takeaway_y, 872, takeaway_h, "#EEF3F1")
        rect(104, takeaway_y, 4, takeaway_h, border)
        text(takeaway, 130, takeaway_y, 820, takeaway_h, 30, 28, "핵심 정리",
             True, "#EEF3F1", valign="middle")
        obstacles.append([px(104), px(takeaway_y), px(976), px(takeaway_y+takeaway_h)])
        y = takeaway_y+takeaway_h
    if cover or closing:
        pet_bottom = min(content_bottom, y+56+pet_h)
        for n in range(3):
            pose = ("wave", "explain", "wave")[n] if cover else "cheer"
            pet(n, pose, 160+n*260, pet_bottom, 240 if cover else 200, pet_h)
    else:
        # Search measured whitespace, including beside short headings and paragraphs.
        occupied = obstacles + [box for block in blocks for box in block["glyph_bounds"]]
        target_x = 104 if layout in ("definition", "list") and index % 2 else 756
        target_y = 250 if layout == "steps" else min(y+40, content_bottom-220)
        candidates = []
        for size_h in (220, 200, 176):
            size_w = size_h*192/208
            for yy in range(240, int(content_bottom-size_h)+1, 16):
                for xx in range(104, int(976-size_w)+1, 16):
                    a, b, c, d = px(xx), px(yy), px(xx+size_w), px(yy+size_h)
                    gap_px = px(24)
                    if any(a < right+gap_px and c > left-gap_px and
                           b < bottom+gap_px and d > top-gap_px
                           for left, top, right, bottom in occupied):
                        continue
                    score = abs(xx-target_x)+abs(yy-target_y)*1.5+(220-size_h)*4
                    candidates.append((score, xx, yy, size_w, size_h))
        if not candidates:
            raise SkillError(f"{index+1}장: 캐릭터를 배치할 여백이 부족합니다. 문장을 줄이거나 장을 나누세요.")
        _, xx, yy, size_w, size_h = min(candidates)
        pose = {"definition": "think", "compare": "explain", "steps": "walk-left",
                "caution": "caution", "summary": "cheer"}.get(layout, "explain")
        if pose.startswith("walk-"):
            pose = "walk-right" if xx < 540 else "walk-left"
        pet(index % 3, pose, xx, yy+size_h, size_w, size_h, "measured-whitespace")
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
                   "content_obstacles": obstacles,
                   "blocks": blocks, "shapes": shapes, "pets": pets, "logo": logo_spec,
                   "warnings": warnings, "overflow": False}
