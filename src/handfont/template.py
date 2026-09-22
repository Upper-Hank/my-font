import math

import cv2
import numpy as np
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from .common import PRODUCT_ZH, SCHEMA, UPM, TOP, OutputDirectory, digest, label_font, parse_cells, read_charset, read_json, write_json
from .storage import data_dir

SYSTEM_PAPER_ID = "paper"
SYSTEM_PAPER_TITLE = "通用书写纸"

TEMPLATE_DPI = 300
MARKER_MM = 12
FRAME_MM = 2
GAP_X_MM = 6
GAP_Y_MM = 12
LABEL_MM = 8
LAYOUT_VERSION = 3
PORTRAIT_MM = (210.0, 297.0)
LANDSCAPE_MM = (297.0, 210.0)


def page_spec(orientation="portrait", paper_format="A4"):
    sizes = {"A5": (148.0, 210.0), "A4": PORTRAIT_MM, "A3": (297.0, 420.0)}
    if paper_format not in sizes:
        raise ValueError("纸张大小支持 A5、A4、A3。")
    width, height = sizes[paper_format]
    if orientation == "landscape":
        width, height = height, width
    markers = [(0, 9, 9), (1, width - 21, 9), (2, width - 21, height - 21), (3, 9, height - 21)]
    qr = (width - 53, 9)
    return width, height, markers, qr


def markers_for(page_mm):
    width, height = page_mm
    return [(0, 9, 9), (1, width - 21, 9), (2, width - 21, height - 21), (3, 9, height - 21)]


MARKERS = markers_for(PORTRAIT_MM)


def grid_geometry(cell_mm=16, orientation="portrait", paper_format="A4"):
    if orientation not in ("portrait", "landscape"):
        raise ValueError("纸张方向只能是纵向或横向。")
    if not math.isfinite(cell_mm) or not 10 <= cell_mm <= 20:
        raise ValueError("书写框大小支持 10–20 mm。")
    width, height, markers, qr = page_spec(orientation, paper_format)
    left, top, right, bottom = 24, 42, width - 24, height - 18
    usable_w, usable_h = right - left, bottom - top
    pitch_x, pitch_y = cell_mm + GAP_X_MM, cell_mm + GAP_Y_MM
    columns = max(1, math.floor((usable_w + GAP_X_MM) / pitch_x))
    rows = max(1, math.floor((usable_h + GAP_Y_MM - LABEL_MM) / pitch_y))
    capacity = columns * rows
    grid_w = columns * cell_mm + (columns - 1) * GAP_X_MM
    grid_h = rows * cell_mm + (rows - 1) * GAP_Y_MM + LABEL_MM
    origin_x = left + (usable_w - grid_w) / 2
    origin_y = top + (usable_h - grid_h) / 2
    slots = []
    for i in range(capacity):
        x = origin_x + (i % columns) * pitch_x
        y = origin_y + (i // columns) * pitch_y
        slots.append([x, y, float(cell_mm), float(cell_mm)])
    return {
        "page_mm": [width, height], "paper_format": paper_format, "orientation": orientation, "cell_mm": float(cell_mm),
        "frame_mm": FRAME_MM, "columns": columns, "rows": rows, "capacity": capacity,
        "qr_mm": list(qr), "slots_mm": slots,
        "markers": [{"id": mid, "box_mm": [x, y, MARKER_MM, MARKER_MM]} for mid, x, y in markers],
    }


def plan_template(chars, cell_mm=16, orientation="portrait", paper_format="A4"):
    if len(chars) > 1000:
        raise ValueError("一次最多生成 1000 格，建议分批书写。")
    geo = grid_geometry(cell_mm, orientation, paper_format)
    width, height = geo["page_mm"]
    capacity = geo["capacity"]
    template_id = digest({"schema": SCHEMA, "layout": LAYOUT_VERSION, "chars": list(chars),
                          "cell_mm": float(cell_mm), "orientation": orientation, "paper_format": paper_format})[:12]
    starts = list(range(0, max(len(chars), 1), capacity))
    pages = []
    for index, start in enumerate(starts, 1):
        cells = []
        for i, char in enumerate(chars[start:start + capacity]):
            x, y, w, h = geo["slots_mm"][i]
            cells.append({"id": i + 1, "char": char, "unicode": f"{ord(char):04X}",
                          "writing_mm": [x, y, w, h],
                          "crop_mm": [x - 1.5, y - 1.5, w + 3, h + 3]})
        manifest = {"schema": SCHEMA, "layout_version": LAYOUT_VERSION, "frame_mm": FRAME_MM,
                    "template_id": template_id, "page_id": f"{template_id}-{index:03d}",
                    "page_mm": [width, height], "paper_format": paper_format, "orientation": orientation, "cell_mm": float(cell_mm),
                    "upm": UPM, "top": TOP, "qr_mm": geo["qr_mm"],
                    "markers": geo["markers"], "grid": {"columns": geo["columns"], "rows": geo["rows"],
                                                       "capacity": capacity},
                    "cells": cells}
        manifest["qr"] = f"HF1:{manifest['page_id']}:{digest(manifest)[:16]}"
        manifest["hash"] = digest(manifest)
        pages.append(manifest)
    return pages


def render_page(manifest, page_number, page_count, label_font_path=None, dpi=TEMPLATE_DPI):
    """One renderer for live previews and printed templates; no approximate GUI layout."""
    scale = dpi / 25.4
    width, height = manifest.get("page_mm") or PORTRAIT_MM
    cell_mm = manifest["cell_mm"]
    markers = [(m["id"], m["box_mm"][0], m["box_mm"][1]) for m in manifest["markers"]]
    qr_x, qr_y = manifest.get("qr_mm") or (width - 53, 9)
    font = label_font(round(3.4 * scale), label_font_path)
    small = label_font(round(2.0 * scale), label_font_path)
    header = label_font(round(2.6 * scale), label_font_path)
    line = max(1, round(0.25 * scale))
    page = Image.new("L", (round(width * scale), round(height * scale)), 255)
    draw = ImageDraw.Draw(page)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    for mid, x, y in markers:
        marker = cv2.aruco.generateImageMarker(dictionary, mid, round(MARKER_MM * scale))
        page.paste(Image.fromarray(marker), (round(x * scale), round(y * scale)))
    qr = np.pad(cv2.QRCodeEncoder_create().encode(manifest["qr"]), 4, constant_values=255)
    module = max(1, round(25 * scale / qr.shape[0]))
    qr_image = Image.fromarray(qr).resize((qr.shape[0] * module,) * 2, Image.Resampling.NEAREST)
    page.paste(qr_image, (round(qr_x * scale), round(qr_y * scale)))
    draw.text((28 * scale, 10 * scale), PRODUCT_ZH, font=header, fill=0)
    draw.text((28 * scale, 16 * scale), f"Page {page_number} / {page_count}   {cell_mm:g} mm", font=small, fill=0)
    draw.text((28 * scale, 22 * scale), "正常速度写；不用填满；写错留着，之后补写。", font=small, fill=0)
    draw.text((28 * scale, 28 * scale), "100% 打印 · 拍全四角与二维码 · 纸张铺平", font=small, fill=0)
    for cell in manifest["cells"]:
        x, y, w, h = cell["writing_mm"]
        cx = (x + w / 2) * scale
        draw.rectangle([(x - FRAME_MM) * scale, (y - FRAME_MM) * scale,
                        (x + w + FRAME_MM) * scale, (y + h + FRAME_MM) * scale], outline=40, width=line)
        label_top = y + h + FRAME_MM + 0.55
        draw.text((cx, label_top * scale), cell["char"], font=font, fill=0, anchor="mt")
        draw.text((cx, (label_top + 3.7) * scale), f"U+{cell['unicode']}" if cell["char"] else f"第 {cell['id']} 格", font=small, fill=0, anchor="mt")
        if cell["char"] and ord(cell["char"]) < 128:
            baseline = y + h * TOP / UPM
            for a, b in [(x-FRAME_MM-1.5, x-FRAME_MM-0.4), (x+w+FRAME_MM+0.4, x+w+FRAME_MM+1.5)]:
                draw.line([(a*scale, baseline*scale), (b*scale, baseline*scale)], fill=80, width=max(1, line))
    draw.text((28 * scale, (height - 16) * scale), manifest["page_id"], font=small, fill=0)
    return page


def plan_editor_pages(pages, mode="assigned"):
    if mode not in ("assigned", "generic"):
        raise ValueError("模板类型无效。")
    if not isinstance(pages, list) or not 1 <= len(pages) <= 30:
        raise ValueError("支持 1–30 个页面。")
    normalized = []
    total = 0
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("页面数据无效。")
        geo = grid_geometry(float(page.get("cell_mm", 16)), page.get("orientation", "portrait"), page.get("paper_format", "A4"))
        entries = ([{"slot": i, "char": ""} for i in range(geo["capacity"])]
                   if mode == "generic" else page.get("cells", []))
        occupied = set()
        if not isinstance(entries, list):
            raise ValueError("字格数据无效。")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("char"), str) or (len(entry["char"]) != 1 and mode != "generic"):
                raise ValueError("字块数据无效。")
            slot = entry.get("slot")
            chars = [] if mode == "generic" else parse_cells(entry.get("char", ""))
            if type(slot) is not int or not 0 <= slot < geo["capacity"] or slot in occupied or (len(chars) != 1 and mode != "generic"):
                raise ValueError("字格位置重复、超出页面或字符无效。")
            occupied.add(slot)
        total += len(entries)
        normalized.append({"paper_format": geo["paper_format"], "cell_mm": geo["cell_mm"], "orientation": geo["orientation"],
                           "cells": sorted(entries, key=lambda c: c["slot"])})
    if not 1 <= total <= 1000:
        raise ValueError("请在页面上放置 1–1000 个字块后导出。")
    template_id = digest({"schema": SCHEMA, "editor_pages": normalized, "mode": mode})[:12]
    manifests = []
    for number, page in enumerate(normalized, 1):
        geo = grid_geometry(page["cell_mm"], page["orientation"], page["paper_format"])
        manifest = plan_template([], page["cell_mm"], page["orientation"], page["paper_format"])[0]
        manifest.update(mode=mode, template_id=template_id, page_id=f"{template_id}-{number:03d}")
        for entry in page["cells"]:
            x, y, w, h = geo["slots_mm"][entry["slot"]]
            manifest["cells"].append({"id": entry["slot"] + 1, "char": entry["char"],
                "unicode": f"{ord(entry['char']):04X}" if entry["char"] else "", "writing_mm": [x, y, w, h],
                "crop_mm": [x - 1.5, y - 1.5, w + 3, h + 3]})
        manifest.pop("qr", None)
        manifest.pop("hash", None)
        manifest["qr"] = f"HF1:{manifest['page_id']}:{digest(manifest)[:16]}"
        manifest["hash"] = digest(manifest)
        manifests.append(manifest)
    return manifests


def locked_template_mode(work, name, requested="assigned"):
    if not name:
        if requested == "generic":
            raise ValueError("通用书写纸是系统模板，请从模板库打开。")
        return "assigned", False
    if name == SYSTEM_PAPER_ID:
        return "generic", True
    index_path = data_dir(work, "templates") / name / "index.json"
    if not index_path.is_file():
        raise ValueError("找不到这个模板。")
    mode = read_json(index_path).get("mode", "assigned")
    return ("generic" if mode == "generic" else "assigned"), False


def ensure_system_paper(work):
    dest = data_dir(work, "templates") / SYSTEM_PAPER_ID
    index_path = dest / "index.json"
    if index_path.is_file():
        index = read_json(index_path)
        if index.get("mode", "assigned") != "generic":
            return dest
        index["system"] = True
        if not index.get("title") or index.get("title") == "我的书写模板":
            index["title"] = SYSTEM_PAPER_TITLE
        write_json(index_path, index)
        return dest
    make_template(None, dest, title=SYSTEM_PAPER_TITLE, mode="generic",
                  editor_pages=[{"cells": []}], system=True)
    return dest


def make_template(charset, output, cell_mm=16, label_font_path=None, title="", orientation="portrait", editor_pages=None, editor_library=None, replace=False, mode="assigned", system=False):
    if mode not in ("assigned", "generic"):
        raise ValueError("模板类型无效。")
    if mode == "generic" and editor_pages is None:
        editor_pages = [{"cell_mm": cell_mm, "orientation": orientation}]
    chars = read_charset(charset) if editor_pages is None else []
    if editor_pages is None and not chars:
        raise ValueError("先在格子里加入要写的字。")
    manifests = plan_template(chars, cell_mm, orientation) if editor_pages is None else plan_editor_pages(editor_pages, mode)
    chars = [c["char"] for m in manifests for c in m["cells"]]
    library = editor_library or []
    if not isinstance(library, list) or len(library) + len(chars) > 1000:
        raise ValueError("每个模板最多 1000 个字块。")
    if any(not isinstance(c, str) or len(c) != 1 or len(parse_cells(c)) != 1 for c in library):
        raise ValueError("字块库包含无效字符。")
    width, height = manifests[0]["page_mm"]
    with OutputDirectory(output, replace=replace) as folder:
        pdf = canvas.Canvas(str(folder / "template.pdf"), pagesize=(width * 72 / 25.4, height * 72 / 25.4))
        pdf.setTitle(title or f"{PRODUCT_ZH} — 书写模板")
        for index, manifest in enumerate(manifests, 1):
            width, height = manifest["page_mm"]
            pdf.setPageSize((width * 72 / 25.4, height * 72 / 25.4))
            page = render_page(manifest, index, len(manifests), label_font_path)
            page.save(folder / f"{manifest['page_id']}.png", dpi=(TEMPLATE_DPI, TEMPLATE_DPI))
            pdf.drawImage(ImageReader(page), 0, 0, width=width*72/25.4, height=height*72/25.4)
            pdf.showPage()
            write_json(folder / f"{manifest['page_id']}.json", manifest)
        pdf.save()
        write_json(folder / "index.json", {"template_id": manifests[0]["template_id"], "title": title,
                   "cell_mm": manifests[0]["cell_mm"], "orientation": manifests[0]["orientation"], "charset": "".join(chars),
                   "characters": len(chars), "mode": mode, "system": bool(system), "editor_library": library,
                   "pages": [{"page_id": m["page_id"], "characters": len(m["cells"])} for m in manifests]})
    return {"template": str(output), "pages": len(manifests), "characters": len(chars)}
