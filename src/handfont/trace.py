import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen, replayRecording
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path


def trace_bitmap(bitmap, output, image_size, transform):
    """Read only the documented, fixed Potrace SVG layout we request here.

    Raw Potrace paths use a bottom-left origin and ten units per pixel.
    Converting those directly avoids SVG importer auto-fit/viewBox behavior.
    """
    executable = shutil.which("potrace")
    if not executable:
        raise ValueError("缺少 potrace。macOS 请运行 brew install potrace。")
    subprocess.run([executable, str(bitmap), "--svg", "--flat", "--unit", "10",
                    "--resolution", "72", "--turdsize", "0", "--opttolerance", "0.2",
                    "--output", str(output)], check=True, capture_output=True, timeout=60)
    root = ET.parse(output).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    width, height = image_size
    if [float(n) for n in root.attrib["viewBox"].split()] != [0, 0, width, height]:
        raise ValueError("Potrace 输出画布与原图不一致，停止导入。")
    groups = root.findall(f"{ns}g")
    if len(groups) != 1:
        raise ValueError("不支持此 Potrace SVG 结构。")
    group = groups[0]
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", group.attrib.get("transform", ""))]
    if numbers != [0, height, 0.1, -0.1] or group.findall(f"{ns}g"):
        raise ValueError("Potrace 坐标约定发生变化，停止导入。")
    pen = RecordingPen()
    # Input transform maps bottom-left bitmap pixels into font coordinates.
    a, b, c, d, e, f = transform
    mapped = TransformPen(pen, (a / 10, b / 10, c / 10, d / 10, e, f))
    for path in group.findall(f"{ns}path"):
        if "transform" in path.attrib:
            raise ValueError("Potrace path 出现未预期的独立变换。")
        parse_path(path.attrib["d"], mapped)
    return pen.value


def bounds(commands):
    pen = BoundsPen(None)
    replayRecording(commands, pen)
    return pen.bounds


def shift(commands, dx):
    pen = RecordingPen()
    replayRecording(commands, TransformPen(pen, (1, 0, 0, 1, dx, 0)))
    return pen.value


def write_preview_svg(path, commands, box):
    x, y, width, height = box
    pen = SVGPathPen(None)
    replayRecording(commands, TransformPen(pen, (1, 0, 0, -1, 0, 0)))
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {-y-height} {width} {height}">'
                    f'<path fill="black" d="{pen.getCommands()}"/></svg>\n', encoding="utf-8")
