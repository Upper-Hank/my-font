"""Verify sparse page positions and mixed-size export round trips."""
import tempfile
import unittest
from pathlib import Path
from handfont.storage import data_dir
from handfont.common import read_json, validate_manifest
from handfont.template import grid_geometry, make_template, plan_editor_pages
from handfont.web import template_payload


class TemplateCanvasTest(unittest.TestCase):
    def test_sparse_mixed_pages_round_trip(self):
        pages = [{"paper_format": "A4", "orientation": "portrait", "cell_mm": 16, "cells": [{"slot": 5, "char": "甲"}]},
                 {"paper_format": "A5", "orientation": "landscape", "cell_mm": 20, "cells": [{"slot": 2, "char": "A"}]}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'charset').mkdir()
            (root / 'charset/mvp.txt').write_text('甲A')
            output = data_dir(root, 'templates') / 'test'
            make_template(None, output, editor_pages=pages, editor_library=['乙'])
            index = read_json(output / 'index.json')
            for spec, record in zip(pages, index['pages']):
                manifest = read_json(output / (record['page_id'] + '.json'))
                validate_manifest(manifest)
                geometry = grid_geometry(spec['cell_mm'], spec['orientation'], spec['paper_format'])
                self.assertEqual(manifest['page_mm'], geometry['page_mm'])
                self.assertEqual(manifest['cells'][0]['writing_mm'], geometry['slots_mm'][spec['cells'][0]['slot']])
            payload = template_payload(root, root, 'test')
            self.assertEqual(payload['editor_pages'], pages)
            self.assertEqual(payload['editor_library'], ['乙'])
            self.assertTrue((output / 'template.pdf').is_file())

    def test_replace_existing_template(self):
        first = [{"paper_format": "A4", "orientation": "portrait", "cell_mm": 16, "cells": [{"slot": 0, "char": "甲"}]}]
        second = [{"paper_format": "A4", "orientation": "portrait", "cell_mm": 16, "cells": [{"slot": 1, "char": "乙"}]}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'charset').mkdir()
            (root / 'charset/mvp.txt').write_text('甲乙')
            output = data_dir(root, 'templates') / 'test'
            make_template(None, output, editor_pages=first)
            make_template(None, output, editor_pages=second, replace=True)
            payload = template_payload(root, root, 'test')
            self.assertEqual(payload['editor_pages'][0]['cells'][0]['char'], '乙')

    def test_reject_invalid_positions(self):
        for cells in [[{'slot': 999, 'char': 'A'}], [{'slot': 0, 'char': 'A'}, {'slot': 0, 'char': 'B'}]]:
            with self.assertRaises(ValueError):
                plan_editor_pages([{'cells': cells}])
