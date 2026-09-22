import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unicodedata

SCHEMA = 1
UPM = 1000
TOP = 880
PAGE_MM = (210, 297)
PRODUCT_ZH = "字记"
PRODUCT_EN = "myfont"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_manifest(manifest):
    if manifest.get("schema") != SCHEMA:
        raise ValueError("不支持的模板版本，请重新生成模板。")
    body = {k: v for k, v in manifest.items() if k != "hash"}
    if digest(body) != manifest.get("hash"):
        raise ValueError("模板 manifest 已被修改，不能继续切字。")


def read_charset(path):
    return parse_cells(Path(path).read_text(encoding="utf-8-sig"))


def parse_charset(text):
    """Legacy unique list. Templates use parse_cells, which keeps repeats."""
    chars = []
    for char in parse_cells(text):
        if char not in chars:
            chars.append(char)
    return chars


def _check_char(char):
    if unicodedata.category(char)[0] in "CM":
        raise ValueError(f"首版不支持控制字符、组合标记或未分配字符：U+{ord(char):04X}")
    return char


def parse_cells(text):
    """Keep every writing box, including the same character more than once."""
    chars = []
    raw = text.replace("\ufeff", "")
    tokens = raw.split() if any(part.upper().startswith("U+") for part in raw.replace(",", " ").split()) else None
    if tokens is not None:
        for token in tokens:
            token = token.strip().strip(",")
            if not token:
                continue
            if token.upper().startswith("U+"):
                chars.append(_check_char(chr(int(token[2:], 16))))
            else:
                for char in token:
                    if not char.isspace():
                        chars.append(_check_char(char))
    else:
        for char in raw:
            if char.isspace():
                continue
            chars.append(_check_char(char))
    if not chars:
        raise ValueError("字表为空。")
    return chars


def parse_one_cell(text):
    chars = parse_cells(text)
    if len(chars) != 1:
        raise ValueError("一次只加入一个字，或一个 U+ 编码。")
    return chars[0]


def glyph_name(char):
    from fontTools.agl import UV2AGL
    cp = ord(char)
    return UV2AGL.get(cp, f"uni{cp:04X}" if cp <= 0xFFFF else f"u{cp:05X}")


BUNDLED_LABEL_FONT = Path(__file__).resolve().parent / "fonts" / "IBMPlexSansSC-Regular.otf"


def label_font(size, path=None):
    from PIL import ImageFont
    choices = [path] if path else [
        BUNDLED_LABEL_FONT,
        Path.home() / "Library/Fonts/IBMPlexSansSC-Regular.otf",
        Path("/Library/Fonts/IBMPlexSansSC-Regular.otf"),
    ]
    for choice in choices:
        if choice and Path(choice).is_file():
            return ImageFont.truetype(str(choice), size)
    raise ValueError("找不到 IBM Plex Sans SC，请通过 --label-font 指定该字体的 TTF/OTF。")


class OutputDirectory:
    """Publish a complete directory; never overwrite unless replace=True."""

    def __init__(self, target, replace=False):
        self.target = Path(target).resolve()
        self.replace = replace

    def __enter__(self):
        if self.target.exists() and not self.replace:
            raise ValueError(f"输出目录已存在，为保护文件不会覆盖：{self.target}")
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix=".handfont-", dir=self.target.parent)
        self.path = Path(self.tmp.name)
        return self.path

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                if self.replace and self.target.exists():
                    shutil.rmtree(self.target)
                elif self.target.exists():
                    raise ValueError(f"输出目录已被另一操作创建：{self.target}")
                os.rename(self.path, self.target)
        finally:
            self.tmp.cleanup()
