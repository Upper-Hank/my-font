"""Placement math and export use the same non-destructive adjustment."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from handfont.adjust import adjust_glyph, adjustment_options, reference_boxes
from handfont.common import write_json, read_json
from handfont.project import select_sample, set_adjustment, resolve_glyph, load_live, export_selection
from handfont.storage import data_dir
from handfont.trace import bounds
from handfont.web import live_payload


class AdjustmentTest(unittest.TestCase):
    def row(self):
        return {'sample_id': 'one', 'char': '自', 'unicode': '81EA', 'glyph_name': 'uni81EA',
                'status': 'review', 'width': 1000, 'gray': 'one/gray.png',
                'page_id': 'page', 'cell_id': 1, 'image_transform': [1, 0, 0, 1, 0, 0],
                'commands': [['moveTo', [[100, 100]]], ['lineTo', [[200, 100]]],
                             ['lineTo', [[200, 300]]], ['lineTo', [[100, 300]]], ['closePath', []]]}

    def test_normalization_centers_without_stretching_or_mutating_original(self):
        row = self.row()
        options = {'normalize': True, 'center_x': True, 'center_y': True}
        adjusted = adjust_glyph(row, options)
        self.assertEqual(bounds(adjusted['commands']), (300, -20, 700, 780))
        self.assertEqual(bounds(row['commands']), (100, 100, 200, 300))
        self.assertEqual(adjusted['image_transform'], [4, 0, 0, 4, -100, -420])
        self.assertEqual(adjust_glyph(row)['commands'], row['commands'])
        punctuation = {**row, 'char': '。'}
        self.assertEqual(bounds(adjust_glyph(punctuation, {'normalize': True})['commands']), bounds(row['commands']))
        with self.assertRaises(ValueError):
            adjustment_options({'scale': float('nan')})

    def test_reference_fit_offsets_and_unsupported_character_fallback(self):
        row = self.row()
        ref = reference_boxes()[ord(row['char'])]
        adjusted = adjust_glyph(row, {'reference': True})
        box = bounds(adjusted['commands'])
        self.assertAlmostEqual(max(box[2]-box[0], box[3]-box[1]),
                               max(ref[2]-ref[0], ref[3]-ref[1]))
        self.assertAlmostEqual((box[2]-box[0]) / (box[3]-box[1]), 0.5)
        shifted = bounds(adjust_glyph(row, {'reference': True, 'offset_x': 25, 'offset_y': -40})['commands'])
        self.assertEqual(shifted, (box[0]+25, box[1]-40, box[2]+25, box[3]-40))
        for char in ('。', 'A', chr(0x31350)):
            self.assertEqual(adjust_glyph({**row, 'char': char}, {'reference': True})['commands'], row['commands'])
        with self.assertRaises(ValueError):
            adjustment_options({'offset_x': float('inf')})
        self.assertEqual(adjustment_options({'reference': True, 'unknown': 1})['reference'], True)

    def test_saved_adjustment_reaches_font_export_and_can_be_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            folder = data_dir(work, 'runs') / 'batch'
            (folder / 'one').mkdir(parents=True)
            Image.new('L', (20, 20), 255).save(folder / 'one/gray.png')
            write_json(folder / 'run.json', {'run_id': 'batch', 'cell_mm': 16, 'glyphs': [self.row()]})
            select_sample(work, 'batch/one')
            original = read_json(data_dir(work, 'glyphs') / 'batch/run.json')
            set_adjustment(work, ['batch/one'], {'normalize': True, 'center_x': True, 'center_y': True})
            member = load_live(work)['members'][0]
            expected = bounds(resolve_glyph(work, member)['commands'])
            build = export_selection(work)
            with TTFont(data_dir(work, 'builds') / build / 'Preview.otf') as font:
                glyphs = font.getGlyphSet()
                pen = BoundsPen(glyphs)
                glyphs[font.getBestCmap()[ord('自')]].draw(pen)
                self.assertEqual(pen.bounds, expected)
            self.assertFalse(live_payload(work)['dirty'])
            self.assertEqual(live_payload(work)['pending'], {'added': [], 'removed': [], 'replaced': []})
            set_adjustment(work, ['batch/one'], {})
            payload = live_payload(work)
            self.assertTrue(payload['dirty'])
            self.assertEqual(payload['pending']['replaced'], ['自'])
            self.assertEqual(bounds(resolve_glyph(work, member)['commands']), (100, 100, 200, 300))
            self.assertEqual(read_json(data_dir(work, 'glyphs') / 'batch/run.json'), original)

    def test_font_pending_marks_added_removed_and_replaced(self):
        from handfont.project import font_pending
        previous = [{'char': '字', 'run': 'a', 'sample_id': '1'}, {'char': '己', 'run': 'a', 'sample_id': '2'}]
        current = [{'char': '字', 'run': 'a', 'sample_id': '9'}, {'char': '我', 'run': 'a', 'sample_id': '3'}]
        self.assertEqual(font_pending(current, previous), {'added': ['我'], 'removed': ['己'], 'replaced': ['字']})
        self.assertEqual(font_pending(current, None), {'added': [], 'removed': [], 'replaced': []})
        self.assertEqual(font_pending(current, [{'char': '字'}, {'char': '己'}]), {'added': ['我'], 'removed': ['己'], 'replaced': []})

    def test_reselecting_the_same_formal_glyph_is_not_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            folder = data_dir(work, 'runs') / 'batch'
            (folder / 'one').mkdir(parents=True)
            Image.new('L', (20, 20), 255).save(folder / 'one/gray.png')
            write_json(folder / 'run.json', {'run_id': 'batch', 'cell_mm': 16, 'glyphs': [self.row()]})
            select_sample(work, 'batch/one')
            set_adjustment(work, ['batch/one'], {'normalize': True, 'center_x': True, 'center_y': True})
            export_selection(work)
            select_sample(work, 'batch/one', remove=True)
            self.assertEqual(live_payload(work)['pending']['removed'], ['自'])
            self.assertTrue(live_payload(work)['dirty'])
            select_sample(work, 'batch/one', remove=False)
            payload = live_payload(work)
            self.assertEqual(payload['pending'], {'added': [], 'removed': [], 'replaced': []})
            self.assertFalse(payload['dirty'])
