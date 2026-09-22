"""Turn a phone photo into an A4 grayscale scan for later confirmation."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .scan import detect_markers, find_page_quad, order_quad, warp_to_page

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic", ".heif"}


def open_photo(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in PHOTO_SUFFIXES:
        raise ValueError("照片请用 JPEG、PNG、WEBP、HEIC 或 TIFF。")
    try:
        image = Image.open(path)
        image.load()
        return ImageOps.exif_transpose(image)
    except OSError:
        if suffix in {".heic", ".heif"} and shutil.which("sips"):
            converted = path.with_name(path.stem + "-converted.png")
            subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(converted)],
                           check=True, capture_output=True)
            image = Image.open(converted)
            image.load()
            return ImageOps.exif_transpose(image)
        raise ValueError("无法打开这张照片。iPhone 的 HEIC 若失败，请先在系统里导出为 JPEG。")


def photo_to_scan(image, dpi=600):
    if dpi not in (300, 600):
        raise ValueError("分辨率只能是 300 或 600。")
    gray = np.asarray(ImageOps.grayscale(image))
    cropped = False
    found = detect_markers(gray)
    source = gray
    if found is None:
        quad = find_page_quad(gray)
        if quad is None:
            raise ValueError("找不到纸张，也看不到四角定位标记。请铺平、拍全四角、避免强反光后重拍。")
        height, width = gray.shape
        dest = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
        matrix = cv2.getPerspectiveTransform(order_quad(quad), dest)
        source = cv2.warpPerspective(gray, matrix, (width, height), flags=cv2.INTER_CUBIC, borderValue=255)
        found = detect_markers(source)
        cropped = True
        if found is None:
            raise ValueError("已经按纸边裁切，仍看不到四角 0–3 定位标记。请把标记完整拍进画面。")
    page, info = warp_to_page(source, found, dpi)
    if info["marker_max_error_mm"] > 1.5:
        raise ValueError("照片形变较大，无法可靠切字；请铺平纸张后重拍。")
    # Remove slow lighting changes before thresholding; retain original photo separately.
    background = cv2.GaussianBlur(page, (0, 0), sigmaX=3 * dpi / 25.4)
    page = cv2.divide(page, np.maximum(background, 1), scale=255)
    info["illumination_normalized"] = True
    info["page_crop"] = cropped
    warning = None
    if info["marker_max_error_mm"] > 0.4:
        warning = (f"定位拟合 {info['marker_max_error_mm']:.2f} mm，纸可能不平或镜头畸变较大。"
                   "可以先看扫描图再决定；不满意请重拍。")
    info["warning"] = warning
    return page, info
