# MenuTitle: Handfont - 导入候选（保留现有微调）
# -*- coding: utf-8 -*-
"""Run inside Glyphs 3. Only new glyphs or auxiliary layers are added."""
from pathlib import Path
import uuid

from GlyphsApp import Glyphs, GetOpenFile, Message


def main():
    target = Glyphs.font
    if target is None:
        Message("先打开正式字体", "首次制作请直接打开 build 生成的 Candidates.glyphs，并另存为自己的字体。")
        return
    profile = target.userData["com.handfont.profile"]
    if not profile or len(target.masters) != 1:
        raise ValueError("目标必须是 Handfont 生成的单 master 字体。")
    filename = GetOpenFile("选择新批次的 Candidates.glyphs", allowsMultipleSelection=False, filetypes=["glyphs"])
    if not filename:
        return
    if target.filepath and Path(filename).resolve() == Path(target.filepath).resolve():
        Message("已经是当前文件", "请选另一批次的 Candidates.glyphs。")
        return
    source = Glyphs.open(filename, showInterface=False)
    if source is None:
        raise ValueError("无法打开候选文件。")
    if source == target:
        return
    try:
        if source.userData["com.handfont.profile"] != profile or len(source.masters) != 1:
            raise ValueError("候选与正式字体的书写比例或 master 不一致。")
        run_id = source.userData["com.handfont.run"]
        if not run_id:
            raise ValueError("文件没有 Handfont 批次标记。")
        target_master = target.masters[0].id
        source_master = source.masters[0].id
        existing = {g.unicode: g for g in target.glyphs if g.unicode}
        added, candidates, skipped = 0, 0, 0
        for incoming in source.glyphs:
            if not incoming.userData["com.handfont.sample"]:
                continue
            glyph = existing.get(incoming.unicode)
            if glyph and any(layer.userData["com.handfont.run"] == run_id for layer in glyph.layers):
                skipped += 1
                continue
            if glyph is None:
                if target.glyphs[incoming.name] is not None:
                    raise ValueError("字形名称冲突：" + incoming.name)
                glyph = incoming.copy()
                glyph.layers = []
                target.glyphs.append(glyph)
                existing[incoming.unicode] = glyph
                added += 1
                new_glyph = True
            else:
                candidates += 1
                new_glyph = False
            layer = incoming.layers[source_master].copy()
            layer.associatedMasterId = target_master
            layer.layerId = target_master if new_glyph else str(uuid.uuid4()).upper()
            layer.name = "Regular" if new_glyph else "Handfont candidate " + run_id
            layer.userData["com.handfont.run"] = run_id
            if layer.backgroundImage:
                path = Path(layer.backgroundImage.path)
                if not path.is_absolute():
                    path = Path(filename).parent / path
                layer.backgroundImage.path = str(path.resolve())
            glyph.layers.append(layer)
        Message("导入完成", f"新增 {added} 字；已有字的候选 {candidates} 个；跳过重复 {skipped} 个。\n已有正式轮廓保持原样，请保存字体。")
    finally:
        if source != target:
            source.close(ignoreChanges=True)


try:
    main()
except Exception as error:
    Glyphs.showMacroWindow()
    print(error)
    Message("未完成导入", str(error))
