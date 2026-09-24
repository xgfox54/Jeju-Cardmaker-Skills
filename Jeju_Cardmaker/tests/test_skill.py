"""Local/offline tests. Mocked upstream tests are NOT real upstream API tests."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from rp_core import (SkillError, approve, canonical, extract_document, new_json, plan_hash,
                     read_json, require_approval, source_hash, validate_plan, validate_source, write_json)
from rp_render import (check_glyphs, create_run, fit_block, load_profile, package_run,
                       resolve_fonts, validate_run, wrap_text)
from rp_bridge import (BudgetClient, EXPECTED, generate_upstream_plan, inspect_upstream,
                       original_export, paid_client, render_upstream_api, upstream_modules)
import bootstrap

PLAN = json.loads((SKILL / 'assets/sample.plan.json').read_text(encoding='utf-8'))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plan = copy.deepcopy(PLAN)
        self.source = extract_document(SKILL / 'assets/sample.source.txt')

    def tearDown(self):
        self.tmp.cleanup()

    def hwpx(self, entries):
        p = self.root / 'sample.hwpx'
        with zipfile.ZipFile(p, 'w') as z:
            for name, data in entries:
                z.writestr(name, data)
        return p

    def upstream(self):
        root = self.root / 'upstream-mock'
        code = root / 'code'
        code.mkdir(parents=True)
        for filename, items in EXPECTED.items():
            lines = []
            for name, fields in items.items():
                if name in {'SlidePlan', 'CardNewsPlan'}:
                    lines += [f'class {name}:'] + [f'    {field}: object' for field in sorted(fields)]
                else:
                    lines += [f'def {name}({", ".join(sorted(fields))}):', '    return None']
            (code / filename).write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return root


class SchemaTests(Base):
    def test_valid_sample(self):
        self.assertEqual(validate_plan(self.plan, 3), self.plan)

    def test_roles_are_not_repaired(self):
        self.plan['slides'][0]['role'] = 'body'
        with self.assertRaises(SkillError): validate_plan(self.plan)

    def test_page_count_must_match(self):
        with self.assertRaises(SkillError): validate_plan(self.plan, 5)

    def test_unknown_fields_rejected(self):
        self.plan['source'] = 'invented'
        with self.assertRaises(SkillError): validate_plan(self.plan)

    def test_string_bullet_not_coerced(self):
        self.plan['slides'][1]['bullets'] = 'not an array'
        with self.assertRaises(SkillError): validate_plan(self.plan)

    def test_long_title_rejected_not_truncated(self):
        self.plan['slides'][0]['title'] = '가' * 501
        with self.assertRaises(SkillError): validate_plan(self.plan)
        self.assertEqual(len(self.plan['slides'][0]['title']), 501)

    def test_empty_slide_list_rejected(self):
        self.plan['slides'] = []
        with self.assertRaises(SkillError): validate_plan(self.plan)

    def test_one_page_role(self):
        self.plan['slides'] = self.plan['slides'][:1]
        self.assertEqual(len(validate_plan(self.plan)['slides']), 1)

    def test_optional_defaults_only(self):
        self.plan['slides'][0].pop('footnote')
        self.assertIsNone(validate_plan(self.plan)['slides'][0]['footnote'])

    def test_hash_stable_under_key_order(self):
        self.assertEqual(plan_hash(self.plan), plan_hash(dict(reversed(list(self.plan.items())))))

    def test_json_no_overwrite(self):
        dest = self.root / 'a.json'
        new_json(dest, self.plan)
        with self.assertRaises(FileExistsError): new_json(dest, {})
        self.assertEqual(read_json(dest), self.plan)

    def test_non_finite_json_rejected(self):
        with self.assertRaises(ValueError): canonical({'a': float('nan')})


class ExtractionTests(Base):
    def test_utf8_source(self):
        self.assertEqual(validate_source(self.source), self.source)
        self.assertIn('가상 자료', self.source['text'])
        self.assertNotIn(str(SKILL), json.dumps(self.source, ensure_ascii=False))

    def test_cp949_source(self):
        p = self.root / 'source.txt'
        p.write_bytes('한국어 자료'.encode('cp949'))
        self.assertIn('한국어 자료', extract_document(p)['text'])

    def test_empty_text_rejected(self):
        p = self.root / 'empty.txt'; p.write_text('   ')
        with self.assertRaises(SkillError): extract_document(p)

    def test_old_hwp_rejected(self):
        p = self.root / 'old.hwp'; p.write_bytes(b'not-an-hwp')
        with self.assertRaises(SkillError): extract_document(p)

    def test_hwpx_natural_section_order(self):
        p = self.hwpx([(f'Contents/section{i}.xml', f'<s><t>{i}번</t></s>') for i in (10, 2, 0)])
        result = extract_document(p)
        self.assertEqual([u['text'] for u in result['units']], ['0번', '2번', '10번'])
        self.assertTrue(result['warnings'])

    def test_hwpx_malformed_is_not_silently_skipped(self):
        p = self.hwpx([('Contents/section0.xml', '<s><t>good</t></s>'), ('Contents/section1.xml', '<broken')])
        with self.assertRaises(SkillError): extract_document(p)

    def test_hwpx_dtd_entities_rejected(self):
        p = self.hwpx([('Contents/section0.xml', '<!DOCTYPE s [<!ENTITY x "test">]><s><t>&x;</t></s>')])
        with self.assertRaises(SkillError): extract_document(p)

    def test_hwpx_missing_sections(self):
        p = self.hwpx([('not-a-section.xml', '<t>hello</t>')])
        with self.assertRaises(SkillError): extract_document(p)

    def test_pdf_text_and_blank_warning(self):
        import fitz
        p = self.root / 'test.pdf'
        doc = fitz.open(); page = doc.new_page(); page.insert_text((72,72), 'Synthetic fixture 42')
        doc.new_page(); doc.save(p); doc.close()
        result = extract_document(p)
        self.assertIn('Synthetic fixture 42', result['text'])
        self.assertEqual(len(result['units']), 2)
        self.assertFalse(result['complete_text_layer'])
        self.assertTrue(result['warnings'])

    def test_blank_pdf_rejected(self):
        import fitz
        p = self.root / 'blank.pdf'
        doc = fitz.open(); doc.new_page(); doc.save(p); doc.close()
        with self.assertRaises(SkillError): extract_document(p)

    def test_encrypted_pdf_rejected(self):
        import fitz
        p = self.root / 'encrypted.pdf'
        doc = fitz.open(); doc.new_page(); doc.save(p, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw='fixture', owner_pw='test-owner'); doc.close()
        with self.assertRaises(SkillError): extract_document(p)

    def test_source_units_must_match_text(self):
        self.source['units'][0]['text'] += 'tampered'
        with self.assertRaises(SkillError): validate_source(self.source)


class ApprovalTests(Base):
    def test_explicit_confirmation_required(self):
        with self.assertRaises(SkillError): approve(self.plan, self.source, 'fixture', False)

    def test_matching_approval(self):
        ap = approve(self.plan, self.source, 'fixture', True)
        require_approval(self.plan, self.source, ap)

    def test_plan_change_invalidates(self):
        ap = approve(self.plan, self.source, 'fixture', True)
        self.plan['head_copy'] += ' 변경'
        with self.assertRaises(SkillError): require_approval(self.plan, self.source, ap)

    def test_source_change_invalidates(self):
        ap = approve(self.plan, self.source, 'fixture', True)
        self.source['units'][0]['text'] += '\nchanged'
        self.source['text'] = '\n\n'.join(f"[{u['locator']}]\n{u['text']}" for u in self.source['units'])
        with self.assertRaises(SkillError): require_approval(self.plan, self.source, ap)


class RenderTests(Base):
    def test_wrapping_preserves_nonwhitespace(self):
        from PIL import Image, ImageDraw, ImageFont
        text = '한글 확인 test rendering without silent cuts and 1234'
        draw = ImageDraw.Draw(Image.new('RGB', (400,100)))
        font = ImageFont.truetype(str(resolve_fonts()[0]), 24)
        lines = wrap_text(draw, text, font, 130)
        self.assertEqual(''.join(''.join(lines).split()), ''.join(text.split()))
        self.assertTrue(all(draw.textlength(s, font=font) <= 130 for s in lines))

    def test_overflow_fails_before_output(self):
        self.plan['slides'][0]['bullets'] = ['긴문장' * 200] * 8
        out = self.root / 'overflow'
        with self.assertRaises(SkillError): create_run(self.plan, out, load_profile('neutral'))
        self.assertFalse(out.exists())

    def test_missing_glyph_detected(self):
        with self.assertRaises(SkillError): check_glyphs(resolve_fonts(), ['\U0010FFFF'])

    def test_profile_color_validation(self):
        profile = load_profile('neutral'); profile['primary'] = 'not a color'
        write_json(self.root / 'profile.json', profile)
        with self.assertRaises(SkillError): load_profile(str(self.root / 'profile.json'))

    def test_render_and_zip_e2e(self):
        from PIL import Image
        from pptx import Presentation
        run = create_run(self.plan, self.root / 'run', load_profile('jeju'), source=self.source)
        root, manifest, plan, images = validate_run(run)
        self.assertEqual(manifest['api_calls'], 0)
        self.assertEqual(len(images), 3)
        for p in images:
            with Image.open(p) as im: self.assertEqual(im.size, (1000,1350))
        (run / '.env').write_text('FAKE_TEST_KEY=never-export', encoding='utf-8')
        (run / 'extra.txt').write_text('exclude me')
        bundle = package_run(run, self.root / 'cards.zip')
        with zipfile.ZipFile(bundle) as z:
            self.assertNotIn('.env', z.namelist())
            self.assertNotIn('extra.txt', z.namelist())
            self.assertNotIn('source.json', z.namelist())
            self.assertFalse(any(n.endswith(('.ttf','.otf','.ttc')) for n in z.namelist()))
            prs = Presentation(io.BytesIO(z.read('cardnews-preview.pptx')))
            self.assertEqual(len(prs.slides), 3)
            self.assertTrue(all(len(s.shapes) == 1 for s in prs.slides))
            self.assertNotIn(b'never-export', b''.join(z.read(n) for n in z.namelist()))

    def test_final_requires_approval(self):
        with self.assertRaises(SkillError): create_run(self.plan, self.root/'final', load_profile('neutral'), source=self.source, final=True)

    def test_approved_render(self):
        ap = approve(self.plan, self.source, 'test user', True)
        run = create_run(self.plan, self.root/'final', load_profile('neutral'), source=self.source, approval=ap, final=True)
        self.assertEqual(read_json(run/'manifest.json')['status'], 'copy-approved')
        self.assertTrue((run/'approval.json').is_file())

    def test_existing_run_is_not_overwritten(self):
        run = self.root/'existing'; run.mkdir(); (run/'keep.txt').write_text('original')
        with self.assertRaises(SkillError): create_run(self.plan, run, load_profile('neutral'))
        self.assertEqual((run/'keep.txt').read_text(), 'original')

    def test_tampered_image_detected(self):
        run = create_run(self.plan, self.root/'run', load_profile('neutral'))
        image = next((run/'jpeg/ko').glob('*.jpg')); image.write_bytes(image.read_bytes()+b'tampered')
        with self.assertRaises(SkillError): package_run(run, self.root/'tampered.zip')

    def test_path_traversal_detected(self):
        run = create_run(self.plan, self.root/'run', load_profile('neutral'))
        manifest = read_json(run/'manifest.json'); manifest['image_paths'][0] = '../../private.txt'
        write_json(run/'manifest.json', manifest)
        with self.assertRaises(SkillError): package_run(run, self.root/'bad.zip')

    def test_metadata_symlink_not_exported(self):
        run = create_run(self.plan, self.root/'run', load_profile('neutral'))
        p = run/'review.md'; original = p.read_text(); p.unlink()
        outside = self.root/'outside.md'; outside.write_text(original)
        try: p.symlink_to(outside)
        except OSError: self.skipTest('OS does not allow symlinks for this user')
        with self.assertRaises(SkillError): package_run(run, self.root/'bad.zip')

    def test_html_is_escaped(self):
        self.plan['slides'][0]['title'] = '<script>alert(1)</script>'
        run = create_run(self.plan, self.root/'run', load_profile('neutral'))
        html = (run/'preview.html').read_text(encoding='utf-8')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_black_logo_pixels_preserved(self):
        from PIL import Image
        logo = self.root/'logo.png'; Image.new('RGBA', (80,40),(0,0,0,255)).save(logo)
        run = create_run(self.plan, self.root/'run', load_profile('neutral'), logo=str(logo))
        with Image.open(run/'jpeg/ko/01_cover.jpg') as im:
            self.assertLess(max(im.getpixel((WIDTH:=900, 1290))), 15)


class BridgeTests(Base):
    def test_api_no_permission_fails_without_sdk(self):
        with self.assertRaises(SkillError): paid_client(False, 1)

    def test_api_requires_call_budget(self):
        with self.assertRaises(SkillError): paid_client(True, None)

    def test_api_requires_key(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':''}):
            with self.assertRaises(SkillError): paid_client(True, 1)

    def test_call_budget_counts_failures(self):
        fn = Mock(side_effect=RuntimeError('test-only'))
        native = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fn)), images=SimpleNamespace(generate=fn))
        client = BudgetClient(native, 1)
        with self.assertRaises(RuntimeError): client.images.generate()
        with self.assertRaises(SkillError): client.images.generate()
        self.assertEqual(fn.call_count, 1)
        self.assertEqual(client.calls, 1)

    def test_mock_upstream_ast_contract(self):
        self.assertTrue(inspect_upstream(self.upstream())['compatible'])

    def test_changed_contract_fails(self):
        root = self.upstream(); (root/'code/image_gen.py').write_text('def changed(): pass')
        self.assertFalse(inspect_upstream(root)['compatible'])

    def test_upstream_requires_trust(self):
        with self.assertRaises(SkillError):
            with upstream_modules(self.upstream(), False): pass

    def test_mock_original_export_contract(self):
        root = self.upstream()
        (root/'code/package_export.py').write_text('def build_export_zip_bytes(plan_dict, jpeg_paths, *, cards_root=None):\n    return b"mock-export-fixture"\n')
        self.assertEqual(original_export(str(root), self.plan, [], self.root, True), b'mock-export-fixture')

    def test_api_branding_must_be_accepted(self):
        with self.assertRaises(SkillError): render_upstream_api('not-accessed', self.plan, self.root/'api', model='test', trusted=False, allowed=True, max_calls=3, accept_branding=False)

    def test_api_plan_denies_unapproved_without_loading_source(self):
        with self.assertRaises(SkillError): generate_upstream_plan('not-accessed', self.source, pages=3, model='test', trusted=False, allowed=False, max_calls=1)

    def test_bootstrap_network_optin(self):
        with patch('subprocess.run') as run:
            with patch('sys.stderr', new_callable=io.StringIO):
                self.assertEqual(bootstrap.main(['core']), 2)
            run.assert_not_called()


class InstallerTests(Base):
    @classmethod
    def setUpClass(cls):
        path = SKILL.parent/'install.py'
        if not path.is_file():
            raise unittest.SkipTest('Installer tests run from the release bundle, not the installed skill.')
        spec = importlib.util.spec_from_file_location('Jeju_Cardmaker_installer', path)
        cls.mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.mod)

    def test_user_scope_copy_without_runtime(self):
        base=self.root/'.agents'
        result=self.mod.install(SKILL, base)
        target=Path(result['installed'])
        self.assertTrue((target/'SKILL.md').is_file())
        self.assertFalse((target/'.venv').exists())
        self.assertFalse((target/'scripts/__pycache__').exists())

    def test_duplicate_requires_replace(self):
        base=self.root/'.agents'; self.mod.install(SKILL,base)
        with self.assertRaises(FileExistsError): self.mod.install(SKILL,base)

    def test_replace_backs_up_old_skill(self):
        base=self.root/'.agents'; self.mod.install(SKILL,base)
        marker=base/'skills/Jeju_Cardmaker/old.txt'; marker.write_text('keep me')
        result=self.mod.install(SKILL,base,replace=True)
        self.assertEqual((Path(result['backup'])/'old.txt').read_text(),'keep me')
        self.assertNotIn('skill-backups', str(Path(result['installed'])))
        self.assertFalse(marker.exists())

    def test_replace_moves_earlier_releasepick_install(self):
        base=self.root/'.agents'; legacy=base/'skills/releasepick'; legacy.mkdir(parents=True)
        (legacy/'SKILL.md').write_text('old', encoding='utf-8')
        with self.assertRaises(FileExistsError): self.mod.install(SKILL,base)
        self.assertTrue(legacy.is_dir())
        result=self.mod.install(SKILL,base,replace=True)
        self.assertFalse(legacy.exists())
        self.assertEqual((Path(result['legacy_backups'][0])/'SKILL.md').read_text(encoding='utf-8'),'old')
        self.assertTrue((base/'skills/Jeju_Cardmaker/SKILL.md').is_file())

    def test_project_scope_cli(self):
        project=self.root/'my-project'; project.mkdir()
        completed=subprocess.run([sys.executable,str(SKILL.parent/'install.py'),'--project',str(project)],capture_output=True,text=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertTrue((project/'.agents/skills/Jeju_Cardmaker/SKILL.md').is_file())

    def test_missing_project_not_created(self):
        missing=self.root/'does-not-exist'
        completed=subprocess.run([sys.executable,str(SKILL.parent/'install.py'),'--project',str(missing)],capture_output=True,text=True)
        self.assertEqual(completed.returncode,2)
        self.assertFalse(missing.exists())

    def test_symlink_package_rejected(self):
        source=self.root/'source'; source.mkdir(); (source/'SKILL.md').write_text('fixture')
        try: (source/'linked').symlink_to(SKILL/'SKILL.md')
        except OSError: self.skipTest('No symlink permission')
        with self.assertRaises(ValueError): self.mod.install(source,self.root/'base')


class MetadataTests(unittest.TestCase):
    def test_skill_frontmatter_and_interface(self):
        # No PyYAML dependency needed in core. Check the deliberately simple metadata.
        text=(SKILL/'SKILL.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('---\nname: Jeju_Cardmaker\ndescription: '))
        self.assertIn('\n---\n',text)
        meta=(SKILL/'agents/openai.yaml').read_text(encoding='utf-8')
        self.assertIn('allow_implicit_invocation: false',meta)
        self.assertIn('$Jeju_Cardmaker',meta)

    def test_schema_parses(self):
        schema=read_json(SKILL/'references/plan.schema.json')
        self.assertEqual(schema['properties']['slides']['maxItems'],12)

    def test_required_cli_help(self):
        completed=subprocess.run([sys.executable,str(SKILL/'scripts/Jeju_Cardmaker.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(completed.returncode,0)
        self.assertIn('upstream-check',completed.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
