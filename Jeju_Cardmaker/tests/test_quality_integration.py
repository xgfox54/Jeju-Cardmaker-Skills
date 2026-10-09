"""Optional real-upstream regression tests; skip explicitly without the original repo."""
from __future__ import annotations
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
HAVE_BASELINE = all(importlib.util.find_spec(name) is not None for name in ("rp_core", "rp_render", "rp_studio"))

@unittest.skipUnless(HAVE_BASELINE, "Original Jeju_Cardmaker 1.1.1 source is not installed; real renderer integration NOT executed")
class OriginalIntegrationTests(unittest.TestCase):
    def test_original_core_hash_compatibility(self):
        from rp_core import plan_hash, source_hash
        from rp_quality import normalized_plan, source_digest, sha, canonical
        root = Path(__file__).resolve().parents[1]/"assets"/"quality-example"
        plan = json.loads((root/"plan.json").read_text(encoding="utf-8"))
        source = json.loads((root/"source.json").read_text(encoding="utf-8"))
        self.assertEqual(plan_hash(plan), sha(canonical(normalized_plan(plan))))
        self.assertEqual(source_hash(source), source_digest(source))

    def test_real_renderer_and_checked_package(self):
        from quality_cli import checked_build
        from rp_quality import verify_checked
        root = Path(__file__).resolve().parents[1]/"assets"/"quality-example"
        with tempfile.TemporaryDirectory() as temp:
            out = checked_build(root, Path(temp)/"out", as_of="2026-10-09", preset="portrait", pptx=False)
            self.assertTrue(verify_checked(out)["ok"])
            self.assertTrue((out/"cardnews.zip").is_file())
            self.assertTrue((out/"cardnews-checked.zip").is_file())

    def test_real_low_contrast_build_leaves_no_final_output(self):
        from quality_cli import checked_build
        from rp_quality import QualityError
        from rp_render import load_profile
        root = Path(__file__).resolve().parents[1]/"assets"/"quality-example"
        with tempfile.TemporaryDirectory() as temp:
            profile = load_profile("jeju")
            profile["text"] = "#EEEEEE"
            path = Path(temp)/"low-contrast.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaises(QualityError):
                checked_build(root, Path(temp)/"out", as_of="2026-10-09", preset="portrait", profile_name=str(path), pptx=False)
            self.assertFalse((Path(temp)/"out").exists())

if __name__ == "__main__": unittest.main(verbosity=2)
