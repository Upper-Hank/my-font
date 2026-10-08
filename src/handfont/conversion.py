"""Source presets and editable regions share one local outline conversion."""
import math
import shutil

import cv2
import numpy as np
from PIL import Image, ImageOps

from .common import TOP, UPM, OutputDirectory, digest, file_hash, glyph_name, parse_one_cell, write_json
from .trace import trace_bitmap, write_preview_svg


def free_photo(image):
    image = ImageOps.grayscale(image)
    image.thumbnail((4096, 4096))
    gray = np.asarray(image)
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=max(3, min(gray.shape) / 60))
    return cv2.divide(gray, np.maximum(background, 1), scale=255)


def template_regions(manifest, offsets, dpi):
    ppm = dpi / 25.4
    regions = []
    for cell in manifest['cells']:
        x, y, w, h = cell['writing_mm']
        dx, dy = offsets.get(cell['id'], (0, 0))
        x, y = (x + dx) * ppm, (y + dy) * ppm
        regions.append({'id': f"cell-{cell['id']}", 'char': cell['char'],
                        'rect': [x - ppm, y - ppm, (w + 2) * ppm, (h + 2) * ppm],
                        'frame': [x, y, manifest['cell_mm'] * ppm], 'preset': True})
    return regions


def checked_regions(pages, edits):
    if not isinstance(edits, list) or len(edits) != len(pages):
        raise ValueError('请检查所有照片的取字区域。')
    total = 0
    result = []
    for page, edit in zip(pages, edits):
        if not isinstance(edit, dict) or edit.get('page_id') != page['page_id']:
            raise ValueError('照片编号不匹配。')
        regions = edit.get('regions')
        if not isinstance(regions, list):
            raise ValueError('取字区域无效。')
        total += len(regions)
        if total > 1000:
            raise ValueError('一次最多提取 1000 个字形。')
        presets = {r['id']: r for r in page.get('presets', page.get('regions', [])) if r.get('preset')}
        checked, seen = [], set()
        for region in regions:
            if not isinstance(region, dict):
                raise ValueError('取字区域无效。')
            identifier, rect = region.get('id'), region.get('rect')
            if not isinstance(identifier, str) or not identifier or len(identifier) > 64 or identifier in seen:
                raise ValueError('取字区域编号无效或重复。')
            seen.add(identifier)
            if not isinstance(rect, list) or len(rect) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in rect):
                raise ValueError('取字区域坐标无效。')
            x, y, w, h = rect
            if x < 0 or y < 0 or w < 2 or h < 2 or x + w > page['width'] + .01 or y + h > page['height'] + .01:
                raise ValueError('取字区域必须位于照片内，宽高至少为 2 像素。')
            char = region.get('char', '')
            if not isinstance(char, str):
                raise ValueError('对应字符无效。')
            char = parse_one_cell(char) if char.strip() else ''
            # Frame scale comes only from the saved source preset, never the client.
            preset = presets.get(identifier)
            metadata = {}
            if preset:
                px, py, pw, ph = preset['rect']
                fx, fy, side = preset['frame']
                metadata = {'preset': True, 'frame': [fx + ((x + w / 2) - (px + pw / 2)),
                                                       fy + ((y + h / 2) - (py + ph / 2)), side]}
            checked.append({'id': identifier, 'rect': rect, 'char': char, **metadata})
        result.append({**page, 'regions': checked})
    return result


def process_regions(staging, preview, output):
    if not shutil.which('potrace'):
        raise ValueError('缺少 potrace。macOS 请运行 brew install potrace。')
    threshold = int(preview['threshold']) if preview.get('threshold') else None
    if threshold is not None and not 1 <= threshold <= 254:
        raise ValueError('墨迹阈值必须在 1–254 之间。')
    if not any(page.get('regions') for page in preview['pages']):
        raise ValueError('请先在照片上框选需要提取的字。')
    rows, pages = [], []
    provenance = {'pipeline': 'regions-v1', 'pages': preview['pages'], 'threshold': threshold, 'sources': []}
    with OutputDirectory(output) as folder:
        (folder / 'raw').mkdir()
        for page_index, page in enumerate(preview['pages'], 1):
            with Image.open(staging / page['scan']) as image:
                gray_page = np.asarray(image.convert('L'))
            source_hash = file_hash(staging / page['original'])
            provenance['sources'].append(source_hash)
            raw_name = f"{page_index:02d}{(staging / page['original']).suffix}"
            shutil.copyfile(staging / page['original'], folder / 'raw' / raw_name)
            used_threshold = threshold if threshold is not None else int(cv2.threshold(gray_page, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0])
            pages.append({'page_id': page['page_id'], 'source_hash': source_hash, 'source_name': page['source_name'], 'source_kind': page['source_kind'], 'threshold': used_threshold})
            for index, region in enumerate(page['regions'], 1):
                sample = f'page-{page_index:02d}-region-{index:04d}'
                dest = folder / sample
                dest.mkdir()
                x, y, w, h = region['rect']
                left, top, right, bottom = [round(v) for v in (x, y, x + w, y + h)]
                gray = gray_page[top:bottom, left:right]
                binary = np.where(gray <= used_threshold, 0, 255).astype('uint8')
                Image.fromarray(gray).save(dest / 'gray.png')
                Image.fromarray(binary).save(dest / 'binary.png')
                Image.fromarray(binary).convert('1').save(dest / 'trace.pbm')
                ink = int(np.count_nonzero(binary == 0))
                edge = any(np.any(side == 0) for side in (binary[0], binary[-1], binary[:, 0], binary[:, -1]))
                if region.get('frame'):
                    fx, fy, side = region['frame']
                    scale = UPM / side
                    ox, oy = (left - fx) * scale, TOP - (bottom - fy) * scale
                else:
                    scale = UPM / max(right - left, bottom - top)
                    ox = (UPM - (right - left) * scale) / 2
                    oy = TOP - (UPM + (bottom - top) * scale) / 2
                transform = [scale, 0, 0, scale, ox, oy]
                commands = trace_bitmap(dest / 'trace.pbm', dest / 'potrace.svg', (right - left, bottom - top), transform) if ink else []
                if commands:
                    write_preview_svg(dest / 'outline.svg', commands, (0, TOP - UPM, UPM, UPM))
                char = region['char']
                rows.append({'sample_id': sample, 'char': char, 'unicode': f'{ord(char):04X}' if char else '',
                             'glyph_name': glyph_name(char) if char else '', 'page_id': page['page_id'], 'cell_id': index,
                             'matching_required': True, 'status': 'blank' if not ink else 'edge' if edge else 'review',
                             'width': UPM, 'ink_pixels': ink, 'commands': commands, 'gray': f'{sample}/gray.png',
                             'image_transform': transform, 'source_hash': source_hash, 'source_kind': page['source_kind'],
                             'source_name': page['source_name'], 'source_rect': region['rect'], 'spacing_shift': 0})
        write_json(folder / 'run.json', {'schema': 1, 'run_id': digest(provenance)[:16], 'cell_mm': 16,
                                        'provenance': provenance, 'pages': pages, 'glyphs': rows, 'review_pending': True})
