"""Unit/contract tests using synthetic inputs and synthetic render-report fixtures.

These tests do not claim to execute the original rp_studio renderer.
"""
from __future__ import annotations
import copy
import json
import socket
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from rp_quality import (QualityError, attach_approval, canonical, contrast, decode_json,
                        normalized_plan, numeric_tokens, policy, postflight, preflight,
                        require_quality_approval, safe_file, seal_checked_build, sha,
                        source_digest, validate_source, verify_checked)
from quality_cli import checked_build, main


def fixture():
    sentence = "가상 서비스는 65세 이상에게 최대 10만원을 안내합니다."
    plan = {"series_title": "검증 기능 시험", "head_copy": "실제 정책 안내가 아닌 가상 시험입니다.",
            "slides": [{"role": "cover", "title": "제작 전에 근거를 확인합니다", "bullets": [sentence],
                        "footnote": "출처 [1] 가상 시험 자료"}]}
    source = {"schema_version": 1, "source_name": "fictional.txt", "source_sha256": sha(sentence.encode()),
              "format": "txt", "warnings": [], "complete_text_layer": True,
              "units": [{"locator": "text:1", "text": sentence}], "text": "[text:1]\n"+sentence}
    evidence = {"schema_version": 1, "as_of": "2026-10-09", "source_record_sha256": source_digest(source),
                "sources": [{"id": "1", "title": "가상 시험 자료", "reference": "fictional.txt#text:1",
                             "checked_on": "2026-10-09", "checked_by": "시험용 가상 확인자"}],
                "claims": [
                    {"pointer": "/series_title", "text": plan["series_title"], "kind": "editorial"},
                    {"pointer": "/head_copy", "text": plan["head_copy"], "kind": "editorial"},
                    {"pointer": "/slides/0/title", "text": plan["slides"][0]["title"], "kind": "editorial"},
                    {"pointer": "/slides/0/bullets/0", "text": sentence, "kind": "fact", "source_id": "1",
                     "locator": "text:1", "quote": sentence, "required_terms": ["65세 이상", "최대"]},
                    {"pointer": "/slides/0/footnote", "text": plan["slides"][0]["footnote"], "kind": "attribution"}]}
    return plan, source, "[1] 가상 시험 자료\n실제 정책 근거가 아닙니다.\n", evidence


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def fake_build(root, plan, notes):
    """Create a synthetic report/artifact contract, not an actual typography render."""
    from PIL import Image
    root.mkdir()
    plan = normalized_plan(plan)
    dump(root/"plan.json", plan)
    size = [1080, 1350]
    reports = []
    for i, slide in enumerate(plan["slides"], 1):
        for folder, suffix in (("png", "png"), ("jpeg", "jpg")):
            (root/folder).mkdir(exist_ok=True)
            Image.new("RGB", tuple(size), "white").save(root/folder/f"{i:02d}_{slide['role']}.{suffix}")
        text = [(f"{i}장 시리즈", plan["series_title"]), (f"{i}장 제목", slide["title"])]
        if i == 1 and plan["head_copy"]:
            text.append((f"{i}장 헤드카피", plan["head_copy"]))
        text += [(f"{i}장 본문 {j}", t) for j, t in enumerate(slide["bullets"], 1)]
        text.append((f"{i}장 출처/각주", slide.get("footnote") or ""))
        text += [(f"{i}장 상태", "검토용 초안"), (f"{i}장 쪽수", f"{i:02d} / {len(plan['slides']):02d}"),
                 (f"{i}장 기관/푸터", "")]
        blocks = []
        for j, (label, value) in enumerate(text):
            y = 50 + j*140
            blocks.append({"label": label, "text": value, "lines": [value], "size": 32,
                           "glyph_bounds": [[60, y, 1000, y+45]], "x": 60, "y": y,
                           "box_width": 950, "box_height": 100, "color": "#000000",
                           "background": "#FFFFFF", "contrast_ratio": 21., "overflow": False})
        reports.append({"page": i, "size": size, "blocks": blocks, "overflow": False})
    dump(root/"render-report.json", {"size": size, "pages": reports})
    dump(root/"profile.json", {"name": "synthetic"})
    dump(root/"source-summary.json", {"synthetic": True})
    for name in ("review.md", "preview.html", "ABOUT.txt"):
        (root/name).write_text("Synthetic test fixture, not a real cardnews render.", encoding="utf-8")
    (root/"SOURCES.md").write_text(notes, encoding="utf-8")
    refresh(root)
    return root


def refresh(root):
    names = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
             and p.name not in {"manifest.json", "cardnews.zip", "quality-report.json", "quality-manifest.json", "cardnews-checked.zip", ".env"}]
    plan = json.loads((root/"plan.json").read_text())
    manifest = {"engine": "Jeju_Cardmaker-studio-v1", "files": {name: sha((root/name).read_bytes()) for name in names},
                "size": [1080, 1350], "status": "draft", "pages": len(plan["slides"]),
                "plan_sha256": sha(canonical(plan))}
    dump(root/"manifest.json", manifest)
    with zipfile.ZipFile(root/"cardnews.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names+["manifest.json"]:
            archive.write(root/name, name)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.source, self.notes, self.evidence = fixture()
        self.rules = policy("2026-10-09")

    def check(self):
        return preflight(self.plan, self.source, self.notes, self.evidence, self.rules)

    def fact(self):
        return self.evidence["claims"][3]

    def update_text(self, text):
        self.plan["slides"][0]["bullets"][0] = text
        self.fact()["text"] = text

    def test_valid_fixture_is_not_fact_verification(self):
        report = self.check()
        self.assertTrue(report["ok"])
        self.assertFalse(report["factual_accuracy_verified"])
        self.assertFalse(report["urls_fetched"])

    def test_numbers_complete_not_substrings(self):
        self.assertNotEqual(numeric_tokens("65세"), numeric_tokens("165세"))
        self.assertNotEqual(numeric_tokens("10명"), numeric_tokens("110명"))

    def test_single_digit_checked(self):
        self.assertEqual(numeric_tokens("3명"), {("3", "명")})

    def test_money_equivalence(self):
        self.assertEqual(numeric_tokens("10만원"), numeric_tokens("100,000원"))
        self.assertNotEqual(numeric_tokens("10만원"), numeric_tokens("10억원"))

    def test_scaled_count_units(self):
        self.assertEqual(numeric_tokens("1만 명"), numeric_tokens("10,000명"))
        self.assertNotEqual(numeric_tokens("1만명"), numeric_tokens("1만건"))
        self.assertNotEqual(numeric_tokens("1천만원"), numeric_tokens("1천만명"))
        self.assertEqual(numeric_tokens("1천만원"), numeric_tokens("10,000,000원"))

    def test_malformed_comma_groups_rejected(self):
        with self.assertRaises(QualityError): numeric_tokens("1,20원")

    def test_long_numeric_values_not_rounded_equal(self):
        self.assertNotEqual(numeric_tokens("100000000000000000000000000001원"),
                            numeric_tokens("100000000000000000000000000002원"))

    def test_percent_and_year_checked(self):
        self.assertEqual(numeric_tokens("3.5퍼센트"), numeric_tokens("3.5%"))
        self.assertNotEqual(numeric_tokens("2025년"), numeric_tokens("2026년"))

    def test_wrong_number(self):
        self.update_text(self.fact()["text"].replace("65세", "66세"))
        with self.assertRaises(QualityError): self.check()

    def test_wrong_unit(self):
        self.update_text(self.fact()["text"].replace("10만원", "10억원"))
        with self.assertRaises(QualityError): self.check()

    def test_missing_qualifier(self):
        self.update_text(self.fact()["text"].replace("최대 ", ""))
        with self.assertRaises(QualityError): self.check()

    def test_qualifier_automatically_checked(self):
        self.fact()["required_terms"] = []
        self.update_text(self.fact()["text"].replace("이상", ""))
        with self.assertRaises(QualityError): self.check()

    def test_nonexistent_quote(self):
        self.fact()["quote"] += " invented"
        with self.assertRaises(QualityError): self.check()

    def test_wrong_locator(self):
        self.fact()["locator"] = "missing"
        with self.assertRaises(QualityError): self.check()

    def test_source_unit_change_detected(self):
        self.source["units"][0]["text"] += " change"
        self.source["text"] += " change"
        with self.assertRaises(QualityError): self.check()

    def test_source_text_units_mismatch(self):
        self.source["text"] += " change"
        with self.assertRaises(QualityError): self.check()

    def test_duplicate_locator(self):
        self.source["units"].append(copy.deepcopy(self.source["units"][0]))
        with self.assertRaises(QualityError): validate_source(self.source)

    def test_missing_claim(self):
        self.evidence["claims"].pop()
        with self.assertRaises(QualityError): self.check()

    def test_duplicate_claim(self):
        self.evidence["claims"].append(copy.deepcopy(self.fact()))
        with self.assertRaises(QualityError): self.check()

    def test_mismatched_claim_text(self):
        self.fact()["text"] += " changed"
        with self.assertRaises(QualityError): self.check()

    def test_no_numeric_editorial_bypass(self):
        self.fact()["kind"] = "editorial"
        with self.assertRaises(QualityError): self.check()

    def test_missing_citation_definition(self):
        self.notes = "[2] other"
        with self.assertRaises(QualityError): self.check()

    def test_missing_per_card_citation(self):
        self.plan["slides"][0]["footnote"] = "출처 [2]"
        with self.assertRaises(QualityError): self.check()

    def test_future_checked_date(self):
        self.evidence["sources"][0]["checked_on"] = "2026-10-10"
        with self.assertRaises(QualityError): self.check()

    def test_expired_checked_date(self):
        self.evidence["sources"][0]["checked_on"] = "2026-01-01"
        with self.assertRaises(QualityError): self.check()

    def test_invalid_calendar_date(self):
        self.evidence["sources"][0]["checked_on"] = "2026-02-30"
        with self.assertRaises(QualityError): self.check()

    def test_expired_application(self):
        self.evidence["sources"][0]["valid_until"] = "2026-10-08"
        with self.assertRaises(QualityError): self.check()

    def test_not_yet_effective(self):
        self.evidence["sources"][0]["valid_from"] = "2026-10-10"
        with self.assertRaises(QualityError): self.check()

    def test_as_of_mismatch(self):
        self.evidence["as_of"] = "2026-10-08"
        with self.assertRaises(QualityError): self.check()

    def test_unsupported_schema(self):
        self.evidence["schema_version"] = True
        with self.assertRaises(QualityError): self.check()

    def test_json_duplicate_nan_and_oversize_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b' '* (2*1024*1024+1)):
            with self.subTest(raw=raw[:20]), self.assertRaises(QualityError): decode_json(raw)

    def test_plan_normalizes_optional_defaults_like_existing_core(self):
        del self.plan["slides"][0]["footnote"]
        self.assertIsNone(normalized_plan(self.plan)["slides"][0]["footnote"])

    def base_approval(self):
        hashes = self.check()["binding"]
        return {"copy_approved": True, "reviewer": "fixture only", "approved_at": "fixture",
                "plan_sha256": hashes["plan_sha256"], "source_record_sha256": hashes["source_record_sha256"]}

    def test_approval_binds_notes(self):
        approved = attach_approval(self.base_approval(), self.check())
        require_quality_approval(approved, self.check())
        self.notes += "new source note"
        with self.assertRaises(QualityError): require_quality_approval(approved, self.check())

    def test_approval_binds_evidence_and_policy(self):
        approved = attach_approval(self.base_approval(), self.check())
        self.evidence["sources"][0]["reference"] = "other.txt"
        with self.assertRaises(QualityError): require_quality_approval(approved, self.check())
        self.evidence = fixture()[3]
        self.rules = policy("2026-10-09", 31)
        with self.assertRaises(QualityError): require_quality_approval(approved, self.check())

    def test_old_approval_cannot_claim_new_gate(self):
        with self.assertRaises(QualityError):
            require_quality_approval({"copy_approved": True, "reviewer": "fixture", "approved_at": "fixture"}, self.check())

    def test_no_network_calls(self):
        with patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
            self.assertTrue(self.check()["ok"])


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plan, self.source, self.notes, self.evidence = fixture()
        self.rules = policy("2026-10-09")
        self.out = fake_build(self.root/"run", self.plan, self.notes)
        self.pre = preflight(self.plan, self.source, self.notes, self.evidence, self.rules)

    def tearDown(self): self.tmp.cleanup()
    def check(self): return postflight(self.out, self.plan, self.rules)

    def mutate_report(self, callback):
        path = self.out/"render-report.json"
        report = json.loads(path.read_text())
        callback(report)
        dump(path, report)
        refresh(self.out)

    def test_valid_contract(self): self.assertTrue(self.check()["ok"])

    def test_v111_unnumbered_body_label_compatibility(self):
        def old_labels(report):
            for block in report["pages"][0]["blocks"]:
                if block["label"].startswith("1장 본문 "):
                    block["label"] = "1장 본문"
        self.mutate_report(old_labels)
        self.assertTrue(self.check()["ok"])

    def test_v111_repeated_unnumbered_body_labels_keep_order(self):
        self.plan["slides"][0]["bullets"].append("추가 시험 문장입니다.")
        other = fake_build(self.root/"multiple", self.plan, self.notes)
        report = json.loads((other/"render-report.json").read_text())
        for block in report["pages"][0]["blocks"]:
            if block["label"].startswith("1장 본문 "):
                block["label"] = "1장 본문"
        dump(other/"render-report.json", report)
        refresh(other)
        self.assertTrue(postflight(other,self.plan,self.rules)["ok"])

    def test_low_contrast_blocks_even_when_manifest_updated(self):
        def change(report):
            block = report["pages"][0]["blocks"][0]
            block["color"] = "#CCCCCC"
            block["contrast_ratio"] = round(contrast(block["color"], "#FFFFFF"), 3)
        self.mutate_report(change)
        with self.assertRaises(QualityError): self.check()

    def test_forged_contrast_metadata(self):
        self.mutate_report(lambda r: r["pages"][0]["blocks"][0].update(color="#FFFFFF", contrast_ratio=21.0))
        with self.assertRaises(QualityError): self.check()

    def test_missing_all_page_reports(self):
        self.mutate_report(lambda r: r.update(pages=[]))
        with self.assertRaises(QualityError): self.check()

    def test_overflow(self):
        self.mutate_report(lambda r: r["pages"][0]["blocks"][0].update(glyph_bounds=[[60,50,1070,95]]))
        with self.assertRaises(QualityError): self.check()

    def test_false_approved_status_in_draft(self):
        def change(r):
            block = r["pages"][0]["blocks"][5]
            block.update(text="문안 승인본", lines=["문안 승인본"])
        self.mutate_report(change)
        with self.assertRaises(QualityError): self.check()

    def test_safe_area(self):
        self.mutate_report(lambda r: r["pages"][0]["blocks"][0].update(x=0,glyph_bounds=[[0,50,940,95]]))
        with self.assertRaises(QualityError): self.check()

    def test_tiny_body(self):
        self.mutate_report(lambda r: r["pages"][0]["blocks"][3].update(size=29))
        with self.assertRaises(QualityError): self.check()

    def test_missing_text_block(self):
        self.mutate_report(lambda r: r["pages"][0]["blocks"].pop(1))
        with self.assertRaises(QualityError): self.check()

    def test_text_truncation_in_lines(self):
        self.mutate_report(lambda r: r["pages"][0]["blocks"][1].update(lines=["truncated"]))
        with self.assertRaises(QualityError): self.check()

    def test_missing_image_even_after_refresh(self):
        (self.out/"png/01_cover.png").unlink()
        refresh(self.out)
        with self.assertRaises(QualityError): self.check()

    def test_wrong_image_size(self):
        from PIL import Image
        Image.new("RGB",(64,64)).save(self.out/"png/01_cover.png")
        refresh(self.out)
        with self.assertRaises(QualityError): self.check()

    def test_corrupt_image(self):
        (self.out/"png/01_cover.png").write_bytes(b"invalid png")
        refresh(self.out)
        with self.assertRaises((OSError, QualityError)): self.check()

    def test_tampering_without_refresh(self):
        (self.out/"plan.json").write_text("{}")
        with self.assertRaises(QualityError): self.check()

    def test_untracked_private_neighbors_not_packaged(self):
        (self.out/".env").write_text("synthetic secret")
        seal_checked_build(self.out, self.pre, self.check())
        with zipfile.ZipFile(self.out/"cardnews-checked.zip") as archive:
            for name in (".env", "source.json", "evidence.json", "cardnews.zip"):
                self.assertNotIn(name, archive.namelist())
            self.assertIn("quality-report.json", archive.namelist())
        self.assertTrue(verify_checked(self.out)["ok"])

    def test_checked_archive_duplicate_entry(self):
        seal_checked_build(self.out, self.pre, self.check())
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.out/"cardnews-checked.zip", "a") as archive:
                archive.writestr("plan.json", "{}")
        with self.assertRaises(QualityError): verify_checked(self.out)

    def test_checked_report_tampering(self):
        seal_checked_build(self.out, self.pre, self.check())
        (self.out/"quality-report.json").write_text("{}")
        with self.assertRaises(QualityError): verify_checked(self.out)

    def test_path_traversal(self):
        for path in ("../file", "a/../../file", "/etc/passwd", "C:/secret", "a\\b", "a//b", "./a"):
            with self.subTest(path=path), self.assertRaises(QualityError): safe_file(self.out, path)

    def test_symlink(self):
        path = self.out/"SOURCES.md"
        path.unlink()
        outside = self.root/"outside.txt"
        outside.write_text("test")
        try: path.symlink_to(outside)
        except OSError: self.skipTest("symlink not supported")
        with self.assertRaises(QualityError): safe_file(self.out, "SOURCES.md")

    def test_seal_refuses_failed_report(self):
        with self.assertRaises(QualityError): seal_checked_build(self.out, {"ok": False}, self.check())


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root/"project"
        self.project.mkdir()
        self.plan, self.source, self.notes, self.evidence = fixture()
        for name, data in (("plan.json",self.plan),("source.json",self.source),("evidence.json",self.evidence)):
            dump(self.project/name,data)
        (self.project/"SOURCES.md").write_text(self.notes,encoding="utf-8")
        self.called = 0

    def tearDown(self): self.tmp.cleanup()
    def engine(self, project, output, **kwargs):
        self.called += 1
        self.assertNotEqual(Path(project), self.project)
        return fake_build(Path(output), json.loads((Path(project)/"plan.json").read_text()), self.notes)

    def build(self, **kwargs):
        return checked_build(self.project, self.root/"out", as_of="2026-10-09",
                             _engine=kwargs.pop("_engine",self.engine), _verifier=lambda path:{"ok":True}, **kwargs)

    def test_success_and_input_preservation(self):
        before = {p.name:p.read_bytes() for p in self.project.iterdir()}
        out = self.build()
        self.assertTrue(verify_checked(out)["ok"])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.project.iterdir()})
        self.assertFalse(list(self.root.glob(".Jeju_Cardmaker-quality-*")))

    def test_missing_evidence_stops_before_render(self):
        (self.project/"evidence.json").unlink()
        with self.assertRaises(QualityError): self.build()
        self.assertEqual(self.called,0)
        self.assertFalse((self.root/"out").exists())

    def test_postflight_failure_leaves_no_success_folder(self):
        def broken(project, output, **kwargs):
            result = self.engine(project,output,**kwargs)
            (result/"png/01_cover.png").unlink()
            refresh(result)
            return result
        with self.assertRaises(QualityError): self.build(_engine=broken)
        self.assertFalse((self.root/"out").exists())
        self.assertFalse(list(self.root.glob(".Jeju_Cardmaker-quality-*")))

    def test_false_original_verifier_blocks_publication(self):
        with self.assertRaises(QualityError):
            checked_build(self.project,self.root/"out",as_of="2026-10-09",
                          _engine=self.engine,_verifier=lambda path:{"ok":False})
        self.assertFalse((self.root/"out").exists())

    def test_engine_failure_cleans_staging(self):
        def broken(*args,**kwargs): raise RuntimeError("fixture failure")
        with self.assertRaises(RuntimeError): self.build(_engine=broken)
        self.assertFalse((self.root/"out").exists())
        self.assertFalse(list(self.root.glob(".Jeju_Cardmaker-quality-*")))

    def test_changed_input_during_build(self):
        def concurrent(project,output,**kwargs):
            result=self.engine(project,output,**kwargs)
            (self.project/"SOURCES.md").write_text(self.notes+"changed",encoding="utf-8")
            return result
        with self.assertRaises(QualityError): self.build(_engine=concurrent)
        self.assertFalse((self.root/"out").exists())

    def test_existing_output_preserved(self):
        (self.root/"out").mkdir()
        (self.root/"out/keep.txt").write_text("keep")
        with self.assertRaises(QualityError): self.build()
        self.assertEqual((self.root/"out/keep.txt").read_text(),"keep")

    def test_final_needs_quality_approval(self):
        with self.assertRaises(QualityError): self.build(final=True)
        self.assertEqual(self.called,0)

    def test_draft_status_cannot_be_hidden(self):
        with self.assertRaises(QualityError): self.build(hide_status=True)

    def test_cli_malformed_input_returns_nonzero(self):
        from io import StringIO
        (self.project/"evidence.json").write_text("{}")
        with patch("sys.stderr",new_callable=StringIO):
            self.assertEqual(main(["preflight","--project",str(self.project),"--as-of","2026-10-09"]),2)

    def test_cli_reports_core_skill_error_reason(self):
        from io import StringIO
        from rp_core import SkillError
        with patch("sys.stderr",new_callable=StringIO) as err, \
             patch("quality_cli.read_bundle", side_effect=SkillError("승인 후 기획안 또는 출처가 변경되었습니다.")):
            self.assertEqual(main(["preflight","--project",str(self.project),"--as-of","2026-10-09"]),2)
        self.assertIn("승인 후 기획안 또는 출처가 변경되었습니다.", err.getvalue())


if __name__ == "__main__": unittest.main(verbosity=2)
