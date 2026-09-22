# MenuTitle: Handfont - 采用当前候选（保留旧轮廓）
# -*- coding: utf-8 -*-
"""Select a Handfont candidate layer in the Layers panel before running."""
from datetime import datetime
import uuid

from GlyphsApp import Glyphs, Message


def main():
    font = Glyphs.font
    if font is None or len(font.masters) != 1 or not font.userData["com.handfont.profile"]:
        raise ValueError("请打开 Handfont 单 master 字体。")
    selected = [layer for layer in font.selectedLayers if (layer.name or "").startswith("Handfont candidate ")]
    if not selected:
        Message("未选择候选", "先在字形的图层面板选择 Handfont candidate 图层，再运行此脚本。")
        return
    for candidate in selected:
        glyph = candidate.parent
        master_id = font.masters[0].id
        previous = glyph.layers[master_id].copy()
        previous.layerId = str(uuid.uuid4()).upper()
        previous.name = "Handfont previous " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        glyph.layers.append(previous)
        replacement = candidate.copy()
        replacement.layerId = master_id
        replacement.associatedMasterId = master_id
        replacement.name = "Regular"
        glyph.layers[master_id] = replacement
        candidate.name = "Handfont used " + str(candidate.userData["com.handfont.run"])
    Message("已采用候选", f"已替换 {len(selected)} 字。旧轮廓保存在 Handfont previous 图层；请检查并保存。")


try:
    main()
except Exception as error:
    Glyphs.showMacroWindow()
    print(error)
    Message("未完成替换", str(error))
