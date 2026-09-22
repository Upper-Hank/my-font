"""Shared catalog migration and formal-glyph/template usage metadata."""
import tempfile
import unittest
from pathlib import Path
from handfont.common import write_json
from handfont.storage import data_dir
from handfont.project import manage_characters, trash_samples
from handfont.web import block_library_payload


class BlockLibraryTest(unittest.TestCase):
    def test_catalog_is_shared_and_usage_survives_template_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            folder = data_dir(work, 'templates') / 'old'
            folder.mkdir(parents=True)
            write_json(folder / 'index.json', {'pages': [{'page_id': 'p'}], 'editor_library': ['乙']})
            write_json(folder / 'p.json', {'cells': [{'char': '甲'}, {'char': '甲'}]})
            glyphs = data_dir(work, 'runs') / 'batch'
            (glyphs / 'one').mkdir(parents=True)
            (glyphs / 'one/gray.png').write_bytes(b'fixture')
            write_json(glyphs / 'run.json', {'run_id': 'batch', 'cell_mm': 16, 'glyphs': [
                {'sample_id': 'one', 'char': '甲', 'unicode': '7532', 'status': 'review', 'commands': [['moveTo', [0, 0]]]}]})
            rows = {c['char']: c for c in block_library_payload(work)['characters']}
            self.assertEqual(set(rows), {'甲', '乙'})
            self.assertTrue(rows['甲']['has_glyph'])
            self.assertTrue(rows['甲']['used_in_template'])
            self.assertFalse(rows['乙']['has_glyph'])
            self.assertFalse(rows['乙']['used_in_template'])
            manage_characters(work, '丙丙')
            self.assertEqual(len(block_library_payload(work)['characters']), 3)
            trash_samples(work, ['batch/one'])
            rows = {c['char']: c for c in block_library_payload(work)['characters']}
            self.assertFalse(rows['甲']['has_glyph'])
            (folder / 'index.json').unlink()
            rows = {c['char']: c for c in block_library_payload(work)['characters']}
            self.assertTrue(rows['甲']['used_in_template'])
            manage_characters(work, '乙', remove=True)
            self.assertNotIn('乙', [c['char'] for c in block_library_payload(work)['characters']])
