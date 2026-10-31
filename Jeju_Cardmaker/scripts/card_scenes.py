"""Scene-type layout engine for Jeju_Cardmaker staff AI cards.

Each page in diagrams.json names one scene. The engine measures every string at a fixed
size for its role, stacks the blocks from the same anchor on every page, and gives one
character a position that differs from the previous page. Overflow raises an error so the
author shortens copy or splits the page; type is never shrunk to make room.
"""
from __future__ import annotations

import html
import math
from functools import partial
from pathlib import Path
from typing import Any, Callable

from rp_core import SkillError, sha256
from rp_render import fit_block, left_overhang
from rp_seogwipo import PET_ROOT, validate_pets

ENGINE_VERSION = "scenes-1"
fit_words = partial(fit_block, prefer_words=True)

PETS = {"gyulmo": "귤귤", "harubang": "하르방", "halla": "한라"}
PET_ROTATION = ("harubang", "halla", "gyulmo")
POSES = ("wave", "walk-right", "walk-left", "explain", "think", "cheer", "caution")
# One size per semantic role, in 1080 px logical width. Same role, same size on every page.
SIZE = {"cover_title": 56, "title": 54, "body": 32, "panel_title": 29, "panel_body": 28,
        "bubble": 30, "note": 26, "row_name": 27, "row_text": 26, "number": 150,
        "number_caption": 32, "checklist": 31, "caption": 28, "badge": 24}
LIGHT = ("#EAF6F1", "#EAF3FA", "#FFF3E5")
X0, X1 = 104, 976
TOP, BOTTOM = 586, 1112
GAP = 24
PET_W, PET_H = 180, 168
PLACEMENTS = ("bottom-left", "side-right", "bottom-right", "title-right")
NARROW_UNSAFE = {"rows", "flow", "pillars"}
SCENES = {"hero": (), "steps": ("steps",), "compare": ("panels",), "pillars": ("panels",),
          "rows": ("rows",), "flow": ("flow",), "stat": ("number", "caption"),
          "checklist": ("items", "captions")}
COUNTS = {"steps": ("steps", 2, 4), "compare": ("panels", 2, 2), "pillars": ("panels", 3, 3),
          "rows": ("rows", 2, 5), "flow": ("flow", 2, 4), "checklist": ("items", 2, 5)}


def _pairs(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, list) and len(item) == 2 and all(isinstance(s, str) and s.strip() for s in item)
        for item in value)


def validate_scenes(plan: dict, diagrams: Any) -> list[dict]:
    """Check scene names, required fields and item counts before anything is drawn."""
    pages = diagrams.get("pages") if isinstance(diagrams, dict) else None
    if not isinstance(pages, list) or len(pages) != len(plan["slides"]):
        raise SkillError("diagrams.json의 pages 수가 plan.json의 장수와 같아야 해요.")
    for n, (slide, page) in enumerate(zip(plan["slides"], pages), 1):
        if not isinstance(page, dict):
            raise SkillError(f"{n}장: 그림 원고는 객체여야 해요.")
        scene = page.get("scene")
        if scene not in SCENES:
            raise SkillError(f"{n}장: scene은 {', '.join(SCENES)} 중 하나여야 해요.")
        if not isinstance(page.get("badge"), str) or not page["badge"].strip():
            raise SkillError(f"{n}장: 분류 라벨(badge)을 적어 주세요.")
        if (slide["role"] == "cover") != (scene == "hero"):
            raise SkillError(f"{n}장: 표지는 hero, hero는 표지에만 써요.")
        if (slide["role"] == "closing") != (scene == "checklist"):
            raise SkillError(f"{n}장: 마지막 장은 checklist, checklist는 마지막 장에만 써요.")
        missing = [key for key in SCENES[scene] if not page.get(key)]
        if scene == "hero":
            if not page.get("question") or not page.get("note"):
                missing += [k for k in ("question", "note") if not page.get(k)]
            if not page.get("number") and not page.get("facts"):
                missing.append("number 또는 facts")
            if page.get("number") and not page.get("number_caption"):
                missing.append("number_caption")
        if missing:
            raise SkillError(f"{n}장 {scene}: {', '.join(missing)} 항목이 필요해요.")
        limits = [COUNTS[scene]] if scene in COUNTS else []
        if scene == "checklist":
            limits.append(("captions", 3, 3))
        if "facts" in page:
            limits.append(("facts", 3, 3))
        for key, low, high in limits:
            items = page.get(key)
            if not isinstance(items, list) or not low <= len(items) <= high:
                raise SkillError(f"{n}장 {scene}: {key} 항목은 {low}~{high}개여야 해요.")
        for key in ("steps", "panels", "flow", "facts"):
            if key in page and not _pairs(page[key]):
                raise SkillError(f"{n}장: {key}는 [제목, 설명] 쌍의 목록이어야 해요.")
        if "rows" in page and not (isinstance(page["rows"], list) and all(
                isinstance(r, list) and len(r) == 3 and all(isinstance(s, str) and s.strip() for s in r)
                for r in page["rows"])):
            raise SkillError(f"{n}장: rows는 [이름, 내용, 결과] 목록이어야 해요.")
        character = page.get("character", {})
        if not isinstance(character, dict) or set(character) - {"place", "pet", "pose"}:
            raise SkillError(f"{n}장: character는 place, pet, pose만 쓸 수 있어요.")
        if character.get("place") not in (None, *PLACEMENTS):
            raise SkillError(f"{n}장: place는 {', '.join(PLACEMENTS)} 중 하나여야 해요.")
        if character.get("pet") not in (None, *PETS) or character.get("pose") not in (None, *POSES):
            raise SkillError(f"{n}장: 캐릭터 이름 또는 포즈를 확인하세요.")
    return pages


def _compatible(scene: str, place: str, speech: bool) -> bool:
    if place == "title-right":
        return not speech
    if place == "side-right":
        return scene not in NARROW_UNSAFE
    return True


def plan_characters(plan: dict, pages: list[dict]) -> list[dict]:
    """Choose one character per body page, never repeating the previous place or pet."""
    chosen: list[dict] = []
    prev_place = prev_pet = None
    for i, (slide, page) in enumerate(zip(plan["slides"], pages)):
        if page["scene"] in ("hero", "checklist"):
            chosen.append({"place": "group"})
            prev_place, prev_pet = "group", None
            continue
        speech = bool(page.get("speech"))
        override = page.get("character", {})
        place = override.get("place")
        if place and not _compatible(page["scene"], place, speech):
            raise SkillError(f"{i+1}장: {place} 자리는 이 장면이나 말풍선과 함께 쓸 수 없어요.")
        if not place:
            if not speech and prev_place != "title-right":
                place = "title-right"
            else:
                options = [p for p in PLACEMENTS if _compatible(page["scene"], p, speech)]
                start = i % len(options)
                order = options[start:] + options[:start]
                place = next((p for p in order if p != prev_place), order[0])
        pet = override.get("pet")
        if not pet:
            order = PET_ROTATION[i % 3:] + PET_ROTATION[:i % 3]
            pet = next(p for p in order if p != prev_pet)
        pose = override.get("pose")
        if not pose:
            text = page.get("speech", "")
            pose = ("caution" if slide.get("layout") == "caution" else
                    "think" if text.rstrip().endswith("?") else
                    "wave" if place == "title-right" else "explain")
        chosen.append({"place": place, "pet": pet, "pose": pose})
        prev_place, prev_pet = place, pet
    return chosen


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def diagram_strings(diagrams: dict) -> list[str]:
    return list(_strings(diagrams))


def make_renderer(plan: dict, diagrams: dict) -> Callable:
    """Return a render_card-compatible function plus the collected page reports."""
    pages = validate_scenes(plan, diagrams)
    characters = plan_characters(plan, pages)
    reports: list[dict] = []

    def render(plan: dict, index: int, profile: dict, fonts: tuple[Path, Path],
               size: tuple[int, int], status: str, hide_status: bool = True,
               logo: Path | None = None) -> tuple[Any, dict]:
        image, report = _render(plan, index, profile, fonts, size, status, hide_status,
                                pages[index], characters)
        reports.append(report)
        return image, report

    render.reports = reports  # type: ignore[attr-defined]
    render.characters = characters  # type: ignore[attr-defined]
    return render


def _render(plan, index, profile, fonts, size, status, hide_status, page, characters):
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
    n = index + 1
    scene = page["scene"]
    layout = slide.get("layout", "summary" if slide["role"] == "closing" else "list")
    colors = (profile["accent"], profile["primary"], profile["secondary"])
    border = colors[2] if layout == "caution" else colors[index % 3]
    blocks: list[dict] = []
    shapes: list[dict] = []
    pets: list[dict] = []
    paper = "#FFFFFF"
    character = dict(characters[index])

    def rect(x, y, w, h, fill):
        draw.rectangle((px(x), px(y), px(x + w), px(y + h)), fill=fill)
        shapes.append({"x": px(x), "y": px(y), "width": px(w), "height": px(h), "fill": fill, "radius": 0})

    def frame(x, y, w, h, fill, line, thickness=2):
        rect(x, y, w, h, line)
        rect(x + thickness, y + thickness, w - 2 * thickness, h - 2 * thickness, fill)

    def circle(x, y, diameter, fill):
        draw.ellipse((px(x), px(y), px(x + diameter) - 1, px(y + diameter) - 1), fill=fill)
        shapes.append({"kind": "ellipse", "x": px(x), "y": px(y), "width": px(diameter),
                       "height": px(diameter), "fill": fill, "radius": 0})

    def shape(value, hi, lo, w, strong, leading, label):
        path = fonts[1 if strong else 0]
        spec = fit_words(draw, value, path, px(w), px(5000), px(hi), px(lo), f"{n}장 {label}")
        font = ImageFont.truetype(str(path), spec["size"])
        metrics = [draw.textbbox((0, 0), line, font=font, anchor="lt") for line in spec["lines"]]
        lh = max(round(spec["size"] * leading), max((b[3] - b[1] + 4 for b in metrics), default=0))
        ink = ((len(metrics) - 1) * lh + metrics[-1][3]) if metrics else 0
        return path, spec, font, metrics, lh, ink

    def measure(value, size_, w, strong=False, leading=1.38):
        if not value:
            return 0
        return math.ceil(shape(value, size_, size_, w, strong, leading, "측정")[5] / scale) + 2

    def text(value, x, y, w, h, size_, label, strong=False, bg=paper, color=None,
             align="left", valign="top", leading=1.38, lo=None):
        if not value:
            return 0
        path, spec, font, metrics, lh, ink = shape(value, size_, lo or size_, w, strong, leading, label)
        offset = (px(h) - ink) // 2 if valign == "middle" else 0
        fill = color or profile["text"]
        bounds = []
        for row, line in enumerate(spec["lines"]):
            metric = metrics[row]
            xx = (px(x) + (px(w) - (metric[2] - metric[0])) // 2 - metric[0] if align == "center"
                  else px(x) + left_overhang(draw, line, font))
            yy = px(y) + offset + row * lh
            box = draw.textbbox((xx, yy), line, font=font, anchor="lt")
            if box[0] < px(x) - 1 or box[1] < px(y) - 1 or box[2] > px(x + w) + 1 or box[3] > px(y + h) + 1:
                raise SkillError(f"{n}장 {label}: 글자가 영역을 넘어요. 문구를 줄이거나 장을 나누세요.")
            draw.text((xx, yy), line, font=font, fill=fill, anchor="lt")
            bounds.append(list(box))
        spec = {**spec, "line_height": lh, "height": ink}
        blocks.append({**spec, "text": value, "x": px(x), "y": px(y), "box_width": px(w),
                       "box_height": px(h), "bold": strong, "align": align, "valign": valign,
                       "color": fill, "background": bg,
                       "contrast_ratio": round(contrast(fill, bg), 3),
                       "font_family": font_family(path), "glyph_bounds": bounds, "overflow": False})
        return ink / scale

    def pet(pet_id, pose, x, bottom, max_w, max_h, placement):
        filename = f"{pet_id}-{pose}.png"
        path = PET_ROOT / filename
        with Image.open(path) as original:
            sprite = original.convert("RGBA")
            ratio = min(px(max_w) / sprite.width, px(max_h) / sprite.height)
            sprite = sprite.resize((round(sprite.width * ratio), round(sprite.height * ratio)),
                                   Image.Resampling.NEAREST)
            xx, yy = px(x) + (px(max_w) - sprite.width) // 2, px(bottom) - sprite.height
            image.paste(sprite, (xx, yy), sprite)
            pets.append({"id": pet_id, "name": PETS[pet_id], "pose": pose, "placement": placement,
                         "asset": f"assets/jeju-pets/{filename}", "sha256": sha256(path.read_bytes()),
                         "x": xx, "y": yy, "width": sprite.width, "height": sprite.height})
        return xx / scale, yy / scale, sprite.width / scale, sprite.height / scale

    def arrow(x, y, w):
        rect(x, y - 1.5, w - 12, 3, profile["text"])
        for step in range(14):
            rect(x + w - 14 + step, y - 10 + step * .7, 1.2, 20 - step * 1.4, profile["text"])

    def bubble_height(value, w):
        return max(88, measure(value, SIZE["bubble"], w - 48) + 34)

    def bubble(value, x, y, w, h, tone, side):
        frame(x, y, w, h, LIGHT[tone], colors[tone])
        for step in range(18):
            if side == "left":
                rect(x - 18 + step, y + h * .5 - step * .55, 1.2, 2 + step * 1.1, colors[tone])
            elif side == "right":
                rect(x + w + 17 - step, y + h * .5 - step * .55, 1.2, 2 + step * 1.1, colors[tone])
            elif side == "bottom":
                rect(x + w / 2 - step * .55, y + h + 17 - step, 2 + step * 1.1, 1.2, colors[tone])
        th = measure(value, SIZE["bubble"], w - 48)
        text(value, x + 24, y + (h - th) / 2, w - 48, th, SIZE["bubble"], "캐릭터 말", bg=LIGHT[tone])

    def panel(x, y, w, h, title, body, tone, paint=True):
        th = measure(title, SIZE["panel_title"], w - 40, True, 1.3)
        bh = measure(body, SIZE["panel_body"], w - 48, False, 1.42)
        need = 18 + th + (14 + bh if body else 0) + 22
        if not paint:
            return need
        h = max(h or 0, need)
        frame(x, y, w, h, LIGHT[tone], colors[tone])
        text(title, x + 20, y + 18, w - 40, th, SIZE["panel_title"], "그림 제목", True, LIGHT[tone],
             align="center", leading=1.3)
        if body:
            text(body, x + 24, y + 18 + th + 14, w - 48, bh, SIZE["panel_body"], "그림 설명",
                 bg=LIGHT[tone], align="center", leading=1.42)
        return h

    def columns(items, x, y, w, gap, tones, paint, arrows=False, row_size=None):
        cols = row_size or len(items)
        cw = (w - gap * (cols - 1)) / cols
        yy = y
        for r in range(0, len(items), cols):
            row = items[r:r + cols]
            hmax = max(panel(0, 0, cw, 0, t, b, 0, False) for t, b in row)
            if paint:
                for c, (t, b) in enumerate(row):
                    xx = x + c * (cw + gap)
                    panel(xx, yy, cw, hmax, t, b, tones[(r + c) % len(tones)])
                    if arrows and c < len(row) - 1:
                        arrow(xx + cw + 8, yy + hmax / 2, gap - 16)
            yy += hmax + 20
        return yy - 20 - y

    def scene_body(x, y, w, paint):
        if scene == "steps":
            items = page["steps"]
            return columns(items, x, y, w, 48, page.get("tones", (1, 2, 0, 1)), paint, True,
                           2 if len(items) == 4 else len(items))
        if scene == "compare":
            return columns(page["panels"], x, y, w, 24, page.get("tones", (0, 2)), paint)
        if scene == "pillars":
            return columns(page["panels"], x, y, w, 16, page.get("tones", (1, 2, 0)), paint)
        if scene == "flow":
            used = columns(page["flow"], x, y, w, 64, page.get("tones", (1, 0, 2, 1)), paint, True)
            if page.get("detail"):
                title, body = page["detail"]
                dh = panel(0, 0, w, 0, title, body, 1, False)
                if paint:
                    panel(x, y + used + 20, w, dh, title, body, 1)
                used += 20 + dh
            return used
        if scene == "rows":
            name_w, result_w = 200, 180
            desc_w = w - name_w - result_w - 24
            yy = y
            for i, (name, desc, result) in enumerate(page["rows"]):
                hn = measure(name, SIZE["row_name"], name_w - 20, True)
                hd = measure(desc, SIZE["row_text"], desc_w)
                hr = measure(result, SIZE["row_name"], result_w - 20, True)
                rh = max(72, max(hn, hd, hr) + 28)
                if paint:
                    tone = (1, 2, 0, 1, 2)[i]
                    bg = LIGHT[tone]
                    frame(x, yy, w, rh, bg, colors[tone])
                    text(name, x + 18, yy + (rh - hn) / 2, name_w - 20, hn, SIZE["row_name"],
                         "그림 표 제목", True, bg)
                    text(desc, x + name_w + 12, yy + (rh - hd) / 2, desc_w, hd, SIZE["row_text"],
                         "그림 표 설명", bg=bg)
                    text(result, x + w - result_w, yy + (rh - hr) / 2, result_w - 20, hr,
                         SIZE["row_name"], "그림 표 제목", True, bg, align="center")
                yy += rh + 10
            return yy - 10 - y
        if scene == "stat":
            nh = measure(page["number"], SIZE["number"], w, True, 1.08)
            ch = measure(page["caption"], SIZE["number_caption"], w, False, 1.45)
            if paint:
                accent = colors[1] if contrast(colors[1], paper) >= 4.5 else profile["text"]
                text(page["number"], x, y, w, nh, SIZE["number"], "그림 숫자", True, color=accent,
                     leading=1.08)
                rect(x, y + nh + 8, 96, 8, colors[0])
                text(page["caption"], x, y + nh + 32, w, ch, SIZE["number_caption"], "그림 숫자 설명",
                     leading=1.45)
            return nh + 32 + ch
        raise SkillError(f"{n}장: 알 수 없는 장면이에요.")

    # Fixed chrome: identical on every page so nothing jumps while swiping.
    text(plan["series_title"], 56, 42, 800, 60, 28, "시리즈", True, profile["background"], lo=23)
    text(f"{n:02d} / {len(plan['slides']):02d}", 888, 46, 136, 40, 25, "쪽수",
         bg=profile["background"], lo=23)
    frame(48, 130, 984, logical_h - 340, paper, border, 6)
    for k, color in enumerate((colors[2], colors[1], colors[0])):
        circle(48 + k * 34, 96, 20, color)
    rect(104, 178, 176, 48, border)
    badge_color = "#FFFFFF" if contrast("#FFFFFF", border) >= 4.5 else profile["text"]
    text(page["badge"], 104, 178, 176, 48, SIZE["badge"], "분류", True, border, badge_color,
         align="center", valign="middle")
    title_size = SIZE["cover_title"] if scene == "hero" else SIZE["title"]
    title_h = measure(slide["title"], title_size, 872, True, 1.25)
    if title_h > 150:
        raise SkillError(f"{n}장 제목: 두 줄을 넘어요. 제목을 줄이세요.")
    text(slide["title"], 104, 265, 872, 150, title_size, "제목", True, leading=1.25)
    title_right = max((b[2] for b in blocks[-1]["glyph_bounds"]), default=0) / scale
    body = "\n".join(slide["bullets"])
    if measure(body, SIZE["body"], 872, False, 1.5) > 120:
        raise SkillError(f"{n}장 본문: 두 줄을 넘어요. 문장을 줄이거나 장을 나누세요.")
    text(body, 104, 428, 872, 120, SIZE["body"], "본문", leading=1.5)

    place = character["place"]
    if place == "title-right" and title_right + GAP > X1 - PET_W:
        place = "bottom-left" if characters[index - 1].get("place") != "bottom-left" else "bottom-right"
        character["place"] = place

    if scene == "hero":
        _hero(page, text, measure, bubble, bubble_height, panel, pet, rect, colors, profile, paper,
              contrast, n)
    elif scene == "checklist":
        box_h = measure("\n".join(page["items"]), SIZE["checklist"], 816, False, 1.45)
        title_h = measure(page.get("title", ""), SIZE["panel_title"], 816, True)
        need = 19 + title_h + 14 + box_h + 26
        if TOP + need > 1072 - 180 - 12:
            raise SkillError(f"{n}장 점검 목록: 공간보다 길어요. 항목을 줄이세요.")
        frame(X0, TOP, 872, need, LIGHT[1], colors[1])
        text(page.get("title", ""), X0 + 28, TOP + 19, 816, title_h, SIZE["panel_title"], "그림 제목", True, LIGHT[1])
        text("\n".join(page["items"]), X0 + 28, TOP + 19 + title_h + 14, 816, box_h,
             SIZE["checklist"], "연습 요청문", bg=LIGHT[1], leading=1.45)
        for k, (pose, caption) in enumerate(zip(("think", "explain", "cheer"), page["captions"])):
            pet(("gyulmo", "harubang", "halla")[k], pose, 142 + k * 298, 1072, 196, 180, f"group-{k+1}")
            text(caption, 104 + k * 298, 1080, 276, 38, SIZE["caption"], "캐릭터 설명", True,
                 align="center", valign="middle")
    else:
        speech = page.get("speech", "")
        note = page.get("note", "")
        x, w, bottom = X0, X1 - X0, BOTTOM
        tone = 2 if layout == "caution" else (1, 0, 2)[index % 3]
        pet_id, pose = character["pet"], character["pose"]
        if place == "title-right" and note and not speech:
            # A small diagram under a title-side character leaves the lower half empty.
            # Let the character say the note instead, in a place unused by both neighbours.
            spare = BOTTOM - TOP - scene_body(x, TOP, w, False) - GAP - measure(note, SIZE["note"], w)
            if spare > 220:
                neighbours = {characters[index - 1].get("place"),
                              characters[index + 1].get("place") if index + 1 < len(characters) else None}
                place = next((p for p in ("bottom-left", "bottom-right") if p not in neighbours), "bottom-right")
                character["place"] = place
                speech, note = note, ""
                if pose == "wave":
                    pose = character["pose"] = "explain"
        if place in ("bottom-left", "bottom-right"):
            bw = 650
            bh = bubble_height(speech, bw) if speech else 0
            band = max(PET_H, bh)
            bottom = BOTTOM - band - GAP
        elif place == "side-right":
            w = 572
        note_h = measure(note, SIZE["note"], w)
        need = scene_body(x, TOP, w, False) + (GAP + note_h if note else 0)
        if TOP + need > bottom:
            raise SkillError(f"{n}장 {scene}: 그림이 남은 공간보다 {round(TOP + need - bottom)}px 커요. "
                             "항목을 줄이거나 장을 나누세요.")
        leftover = bottom - TOP - need
        start = TOP + (min(140, leftover / 2) if leftover > 60 else 0)
        used = scene_body(x, start, w, True)
        if note:
            text(note, x, start + used + GAP, w, note_h, SIZE["note"], "그림 메모")
        if place in ("bottom-left", "bottom-right"):
            band_top = BOTTOM - band
            left = place == "bottom-left"
            pet_x = X0 if left else X1 - PET_W
            pet(pet_id, pose, pet_x, BOTTOM, PET_W, PET_H, place)
            if speech:
                bx = X0 + PET_W + 42 if left else X0
                bubble(speech, bx, band_top + (band - bh) / 2, bw, bh, tone, "left" if left else "right")
        elif place == "side-right":
            cx, cw = 700, 276
            bh = bubble_height(speech, cw) if speech else 0
            if speech:
                bubble(speech, cx, TOP, cw, bh, tone, "bottom")
            room = BOTTOM - (TOP + bh + (30 if speech else 0))
            if room < 150:
                raise SkillError(f"{n}장: 말풍선이 길어서 캐릭터를 놓을 공간이 없어요. 말을 줄이세요.")
            pet(pet_id, pose, cx + 18, BOTTOM, cw - 36, min(250, room), place)
        else:
            pet(pet_id, pose, X1 - PET_W, 412, PET_W, 200, place)

    footnote = slide.get("footnote") or ""
    text(footnote, 56, logical_h - 174, 968, 83, 23, "출처/각주", bg=profile["background"], lo=19)
    if not hide_status:
        text("검토용 초안" if status == "draft" else "문안 승인본", 56, logical_h - 67, 210, 35, 21,
             "상태", bg=profile["background"], lo=19)

    glyphs = [box for block in blocks for box in block["glyph_bounds"]]
    for i, a in enumerate(glyphs):
        for b in glyphs[i + 1:]:
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                raise SkillError(f"{n}장: 글자끼리 겹쳐요.")
    for item in pets:
        box = [item["x"], item["y"], item["x"] + item["width"], item["y"] + item["height"]]
        if any(g[0] < box[2] and box[0] < g[2] and g[1] < box[3] and box[1] < g[3] for g in glyphs):
            raise SkillError(f"{n}장: 캐릭터가 글자를 가려요.")
    warnings = [f"{n}장 {b['label']}: 글자 대비 {b['contrast_ratio']}" for b in blocks
                if b["text"] and b["contrast_ratio"] < 4.5]
    return image, {"page": n, "size": list(size), "background": profile["background"],
                   "template": "seogwipo-ai-scenes", "scene": scene,
                   "placement": character["place"], "layout": layout, "border_color": border,
                   "content_obstacles": [], "blocks": blocks, "shapes": shapes, "pets": pets,
                   "logo": None, "warnings": warnings, "overflow": False}


def _hero(page, text, measure, bubble, bubble_height, panel, pet, rect, colors, profile, paper,
          contrast, n):
    """Cover: one big number or three facts, a question from 귤귤, and all three pets."""
    if page.get("number"):
        lw = 520
        nh = measure(page["number"], SIZE["number"], lw, True, 1.08)
        ch = measure(page["number_caption"], SIZE["number_caption"], lw, False, 1.45)
        if TOP + nh + 32 + ch > 950:
            raise SkillError(f"{n}장 표지 숫자: 공간보다 커요. 숫자나 설명을 줄이세요.")
        accent = colors[1] if contrast(colors[1], paper) >= 4.5 else profile["text"]
        text(page["number"], X0, TOP, lw, nh, SIZE["number"], "그림 숫자", True, color=accent, leading=1.08)
        rect(X0, TOP + nh + 8, 96, 8, colors[0])
        text(page["number_caption"], X0, TOP + nh + 32, lw, ch, SIZE["number_caption"], "그림 숫자 설명",
             leading=1.45)
        cx, cw = 650, 326
        bh = bubble_height(page["question"], cw)
        bubble(page["question"], cx, TOP, cw, bh, 2, "bottom")
        room = 950 - (TOP + bh + 30)
        if room < 150:
            raise SkillError(f"{n}장 표지 질문: 너무 길어요.")
        pet("gyulmo", "think", cx + 40, 950, cw - 80, min(220, room), "asks-question")
    else:
        bh = bubble_height(page["question"], 644)
        pet("gyulmo", "think", X0, TOP + max(bh, 164), 194, 164, "asks-question")
        bubble(page["question"], 332, TOP, 644, bh, 2, "left")
        fy = TOP + max(bh, 164) + 30
        need = max(panel(0, 0, 276, 0, t, b, 0, False) for t, b in page["facts"])
        if fy + need > 950:
            raise SkillError(f"{n}장 표지 요약: 공간보다 커요. 요약을 줄이세요.")
        for k, (t, b) in enumerate(page["facts"]):
            panel(X0 + k * 298, fy, 276, need, t, b, (2, 1, 0)[k])
    pet("harubang", "explain", 130, 1118, 150, 150, "introduces-topic")
    pet("halla", "wave", 800, 1118, 150, 150, "points-to-request")
    text(page["note"], 330, 985, 420, 110, 32, "그림 메모", True, align="center", valign="middle")


def make_preview(plan: dict, diagrams: dict, reports: list[dict]) -> Callable:
    """Accessible preview page whose alt text summarises each scene."""
    pages = diagrams["pages"]

    def summary(page: dict) -> str:
        parts = [page.get("question", ""), page.get("number", ""), page.get("number_caption", "")]
        for key in ("steps", "panels", "flow", "facts"):
            parts += [f"{t}: {b}" for t, b in page.get(key, [])]
        parts += [" ".join(r) for r in page.get("rows", [])]
        parts += page.get("items", []) + [page.get("note", ""), page.get("speech", "")]
        return " ".join(p.replace("\n", " ") for p in parts if p)

    def preview(plan_: dict, paths: list[str], status: str, notes: str | None, digest: str) -> str:
        esc = html.escape
        cards = []
        for i, (slide, rel) in enumerate(zip(plan_["slides"], paths), 1):
            page = pages[i - 1]
            title = slide["title"].replace("\n", " ")
            alt = page.get("alt") or f"{title}. {summary(page)}"
            texts = [b["text"] for b in (reports[i - 1]["blocks"] if i <= len(reports) else []) if b["text"]]
            paragraphs = "".join("<p>" + esc(t).replace("\n", "<br>") + "</p>" for t in texts)
            jpg = rel.replace("png/", "jpeg/").replace(".png", ".jpg")
            cards.append(f'<article><a href="{esc(rel)}" aria-label="{i}장 크게 보기">'
                         f'<img src="{esc(rel)}" alt="{esc(alt, quote=True)}" width="2160" height="2700"></a>'
                         f'<p class="downloads"><a download href="{esc(rel)}">{i}장 PNG</a>'
                         f' · <a download href="{esc(jpg)}">JPEG</a></p>'
                         f'<details><summary>{i}장 문구 읽기</summary>{paragraphs}</details></article>')
        state = "검토용 초안" if status == "draft" else "문안 승인본"
        intro = esc(diagrams.get("preview_intro", "이미지를 누르면 크게 볼 수 있어요."))
        note = esc(diagrams.get("preview_note", ""))
        return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{esc(plan_["series_title"])}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#eef3f1;color:#172532;font-family:Pretendard,system-ui,sans-serif}}
header,main,footer{{max-width:1180px;margin:auto;padding:28px}}header{{padding-top:48px}}
h1{{font-size:clamp(26px,4vw,38px);line-height:1.35;margin:12px 0}}p{{line-height:1.65}}
main{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:36px}}
article{{min-width:0}}img{{display:block;width:100%;height:auto}}a{{color:#0167a8;text-underline-offset:4px}}
.downloads{{margin:12px 0}}details{{padding:16px;background:#fff}}summary{{cursor:pointer}}
details p{{margin:12px 0}}nav{{display:flex;gap:12px 24px;flex-wrap:wrap}}
footer{{padding-bottom:48px}}@media(max-width:760px){{main{{grid-template-columns:1fr}}header,main,footer{{padding:20px}}}}
</style></head><body><header><p>{esc(plan_["series_title"])} · {state} · {len(paths)}장</p>
<h1>{esc(plan_.get("head_copy") or plan_["series_title"])}</h1><p>{intro}</p>
<nav><a download href="cardnews.zip">전체 자료 ZIP</a><a download href="cardnews-editable.pptx">편집용 PPTX</a>
<a href="SOURCES.md">설명 근거</a></nav></header><main>{''.join(cards)}</main>
<footer>{f"<p>{note}</p>" if note else ""}<p>편집용 PPTX를 사용하는 PC에는 Pretendard가 필요해요.</p></footer></body></html>'''
    return preview
