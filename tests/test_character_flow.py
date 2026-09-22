"""Two focused checks for character ownership and reviewed conversion imports."""
from pathlib import Path
import tempfile
import unittest

from handfont.common import read_json, write_json
from handfont.project import (manage_characters, sample_library, load_live, select_sample,
                              trash_samples, archive_item, review_run, cleanup_history)
from handfont.storage import data_dir
from handfont.web import live_payload, photos_payload


class CharacterFlowTest(unittest.TestCase):
    def make_run(self, work, name, pending=False):
        folder = data_dir(work, 'runs') / name
        rows = []
        for sample in ('one', 'two'):
            (folder / sample).mkdir(parents=True)
            (folder / sample / 'gray.png').write_bytes(b'fixture')
            rows.append({'sample_id': sample, 'char': '字', 'unicode': '5B57',
                         'status': 'review', 'commands': [['moveTo', [0, 0]]]})
        write_json(folder / 'run.json', {'run_id': name, 'cell_mm': 16,
                                        'glyphs': rows, 'review_pending': pending})
        return folder

    def test_characters_exist_without_glyphs_and_survive_glyph_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            manage_characters(work, '春春 风 U+5B57')
            self.assertEqual(live_payload(work)['characters'], ['春', '风', '字'])
            self.assertEqual(sample_library(work), [])
            self.make_run(work, 'legacy')
            self.assertEqual(len(sample_library(work)), 2)
            select_sample(work, 'legacy/one')
            trash_samples(work, ['legacy/one', 'legacy/two'])
            self.assertIn('字', live_payload(work)['characters'])
            self.assertEqual(live_payload(work)['samples'], [])
            self.assertEqual(load_live(work)['members'], [])
            manage_characters(work, '春字', remove=True)
            self.assertEqual(live_payload(work)['characters'], ['风'])
            archive_item(work, 'sample', 'legacy/one', restore=True)
            self.assertIn('字', live_payload(work)['characters'])
            select_sample(work, 'legacy/one')
            manage_characters(work, '字', remove=True)
            self.assertNotIn('字', live_payload(work)['characters'])
            self.assertEqual(load_live(work)['members'], [])

    def test_review_persists_and_adds_multiple_glyphs_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            self.make_run(work, 'legacy')
            select_sample(work, 'legacy/one')
            folder = self.make_run(work, 'new', pending=True)
            self.assertEqual(len(sample_library(work)), 2)
            choices = [{'sample_id': sample, 'char': '字', 'keep': True} for sample in ('one', 'two')]
            review_run(work, 'new', choices)
            self.assertEqual(read_json(folder / 'run.json')['review_choices'], choices)
            self.assertEqual(len(sample_library(work)), 2)
            self.assertEqual(photos_payload(work)['pending'], [{'id': 'new'}])
            review_run(work, 'new', choices, commit=True)
            review_run(work, 'new', choices, commit=True)
            self.assertEqual(len(sample_library(work)), 4)
            self.assertEqual(load_live(work)['members'][0]['run'], 'legacy')
            self.make_run(work, 'corrected', pending=True)
            corrected = [{'sample_id': 'one', 'char': '新', 'keep': True},
                         {'sample_id': 'two', 'char': '字', 'keep': False}]
            review_run(work, 'corrected', corrected, commit=True)
            cleanup_history(work, 'run', 'corrected')
            rows = [s for s in sample_library(work) if s['run'] == 'corrected']
            self.assertEqual([(s['char'], s['unicode']) for s in rows], [('新', '65B0')])
            self.assertIn('新', live_payload(work)['characters'])
            self.make_run(work, 'discarded', pending=True)
            cleanup_history(work, 'run', 'discarded')
            self.assertEqual(len(sample_library(work)), 5)
