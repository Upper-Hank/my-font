"""Non-destructive outline placement in the font's em square."""
import math
import unicodedata
from functools import lru_cache
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen, replayRecording
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.svgPathPen import SVGPathPen
from .common import TOP, UPM
from .trace import bounds, shift

DEFAULT_ADJUSTMENT = {'normalize': False, 'center_x': False, 'center_y': False,
                      'target': 800, 'scale': 1.0, 'reference': False, 'offset_x': 0, 'offset_y': 0}


def adjustment_options(value=None):
    if value is None:
        return dict(DEFAULT_ADJUSTMENT)
    if not isinstance(value, dict):
        raise ValueError('字形修正参数无效。')
    result = {**DEFAULT_ADJUSTMENT, **{key: value[key] for key in DEFAULT_ADJUSTMENT if key in value}}
    for key in ('normalize', 'center_x', 'center_y', 'reference'):
        if not isinstance(result[key], bool):
            raise ValueError('字形修正开关无效。')
    for key, low, high in (('target', 400, 950), ('scale', 0.25, 4), ('offset_x', -1000, 1000), ('offset_y', -1000, 1000)):
        number = result[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError('目标大小应为 400–950，缩放应为 0.25–4 倍，位移应为 -1000–1000。')
    return result


@lru_cache(maxsize=1)
def reference_boxes():
    """Bundled reference metrics in project font units; no source outline replacement."""
    with TTFont(Path(__file__).parent / 'fonts/IBMPlexSansSC-Regular.otf') as font:
        glyphs = font.getGlyphSet()
        ratio = UPM / font['head'].unitsPerEm
        result = {}
        for code, name in font.getBestCmap().items():
            pen = BoundsPen(glyphs)
            glyphs[name].draw(pen)
            if pen.bounds:
                result[code] = tuple(v * ratio for v in pen.bounds)
        return result


def adjust_glyph(row, options=None):
    opts = adjustment_options(options)
    if not opts['normalize'] and not opts['center_x'] and not opts['center_y'] and opts['scale'] == 1 and not opts['reference'] and not opts['offset_x'] and not opts['offset_y']:
        return dict(row)
    box = bounds(row['commands'])
    if not box:
        return dict(row)
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    scale = opts['scale']
    name = unicodedata.name(row.get('char', ''), '') if len(row.get('char', '')) == 1 else ''
    # Punctuation and Latin have intentional size relationships; do not auto-fill them.
    han = name.startswith(('CJK UNIFIED IDEOGRAPH', 'CJK COMPATIBILITY IDEOGRAPH'))
    ref = reference_boxes().get(ord(row['char'])) if opts['reference'] and han else None
    if ref:
        extent = max(x1 - x0, y1 - y0)
        if extent > 0:
            scale *= max(ref[2] - ref[0], ref[3] - ref[1]) / extent
    elif opts['normalize'] and not opts['reference'] and name.startswith(('CJK UNIFIED IDEOGRAPH', 'CJK COMPATIBILITY IDEOGRAPH')):
        extent = max(x1 - x0, y1 - y0)
        if extent > 0:
            scale *= opts['target'] / extent
    dx = (row['width'] / 2 if opts['center_x'] else cx) - cx * scale + opts['offset_x']
    dy = (TOP - UPM / 2 if opts['center_y'] else cy) - cy * scale + opts['offset_y']
    if scale == 1 and dx == 0 and dy == 0:
        return dict(row)
    pen = RecordingPen()
    replayRecording(row['commands'], TransformPen(pen, (scale, 0, 0, scale, dx, dy)))
    result = {**row, 'commands': pen.value}
    if 'image_transform' in row:
        a, b, c, d, e, f = row['image_transform']
        result['image_transform'] = [a*scale, b*scale, c*scale, d*scale, e*scale+dx, f*scale+dy]
    return result


def character_placement(row, char):
    """Recompute spacing from the final identity, including changed template labels."""
    result = {**row, 'char': char, 'width': UPM}
    previous = row.get('spacing_shift', 0)
    result['commands'] = shift(row['commands'], -previous) if previous else row['commands']
    dx = 0
    box = bounds(result['commands']) if len(char) == 1 and ord(char) < 128 else None
    if box:
        dx = 60 - box[0]
        result['commands'] = shift(result['commands'], dx)
        result['width'] = round(box[2] - box[0] + 120)
    result['spacing_shift'] = dx
    if 'image_transform' in row:
        result['image_transform'] = list(row['image_transform'])
        result['image_transform'][4] += dx - previous
    return result


def preview_svg(row):
    pen = SVGPathPen(None)
    replayRecording(row['commands'], TransformPen(pen, (1, 0, 0, -1, 0, 0)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {-TOP} {UPM} {UPM}">'
            f'<path fill="black" d="{pen.getCommands()}"/></svg>')
