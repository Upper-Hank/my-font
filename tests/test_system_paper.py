import tempfile
import unittest
from pathlib import Path
from handfont.common import read_json
from handfont.project import archive_item, cleanup_history
from handfont.storage import data_dir
from handfont.template import SYSTEM_PAPER_ID, SYSTEM_PAPER_TITLE, ensure_system_paper, locked_template_mode, make_template
from handfont.web import template_payload


class SystemPaperTest(unittest.TestCase):
    def test_ensure_once_and_reject_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            first = ensure_system_paper(work)
            second = ensure_system_paper(work)
            self.assertEqual(first, second)
            index = read_json(first / 'index.json')
            self.assertTrue(index['system'])
            self.assertEqual(index['mode'], 'generic')
            self.assertEqual(index['title'], SYSTEM_PAPER_TITLE)
            self.assertGreater(index['characters'], 0)
            with self.assertRaisesRegex(ValueError, '系统模板'):
                archive_item(work, 'template', SYSTEM_PAPER_ID)
            with self.assertRaisesRegex(ValueError, '系统模板'):
                cleanup_history(work, 'template', SYSTEM_PAPER_ID)

    def test_payload_creates_paper_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'charset').mkdir()
            (root / 'charset/mvp.txt').write_text('甲')
            payload = template_payload(root, root)
            self.assertEqual(payload['paper']['id'], SYSTEM_PAPER_ID)
            self.assertEqual(payload['paper']['title'], SYSTEM_PAPER_TITLE)

    def test_payload_keeps_paper_out_of_user_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'charset').mkdir()
            (root / 'charset/mvp.txt').write_text('甲')
            work = root
            ensure_system_paper(work)
            make_template(None, data_dir(work, 'templates') / 'mine',
                          editor_pages=[{'cells': [{'slot': 0, 'char': '甲'}]}])
            payload = template_payload(root, work)
            self.assertEqual(payload['paper']['id'], SYSTEM_PAPER_ID)
            self.assertEqual([item['id'] for item in payload['records']], ['mine'])

    def test_cannot_create_another_generic_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            with self.assertRaisesRegex(ValueError, '系统模板'):
                locked_template_mode(work, '', 'generic')
            self.assertEqual(locked_template_mode(work, '', 'assigned'), ('assigned', False))
            ensure_system_paper(work)
            self.assertEqual(locked_template_mode(work, SYSTEM_PAPER_ID, 'assigned'), ('generic', True))
