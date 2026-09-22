"""Sample identity and failed-export preservation, without image processing."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from handfont.common import write_json
from handfont.project import (ensure_live, sample_library, select_sample, load_live, export_selection,
                              archive_item, cleanup_history, resolve_glyph, trash_samples, delete_samples,
                              import_run)
from handfont.storage import data_dir, migrate_storage

class LibraryTest(unittest.TestCase):
    def test_samples_survive_selection_and_failed_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            for batch in ('a', 'b'):
                folder = data_dir(work, 'runs') / batch
                folder.mkdir(parents=True)
                for sample in ('one', 'two'):
                    (folder / sample).mkdir()
                    (folder / sample / 'gray.png').write_bytes(b'image fixture')
                write_json(folder / 'run.json', {'run_id': batch, 'cell_mm': 16, 'glyphs': [
                    {'sample_id': sample, 'char': '字', 'unicode': 'U+5B57',
                     'status': 'review', 'commands': [['moveTo', [0, 0]]]}
                    for sample in ('one', 'two')]})
            ensure_live(work)
            self.assertEqual(len(sample_library(work)), 4)
            select_sample(work, 'a/one')
            select_sample(work, 'a/two')
            self.assertEqual(load_live(work)['members'][0]['sample_id'], 'two')
            select_sample(work, 'b/one')
            self.assertEqual(len(load_live(work)['members']), 1)
            archive_item(work, 'sample', 'b/one')
            self.assertEqual(load_live(work)['members'], [])
            self.assertEqual(len(sample_library(work)), 4)
            with self.assertRaises(ValueError):
                select_sample(work, 'b/one')
            archive_item(work, 'sample', 'b/one', restore=True)
            self.assertEqual(load_live(work)['members'], [])
            (data_dir(work, 'templates') / 'demo').mkdir(parents=True)
            write_json(data_dir(work, 'templates') / 'demo' / 'index.json', {'title': '试印', 'characters': 2, 'pages': []})
            (data_dir(work, 'staging') / 'page-01').mkdir(parents=True)
            write_json(data_dir(work, 'staging') / 'page-01' / 'preview.json', {'pages': []})
            (data_dir(work, 'runs') / 'cut-01').mkdir(parents=True)
            write_json(data_dir(work, 'runs') / 'cut-01' / 'run.json', {'run_id': 'cut-01', 'cell_mm': 16, 'glyphs': []})
            archive_item(work, 'template', 'demo')
            archive_item(work, 'preview', 'page-01')
            archive_item(work, 'run', 'cut-01')
            live = load_live(work)
            self.assertEqual(live['archived_template'], ['demo'])
            self.assertEqual(live['archived_preview'], ['page-01'])
            self.assertEqual(live['archived_run'], ['cut-01'])
            archive_item(work, 'template', 'demo', restore=True)
            self.assertEqual(load_live(work)['archived_template'], [])
            cleanup_history(work, 'template', 'demo')
            self.assertFalse((data_dir(work, 'templates') / 'demo').exists())
            self.assertEqual(load_live(work)['archived_template'], [])
            select_sample(work, 'b/one')
            before = load_live(work)
            with patch('handfont.build.compile_glyphs', side_effect=ValueError('compile failed')):
                with self.assertRaises(ValueError):
                    export_selection(work)
            self.assertEqual(load_live(work), before)
            select_sample(work, 'b/one', remove=True)
            self.assertEqual(load_live(work)['members'], [])
            self.assertEqual(len(sample_library(work)), 4)

    def test_cleanup_preserves_assets_selection_and_font_export(self):
        from PIL import Image
        from fontTools.ttLib import TTFont
        from handfont.common import read_json
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            source = data_dir(work, 'runs') / 'conversion'
            (source / 'one').mkdir(parents=True)
            Image.new('L', (20, 20), 255).save(source / 'one/gray.png')
            row = {'sample_id': 'one', 'char': 'A', 'unicode': '0041', 'glyph_name': 'A',
                   'status': 'review', 'gray': 'one/gray.png', 'width': 1000,
                   'page_id': 'page', 'cell_id': 1, 'image_transform': [1, 0, 0, 1, 0, 0],
                   'commands': [['moveTo', [[100, 100]]], ['lineTo', [[600, 100]]],
                                ['lineTo', [[600, 700]]], ['lineTo', [[100, 700]]], ['closePath', []]]}
            write_json(source / 'run.json', {'run_id': 'conversion', 'cell_mm': 16, 'glyphs': [row]})
            template = data_dir(work, 'templates') / 'sheet'
            template.mkdir(parents=True)
            write_json(template / 'index.json', {'pages': []})
            write_json(template / 'page.json', {'page_id': 'page', 'geometry': 'retained'})
            pending = data_dir(work, 'staging') / 'pending'
            pending.mkdir(parents=True)
            write_json(pending / 'preview.json', {'template': 'sheet', 'pages': []})
            completed = data_dir(work, 'staging') / 'conversion'
            completed.mkdir()
            (completed / 'original.jpg').write_bytes(b'original photo')
            select_sample(work, 'conversion/one')
            before = load_live(work)['members']
            retained = data_dir(work, 'glyphs') / 'conversion/one/gray.png'
            original = retained.read_bytes()
            retained.write_bytes(b'damaged')
            cleanup_history(work, 'run', 'conversion')
            cleanup_history(work, 'template', 'sheet')
            self.assertFalse(source.exists())
            self.assertFalse(completed.exists())
            self.assertFalse(template.exists())
            self.assertEqual(read_json(pending / 'template/page.json')['page_id'], 'page')
            self.assertEqual(load_live(work)['members'], before)
            self.assertEqual(len(sample_library(work)), 1)
            self.assertEqual((data_dir(work, 'glyphs') / 'conversion/one/gray.png').read_bytes(), original)
            self.assertEqual(resolve_glyph(work, before[0])['commands'], row['commands'])
            build = export_selection(work)
            with TTFont(data_dir(work, 'builds') / build / 'Preview.otf') as font:
                self.assertIn(ord('A'), font.getBestCmap())

    def test_trashed_glyphs_can_be_purged(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            folder = data_dir(work, 'runs') / 'batch'
            (folder / 'keep').mkdir(parents=True)
            (folder / 'drop').mkdir()
            (folder / 'keep/gray.png').write_bytes(b'keep')
            (folder / 'drop/gray.png').write_bytes(b'drop')
            write_json(folder / 'run.json', {'run_id': 'batch', 'cell_mm': 16, 'glyphs': [
                {'sample_id': name, 'char': '字' if name == 'keep' else '去', 'unicode': '5B57',
                 'status': 'review', 'commands': [['moveTo', [0, 0]]]}
                for name in ('keep', 'drop')]})
            ensure_live(work)
            self.assertEqual(len(sample_library(work)), 2)
            with self.assertRaises(ValueError):
                delete_samples(work, ['batch/drop'])
            trash_samples(work, ['batch/drop'])
            self.assertEqual(load_live(work)['archived_sample'], ['batch/drop'])
            self.assertTrue((data_dir(work, 'glyphs') / 'batch/drop/gray.png').is_file())
            delete_samples(work, ['batch/drop'])
            self.assertFalse((data_dir(work, 'glyphs') / 'batch/drop').exists())
            self.assertFalse((data_dir(work, 'runs') / 'batch/drop').exists())
            self.assertTrue((data_dir(work, 'glyphs') / 'batch/keep/gray.png').is_file())
            self.assertEqual([s['id'] for s in sample_library(work)], ['batch/keep'])
            self.assertIn('batch/drop', load_live(work)['deleted_sample'])
            self.assertEqual(load_live(work)['archived_sample'], [])
            import_run(work, 'batch')
            self.assertEqual([s['id'] for s in sample_library(work)], ['batch/keep'])

    def test_photo_preview_deletes_without_recycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            pending = data_dir(work, 'staging') / 'photo-01'
            pending.mkdir(parents=True)
            write_json(pending / 'preview.json', {'pages': []})
            (pending / '01-original.jpg').write_bytes(b'photo')
            cleanup_history(work, 'preview', 'photo-01')
            self.assertFalse(pending.exists())

    def test_storage_layout_migrates_legacy_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / 'glyphs/old').mkdir(parents=True)
            (work / 'glyphs/old/run.json').write_text('{}')
            (work / 'web-demo').mkdir()
            (work / 'web-verification.json').write_text('{}')
            migrate_storage(work)
            self.assertTrue((work / 'assets/glyphs/old/run.json').is_file())
            self.assertFalse((work / 'glyphs').exists())
            self.assertTrue((work / 'legacy/experiments/web-demo').is_dir())
            self.assertTrue((work / 'legacy/web-verification.json').is_file())
            self.assertEqual(data_dir(work, 'live'), work / 'state')
