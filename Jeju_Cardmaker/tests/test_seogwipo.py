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
from rp_seogwipo import PET_FILES, PET_ROOT, validate_pets
from rp_studio import build_project, verify_build
from PIL import Image
from pptx import Presentation


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
