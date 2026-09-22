"""Two focused pipeline checks: crossing ink, edits, persistence, and real font output."""
import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from fontTools.ttLib import TTFont
from handfont.common import write_json, read_json
from handfont.project import select_sample, load_live, sample_library, export_selection, cleanup_history
from handfont.storage import data_dir
from handfont import strokes
from handfont.stroke_geometry import decode_mask, source_raster


def fixture(work, char='十'):
    folder=data_dir(work,'runs')/'batch'
    (folder/'one').mkdir(parents=True)
    Image.new('L',(256,256),255).save(folder/'one/gray.png')
    Image.new('L',(256,256),255).save(folder/'one/binary.png')
    # Union outline of a crossing, not disjoint rectangles.
    points=[(100,340),(450,340),(450,50),(550,50),(550,340),(900,340),
            (900,440),(550,440),(550,780),(450,780),(450,440),(100,440)]
    commands=[['moveTo',[points[0]]]]+[['lineTo',[p]] for p in points[1:]]+[['closePath',[]]]
    row={'char':char,'unicode':f'{ord(char):04X}','glyph_name':f'uni{ord(char):04X}','sample_id':'one',
         'page_id':'p','cell_id':1,'status':'review','width':1000,'commands':commands,
         'gray':'one/gray.png','image_transform':[1,0,0,1,0,0]}
    write_json(folder/'run.json',{'run_id':'batch','cell_mm':16,'glyphs':[row]})
    sample_library(work)
    return row


class StrokeTest(unittest.TestCase):
    def test_crossing_coverage_edit_undo_and_non_destructive_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp); row=fixture(work); identifier='batch/one'
            select_sample(work,identifier)
            original=copy.deepcopy(load_live(work)['members'])
            generated=strokes.generate(work,identifier,0)
            self.assertEqual(generated['method'],'structure+geometry')
            self.assertEqual(generated['expected_count'],2)
            self.assertEqual(generated['unassigned_pixels'],0)
            self.assertGreaterEqual(len(generated['strokes']),2)
            path=data_dir(work,'glyphs')/'batch/one/strokes.json'
            doc=read_json(path)
            ink,_=source_raster(row)
            masks=[decode_mask(s['mask']) for s in doc['strokes']]
            self.assertTrue(np.array_equal(np.maximum.reduce(masks),ink))
            self.assertGreater(int(np.count_nonzero(sum(masks)>1)),0)
            ids=[s['id'] for s in generated['strokes']]
            merged=strokes.edit(work,identifier,generated['revision'],'merge',{'ids':ids})
            self.assertEqual(len(merged['strokes']),1)
            restored=strokes.edit(work,identifier,merged['revision'],'undo',{})
            self.assertEqual(len(restored['strokes']),len(ids))
            confirmed=strokes.edit(work,identifier,restored['revision'],'update',{'ids':ids,'patch':{'review':False}})
            result=strokes.publish(work,identifier,confirmed['revision'])
            self.assertEqual(strokes.publish(work,identifier,confirmed['revision']),result)
            self.assertEqual(load_live(work)['members'],original)
            self.assertEqual(read_json(data_dir(work,'glyphs')/'batch/run.json')['glyphs'][0]['commands'],read_json(data_dir(work,'runs')/'batch/run.json')['glyphs'][0]['commands'])
            cleanup_history(work,'run','batch')
            self.assertEqual(strokes.get_strokes(work,identifier)['revision'],confirmed['revision'])
            select_sample(work,result['sample'])
            build=export_selection(work)
            with TTFont(data_dir(work,'builds')/build/'Preview.otf') as font:
                self.assertIn(ord('十'),font.getBestCmap())
            with self.assertRaises(ValueError):
                strokes.edit(work,identifier,0,'undo',{})

    def test_manual_split_paint_and_unknown_character_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);fixture(work,'A'); identifier='batch/one'
            generated=strokes.generate(work,identifier,0)
            self.assertFalse(generated['has_reference'])
            self.assertEqual(generated['strokes'][0]['origin'],'connected-ink')
            first=generated['strokes'][0]['id']
            split=strokes.edit(work,identifier,generated['revision'],'split',{'ids':[first],'points':[[128,0],[128,256]]})
            self.assertEqual(len(split['strokes']),2)
            paint=strokes.edit(work,identifier,split['revision'],'paint',{'ids':[split['strokes'][0]['id']],'points':[[120,120],[140,140]],'brush':5})
            self.assertEqual(paint['revision'],split['revision']+1)
            loaded=strokes.get_strokes(work,identifier)
            self.assertEqual(loaded['revision'],paint['revision'])
            with self.assertRaises(ValueError):
                strokes.edit(work,identifier,paint['revision'],'update',{'ids':[paint['strokes'][0]['id']], 'patch':{'transform':{'x':128,'y':0,'scale':3}}})
            self.assertEqual(strokes.get_strokes(work,identifier)['revision'],paint['revision'])
            with self.assertRaises(ValueError):
                strokes.publish(work,identifier,paint['revision'])
