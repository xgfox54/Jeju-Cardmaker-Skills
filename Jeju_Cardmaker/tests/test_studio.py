"""v1.1 local rendering/integrity tests. Never contact external APIs."""
from __future__ import annotations
import copy
import io
import json
import socket
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL/'scripts'))
from rp_core import SkillError, approve, extract_document, read_json, write_json
from rp_studio import PRESETS, build_project, citation_audit, contrast, render_card, verify_build
from rp_render import load_profile, resolve_fonts
from PIL import Image
from pptx import Presentation

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root/'project'
        self.project.mkdir()
        self.plan = json.loads((SKILL/'assets/sample.plan.json').read_text(encoding='utf-8'))
        for s in self.plan['slides']:
            s['footnote'] = '출처 [1] 가상 시험 자료'
        write_json(self.project/'plan.json', self.plan)
        (self.project/'SOURCES.md').write_text('[1] 가상 시험 자료\n실제 사업이 아닙니다.\n', encoding='utf-8')
        self.source = extract_document(SKILL/'assets/sample.source.txt')
        write_json(self.project/'source.json', self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, **kw):
        return build_project(self.project, self.root/'out', preset=kw.pop('preset','portrait'), profile_name=kw.pop('profile_name','jeju'), **kw)

    def approval(self):
        ap = approve(self.plan, self.source, 'test fixture, not real approval', True)
        write_json(self.root/'approval.json', ap)
        return {'source_path':str(self.project/'source.json'), 'approval_path':str(self.root/'approval.json'), 'final':True}

    def test_presets(self):
        self.assertEqual(PRESETS['portrait-2x'],(2160,2700))
        self.assertEqual(PRESETS['legacy'],(1000,1350))

    def test_citation_missing_id(self):
        with self.assertRaises(SkillError): citation_audit(self.plan, '[2] other')

    def test_citation_heading_id(self):
        self.assertEqual(citation_audit(self.plan,'## [1] 시험')['defined_ids'],['1'])

    def test_no_notes_is_warning_not_fake_verification(self):
        report=citation_audit(self.plan,None)
        self.assertTrue(report['warnings'])
        self.assertFalse(report['factual_accuracy_verified'])
        self.assertFalse(report['urls_fetched'])

    def test_no_footnote_warning(self):
        self.plan['slides'][0]['footnote']=None
        self.assertTrue(citation_audit(self.plan,'[1] test')['warnings'])

    def test_contrast(self):
        self.assertAlmostEqual(contrast('#000000','#FFFFFF'),21)
        self.assertAlmostEqual(contrast('#FFFFFF','#FFFFFF'),1)

    def test_portrait_outputs_and_no_network(self):
        with patch.object(socket,'create_connection',side_effect=AssertionError('network forbidden')):
            out=self.build()
        manifest=read_json(out/'manifest.json')
        self.assertEqual(manifest['api_calls'],0)
        self.assertTrue(verify_build(out)['ok'])
        for path in sorted((out/'png').glob('*.png')):
            with Image.open(path) as image: self.assertEqual(image.size,(1080,1350))
        self.assertEqual(len(list((out/'jpeg').glob('*.jpg'))),3)

    def test_2x_output(self):
        self.plan['slides']=self.plan['slides'][:1]
        write_json(self.project/'plan.json',self.plan)
        out=self.build(preset='portrait-2x',pptx=False)
        with Image.open(out/'png/01_cover.png') as image: self.assertEqual(image.size,(2160,2700))

    def test_legacy_size(self):
        self.plan['slides']=self.plan['slides'][:1]
        write_json(self.project/'plan.json',self.plan)
        out=self.build(preset='legacy',pptx=False)
        with Image.open(out/'png/01_cover.png') as image: self.assertEqual(image.size,(1000,1350))

    def test_editable_deck_real_text(self):
        out=self.build()
        prs=Presentation(out/'cardnews-editable.pptx')
        self.assertEqual(len(prs.slides),3)
        clean=lambda t: ''.join(t.split())
        for s,p in zip(prs.slides,self.plan['slides']):
            texts=clean(''.join(sh.text for sh in s.shapes if sh.has_text_frame))
            for expected in [p['title'],*p['bullets'],p['footnote']]:
                self.assertIn(clean(expected),texts)
        self.assertAlmostEqual(prs.slide_width/prs.slide_height,.8,places=6)

    def test_preview_deck_image_only(self):
        out=self.build()
        prs=Presentation(out/'cardnews-preview.pptx')
        self.assertTrue(all(len(s.shapes)==1 for s in prs.slides))
        self.assertAlmostEqual(prs.slide_width/prs.slide_height,.8,places=6)

    def test_html_escapes_notes(self):
        (self.project/'SOURCES.md').write_text('[1] <script>alert(1)</script>',encoding='utf-8')
        out=self.build(pptx=False)
        text=(out/'preview.html').read_text(encoding='utf-8')
        self.assertNotIn('<script>',text)
        self.assertIn('&lt;script&gt;',text)
        self.assertIn('Content-Security-Policy',text)
        self.assertIn('cardnews.zip',text)
        self.assertIn('01_cover.png',text)

    def test_sources_exported_but_private_neighbors_not(self):
        (self.project/'.env').write_text('secret test fixture')
        (self.project/'secret.txt').write_text('do not export')
        (self.project/'preview.html').write_text('<script>throw 1</script>')
        out=self.build(pptx=False)
        with zipfile.ZipFile(out/'cardnews.zip') as z:
            self.assertIn('SOURCES.md',z.namelist())
            for n in ['.env','secret.txt','source.json']: self.assertNotIn(n,z.namelist())
            self.assertNotIn(b'throw 1',z.read('preview.html'))
            self.assertFalse(any(n.endswith(('.ttf','.otf','.ttc','.woff','.woff2')) for n in z.namelist()))

    def test_input_not_modified(self):
        before={p.name:p.read_bytes() for p in self.project.iterdir()}
        self.build(pptx=False)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.project.iterdir()})

    def test_draft_cannot_hide_status(self):
        with self.assertRaises(SkillError): self.build(hide_status=True)
        self.assertFalse((self.root/'out').exists())

    def test_final_requires_approval(self):
        with self.assertRaises(SkillError): self.build(final=True)

    def test_final_with_hide_status(self):
        out=self.build(hide_status=True,**self.approval())
        self.assertEqual(read_json(out/'manifest.json')['status'],'copy-approved')
        report=read_json(out/'render-report.json')
        self.assertFalse(any('상태' in b['label'] for p in report['pages'] for b in p['blocks']))

    def test_changed_copy_cannot_reuse_approval(self):
        opts=self.approval()
        self.plan['head_copy']+=' 수정'
        write_json(self.project/'plan.json',self.plan)
        with self.assertRaises(SkillError): self.build(**opts)

    def test_changed_source_cannot_reuse_approval(self):
        opts=self.approval()
        self.source['units'][0]['text']+=' 수정'
        self.source['text']='\n\n'.join(f"[{u['locator']}]\n{u['text']}" for u in self.source['units'])
        write_json(self.project/'source.json',self.source)
        with self.assertRaises(SkillError): self.build(**opts)

    def test_no_pptx_option(self):
        out=self.build(pptx=False)
        self.assertFalse(list(out.glob('*.pptx')))
        self.assertTrue((out/'cardnews.zip').is_file())

    def test_overflow_rolls_back(self):
        self.plan['slides'][0]['bullets']=['긴문장'*200]*8
        write_json(self.project/'plan.json',self.plan)
        with self.assertRaises(SkillError): self.build(pptx=False)
        self.assertFalse((self.root/'out').exists())
        self.assertFalse(list(self.root.glob('.Jeju_Cardmaker-build-*')))

    def test_existing_output_not_overwritten(self):
        (self.root/'out').mkdir()
        (self.root/'out/keep.txt').write_text('keep')
        with self.assertRaises(SkillError): self.build()
        self.assertEqual((self.root/'out/keep.txt').read_text(),'keep')

    def test_modified_image_is_detected(self):
        out=self.build(pptx=False)
        with (out/'png/01_cover.png').open('ab') as f: f.write(b'change')
        with self.assertRaises(SkillError): verify_build(out)

    def test_modified_notes_is_detected(self):
        out=self.build(pptx=False)
        (out/'SOURCES.md').write_text('change')
        with self.assertRaises(SkillError): verify_build(out)

    def test_modified_pptx_is_detected(self):
        out=self.build()
        (out/'cardnews-editable.pptx').write_bytes(b'change')
        with self.assertRaises(SkillError): verify_build(out)

    def test_modified_zip_is_detected(self):
        out=self.build(pptx=False)
        with zipfile.ZipFile(out/'cardnews.zip','a') as z: z.writestr('extra.txt','change')
        with self.assertRaises(SkillError): verify_build(out)

    def test_path_traversal_manifest_rejected(self):
        out=self.build(pptx=False)
        m=read_json(out/'manifest.json');m['files']['../../secret.txt']='x'
        write_json(out/'manifest.json',m)
        with self.assertRaises(SkillError): verify_build(out)

    def test_symlink_metadata_rejected(self):
        out=self.build(pptx=False)
        path=out/'SOURCES.md';path.unlink()
        try: path.symlink_to(self.project/'SOURCES.md')
        except OSError: self.skipTest('symlinks not permitted')
        with self.assertRaises(SkillError): verify_build(out)

    def test_invalid_preset(self):
        with self.assertRaises(SkillError): self.build(preset='invented')

    def test_missing_glyph(self):
        self.plan['slides'][0]['title']='\U0010FFFF'
        write_json(self.project/'plan.json',self.plan)
        with self.assertRaises(SkillError): self.build()

    def test_actual_glyph_bounds_and_contrast(self):
        out=self.build(pptx=False)
        report=read_json(out/'render-report.json')
        for page in report['pages']:
            self.assertFalse(page['overflow'])
            for block in page['blocks']:
                if block['text']: self.assertGreaterEqual(block['contrast_ratio'],4.5)
                for left,top,right,bottom in block['glyph_bounds']:
                    self.assertGreaterEqual(left,block['x']-1)
                    self.assertLessEqual(right,block['x']+block['box_width']+1)
                    self.assertLessEqual(bottom,block['y']+block['box_height']+1)

    def test_line_starting_with_hanging_glyph_stays_in_box(self):
        # A lowercase j extends left of its origin in fonts such as Malgun Gothic.
        self.plan['slides'][1]['title']='jev 판단 모델'
        self.plan['slides'][1]['bullets'][0]='jev-ultrafast는 Jev를 활용한 브라우저 자동화 데모입니다.'
        write_json(self.project/'plan.json',self.plan)
        for preset in ('portrait-2x','legacy'):
            out=build_project(self.project,self.root/f'out-{preset}',preset=preset,profile_name='jeju',pptx=False)
            report=read_json(out/'render-report.json')
            blocks=[b for p in report['pages'] for b in p['blocks'] if b['text'].startswith('jev')]
            self.assertEqual(len(blocks),2)
            for block in blocks:
                for left,_,right,_ in block['glyph_bounds']:
                    self.assertGreaterEqual(left,block['x'])
                    self.assertLessEqual(right,block['x']+block['box_width'])

    def test_black_logo_kept(self):
        logo=self.root/'black.png';Image.new('RGBA',(80,40),(0,0,0,255)).save(logo)
        out=self.build(logo_path=str(logo),pptx=False)
        with Image.open(out/'png/01_cover.png') as im:
            self.assertEqual(im.getpixel((980,1290)),(0,0,0))

if __name__=='__main__': unittest.main(verbosity=2)
