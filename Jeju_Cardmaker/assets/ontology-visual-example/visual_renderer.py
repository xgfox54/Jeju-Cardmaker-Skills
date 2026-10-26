"""Staff learning cards using the bundled Jeju characters and measured text."""
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Any

from rp_core import SkillError, read_json, sha256
from rp_render import fit_block, left_overhang

fit_learning_block = partial(fit_block, prefer_words=True)

from rp_seogwipo import PET_ROOT
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
        spec = fit_learning_block(draw, value, path, px(w), px(3000), px(hi), px(lo), f"{index+1}장 {label}")
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

    diagrams = read_json(Path(__file__).with_name("diagrams.json"))
    diagram = diagrams["pages"][index]
    light = ("#EAF6F1", "#EAF3FA", "#FFF3E5")

    def label_text(value, x, y, w, h=48, fs=30, strong=False, bg=paper):
        return text(value, x, y, w, h, fs, fs, "그림 설명", strong,
                    background=bg, align="center", valign="middle")

    def arrow(x, y, w, label, color=profile["text"]):
        rect(x, y-1.5, w-12, 3, color)
        for step in range(16):
            rect(x+w-16+step, y-12+step*.75, 1.2, 24-step*1.5, color)
        label_text(label, x-8, y-65, w+16, 45, 27, True)

    def node(x, y, w, h, title, caption, n):
        frame(x, y, w, h, light[n], colors[n], 2)
        label_text(caption, x+8, y+15, w-16, 42, 27, True, light[n])
        label_text(title, x+8, y+64, w-16, h-74, 32, True, light[n])
        obstacles.append([px(x), px(y), px(x+w), px(y+h)])

    def chain(y, names=None):
        names = names or diagrams["chain_names"]
        for n in range(3):
            node(104+n*338, y, 196, 160, names[n], diagrams["chain_types"][n], n)
        arrow(300, y+105, 142, diagrams["chain_relations"][0])
        arrow(638, y+105, 142, diagrams["chain_relations"][1])

    def icon(kind, x, y, color):
        if kind == 0:
            frame(x, y, 68, 64, paper, color, 3)
            for xx in (12, 40):
                for yy in (12, 32):
                    rect(x+xx, y+yy, 12, 10, color)
            rect(x+28, y+48, 12, 16, color)
        elif kind == 1:
            frame(x+4, y+5, 60, 61, paper, color, 3)
            rect(x+19, y, 30, 12, color)
            for yy in (24, 40, 54):
                rect(x+14, y+yy, 8, 4, color)
                rect(x+29, y+yy, 25, 4, color)
        else:
            frame(x+8, y, 52, 68, paper, color, 3)
            for yy in (20, 34, 48):
                rect(x+18, y+yy, 32, 3, color)

    text(plan["series_title"], 56, 42, 800, 60, 28, 23, "시리즈", True, profile["background"])
    text(f"{index+1:02d} / {len(plan['slides']):02d}", 888, 46, 136, 40, 25, 23, "쪽수", background=profile["background"])
    frame(48, 130, 984, logical_h-340, paper, border, 6)
    for n, color in enumerate((colors[2], colors[1], colors[0])):
        circle(48+n*34, 96, 20, color)
    badges = ["업무로 이해", "업무 상황", "개념 이해", "관계 이해", "기록하기", "추론 이해", "확인하기", "직접 해보기"]
    rect(104, 178, 176, 48, border)
    badge_color = "#FFFFFF" if contrast("#FFFFFF", border) >= 4.5 else profile["text"]
    text(badges[index], 104, 178, 176, 48, 24, 24, "분류", True, border, badge_color, align="center", valign="middle")
    text(slide["title"], 104, 265, 872, 174, 60 if cover else 54, 54, "제목", True, leading=1.25)
    text("\n".join(slide["bullets"]), 104, 443, 872, 120, 32, 32, "본문", leading=1.5)

    if index == 0:
        label_text(diagram["caption"], 104, 598, 872, 50, 30)
        chain(682)
    elif index == 1:
        frame(104, 590, 872, 76, light[1], colors[1], 2)
        label_text(diagram["question"], 118, 590, 844, 76, 31, True, light[1])
        chain(714)
        label_text(diagram["caption"], 104, 894, 872, 50, 29)
    elif index == 2:
        for n in range(3):
            x = 104+n*298
            frame(x, 600, 276, 320, light[n], colors[n], 2)
            icon(n, x+104, 629, colors[n])
            label_text(diagrams["chain_types"][n], x+12, 714, 252, 45, 36, True, light[n])
            label_text(diagram["descriptions"][n], x+10, 768, 256, 45, 28, False, light[n])
            label_text(diagram["example_label"], x+10, 829, 256, 30, 23, False, light[n])
            label_text(diagram["examples"][n], x+8, 866, 260, 40, 30, True, light[n])
    elif index == 3:
        label_text(diagram["caption"], 104, 585, 872, 50, 32, True)
        chain(670)
        for n, sentence in enumerate(diagram["sentences"]):
            label_text(sentence, 104, 850+n*43, 872, 40, 28)
    elif index in (4, 6):
        for n, names in enumerate(diagram["rows"]):
            y = 641+n*185
            text(diagram["row_labels"][n], 104, y-48, 872, 40, 27, 27, "그림 행", True)
            tone = 1 if index == 4 else n
            frame(104, y, 300, 112, light[tone], colors[tone], 2)
            label_text(names[0], 112, y+8, 284, 96, 36, True, light[tone])
            frame(676, y, 300, 112, light[1], colors[1], 2)
            label_text(names[1], 684, y+8, 284, 96, 34, True, light[1])
            arrow(404, y+66, 272, diagram["relation"])
    elif index == 5:
        frame(104, 591, 590, 333, light[1], colors[1], 3)
        text(diagram["outer"], 132, 611, 500, 46, 34, 34, "그림 큰 종류", True, light[1])
        frame(150, 677, 498, 210, light[2], colors[2], 3)
        text(diagram["inner"], 178, 696, 420, 42, 32, 32, "그림 작은 종류", True, light[2])
        frame(200, 756, 398, 105, paper, "#D7E2DF", 2)
        icon(2, 219, 775, colors[2])
        label_text(diagram["instance"], 293, 765, 293, 88, 30, True)
        frame(736, 711, 240, 145, light[0], colors[0], 2)
        label_text(diagram["conclusion"], 752, 724, 208, 116, 32, True, light[0])
    else:
        label_text(diagram["caption"], 104, 584, 872, 50, 30)
        chain(652, diagram["names"])

    if cover or closing:
        if closing:
            rect(104, 846, 872, 94, "#EEF3F1")
            text(slide["takeaway"], 126, 850, 828, 86, 30, 30, "정리", True, "#EEF3F1", valign="middle")
        for n in range(3):
            pet(n, ("wave", "explain", "wave")[n] if cover else "cheer", 210+n*250,
                1090, 180 if cover else 144, 195 if cover else 145, "diagram-guide-group")
    else:
        pet_left = index in (2, 5)
        pet_x, note_x = (104, 306) if pet_left else (818, 104)
        rect(note_x, 981, 670, 111, "#EEF3F1")
        rect(note_x, 981, 4, 111, border)
        text(slide["takeaway"], note_x+24, 991, 622, 91, 30, 30, "정리", True, "#EEF3F1", valign="middle")
        pet(index % 3, "caution" if index == 6 else "explain", pet_x, 1106, 158, 162, "beside-diagram-note")

    text(slide["footnote"], 56, logical_h-174, 968, 83, 23, 19, "출처/각주", background=profile["background"])
    text("검토용 초안", 56, logical_h-67, 210, 35, 21, 19, "상태", background=profile["background"])
    warnings = [f"{index+1}장 {b['label']}: 글자 대비 {b['contrast_ratio']}" for b in blocks if b["text"] and b["contrast_ratio"] < 4.5]
    return image, {"page": index+1, "size": list(size), "background": profile["background"],
                   "template": "seogwipo-ai-ontology-diagrams", "layout": layout,
                   "border_color": border, "content_obstacles": obstacles,
                   "blocks": blocks, "shapes": shapes, "pets": pets, "logo": None,
                   "warnings": warnings, "overflow": False}
