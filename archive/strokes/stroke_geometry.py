"""Raster candidates guided by character medians and local ink geometry."""
import base64
import gzip
import json
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import replayRecording
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from .trace import bounds

SIZE = 256


class RasterPen(BasePen):
    def __init__(self):
        super().__init__(None)
        self.contours = []
        self.points = []

    def _moveTo(self, pt):
        self.points = [pt]

    def _lineTo(self, pt):
        self.points.append(pt)

    def _curveToOne(self, p1, p2, p3):
        p0 = self._getCurrentPoint()
        for t in np.linspace(0, 1, 17)[1:]:
            self.points.append(tuple((1-t)**3*p0[i] + 3*(1-t)**2*t*p1[i] + 3*(1-t)*t*t*p2[i] + t**3*p3[i] for i in (0, 1)))

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        for t in np.linspace(0, 1, 13)[1:]:
            self.points.append(tuple((1-t)**2*p0[i]+2*(1-t)*t*p1[i]+t*t*p2[i] for i in (0, 1)))

    def _closePath(self):
        if len(self.points) >= 3:
            self.contours.append(np.round(self.points).astype(np.int32))
        self.points = []

    _endPath = _closePath

    def mask(self):
        winding = np.zeros((SIZE, SIZE), np.int16)
        for contour in self.contours:
            part = np.zeros((SIZE, SIZE), np.uint8)
            cv2.fillPoly(part, [contour], 1)
            winding += part.astype(np.int16) * (1 if cv2.contourArea(contour, oriented=True) >= 0 else -1)
        return (winding != 0).astype(np.uint8)


def source_raster(row):
    box = bounds(row['commands'])
    if box is None:
        raise ValueError('该字形没有可拆分的轮廓。')
    side = max(row['width'], 1000, box[2]-box[0]+80, box[3]-box[1]+80)
    cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
    left, top = cx-side/2, cy+side/2
    pen = RasterPen()
    replayRecording(row['commands'], TransformPen(pen, (SIZE/side, 0, 0, -SIZE/side, -left*SIZE/side, top*SIZE/side)))
    return pen.mask(), [left, top, side]


@lru_cache(maxsize=1)
def references():
    with gzip.open(Path(__file__).parent / 'stroke_data/references.json.gz', 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def skeletonize(mask):
    # Zhang-Suen thinning; no model prediction is implied by this geometric step.
    img = np.pad(mask.astype(np.uint8), 1)
    for _ in range(SIZE):
        changed = False
        for step in (0, 1):
            p = [img[:-2,1:-1], img[:-2,2:], img[1:-1,2:], img[2:,2:], img[2:,1:-1], img[2:,:-2], img[1:-1,:-2], img[:-2,:-2]]
            neighbors = sum(p)
            transitions = sum(((p[i] == 0) & (p[(i+1)%8] == 1)).astype(np.uint8) for i in range(8))
            a,b = ((p[0]*p[2]*p[4], p[2]*p[4]*p[6]) if step == 0 else (p[0]*p[2]*p[6], p[0]*p[4]*p[6]))
            remove = (img[1:-1,1:-1] == 1) & (neighbors >= 2) & (neighbors <= 6) & (transitions == 1) & (a == 0) & (b == 0)
            if remove.any():
                img[1:-1,1:-1][remove] = 0
                changed = True
        if not changed:
            break
    return img[1:-1,1:-1]


def mask_url(mask, color=(0, 0, 0)):
    rgba = np.zeros((*mask.shape, 4), np.uint8)
    rgba[:,:,:3] = color[::-1]
    rgba[:,:,3] = mask.astype(np.uint8)*255
    ok, encoded = cv2.imencode('.png', rgba)
    if not ok:
        raise ValueError('无法生成笔画预览。')
    return 'data:image/png;base64,' + base64.b64encode(encoded).decode()


def encode_mask(mask):
    return base64.b64encode(cv2.imencode('.png', mask.astype(np.uint8)*255)[1]).decode()


def decode_mask(value):
    mask = cv2.imdecode(np.frombuffer(base64.b64decode(value), np.uint8), cv2.IMREAD_GRAYSCALE)
    if mask is None or mask.shape != (SIZE, SIZE):
        raise ValueError('笔画数据损坏。')
    return (mask > 127).astype(np.uint8)


def reference_candidates(ink, reference):
    ys, xs = np.nonzero(ink)
    pen = RasterPen()
    for path in reference['strokes']:
        parse_path(path, TransformPen(pen, (.25, 0, 0, -.25, 0, 225)))
    ref = pen.mask()
    ry, rx = np.nonzero(ref)
    sx, sy = (xs.max()-xs.min())/max(1,rx.max()-rx.min()), (ys.max()-ys.min())/max(1,ry.max()-ry.min())
    tx, ty = xs.min()-rx.min()*sx, ys.min()-ry.min()*sy
    affine = np.array([[sx,0,tx],[0,sy,ty]], np.float32)
    aligned = cv2.warpAffine(ref, affine, (SIZE,SIZE))
    # Smooth nonrigid registration provides local displacement, bounded to avoid runaway matches.
    flow = cv2.calcOpticalFlowFarneback(cv2.GaussianBlur(aligned*255,(9,9),0), cv2.GaussianBlur(ink*255,(9,9),0), None, .5, 3, 25, 4, 7, 1.5, 0)
    flow = np.clip(flow, -16, 16)
    skeleton = skeletonize(ink)
    py, px = np.nonzero(skeleton)
    skpoints = np.stack([px,py],axis=1)
    maps, support = [], []
    for median in reference['medians']:
        points = np.array([[x/4*sx+tx, (900-y)/4*sy+ty] for x,y in median],np.float32)
        path = []
        for start,end in zip(points[:-1],points[1:]):
            for t in np.linspace(0,1,max(2,int(np.linalg.norm(end-start)/3))):
                point = start*(1-t)+end*t
                x,y = np.clip(np.round(point),0,SIZE-1).astype(int)
                point += flow[y,x]
                distances = np.sum((skpoints-point)**2,axis=1)
                nearest = int(np.argmin(distances))
                if distances[nearest] < 12**2:
                    point = .4*point + .6*skpoints[nearest]
                path.append(point)
        if not path:
            path = points.tolist()
        line = np.zeros_like(ink)
        cv2.polylines(line,[np.round(path).astype(np.int32)],False,1,1)
        dist = cv2.distanceTransform(1-line,cv2.DIST_L2,5)
        maps.append(dist)
        support.append(float(np.mean(cv2.distanceTransform(1-ink,cv2.DIST_L2,5)[line>0] < 6)))
    distances = np.stack(maps)
    best = distances.min(axis=0)
    # Overlap is intentional at intersections; never force ink into disjoint strokes.
    candidates = [(ink & ((d <= best+1.5) & (d <= 24))).astype(np.uint8) for d in distances]
    return candidates, support, skeleton


def geometry_candidates(ink):
    skeleton = skeletonize(ink)
    count, labels = cv2.connectedComponents(ink)
    return [np.uint8(labels == i) for i in range(1,count)], skeleton


def component_names(reference):
    expression = iter(reference.get('decomposition',''))
    def parse():
        char = next(expression, '?')
        count = 3 if char in '⿲⿳' else 2 if char in '⿰⿱⿴⿵⿶⿷⿸⿹⿺⿻' else 0
        return (char,[parse() for _ in range(count)])
    tree = parse()
    names = []
    for path in reference.get('matches',[]):
        node = tree
        try:
            for index in path or []:
                node = node[1][index]
            names.append(node[0] if not node[1] and path is not None else '')
        except (IndexError, TypeError):
            names.append('')
    return names


def contour_commands(mask, frame, transform=None):
    left, top, side = frame
    transform = transform or {'x':0,'y':0,'scale':1}
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    commands = []
    for contour in contours:
        if len(contour) < 3:
            continue
        points = contour[:,0,:].astype(float)
        points = (points-SIZE/2)*transform['scale']+SIZE/2+[transform['x'],transform['y']]
        points = [[left+x*side/SIZE,top-y*side/SIZE] for x,y in points]
        commands.append(('moveTo',[points[0]]))
        commands.extend(('lineTo',[point]) for point in points[1:])
        commands.append(('closePath',[]))
    return commands
