"""Generate clearly synthetic strokes to exercise the pipeline without handwriting.

Usage: .venv/bin/python scripts/make_demo.py work/demo
This is a development fixture, never the user's handwriting.
"""
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

from handfont.common import read_json
from handfont.template import make_template, TEMPLATE_DPI


def create_demo(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    charset = output / "charset.txt"
    charset.write_text("一口中A。下", encoding="utf-8")
    make_template(charset, output / "template")
    manifest_path = next(p for p in (output / "template").glob("*.json") if p.name != "index.json")
    manifest = read_json(manifest_path)
    image = Image.open(manifest_path.with_suffix(".png")).convert("L")
    draw = ImageDraw.Draw(image)
    ppm = TEMPLATE_DPI / 25.4
    for cell in manifest["cells"]:
        x, y, w, h = cell["writing_mm"]
        def xy(a, b):
            return (round((x+a*w)*ppm), round((y+b*h)*ppm))
        def line(points):
            draw.line([xy(*point) for point in points], fill=0, width=5)
        if cell["char"] == "一":
            line([(0.15, 0.45), (0.85, 0.45)])
        elif cell["char"] == "口":
            line([(0.25, 0.2), (0.25, 0.65), (0.65, 0.65), (0.65, 0.2), (0.25, 0.2)])
        elif cell["char"] == "中":
            line([(0.2, 0.35), (0.8, 0.35), (0.8, 0.6), (0.2, 0.6), (0.2, 0.35)])
            line([(0.5, 0.1), (0.5, 0.85)])
        elif cell["char"] == "A":
            line([(0.2, 0.88), (0.5, 0.18), (0.8, 0.88)])
            line([(0.32, 0.6), (0.68, 0.6)])
        elif cell["char"] == "下":
            # Deliberately crosses the crop edge; must not enter the preview font.
            line([(-0.15, 0.45), (0.85, 0.45)])
        # 。 intentionally blank: also exercises blank rejection.
    image.save(output / "synthetic-flat.png")
    width, height = image.size
    source = np.float32([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]])
    destination = np.float32([[25, 12], [width-32, 30], [width-10, height-25], [15, height-12]])
    transform = cv2.getPerspectiveTransform(source, destination)
    warped = cv2.warpPerspective(np.asarray(image), transform, image.size, borderValue=255)
    Image.fromarray(warped).save(output / "synthetic-scan.png")
    return output


if __name__ == "__main__":
    print(create_demo(sys.argv[1]))
