"""Local visual candidates from reviewed handwriting; suggestions never confirm identity."""
import cv2
import numpy as np
from PIL import Image

from .common import read_json, write_json
from .project import sample_library, load_live
from .storage import data_dir


def descriptor(path):
    with Image.open(path) as image:
        gray = np.asarray(image.convert('L'))
    ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    points = cv2.findNonZero(ink)
    if points is None:
        return None
    x, y, w, h = cv2.boundingRect(points)
    scale = 40 / max(w, h)
    resized = cv2.resize(ink[y:y+h, x:x+w], (max(1, round(w*scale)), max(1, round(h*scale))), interpolation=cv2.INTER_AREA)
    tile = np.zeros((48, 48), np.float32)
    top, left = (48-resized.shape[0])//2, (48-resized.shape[1])//2
    tile[top:top+resized.shape[0], left:left+resized.shape[1]] = resized / 255
    vector = cv2.GaussianBlur(tile, (5, 5), 0).ravel()
    return vector / max(float(np.linalg.norm(vector)), 1e-6)


def suggest_run(work, name):
    folder = data_dir(work, 'runs') / name
    record = folder / 'run.json'
    run = read_json(record)
    hidden = set(load_live(work).get('archived_sample', []))
    references = []
    for sample in sample_library(work):
        if not sample['usable'] or sample['id'] in hidden:
            continue
        path = data_dir(work, 'glyphs') / sample['id'] / 'gray.png'
        try:
            vector = descriptor(path)
        except (OSError, ValueError):
            continue
        if vector is not None:
            references.append((sample['char'], vector))
    for glyph in run['glyphs']:
        glyph['candidates'] = []
        if not glyph.get('commands') or not references:
            continue
        vector = descriptor(folder / glyph['gray'])
        if vector is None:
            continue
        scores = {}
        for char, reference in references:
            scores[char] = max(scores.get(char, 0), float(vector @ reference))
        glyph['candidates'] = [{'char': char, 'similarity': round(score, 3)}
                               for char, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:3]]
    write_json(record, run)
