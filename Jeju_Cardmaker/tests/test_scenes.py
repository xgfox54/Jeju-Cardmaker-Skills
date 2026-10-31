"""Behaviour tests for the scene-type layout engine using real Pretendard renders."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from card_pipeline import inspect_run  # noqa: E402
from card_scenes import plan_characters, validate_scenes  # noqa: E402
from rp_core import SkillError, read_json, write_json  # noqa: E402
from scene_build import build_scenes  # noqa: E402

EXAMPLE = SKILL / "assets" / "scene-example"


class SceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.project = cls.root / "project"
        shutil.copytree(EXAMPLE, cls.project)
        cls.run_dir = build_scenes(cls.project, cls.root / "run", preset="portrait")
        cls.report = read_json(cls.run_dir / "render-report.json")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def project_copy(self, name):
        target = self.root / name
        shutil.copytree(EXAMPLE, target)
        return target

    def test_example_passes_inspection(self):
        # Given the bundled scene example. When inspected. Then every page passes.
        result = inspect_run(self.project, self.run_dir)
        self.assertTrue(result.passed, result.errors)
        self.assertEqual(len(result.pages), 8)

    def test_same_role_same_size_on_every_page(self):
        # Given a deck. When blocks are grouped by role. Then each role uses one size only.
        sizes = {}
        for page in self.report["pages"]:
            for block in page["blocks"]:
                role = block["label"].split(" ", 1)[1]
                if role in ("그림 제목", "그림 설명", "그림 숫자 설명", "그림 표 제목", "그림 표 설명", "캐릭터 말", "본문"):
                    sizes.setdefault(role, set()).add(block["size"])
        self.assertTrue(sizes)
        for role, found in sizes.items():
            self.assertEqual(len(found), 1, role)

    def test_neighbouring_pages_change_character_place_and_pet(self):
        # Given body pages. When characters are placed. Then neighbours never repeat place or pet.
        body = [p for p in self.report["pages"] if p["scene"] not in ("hero", "checklist")]
        for before, after in zip(body, body[1:]):
            self.assertNotEqual(before["placement"], after["placement"])
            self.assertNotEqual(before["pets"][0]["id"], after["pets"][0]["id"])

    def test_cover_and_closing_show_all_three_pets(self):
        pages = self.report["pages"]
        for page in (pages[0], pages[-1]):
            self.assertEqual({p["id"] for p in page["pets"]}, {"gyulmo", "harubang", "halla"})

    def test_cover_number_is_the_largest_text(self):
        cover = self.report["pages"][0]
        biggest = max(cover["blocks"], key=lambda b: b["size"])
        self.assertEqual(biggest["text"], read_json(EXAMPLE / "diagrams.json")["pages"][0]["number"])

    def test_overflow_is_reported_instead_of_shrinking(self):
        # Given five long rows plus speech. When built. Then the author is told to split the page.
        project = self.project_copy("overflow")
        diagrams = read_json(project / "diagrams.json")
        rows = diagrams["pages"][5]["rows"]
        diagrams["pages"][5]["rows"] = rows + [["추가 서점", "긴 설명이 들어간 문의 내용입니다 " * 3, "거절"]]
        write_json(project / "diagrams.json", diagrams)
        with self.assertRaisesRegex(SkillError, "장을 나누"):
            build_scenes(project, self.root / "overflow-run", preset="portrait", pptx=False)

    def test_unknown_scene_is_rejected_before_drawing(self):
        diagrams = read_json(EXAMPLE / "diagrams.json")
        diagrams["pages"][2]["scene"] = "collage"
        with self.assertRaisesRegex(SkillError, "scene"):
            validate_scenes(read_json(EXAMPLE / "plan.json"), diagrams)

    def test_page_without_speech_puts_character_beside_title(self):
        # Given a large diagram and no speech. When planned. Then the character moves beside the title.
        plan = read_json(EXAMPLE / "plan.json")
        diagrams = read_json(EXAMPLE / "diagrams.json")
        diagrams["pages"][1].pop("speech")
        places = plan_characters(plan, validate_scenes(plan, diagrams))
        self.assertEqual(places[1]["place"], "title-right")
        project = self.project_copy("title-right")
        write_json(project / "diagrams.json", diagrams)
        run = build_scenes(project, self.root / "title-right-run", preset="portrait", pptx=False)
        page = read_json(run / "render-report.json")["pages"][1]
        self.assertEqual(page["placement"], "title-right")
        self.assertLess(page["pets"][0]["y"] + page["pets"][0]["height"], 428)

    def test_changed_diagram_requires_rebuild(self):
        project = self.project_copy("changed")
        run = build_scenes(project, self.root / "changed-run", preset="portrait")
        diagrams = read_json(project / "diagrams.json")
        diagrams["pages"][2]["speech"] = "바뀐 말풍선이에요."
        write_json(project / "diagrams.json", diagrams)
        self.assertIn("INPUT", [i.code for i in inspect_run(project, run).errors])


if __name__ == "__main__":
    unittest.main()
