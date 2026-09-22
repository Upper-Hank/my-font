"""Three production-critical checks. Synthetic data is not handwriting QA."""
import copy
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from glyphsLib import GSFont
from glyphsLib.classes import GSGlyph, GSLayer

from handfont.build import build_run, load_source
from handfont.common import file_hash, read_json
from handfont.scan import process_scans, rectify
from handfont.trace import bounds

ROOT = Path(__file__).resolve().parents[1]
create_demo = runpy.run_path(str(ROOT / "scripts/make_demo.py"))["create_demo"]


class MVPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = create_demo(Path(cls.temp.name) / "demo")
        process_scans(cls.root / "template", [cls.root / "synthetic-scan.png"], cls.root / "run", dpi=300)
        build_run(cls.root / "run", cls.root / "build")
        cls.run_data = read_json(cls.root / "run/run.json")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_scan_coordinates_and_real_font_render(self):
        rows = {r["char"]: r for r in self.run_data["glyphs"]}
        self.assertEqual({c: r["status"] for c, r in rows.items()},
                         {"一": "review", "口": "review", "中": "review", "A": "review", "。": "blank", "下": "edge"})
        # The synthetic 一 is wide and deliberately above the cell centre.
        x0, y0, x1, y1 = bounds(rows["一"]["commands"])
        self.assertAlmostEqual((x0+x1)/2, 500, delta=10)
        self.assertAlmostEqual((y0+y1)/2, 430, delta=10)
        self.assertAlmostEqual(x1-x0, 700, delta=15)
        source = load_source(self.root / "build/Candidates.glyphs")
        with TTFont(self.root / "build/Preview.otf") as font:
            self.assertNotIn(ord("下"), font.getBestCmap())
            self.assertNotIn(ord("。"), font.getBestCmap())
            for char in "一口中A":
                row = rows[char]
                layer = source.glyphs[row["glyph_name"]].layers[0]
                pen = BoundsPen(None)
                layer.draw(pen)
                np.testing.assert_allclose(pen.bounds, bounds(row["commands"]), atol=0.01)
                compiled = BoundsPen(None)
                font.getGlyphSet()[row["glyph_name"]].draw(compiled)
                # CFF charstrings use integer rounding by default.
                np.testing.assert_allclose(compiled.bounds, pen.bounds, atol=1)
                self.assertEqual(layer.width, row["width"])
                image_path = self.root / "build" / layer.backgroundImage.path
                self.assertTrue(image_path.exists())
                np.testing.assert_allclose(tuple(layer.backgroundImage.transform), row["image_transform"], atol=0.001)
        raster = Image.new("L", (1000, 1200), 255)
        font = ImageFont.truetype(str(self.root / "build/Preview.otf"), 1000)
        ImageDraw.Draw(raster).text((0, 1000), "口", font=font, anchor="ls", fill=0)
        # Hole at cell centre survives; top-left stroke stays in the original location.
        self.assertGreater(raster.getpixel((450, 545)), 240)
        self.assertLess(raster.getpixel((450, 320)), 50)

    def test_fail_closed_and_never_overwrite(self):
        path = self.root / "build/Candidates.glyphs"
        before = file_hash(path)
        with self.assertRaisesRegex(ValueError, "不会覆盖"):
            build_run(self.root / "run", self.root / "build")
        self.assertEqual(file_hash(path), before)
        with self.assertRaisesRegex(ValueError, "不会覆盖"):
            process_scans(self.root / "template", [self.root / "synthetic-scan.png"], self.root / "run", dpi=300)
        with Image.open(self.root / "synthetic-flat.png") as original:
            damaged = original.copy()
        ImageDraw.Draw(damaged).rectangle((0, 0, 300, 300), fill=255)
        with self.assertRaisesRegex(ValueError, "四角"):
            rectify(damaged, 300)

    def test_glyphs_candidate_logic_preserves_manual_edits(self):
        # glyphsLib provides the object model; the thin shim only stands in for
        # native dialogs/app lifecycle. Native Glyphs compatibility is a separate check.
        target_font = load_source(self.root / "build/Candidates.glyphs")
        master = target_font.masters[0].id
        glyph = target_font.glyphs["uni4E00"]
        glyph.layers[master].paths[0].nodes[0].position.x += 17  # stand in for a manual edit
        before = RecordingPen()
        glyph.layers[master].draw(before)
        target = types.SimpleNamespace(glyphs=target_font.glyphs, masters=target_font.masters,
                                       userData=target_font.userData, filepath="", selectedLayers=[])
        def open_source(*args, **kwargs):
            source = load_source(self.root / "build/Candidates.glyphs")
            source.userData["com.handfont.run"] = "replacement-run"
            source.close = lambda **kw: None
            return source
        errors = []
        app = types.SimpleNamespace(font=target, open=open_source, showMacroWindow=lambda: None)
        module = types.ModuleType("GlyphsApp")
        module.Glyphs = app
        module.GetOpenFile = lambda *a, **kw: str(self.root / "build/Candidates.glyphs")
        module.Message = lambda title, message: errors.append(title) if title.startswith("未完成") else None
        with patch.dict(sys.modules, {"GlyphsApp": module}), \
             patch.object(GSGlyph, "copy", copy.deepcopy, create=True), \
             patch.object(GSLayer, "copy", copy.deepcopy, create=True):
            for _ in range(2):
                runpy.run_path(str(ROOT / "scripts/glyphs/Import Candidates.py"))
            self.assertEqual(errors, [])
            self.assertEqual(len(glyph.layers), 2)  # one candidate, even after reimport
            after = RecordingPen()
            glyph.layers[master].draw(after)
            self.assertEqual(before.value, after.value)
            target.selectedLayers = [next(l for l in glyph.layers if l.name.startswith("Handfont candidate"))]
            runpy.run_path(str(ROOT / "scripts/glyphs/Use Candidate.py"))
            self.assertEqual(errors, [])
            previous = next(l for l in glyph.layers if l.name.startswith("Handfont previous"))
            saved = RecordingPen()
            previous.draw(saved)
            self.assertEqual(saved.value, before.value)


class ProjectMergeTest(unittest.TestCase):
    def test_duplicate_characters_can_be_kept_or_replaced(self):
        from handfont.project import apply_add, classify_add, empty_project
        project = empty_project("试验")
        project["members"] = [{"char": "的", "unicode": "7684", "run": "a", "sample_id": "a-1", "template": "t1"}]
        glyphs = [
            {"char": "的", "unicode": "7684", "sample_id": "b-1"},
            {"char": "我", "unicode": "6211", "sample_id": "b-2"},
        ]
        fresh, duplicates = classify_add(project, glyphs)
        self.assertEqual([g["char"] for g in fresh], ["我"])
        self.assertEqual([g["char"] for g in duplicates], ["的"])
        kept, info = apply_add(project, "b", glyphs, "", "t2")
        self.assertEqual([m["run"] for m in kept["members"]], ["a", "b"])
        self.assertEqual(info["skipped"], 1)
        swapped, info = apply_add(project, "b", glyphs, "的", "t2")
        self.assertEqual(swapped["members"][0]["run"], "b")
        self.assertEqual(info["replaced"], 1)


class TemplateLayoutTest(unittest.TestCase):
    def test_cells_keep_repeats_and_grid_is_centered(self):
        from handfont.common import parse_cells
        from handfont.template import grid_geometry, plan_template
        self.assertEqual(parse_cells("的的A"), ["的", "的", "A"])
        geo = grid_geometry(16, "portrait")
        width, _ = geo["page_mm"]
        left = min(s[0] for s in geo["slots_mm"])
        right = max(s[0] + s[2] for s in geo["slots_mm"])
        self.assertAlmostEqual(left, width - right, delta=1.5)
        geo = grid_geometry(16, "landscape")
        self.assertEqual(geo["page_mm"], [297.0, 210.0])
        empty = plan_template([], 16, "portrait")
        self.assertEqual(empty[0]["cells"], [])
        self.assertGreater(empty[0]["grid"]["capacity"], 0)


if __name__ == "__main__":
    unittest.main()
