"""End-to-end checks for staff learning cards and asset provenance."""
from __future__ import annotations

import socket
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from rp_core import SkillError, plan_hash, plan_strings, read_json, review_markdown, validate_plan, write_json
from rp_render import create_run, load_profile, resolve_fonts
from rp_seogwipo import PET_FILES, PET_ROOT, POSES, validate_pets
from rp_studio import build_project, verify_build
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.plan = read_json(SKILL / "assets/seogwipo-ai-example/plan.json")
        write_json(self.project / "plan.json", self.plan)
        (self.project / "SOURCES.md").write_text("[1] 가상 업무 예시\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_default_build_preserves_content_fonts_characters_and_zip(self):
        with patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
            out = build_project(self.project, self.root / "out", preset="portrait")
        self.assertTrue(verify_build(out)["ok"])
        report = read_json(out / "render-report.json")
        self.assertEqual(report["fonts"], ["Pretendard-Regular.otf", "Pretendard-Bold.otf"]
                         if report["fonts"][0].endswith(".otf") else ["Pretendard-Regular.ttf", "Pretendard-Bold.ttf"])
        self.assertEqual({p["border_color"] for p in report["pages"]}, {"#00A074", "#0173BC", "#F18101"})
        prs = Presentation(out / "cardnews-editable.pptx")
        for number, (page, source, slide) in enumerate(zip(report["pages"], self.plan["slides"], prs.slides)):
            self.assertEqual(page["template"], "seogwipo-ai")
            self.assertFalse(page["warnings"])
            self.assertEqual(len(page["pets"]), 3 if number in (0, 7) else 1)
            dots = [s for s in page["shapes"] if s.get("kind") == "ellipse"]
            self.assertEqual([s["fill"] for s in dots], ["#F18101", "#0173BC", "#00A074"])
            self.assertEqual(dots[0]["x"], page["shapes"][0]["x"])
            self.assertTrue(all(s["y"]+s["height"] < page["shapes"][0]["y"] for s in dots))
            label = next(b for b in page["blocks"] if b["label"].endswith("장 분류"))
            left, top, right, bottom = label["glyph_bounds"][0]
            self.assertLessEqual(abs((left+right)/2-(label["x"]+label["box_width"]/2)), 1)
            self.assertLessEqual(abs((top+bottom)/2-(label["y"]+label["box_height"]/2)), 1)
            ppt_label = next(s for s in slide.shapes if s.name == label["label"])
            self.assertEqual(ppt_label.text_frame.vertical_anchor, MSO_ANCHOR.MIDDLE)
            self.assertEqual(ppt_label.text_frame.paragraphs[0].alignment, PP_ALIGN.CENTER)
            with Image.open(out / ("png/01_cover.png" if number == 0 else
                                   f"png/{number+1:02d}_{source['role']}.png")) as rendered:
                for dot in dots:
                    self.assertEqual(dot["width"], dot["height"])
                    self.assertEqual(rendered.getpixel((dot["x"]+10, dot["y"]+10)),
                                     tuple(bytes.fromhex(dot["fill"][1:])))
                # The entire bottom edge belongs to the page's single border color.
                for x in (60, 400, 700, 1020):
                    self.assertEqual(rendered.getpixel((x, 1138)),
                                     tuple(bytes.fromhex(page["border_color"][1:])))
            ovals = [s for s in slide.shapes if s.shape_type == 1 and s.auto_shape_type == MSO_SHAPE.OVAL]
            self.assertEqual([str(s.fill.fore_color.rgb) for s in ovals], ["F18101", "0173BC", "00A074"])
            for pet in page["pets"]:
                self.assertIn(pet["pose"], POSES)
                self.assertIn("-"+pet["pose"]+".png", pet["asset"])
                for left, top, right, bottom in page["content_obstacles"]:
                    self.assertTrue(pet["x"]+pet["width"] <= left or pet["x"] >= right or
                                    pet["y"]+pet["height"] <= top or pet["y"] >= bottom)
            all_text = "".join(s.text for s in slide.shapes if s.has_text_frame)
            clean = lambda value: "".join(value.split())
            for value in [source["title"], *source["bullets"], source.get("takeaway", ""), source["footnote"]]:
                self.assertIn(clean(value), clean(all_text))
            pictures = [s for s in slide.shapes if s.shape_type == 13]
            self.assertEqual(len(pictures), len(page["pets"]))
            for picture, pet in zip(pictures, page["pets"]):
                self.assertEqual(picture.image.blob, (SKILL / pet["asset"]).read_bytes())
            for block in page["blocks"]:
                if not block["text"]:
                    continue
                self.assertEqual(block["font_family"], "Pretendard")
                self.assertGreaterEqual(block["contrast_ratio"], 4.5)
                for left, top, right, bottom in block["glyph_bounds"]:
                    self.assertGreaterEqual(left, block["x"])
                    self.assertLessEqual(right, block["x"] + block["box_width"])
                    self.assertLessEqual(bottom, block["y"] + block["box_height"])
                    for pet in page["pets"]:
                        self.assertTrue(right <= pet["x"] or left >= pet["x"]+pet["width"] or
                                        bottom <= pet["y"] or top >= pet["y"]+pet["height"])
        with zipfile.ZipFile(out / "cardnews.zip") as archive:
            for filename in PET_FILES:
                self.assertEqual(archive.read("assets/jeju-pets/"+filename), (PET_ROOT/filename).read_bytes())
        self.assertIn(self.plan["slides"][1]["takeaway"], (out/"preview.html").read_text(encoding="utf-8"))

    def test_high_resolution_and_single_page_keep_all_three(self):
        self.plan["slides"] = self.plan["slides"][:1]
        write_json(self.project/"plan.json", self.plan)
        out = build_project(self.project, self.root/"out", pptx=False)
        with Image.open(out/"png/01_cover.png") as image:
            self.assertEqual(image.size, (2160, 2700))
        report = read_json(out/"render-report.json")
        self.assertEqual({p["id"] for p in report["pages"][0]["pets"]}, {"gyulmo", "harubang", "halla"})
        page = report["pages"][0]
        self.assertEqual([s["width"] for s in page["shapes"] if s.get("kind") == "ellipse"], [40]*3)
        for dot in [s for s in page["shapes"] if s.get("kind") == "ellipse"]:
            self.assertLess(dot["y"]+dot["height"], page["shapes"][0]["y"])
        label = next(b for b in page["blocks"] if b["label"].endswith("장 분류"))
        left, top, right, bottom = label["glyph_bounds"][0]
        self.assertLessEqual(abs((left+right)/2-(label["x"]+label["box_width"]/2)), 1)
        self.assertLessEqual(abs((top+bottom)/2-(label["y"]+label["box_height"]/2)), 1)

    def test_whitespace_placement_changes_with_text_length(self):
        self.plan["slides"] = [self.plan["slides"][0], self.plan["slides"][4], self.plan["slides"][-1]]
        write_json(self.project/"plan.json", self.plan)
        short = build_project(self.project, self.root/"short", preset="portrait", pptx=False)
        first = read_json(short/"render-report.json")["pages"][1]
        self.plan["slides"][1]["title"] = "공개 행사 안내문을 활용하여 요청문을 작성합니다"
        write_json(self.project/"plan.json", self.plan)
        long = build_project(self.project, self.root/"long", preset="portrait", pptx=False)
        second = read_json(long/"render-report.json")["pages"][1]
        a, b = first["pets"][0], second["pets"][0]
        self.assertNotEqual((a["x"], a["y"]), (b["x"], b["y"]))
        for page in (first, second):
            pet = page["pets"][0]
            self.assertEqual(pet["placement"], "measured-whitespace")
            boxes = page["content_obstacles"] + [g for block in page["blocks"] for g in block["glyph_bounds"]]
            for left, top, right, bottom in boxes:
                self.assertTrue(pet["x"]+pet["width"] <= left or pet["x"] >= right or
                                pet["y"]+pet["height"] <= top or pet["y"] >= bottom)

    def test_comparison_preserves_korean_word_boundaries(self):
        out = build_project(self.project, self.root/"out", preset="portrait", pptx=False)
        page = read_json(out/"render-report.json")["pages"][2]
        body = next(b for b in page["blocks"] if b["label"].endswith("장 비교 2"))
        self.assertTrue(any("일정·장소·준비물을" in line for line in body["lines"]))

    def test_pose_catalog_has_distinct_transparent_frames_and_provenance(self):
        manifest = validate_pets()
        self.assertEqual(len(manifest["poses"]), 21)
        for pet in ("gyulmo", "harubang", "halla"):
            hashes = set()
            for pose in POSES:
                filename = f"{pet}-{pose}.png"
                record = manifest["poses"][filename]
                self.assertEqual(record["box"], [record["column"]*192, record["row"]*208,
                                                (record["column"]+1)*192, (record["row"]+1)*208])
                hashes.add(manifest["sha256"][filename])
                with Image.open(PET_ROOT / filename) as frame:
                    self.assertEqual(frame.size, (192, 208))
                    self.assertEqual(frame.mode, "RGBA")
                    self.assertEqual(frame.getchannel("A").getextrema(), (0, 255))
            self.assertEqual(len(hashes), len(POSES))

    def test_new_copy_is_reviewed_and_invalidates_approval_hash(self):
        text = self.plan["slides"][1]["takeaway"]
        self.assertIn(text, plan_strings(self.plan))
        self.assertIn(text, review_markdown(self.plan))
        previous = plan_hash(self.plan)
        self.plan["slides"][1]["takeaway"] += " 수정"
        self.assertNotEqual(previous, plan_hash(self.plan))

    def test_unsupported_fields_are_not_silently_dropped(self):
        for profile in ("jeju", "neutral"):
            with self.assertRaises(SkillError):
                build_project(self.project, self.root/profile, profile_name=profile)
        with self.assertRaises(SkillError):
            create_run(self.plan, self.root/"old", load_profile("jeju"))

    def test_comparison_requires_two_items(self):
        self.plan["slides"][2]["bullets"].append("세 번째 비교")
        with self.assertRaises(SkillError):
            validate_plan(self.plan)

    def test_no_silent_font_substitution(self):
        with self.assertRaises(SkillError):
            resolve_fonts("missing.ttf", "missing-bold.ttf", required_family="Pretendard")

    def test_changed_or_missing_pet_fails_before_output(self):
        with patch("rp_seogwipo.read_json", return_value={"sha256": {}}):
            with self.assertRaises(SkillError):
                build_project(self.project, self.root/"out", pptx=False)
        self.assertFalse((self.root/"out").exists())
        with patch("rp_seogwipo.PET_ROOT", self.root):
            with self.assertRaises(OSError):
                validate_pets()

    def test_long_body_does_not_hide_text_under_pets(self):
        self.plan["slides"][1]["bullets"] = ["확인할 내용 " * 150] * 8
        write_json(self.project/"plan.json", self.plan)
        with self.assertRaises(SkillError):
            build_project(self.project, self.root/"out", pptx=False)
        self.assertFalse((self.root/"out").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
