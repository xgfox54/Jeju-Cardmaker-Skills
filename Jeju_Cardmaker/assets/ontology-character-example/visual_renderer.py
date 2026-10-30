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


    def bubble(value, x, y, w, h, tone=1, tail="left", fs=32):
        # Stair-step tails use the same editable rectangles in PNG and PPTX.
        frame(x, y, w, h, light[tone], colors[tone], 2)
        if tail in ("left", "right"):
            for step in range(18):
                xx = x-18+step if tail == "left" else x+w+17-step
                rect(xx, y+h*.62-step*.55, 1.2, 2+step*1.1, colors[tone])
        elif tail == "bottom":
            for step in range(18):
                rect(x+w*.5-18+step, y+h+step, 36-2*step, 1.2, colors[tone])
        text(value, x+24, y+16, w-48, h-32, fs, fs, "캐릭터 안내",
             False, light[tone], valign="middle", leading=1.38)

    def line_note(value, x=104, y=1035, w=872, h=65, fs=30):
        text(value, x, y, w, h, fs, fs, "그림 정리", True,
             valign="middle", leading=1.35)

    text(plan["series_title"], 56, 42, 800, 60, 28, 23, "시리즈", True, profile["background"])
    text(f"{index+1:02d} / {len(plan['slides']):02d}", 888, 46, 136, 40, 25, 23, "쪽수", background=profile["background"])
    frame(48, 130, 984, logical_h-340, paper, border, 6)
    for n, color in enumerate((colors[2], colors[1], colors[0])):
        circle(48+n*34, 96, 20, color)
    badges = ["업무로 이해", "업무 상황", "개념 이해", "관계 이해", "기록하기", "추론 이해", "확인하기", "직접 해보기"]
    rect(104, 178, 176, 48, border)
    badge_color = "#FFFFFF" if contrast("#FFFFFF", border) >= 4.5 else profile["text"]
    text(badges[index], 104, 178, 176, 48, 24, 24, "분류", True, border, badge_color, align="center", valign="middle")
    text(slide["title"], 104, 265, 872, 146, 56 if cover else 54, 54, "제목", True, leading=1.25)
    text("\n".join(slide["bullets"]), 104, 428, 872, 112, 32, 32, "본문", leading=1.5)

    if index == 0:
        bubble("안내문과 담당팀을\n함께 찾을 수 있나요?", 348, 576, 600, 133, 2)
        pet(0, "think", 120, 746, 194, 210, "asks-about-work")
        chain(787)
        pet(1, "explain", 122, 1110, 130, 141, "introduces-relationship")
        pet(2, "wave", 828, 1110, 130, 141, "joins-learning")
        text("말의 뜻과 관계를\n함께 정해 봐요.", 300, 994, 480, 94, 34, 34,
             "학습 안내", True, align="center", valign="middle")
    elif index == 1:
        bubble("안내문에 관해\n어느 팀에 물어보면 되나요?", 104, 573, 647, 131, 2, "right")
        pet(0, "think", 793, 718, 180, 195, "asks-for-owner")
        chain(758)
        pet(1, "explain", 104, 1111, 170, 184, "explains-search-path")
        bubble("안내문을 쓰는 업무를 확인해요.\n이 업무의 담당은 A팀이에요.", 326, 976, 650, 130, 1, fs=30)
    elif index == 2:
        for n in range(3):
            x = 104+n*298
            frame(x, 586, 276, 456, light[n], colors[n], 2)
            label_text(diagrams["chain_types"][n], x+12, 614, 252, 50, 40, True, light[n])
            label_text(diagram["descriptions"][n], x+10, 680, 256, 45, 27, False, light[n])
            pet(n, ("explain", "walk-right", "think")[n], x+36, 946, 204, 221, "guides-type-example")
            label_text(diagram["examples"][n], x+10, 977, 256, 44, 30, True, light[n])
        line_note("부서·업무·문서는 대상을 나누는 종류예요.", y=1061, h=40)
    elif index == 3:
        bubble("선 위에 관계의 뜻을 적어요.", 104, 573, 650, 89, 1, "right", 30)
        pet(1, "explain", 793, 683, 180, 195, "points-to-relationship")
        chain(727)
        rect(104, 939, 872, 157, light[1])
        for n, sentence in enumerate(diagram["sentences"]):
            circle(128, 970+n*62, 10, colors[1])
            text(sentence, 157, 954+n*62, 787, 54, 31, 31,
                 "관계 문장", background=light[1], valign="middle")
    elif index == 4:
        bubble("먼저 종류를,\n그다음 이름을\n적어요.", 104, 594, 240, 187, 1, "bottom", 30)
        pet(1, "explain", 104, 1073, 240, 260, "explains-template-and-record")
        for n, names in enumerate(diagram["rows"]):
            y = 658+n*225
            text(diagram["row_labels"][n], 390, y-58, 586, 42, 29, 29, "그림 행", True)
            for j, value in enumerate(names):
                x, w = (390, 183) if j == 0 else (750, 226)
                frame(x, y, w, 125, light[j], colors[j], 2)
                label_text(value, x+10, y+20, w-20, 85, 32, True, light[j])
            arrow(573, y+73, 177, diagram["relation"])
        line_note("같은 틀에 다른 업무도\n기록할 수 있어요.", x=390, y=1040, w=586, h=74, fs=30)
    elif index == 5:
        frame(104, 590, 536, 453, light[1], colors[1], 3)
        text(diagram["outer"], 134, 620, 450, 50, 38, 38, "큰 종류", True, light[1])
        frame(148, 712, 448, 284, light[2], colors[2], 3)
        text(diagram["inner"], 177, 742, 390, 48, 34, 34, "작은 종류", True, light[2])
        frame(188, 833, 368, 120, paper, "#CBD8D3", 2)
        label_text(diagram["instance"], 211, 845, 322, 96, 31, True)
        bubble(diagram["conclusion"], 700, 614, 276, 148, 0, "bottom", 34)
        pet(2, "explain", 712, 1050, 252, 273, "explains-inclusion")
        line_note("정해 둔 뜻과 기록으로 얻은 결론이 ‘추론’이에요.", y=1067, h=40, fs=29)
    elif index == 6:
        for n, names in enumerate(diagram["rows"]):
            x = 104+n*448
            frame(x, 585, 424, 285, light[n], colors[n], 2)
            text(diagram["row_labels"][n], x+27, 611, 370, 46, 29, 29, "변경 단계", True, light[n])
            label_text(names[0], x+24, 680, 142, 64, 44, True, light[n])
            label_text("주민설명회", x+209, 680, 191, 64, 31, True, light[n])
            arrow(x+168, 717, 38, "")
            label_text("담당해요", x+24, 780, 376, 55, 30, True, light[n])
        pet(0, "caution", 104, 1111, 180, 195, "checks-changed-record")
        bubble("새 담당팀으로 기록을 고치고\n실제 업무와 맞는지 확인해요.", 328, 922, 648, 130, 2, fs=31)
        text("담당 변경은 사람이 확인해요.", 352, 1072, 600, 37, 30, 30, "확인 책임")
    else:
        chain(602, diagram["names"])
        for n in range(3):
            x = 104+n*298
            text(("우리 팀 이름", "맡은 업무", "쓰는 문서")[n], x+6, 799, 264, 45, 29, 29,
                 "연습 안내", True, align="center", valign="middle")
            rect(x+19, 881, 238, 2, "#8A9C95")
        pet(0, "think", 104, 1106, 168, 182, "fills-team-name")
        pet(1, "explain", 798, 1106, 168, 182, "supports-practice")
        pet(2, "cheer", 464, 1020, 128, 139, "completes-practice")
        text("종류와 관계를 정하고\n실제 이름을 넣어요.", 278, 1034, 500, 78, 30, 30,
             "마지막 정리", True, align="center", valign="middle")

    text(slide["footnote"], 56, logical_h-174, 968, 83, 23, 19, "출처/각주", background=profile["background"])
    if not hide_status:
        text("검토용 초안" if status == "draft" else "문안 승인본", 56, logical_h-67, 210, 35, 21, 19,
             "상태", background=profile["background"])
    warnings = [f"{index+1}장 {b['label']}: 글자 대비 {b['contrast_ratio']}" for b in blocks if b["text"] and b["contrast_ratio"] < 4.5]
    return image, {"page": index+1, "size": list(size), "background": profile["background"],
                   "template": "seogwipo-ai-character-scenes", "layout": layout,
                   "border_color": border, "content_obstacles": obstacles,
                   "blocks": blocks, "shapes": shapes, "pets": pets, "logo": None,
                   "warnings": warnings, "overflow": False}
