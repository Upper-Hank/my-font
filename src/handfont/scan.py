import csv
import importlib.metadata
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from . import __version__
from .common import OutputDirectory, TOP, UPM, digest, file_hash, glyph_name, label_font, read_json, validate_manifest, write_json
from .template import MARKER_MM, markers_for
from .trace import bounds, shift, trace_bitmap, write_preview_svg


def _marker_detector():
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    params = cv2.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 23
    params.minMarkerPerimeterRate = 0.01
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(dictionary, params)


def detect_markers(gray):
    detector = _marker_detector()
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    for max_side in (3200, 2200, 1600, 1100):
        ratio = min(1.0, max_side / max(gray.shape))
        scaled = cv2.resize(gray, None, fx=ratio, fy=ratio) if ratio < 1 else gray
        for variant in (scaled, clahe.apply(scaled)):
            corners, ids, _ = detector.detectMarkers(variant)
            if ids is None:
                continue
            found = {}
            for marker_id, corner in zip(ids.flatten(), corners):
                found[int(marker_id)] = corner.reshape(4, 2) / ratio
            if {0, 1, 2, 3}.issubset(found):
                return {key: found[key] for key in (0, 1, 2, 3)}
    return None


def order_quad(points):
    pts = np.asarray(points, dtype=np.float32)
    total = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(total)], pts[np.argmin(diff)],
                     pts[np.argmax(total)], pts[np.argmax(diff)]], dtype=np.float32)


def find_page_quad(gray):
    height, width = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 140)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_area = None, 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 0.2 * width * height:
            continue
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) != 4:
            continue
        if area > best_area:
            best, best_area = approx.reshape(4, 2), area
    return None if best is None else order_quad(best)


def warp_to_page(gray, found, dpi):
    best = None
    for size in ((210.0, 297.0), (297.0, 210.0)):
        markers = markers_for(size)
        actual, expected = [], []
        for mid, x, y in markers:
            actual.extend(found[mid])
            expected.extend([(x, y), (x + MARKER_MM, y), (x + MARKER_MM, y + MARKER_MM), (x, y + MARKER_MM)])
        actual = np.asarray(actual, dtype=np.float32)
        expected = np.asarray(expected, dtype=np.float32)
        matrix_mm, _ = cv2.findHomography(actual, expected, 0)
        if matrix_mm is None:
            continue
        projected = cv2.perspectiveTransform(actual.reshape(1, -1, 2), matrix_mm)[0]
        error_mm = np.linalg.norm(projected - expected, axis=1)
        max_error = float(error_mm.max())
        if best is not None and max_error >= best[0]:
            continue
        ppm = dpi / 25.4
        matrix = np.diag([ppm, ppm, 1]) @ matrix_mm
        rectified = cv2.warpPerspective(gray, matrix, (round(size[0] * ppm), round(size[1] * ppm)),
                                        flags=cv2.INTER_CUBIC, borderValue=255)
        best = (max_error, rectified, {"scan_to_page_mm": matrix_mm.tolist(),
                                       "marker_max_error_mm": max_error, "page_mm": list(size)})
    if best is None:
        raise ValueError("无法建立页面坐标。")
    return best[1], best[2]


def rectify(image, dpi, max_error_mm=0.4):
    gray = np.asarray(ImageOps.grayscale(image))
    found = detect_markers(gray)
    if found is None:
        raise ValueError("必须完整识别四角 0–3 定位标记；请重拍或重扫，不能裁掉页面边缘。")
    rectified, info = warp_to_page(gray, found, dpi)
    if max_error_mm is not None and info["marker_max_error_mm"] > max_error_mm:
        raise ValueError(f"定位标记拟合误差过大：{info['marker_max_error_mm']:.2f} mm；请平整纸张后重拍。")
    return rectified, info


def page_identity(page, dpi):
    ppm = dpi / 25.4
    region = page[round(5*ppm):round(39*ppm), round(152*ppm):round(187*ppm)]
    detector = cv2.QRCodeDetector()
    for candidate in [region, cv2.resize(region, (600, 600))]:
        text, _, _ = detector.detectAndDecode(candidate)
        if text.startswith("HF1:"):
            return text
    raise ValueError("页面二维码无法识别，请重扫。")


def make_contact_sheet(folder, rows, label_font_path):
    font = label_font(22, label_font_path)
    per_page = 48
    for offset in range(0, len(rows), per_page):
        batch = rows[offset:offset + per_page]
        sheet = Image.new("RGB", (1200, ((len(batch)+5)//6)*235 + 50), "white")
        draw = ImageDraw.Draw(sheet)
        draw.text((15, 10), "核对提示字与实际笔迹；红字需处理。字体仍是未经人工审核的预览。", font=font, fill="black")
        for index, row in enumerate(batch):
            x, y = index % 6 * 200, 50 + index // 6 * 235
            with Image.open(folder / row["gray"]) as source:
                thumb = ImageOps.contain(source.convert("RGB"), (180, 180))
                sheet.paste(thumb, (x+10, y))
            draw.text((x+10, y+183), f"{row['char']} U+{row['unicode']}", font=font, fill="black")
            draw.text((x+10, y+207), row["status"], font=font, fill="#b42318" if row["status"] != "review" else "#444444")
        sheet.save(folder / f"contact-{offset//per_page+1:02d}.png")


def align_photo_cells(page, manifest, dpi):
    """Locate printed frames near known slots, never use handwriting bounds.

    Only translate the local paper origin. All cells retain the same mm/unit scale.
    A missing frame blocks this page instead of silently cropping the wrong glyph.
    """
    ppm = dpi / 25.4
    side = manifest["cell_mm"] + 4
    binary = cv2.threshold(page, 180, 255, cv2.THRESH_BINARY_INV)[1]
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    frames = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if .88*side*ppm < w < 1.12*side*ppm and .88*side*ppm < h < 1.12*side*ppm:
            if cv2.contourArea(contour) > .9*w*h:
                frames.append((x, y, w, h))
    offsets = {}
    for cell in manifest["cells"]:
        x, y, w, h = cell["writing_mm"]
        cx, cy = (x+w/2)*ppm, (y+h/2)*ppm
        nearby = [b for b in frames if abs(b[0]+b[2]/2-cx) < 2*ppm and abs(b[1]+b[3]/2-cy) < 2*ppm]
        if not nearby:
            raise ValueError(f"照片中「{cell['char']}」附近的格框不完整，无法可靠定位，请重拍或重写。")
        # Outer contour is stable; ignore the duplicate contour on the frame's inside.
        b = max(nearby, key=lambda b: b[2]*b[3])
        offsets[cell["id"]] = ((b[0]+b[2]/2-cx)/ppm, (b[1]+b[3]/2-cy)/ppm)
    return offsets


def process_scans(templates, scans, output, dpi=600, threshold=None, label_font_path=None, photo_mode=False, review_pending=False):
    if not shutil.which("potrace"):
        raise ValueError("缺少 potrace，请先运行 brew install potrace。")
    if threshold is not None and not 1 <= threshold <= 254:
        raise ValueError("阈值必须在 1–254 之间。")
    manifests = {}
    for path in Path(templates).glob("*.json"):
        data = read_json(path)
        if "page_id" in data:
            validate_manifest(data)
            manifests[data["qr"]] = data
    if not manifests:
        raise ValueError("模板目录中没有页面 manifest。")
    fingerprints = [file_hash(path) for path in scans]
    if len(set(fingerprints)) != len(fingerprints):
        raise ValueError("重复扫描文件，请每页只传入一个扫描版本。")
    potrace_version = subprocess.run(["potrace", "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    provenance = {"pipeline": __version__, "dpi": dpi, "threshold": threshold, "photo_mode": photo_mode,
                  "scans": fingerprints, "templates": sorted(m["hash"] for m in manifests.values()),
                  "potrace": potrace_version,
                  "dependencies": {name: importlib.metadata.version(name) for name in ["opencv-python-headless", "Pillow", "fonttools"]}}
    run_id = digest(provenance)[:16]
    rows, pages, seen = [], [], set()
    cell_size = None
    with OutputDirectory(output) as folder:
        (folder / "raw").mkdir()
        for source_path, scan_hash in zip(scans, fingerprints):
            suffix = Path(source_path).suffix.lower()
            if not photo_mode and suffix not in {".png", ".tif", ".tiff"}:
                raise ValueError("首版只接收 PNG/TIFF 扫描；不接受照片 JPEG 或扫描 PDF。")
            raw_path = folder / "raw" / f"{scan_hash}{suffix}"
            shutil.copyfile(source_path, raw_path)
            if photo_mode:
                from .photo import open_photo, photo_to_scan
                with open_photo(raw_path) as source:
                    page, geometry = photo_to_scan(source, dpi)
            else:
                with Image.open(raw_path) as source:
                    if getattr(source, "n_frames", 1) != 1:
                        raise ValueError("多页 TIFF 请先拆成每页一张。")
                    page, geometry = rectify(ImageOps.exif_transpose(source), dpi)
            qr = page_identity(page, dpi)
            if qr not in manifests:
                raise ValueError("扫描页不属于此模板目录，请使用对应的模板 manifest。")
            manifest = manifests[qr]
            offsets = align_photo_cells(page, manifest, dpi) if photo_mode else {}
            if cell_size is not None and cell_size != manifest["cell_mm"]:
                raise ValueError("同一批次不能混用不同书写框大小。")
            cell_size = manifest["cell_mm"]
            page_id = manifest["page_id"]
            if page_id in seen:
                raise ValueError(f"同一模板页出现多张扫描：{page_id}，请选一张。")
            seen.add(page_id)
            Image.fromarray(page).save(folder / f"{page_id}-rectified.png")
            write_json(folder / f"{page_id}.json", manifest)
            used_threshold = threshold
            if used_threshold is None:
                used_threshold = int(cv2.threshold(page, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0])
            pages.append({"page_id": page_id, "source_hash": scan_hash, "threshold": used_threshold, **geometry})
            ppm = dpi / 25.4
            units_per_mm = UPM / cell_size
            unit_per_pixel = units_per_mm / ppm
            for cell in manifest["cells"]:
                char = cell["char"]
                glyph_id = f"{page_id}-{cell['id']:03d}-{cell['unicode']}"
                glyph_folder = folder / glyph_id
                glyph_folder.mkdir()
                x, y, w, h = cell["crop_mm"]
                offset_x, offset_y = offsets.get(cell["id"], (0, 0))
                if photo_mode:
                    # One mm of overflow; leave the printed frame and its antialiasing outside.
                    wx, wy, ww, wh = cell["writing_mm"]
                    x, y, w, h = wx - 1, wy - 1, ww + 2, wh + 2
                x, y = x+offset_x, y+offset_y
                left, top, right, bottom = [round(v*ppm) for v in [x, y, x+w, y+h]]
                gray = page[top:bottom, left:right]
                binary = np.where(gray <= used_threshold, 0, 255).astype("uint8")
                Image.fromarray(gray).save(glyph_folder / "gray.png")
                Image.fromarray(binary).save(glyph_folder / "binary.png")
                Image.fromarray(binary).convert("1").save(glyph_folder / "trace.pbm")
                ink_count = int(np.count_nonzero(binary == 0))
                edge = any(np.any(side == 0) for side in [binary[0], binary[-1], binary[:, 0], binary[:, -1]])
                status = "blank" if ink_count == 0 else "edge" if edge else "review"
                wx, wy, _, _ = cell["writing_mm"]
                wx, wy = wx+offset_x, wy+offset_y
                origin_x = units_per_mm * (left / ppm - wx)
                origin_y = TOP - units_per_mm * (bottom / ppm - wy)
                commands = []
                width = UPM
                dx = 0
                if ink_count:
                    commands = trace_bitmap(glyph_folder / "trace.pbm", glyph_folder / "potrace.svg",
                                            (right-left, bottom-top),
                                            (unit_per_pixel, 0, 0, unit_per_pixel, origin_x, origin_y))
                    ink_bounds = bounds(commands)
                    if ink_bounds is None:
                        raise ValueError(f"有墨迹但描边结果为空：{char}")
                    if char and ord(char) < 128:
                        # Proportional Latin spacing only; never scale individual outlines.
                        dx = 60 - ink_bounds[0]
                        commands = shift(commands, dx)
                        width = round(ink_bounds[2] - ink_bounds[0] + 120)
                    write_preview_svg(glyph_folder / "outline.svg", commands,
                                      (origin_x + dx, origin_y, (right-left)*unit_per_pixel, (bottom-top)*unit_per_pixel))
                row = {"char": char, "unicode": cell["unicode"], "glyph_name": glyph_name(char) if char else "",
                       "sample_id": glyph_id, "page_id": page_id, "cell_id": cell["id"],
                       "matching_required": not bool(char), "status": status, "ink_pixels": ink_count, "width": width,
                       "gray": f"{glyph_id}/gray.png", "commands": commands,
                       "image_transform": [unit_per_pixel, 0, 0, unit_per_pixel, origin_x+dx, origin_y],
                       "source_hash": scan_hash, "spacing_shift": dx,
                       "frame_offset_mm": [offset_x, offset_y]}
                rows.append(row)
        write_json(folder / "run.json", {"schema": 1, "run_id": run_id, "cell_mm": cell_size,
                                         "provenance": provenance, "pages": pages, "glyphs": rows, "review_pending": review_pending or any(r["matching_required"] for r in rows)})
        with (folder / "review.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["char", "unicode", "page_id", "cell_id", "status", "ink_pixels"])
            writer.writeheader()
            writer.writerows({k: row[k] for k in writer.fieldnames} for row in rows)
        (folder / "rewrite.txt").write_text("".join(r["char"] for r in rows if r["status"] != "review") + "\n", encoding="utf-8")
        make_contact_sheet(folder, rows, label_font_path)
    return {"run_id": run_id, "output": str(output), "glyphs": len(rows),
            "review": sum(r["status"] == "review" for r in rows), "needs_attention": sum(r["status"] != "review" for r in rows)}
