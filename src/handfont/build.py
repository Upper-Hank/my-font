from pathlib import Path
import shutil

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import replayRecording
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont
from glyphsLib import GSFont, load
from glyphsLib.classes import GSBackgroundImage, GSFontMaster, GSGlyph, GSInstance, GSLayer
from glyphsLib.types import Transform
from PIL import Image, ImageDraw, ImageFont

from .common import PRODUCT_EN, OutputDirectory, UPM, digest, file_hash, read_json, write_json
from .trace import bounds

MASTER_ID = "HANDfont-MVP-Regular"


def load_source(path):
    with Path(path).open(encoding="utf-8") as stream:
        return load(stream)


def engineering_glyphs():
    # Visible missing glyph, plus explicitly empty spaces.
    notdef = [("moveTo", [(50, 0)]), ("lineTo", [(550, 0)]), ("lineTo", [(550, 700)]),
              ("lineTo", [(50, 700)]), ("closePath", []),
              ("moveTo", [(100, 50)]), ("lineTo", [(100, 650)]), ("lineTo", [(500, 650)]),
              ("lineTo", [(500, 50)]), ("closePath", [])]
    return [{"glyph_name": ".notdef", "width": 600, "commands": notdef},
            {"glyph_name": "space", "unicode": "0020", "width": 300, "commands": []},
            {"glyph_name": "uni3000", "unicode": "3000", "width": 1000, "commands": []}]


def check_font(path, expected=None):
    with TTFont(path) as font:
        cmap = font.getBestCmap()
        if not cmap or font.getGlyphOrder()[0] != ".notdef":
            raise ValueError("字体缺少 cmap 或 .notdef。")
        if expected is not None and set(cmap) != set(expected):
            raise ValueError("导出字体 Unicode 覆盖范围与输入不一致。")
        for name in cmap.values():
            if font["hmtx"][name][0] <= 0:
                raise ValueError(f"非法字宽：{name}")
        return {"glyphs": len(font.getGlyphOrder()), "unicode_count": len(cmap),
                "characters": "".join(chr(cp) for cp in sorted(cmap))}


def build_run(run_folder, output, family=PRODUCT_EN, exclude=""):
    run_folder = Path(run_folder).resolve()
    run = read_json(run_folder / "run.json")
    if run.get("schema") != 1:
        raise ValueError("不支持的候选包版本。")
    if run.get("review_pending"):
        raise ValueError("请先确认切字匹配结果后再生成字体。")
    if run.get("review_choices") is not None:
        from .project import reviewed_glyphs
        run["glyphs"] = reviewed_glyphs(run)
    selected = [g for g in run["glyphs"] if g["status"] == "review" and g["char"] not in exclude]
    if not selected:
        raise ValueError("没有可用字形。查看 review.csv，先处理空格/触边或减少排除字符。")
    rows = [{**g, "run_folder": str(run_folder), "run_id": run["run_id"], "cell_mm": run["cell_mm"]} for g in selected]
    result = compile_glyphs(rows, output, family, digest({"run": file_hash(run_folder / "run.json"), "family": family}))
    info = read_json(Path(output) / "build.json")
    selected_chars = {g["char"] for g in selected}
    info.update({"run_id": run["run_id"], "input_hash": file_hash(run_folder / "run.json"),
                 "excluded": [g["char"] for g in run["glyphs"] if g["char"] not in selected_chars]})
    write_json(Path(output) / "build.json", info)
    return result


def compile_glyphs(selected, output, family=PRODUCT_EN, stamp=None):
    if not selected:
        raise ValueError("没有可用字形。")
    glyphs = engineering_glyphs() + selected
    cmap = {int(g["unicode"], 16): g["glyph_name"] for g in glyphs if "unicode" in g}
    names = [g["glyph_name"] for g in glyphs]
    if len(cmap) != len(glyphs)-1 or len(set(names)) != len(names):
        raise ValueError("重复 Unicode 或 glyph name，不能生成字体。")
    ink_bounds = [bounds(g["commands"]) for g in glyphs if g["commands"]]
    ascender = max(1000, round(max(b[3] for b in ink_bounds)) + 30)
    descender = min(-250, round(min(b[1] for b in ink_bounds)) - 30)
    stamp = stamp or digest({"chars": [g["char"] for g in selected], "family": family})
    build_id = stamp[:12]
    preview_family = f"{family} Preview {build_id}"
    run_ids = sorted({g.get("run_id", "") for g in selected if g.get("run_id")})
    cell_mm = selected[0].get("cell_mm", 16)
    with OutputDirectory(output) as folder:
        images = folder / "images"
        images.mkdir()
        source = GSFont()
        source.format_version = 3
        source.familyName = family
        source.upm = UPM
        source.versionMajor, source.versionMinor = 0, 100
        source.userData["com.handfont.profile"] = f"v1:{cell_mm}:1000:880"
        source.userData["com.handfont.run"] = ",".join(run_ids)
        source.customParameters["Use Typo Metrics"] = True
        for key, value in {"hheaAscender": ascender, "hheaDescender": descender, "hheaLineGap": 0,
                           "typoAscender": ascender, "typoDescender": descender, "typoLineGap": 0,
                           "winAscent": ascender, "winDescent": -descender}.items():
            source.customParameters[key] = value
        master = GSFontMaster()
        master.id = MASTER_ID
        master.name = "Regular"
        master.ascender, master.descender = 880, -120
        master.xHeight, master.capHeight = 500, 700
        source.masters.append(master)
        instance = GSInstance()
        instance.name = "Regular"
        source.instances.append(instance)
        charstrings, metrics = {}, {}
        for row in glyphs:
            glyph = GSGlyph(row["glyph_name"])
            if "unicode" in row:
                glyph.unicode = row["unicode"]
            source.glyphs.append(glyph)
            layer = GSLayer()
            layer.layerId = master.id
            layer.associatedMasterId = master.id
            layer.width = row["width"]
            layer.userData["com.handfont.run"] = row.get("run_id", "")
            glyph.layers.append(layer)
            replayRecording(row["commands"], layer.getPen())
            if "gray" in row:
                image_name = f"{row['unicode']}.png"
                shutil.copyfile(Path(row["run_folder"]) / row["gray"], images / image_name)
                layer.backgroundImage = GSBackgroundImage(f"images/{image_name}")
                layer.backgroundImage.transform = Transform(*row["image_transform"])
                layer.backgroundImage.locked = True
                replayRecording(row["commands"], layer.background.getPen())
                glyph.note = f"待审核 | {row['page_id']} / cell {row['cell_id']} | run {row.get('run_id', '')}"
                glyph.userData["com.handfont.sample"] = row["sample_id"]
            pen = T2CharStringPen(row["width"], None)
            replayRecording(row["commands"], pen)
            charstrings[row["glyph_name"]] = pen.getCharString()
            box = bounds(row["commands"])
            metrics[row["glyph_name"]] = (row["width"], round(box[0]) if box else 0)
        source.save(str(folder / "Candidates.glyphs"))
        builder = FontBuilder(UPM, isTTF=False)
        builder.setupGlyphOrder(names)
        builder.setupCharacterMap(cmap)
        builder.setupCFF(f"{PRODUCT_EN}Preview-{build_id}",
                         {"FullName": preview_family, "FamilyName": preview_family, "Weight": "Regular"}, charstrings, {})
        builder.setupHorizontalMetrics(metrics)
        builder.setupHorizontalHeader(ascent=ascender, descent=descender, lineGap=0)
        builder.setupNameTable({"familyName": preview_family, "styleName": "Regular",
                                "uniqueFontIdentifier": f"{PRODUCT_EN}:{build_id}",
                                "fullName": preview_family, "psName": f"{PRODUCT_EN}Preview-{build_id}",
                                "version": "Version 0.100; unreviewed preview"})
        builder.setupOS2(version=4, sTypoAscender=ascender, sTypoDescender=descender, sTypoLineGap=0,
                         usWinAscent=ascender, usWinDescent=-descender, fsSelection=0xC0)
        builder.setupPost()
        builder.save(str(folder / "Preview.otf"))
        result = check_font(folder / "Preview.otf", cmap)
        proof_font = ImageFont.truetype(str(folder / "Preview.otf"), 64)
        proof_chars = "".join(g["char"] for g in selected)
        proof = Image.new("RGB", (1080, 80 + ((len(proof_chars)+13)//14)*110), "white")
        draw = ImageDraw.Draw(proof)
        draw.text((30, 15), "UNREVIEWED PREVIEW — " + (", ".join(run_ids) or "project"), fill="black")
        for i in range(0, len(proof_chars), 14):
            draw.text((30, 130+(i//14)*110), proof_chars[i:i+14], font=proof_font, fill="black", anchor="ls")
        proof.save(folder / "proof.png")
        reopened = load_source(folder / "Candidates.glyphs")
        if len(reopened.glyphs) != len(glyphs):
            raise ValueError("Glyphs 源文件往返校验失败。")
        write_json(folder / "build.json", {"build_id": build_id, "preview": True, "run_ids": run_ids,
                                           "font_hash": file_hash(folder / "Preview.otf"), **result})
        (folder / "coverage.txt").write_text(result["characters"] + "\n", encoding="utf-8")
    return {"output": str(output), "preview": True, **result}
