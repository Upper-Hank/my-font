"""Focused source-to-font checks, without browser automation."""
from pathlib import Path
import tempfile
import unittest
import shutil
import io
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

from handfont.adjust import adjust_glyph, character_placement, adjustment_options
from handfont.common import read_json, write_json
from handfont.conversion import checked_regions, process_regions, template_regions
from handfont.project import review_run, sample_library, select_sample, export_selection, resolve_glyph, load_live
from handfont.storage import data_dir
from handfont.trace import bounds
from handfont.web import make_server, preview_payload
from handfont.template import make_template


class ConversionTest(unittest.TestCase):
    def test_import_sources_and_saved_template_overrides_use_the_same_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'charset').mkdir()
            (root / 'charset/mvp.txt').write_text('字')
            # Exercise production handlers and storage without a browser or network listener.
            with patch('handfont.web.ThreadingHTTPServer', side_effect=lambda address, handler: SimpleNamespace(Handler=handler)):
                server = make_server(root)
            handler = server.Handler.__new__(server.Handler)
            handler.json = lambda status, payload: payload
            handler.wants_json = lambda: True
            def post(path, fields, files=()):
                handler.path = path
                with patch('handfont.web.parse_post', return_value=(fields, files)):
                    return handler.post()
            image = Image.new('L', (200, 140), 255)
            ImageDraw.Draw(image).rectangle((50, 40, 90, 90), fill=0)
            stream = io.BytesIO()
            image.save(stream, format='PNG')
            template = data_dir(root / 'work', 'templates') / 'assigned'
            make_template(None, template, editor_pages=[{'cells': [{'char': '字', 'slot': 0}]}])
            manifest = next(p for p in template.glob('*.json') if p.name != 'index.json')
            page_id = read_json(manifest)['page_id']
            result = post('/prepare', {'source': 'auto', 'dpi': '300'}, [
                ('photos', 'note.png', stream.getvalue()),
                ('photos', 'template.png', (template / f'{page_id}.png').read_bytes()),
            ])
            name = result['redirect'].rsplit('/', 1)[1]
            payload = preview_payload(root / 'work', name)
            self.assertEqual([page['source_kind'] for page in payload['pages']], ['free', 'assigned'])
            self.assertEqual(payload['pages'][0]['regions'], [])
            self.assertEqual(payload['pages'][1]['regions'][0]['char'], '字')
            pages = payload['pages']
            pages[0]['regions'] = [{'id': 'one', 'rect': [30, 20, 100, 100], 'char': ''}]
            pages[1]['regions'][0]['char'] = 'A'
            post('/preview/save', {'run': name, 'pages': pages})
            reopened = preview_payload(root / 'work', name)
            self.assertEqual(reopened['pages'][1]['regions'][0]['char'], 'A')
            self.assertEqual(reopened['pages'][1]['presets'][0]['char'], '字')
            self.assertEqual(reopened['pages'][0]['regions'][0]['rect'], [30, 20, 100, 100])
            self.assertEqual(sample_library(root / 'work'), [])

    def test_source_regions_are_bounded_and_template_frames_cannot_be_overridden(self):
        manifest = {'cell_mm': 16, 'cells': [{'id': 1, 'char': '字', 'writing_mm': [10, 10, 16, 16]}]}
        presets = template_regions(manifest, {}, 300)
        page = {'page_id': 'page-01', 'width': 500, 'height': 500, 'regions': presets, 'presets': presets}
        edits = [{'page_id': 'page-01', 'regions': [{**presets[0], 'char': 'A', 'frame': [0, 0, 1]}]}]
        saved = checked_regions([page], edits)[0]['regions'][0]
        self.assertEqual(saved['char'], 'A')
        self.assertEqual(saved['frame'], presets[0]['frame'])
        moved = dict(edits[0]['regions'][0], rect=[presets[0]['rect'][0] + 20, *presets[0]['rect'][1:]])
        shifted = checked_regions([page], [{'page_id': 'page-01', 'regions': [moved]}])[0]['regions'][0]
        self.assertAlmostEqual(shifted['frame'][0], presets[0]['frame'][0] + 20)
        self.assertEqual(shifted['frame'][2], presets[0]['frame'][2])
        for rect in ([-1, 0, 20, 20], [490, 0, 20, 20], [0, 0, float('nan'), 20]):
            edits[0]['regions'][0]['rect'] = rect
            with self.assertRaises(ValueError):
                checked_regions([page], edits)

    @unittest.skipUnless(shutil.which('potrace'), '真实描边需要本机 Potrace')
    def test_free_photo_review_placement_and_export_share_one_outline(self):
        self.conversion_and_export()

    def test_conversion_review_and_export_with_controlled_trace(self):
        def trace(bitmap, output, size, transform):
            a, _, _, d, e, f = transform
            with Image.open(bitmap) as image:
                box = image.point(lambda value: 255 - value).getbbox()
            x0, y0, x1, y1 = box
            points = [(x0*a+e, (size[1]-y1)*d+f), (x1*a+e, (size[1]-y1)*d+f),
                      (x1*a+e, (size[1]-y0)*d+f), (x0*a+e, (size[1]-y0)*d+f)]
            return [('moveTo', [points[0]]), *[('lineTo', [point]) for point in points[1:]], ('closePath', [])]
        with patch('handfont.conversion.shutil.which', return_value='potrace'), patch('handfont.conversion.trace_bitmap', side_effect=trace):
            self.conversion_and_export()

    def conversion_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            staging = data_dir(work, 'staging') / 'photo'
            staging.mkdir(parents=True)
            image = Image.new('L', (200, 140), 255)
            ImageDraw.Draw(image).rectangle((50, 40, 90, 90), fill=0)
            for name in ('scan.png', 'original.png', 'photo.jpg'):
                image.save(staging / name)
            page = {'page_id': 'page-01', 'width': 200, 'height': 140, 'scan': 'scan.png', 'photo': 'photo.jpg',
                    'original': 'original.png', 'source_name': '手写稿.png', 'source_kind': 'free',
                    'regions': [{'id': 'one', 'rect': [30, 20, 100, 100], 'char': '字'}]}
            preview = {'schema': 2, 'threshold': '180', 'pages': [page]}
            write_json(staging / 'preview.json', preview)
            folder = data_dir(work, 'runs') / 'photo'
            process_regions(staging, preview, folder)
            self.assertTrue(preview_payload(work, 'photo')['converted'])
            run = read_json(folder / 'run.json')
            self.assertTrue(run['review_pending'])
            self.assertEqual(sample_library(work), [])
            glyph = run['glyphs'][0]
            self.assertEqual(glyph['status'], 'review')
            adjustment = adjustment_options({'normalize': True, 'target': 750, 'center_x': True, 'center_y': True})
            choices = [{'sample_id': glyph['sample_id'], 'char': '新', 'confirmed': True, 'keep': True, 'adjustment': adjustment}]
            review_run(work, 'photo', choices)
            self.assertEqual(read_json(folder / 'run.json')['review_choices'], choices)
            review_run(work, 'photo', choices, commit=True)
            review_run(work, 'photo', choices, commit=True)
            samples = sample_library(work)
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]['source_name'], '手写稿.png')
            select_sample(work, samples[0]['id'])
            expected = bounds(adjust_glyph(character_placement(glyph, '新'), adjustment)['commands'])
            self.assertEqual(bounds(resolve_glyph(work, load_live(work)['members'][0])['commands']), expected)
            build = export_selection(work)
            with TTFont(data_dir(work, 'builds') / build / 'Preview.otf') as font:
                glyphs = font.getGlyphSet()
                pen = BoundsPen(glyphs)
                glyphs[font.getBestCmap()[ord('新')]].draw(pen)
                self.assertEqual(pen.bounds, tuple(round(v) for v in expected))
            self.assertTrue((folder / 'raw/01.png').is_file())

    def test_changed_character_recomputes_latin_spacing_without_mutating_source(self):
        row = {'char': '字', 'width': 1000, 'commands': [('moveTo', [(200, 100)]), ('lineTo', [(400, 100)]),
               ('lineTo', [(400, 500)]), ('closePath', [])], 'image_transform': [1, 0, 0, 1, 0, 0]}
        latin = character_placement(row, 'A')
        self.assertEqual(latin['width'], 320)
        self.assertEqual(bounds(latin['commands'])[0], 60)
        restored = character_placement(latin, '字')
        self.assertEqual(restored['width'], 1000)
        self.assertEqual(bounds(restored['commands']), bounds(row['commands']))
        self.assertEqual(restored['image_transform'], row['image_transform'])
        self.assertEqual(row['width'], 1000)
