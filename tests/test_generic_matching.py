"""Generic paper identity, local suggestions and the human confirmation boundary."""
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw
from handfont.common import read_json, validate_manifest
from handfont.template import make_template
from handfont.scan import process_scans
from handfont.matching import suggest_run
from handfont.project import review_run, sample_library
from handfont.storage import data_dir


class GenericMatchingTest(unittest.TestCase):
    def test_scan_match_and_confirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            template = data_dir(work, 'templates') / 'generic'
            make_template(None, template, mode='generic', editor_pages=[{'cells': []}])
            manifest = read_json(next(p for p in template.glob('*.json') if p.name != 'index.json'))
            validate_manifest(manifest)
            self.assertEqual(len(manifest['cells']), manifest['grid']['capacity'])
            self.assertTrue(all(c['char'] == c['unicode'] == '' for c in manifest['cells']))
            with Image.open(template / f"{manifest['page_id']}.png") as source:
                image = source.convert('L')
            x, y, w, h = manifest['cells'][0]['writing_mm']
            scale = 300 / 25.4
            ImageDraw.Draw(image).line(((x+w*.2)*scale, (y+h*.5)*scale, (x+w*.8)*scale, (y+h*.5)*scale), fill=0, width=6)
            scan = work / 'scan.png'
            image.save(scan)
            for name in ('first', 'second'):
                folder = data_dir(work, 'runs') / name
                process_scans(template, [scan], folder, dpi=300)
                suggest_run(work, name)
                run = read_json(folder / 'run.json')
                self.assertTrue(run['review_pending'])
                glyph = run['glyphs'][0]
                self.assertEqual(glyph['char'], '')
                self.assertEqual(glyph['candidates'][0]['char'] if name == 'second' else glyph['candidates'], '一' if name == 'second' else [])
                choices = [{'sample_id': g['sample_id'], 'char': '一' if i == 0 else '', 'keep': i == 0} for i, g in enumerate(run['glyphs'])]
                review_run(work, name, choices)
                with self.assertRaisesRegex(ValueError, '逐字确认'):
                    review_run(work, name, choices, commit=True)
                choices[0]['confirmed'] = True
                review_run(work, name, choices, commit=True)
            self.assertEqual([s['char'] for s in sample_library(work)], ['一', '一'])
