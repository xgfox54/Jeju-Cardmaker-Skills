"""Behavior tests for review-bound delivery using real local build artifacts."""
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SKILL/"scripts"))
from card_pipeline import REVIEW_FIELDS, deliver, init_project, inspect_run, inspect_to_folder
from rp_core import SkillError, extract_document, read_json, sha256, validate_plan, write_json
from rp_studio import build_project, verify_build


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls.fixture.name)
        cls.project = cls.fixture_root/"project"
        cls.project.mkdir()
        plan = read_json(SKILL/"assets/sample.plan.json")
        for slide in plan["slides"]:
            slide["footnote"] = "[1] 시험용 가상 자료"
        write_json(cls.project/"plan.json",plan)
        (cls.project/"SOURCES.md").write_text("[1] 시험용 가상 자료\n",encoding="utf-8")
        (cls.project/"notes.md").write_text("검사 시험용 원문",encoding="utf-8")
        write_json(cls.project/"source.json",extract_document(cls.project/"notes.md"))
        cls.fixture_run = cls.fixture_root/"run"
        build_project(cls.project,cls.fixture_run,preset="portrait",profile_name="seogwipo-ai",source_path=str(cls.project/"source.json"))

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_copy = self.root/"project"
        self.run_copy = self.root/"run"
        shutil.copytree(self.project,self.project_copy)
        shutil.copytree(self.fixture_run,self.run_copy)

    def tearDown(self):
        self.temp.cleanup()

    def review(self):
        gate = inspect_run(self.project_copy,self.run_copy)
        self.assertTrue(gate.passed,gate.errors)
        data = {"version":1,"run_id":gate.run_id,"reviewer":"test fixture only",
                "sources_checked":True,"warning_notes":"Test fixture uses legacy copy.",
                "pages":[{"page":p.page,"png_sha256":p.sha256,
                    **{key:True for key in REVIEW_FIELDS}} for p in gate.pages]}
        file = self.root/"review.json"
        write_json(file,data)
        return file

    def reseal(self):
        """Keep integrity valid to test a deeper inspection failure independently."""
        manifest = read_json(self.run_copy/"manifest.json")
        for name in manifest["files"]:
            manifest["files"][name] = sha256((self.run_copy/name).read_bytes())
        write_json(self.run_copy/"manifest.json",manifest)
        with zipfile.ZipFile(self.run_copy/"cardnews.zip","w",zipfile.ZIP_DEFLATED) as archive:
            for name in [*manifest["files"],"manifest.json"]:
                archive.write(self.run_copy/name,name)

    def test_inspect_accepts_real_build(self):
        # Given a measured portrait build. When inspected. Then every page is covered.
        result = inspect_run(self.project_copy,self.run_copy)
        self.assertTrue(result.passed,result.errors)
        self.assertEqual(len(result.pages),3)

    def test_plan_change_requires_rebuild(self):
        # Given an edited source plan. When inspected. Then the old run is rejected.
        plan = read_json(self.project_copy/"plan.json")
        plan["slides"][0]["title"] += " 수정"
        write_json(self.project_copy/"plan.json",plan)
        result = inspect_run(self.project_copy,self.run_copy)
        self.assertFalse(result.passed)
        self.assertIn("INPUT",[issue.code for issue in result.errors])

    def test_changed_source_record_invalidates_review(self):
        # Given a review followed by changed research input. When delivered. Then no output exists.
        review = self.review()
        source = read_json(self.project_copy/"source.json")
        source["warnings"].append("new review context")
        write_json(self.project_copy/"source.json",source)
        with self.assertRaises(SkillError):
            deliver(self.project_copy,self.run_copy,review,self.root/"delivery")
        self.assertFalse((self.root/"delivery").exists())

    def test_missing_page_review_blocks_delivery(self):
        # Given a review missing one page. When delivered. Then delivery is rejected.
        review = self.review()
        data = read_json(review)
        data["pages"].pop()
        write_json(review,data)
        with self.assertRaises(SkillError):
            deliver(self.project_copy,self.run_copy,review,self.root/"delivery")
        self.assertFalse((self.root/"delivery").exists())

    def test_unchecked_visual_blocks_delivery(self):
        # Given one unreviewed page. When delivered. Then delivery is rejected.
        review = self.review()
        data = read_json(review)
        data["pages"][1]["visual_checked"] = False
        write_json(review,data)
        with self.assertRaises(SkillError):
            deliver(self.project_copy,self.run_copy,review,self.root/"delivery")

    def test_string_true_does_not_count_as_review(self):
        # Given a string in a boolean field. When delivered. Then it is not accepted.
        review = self.review()
        data = read_json(review)
        data["sources_checked"] = "true"
        write_json(review,data)
        with self.assertRaises(SkillError):
            deliver(self.project_copy,self.run_copy,review,self.root/"delivery")

    def test_deliver_preserves_draft_and_excludes_neighbors(self):
        # Given a reviewed draft and an unrelated neighbor. When delivered. Then only declared files ship.
        review = self.review()
        (self.run_copy/"private-neighbor.txt").write_text("not a build artifact")
        output = deliver(self.project_copy,self.run_copy,review,self.root/"delivery")
        self.assertTrue(verify_build(output/"cards")["ok"])
        self.assertEqual(read_json(output/"cards/manifest.json")["status"],"draft")
        self.assertFalse((output/"cards/private-neighbor.txt").exists())

    def test_existing_output_is_preserved(self):
        # Given an existing delivery directory. When delivered again. Then the sentinel stays intact.
        review = self.review()
        output = self.root/"delivery"
        output.mkdir()
        (output/"keep.txt").write_text("keep")
        with self.assertRaises(SkillError):
            deliver(self.project_copy,self.run_copy,review,output)
        self.assertEqual((output/"keep.txt").read_text(),"keep")

    def test_corrupt_png_is_rejected(self):
        # Given changed image bytes. When inspected. Then integrity failure stops delivery.
        next((self.run_copy/"png").glob("*.png")).write_bytes(b"bad image")
        self.assertFalse(inspect_run(self.project_copy,self.run_copy).passed)

    def test_overlapping_glyphs_are_rejected(self):
        # Given valid integrity but colliding measured lines. When inspected. Then overlap is reported.
        file = self.run_copy/"render-report.json"
        report = read_json(file)
        first = report["pages"][0]["blocks"][0]
        first["glyph_bounds"].append(first["glyph_bounds"][0])
        write_json(file,report)
        self.reseal()
        result = inspect_run(self.project_copy,self.run_copy)
        self.assertIn("OVERLAP",[issue.code for issue in result.errors])

    def test_small_body_is_rejected(self):
        # Given a measured body below the policy floor. When inspected. Then font failure is reported.
        file = self.run_copy/"render-report.json"
        report = read_json(file)
        body = next(block for page in report["pages"] for block in page["blocks"] if "본문" in block["label"])
        body["size"] = 10
        write_json(file,report)
        self.reseal()
        result = inspect_run(self.project_copy,self.run_copy)
        self.assertIn("FONT",[issue.code for issue in result.errors])

    def test_inspect_emits_every_page_unreviewed(self):
        # Given a valid run. When an inspection folder is written. Then all pages need explicit review.
        out = self.root/"qc"
        inspect_to_folder(self.project_copy,self.run_copy,out)
        review = read_json(out/"review.json")
        self.assertEqual(len(list(out.glob("page-*.png"))),3)
        self.assertTrue((out/"contact-01.png").is_file())
        self.assertTrue(all(page["visual_checked"] is False for page in review["pages"]))

    def test_init_requires_authored_content(self):
        # Given a topic. When scaffolded. Then the unfinished plan cannot build as finished content.
        out = init_project(self.root/"new","시험 주제","topic",5)
        self.assertEqual(len(read_json(out/"plan.json")["slides"]),5)
        with self.assertRaises(SkillError):
            validate_plan(read_json(out/"plan.json"))

    def test_missing_renderer_fingerprint_is_rejected(self):
        # Given a custom renderer without a recorded recipe. When inspected. Then provenance is incomplete.
        (self.project_copy/"visual_renderer.py").write_text("pass\n")
        result = inspect_run(self.project_copy,self.run_copy)
        self.assertIn("INPUT",[issue.code for issue in result.errors])


if __name__ == "__main__":
    unittest.main()
