import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(prog="handfont", description="字记 / myfont")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="检查运行依赖")
    template = sub.add_parser("template", help="生成模板 PDF、页面 PNG 和 manifest")
    template.add_argument("--charset", type=Path, required=True)
    template.add_argument("--output", type=Path, required=True)
    template.add_argument("--cell-mm", type=float, default=16)
    template.add_argument("--label-font", type=Path)
    template.add_argument("--orientation", choices=["portrait", "landscape"], default="portrait")
    process = sub.add_parser("process", help="扫描 → 页面校正 → 切字 → 矢量候选")
    process.add_argument("scans", nargs="+", type=Path)
    process.add_argument("--templates", type=Path, required=True)
    process.add_argument("--output", type=Path, required=True)
    process.add_argument("--dpi", type=int, choices=[300, 600], default=600)
    process.add_argument("--threshold", type=int, help="1–254；默认整页 Otsu，不逐字求阈值")
    process.add_argument("--label-font", type=Path)
    process.add_argument("--photo", action="store_true", help="整页照片：方向/透视校正、光照修正与格框定位")
    build = sub.add_parser("build", help="候选包 → 可编辑 Glyphs 源文件 + 预览 OTF")
    build.add_argument("run", type=Path)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--family", default="myfont")
    build.add_argument("--exclude", default="", help="本次不要生成的字符，例如 --exclude '中我'")
    check = sub.add_parser("check", help="检查 OTF/TTF 基本结构和 Unicode 覆盖")
    check.add_argument("font", type=Path)
    run = argparse.ArgumentParser(add_help=False)
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8788, help="接口端口")
    run.add_argument("--ui-port", type=int, default=5173, help="前端端口")
    run.add_argument("--api-only", action="store_true", help="只开接口，不开 Vite")
    sub.add_parser("dev", parents=[run], help="一次启动本机接口和前端")
    sub.add_parser("serve", parents=[run], help="dev 的别名")
    args = parser.parse_args()
    try:
        if args.command in ("dev", "serve"):
            from .web import serve as serve_app, serve_stack
            if args.api_only:
                serve_app(Path.cwd(), args.host, args.port)
            else:
                serve_stack(Path.cwd(), args.host, args.port, args.ui_port)
            return 0
        if args.command == "doctor":
            from .common import BUNDLED_LABEL_FONT
            result = {"python": sys.version.split()[0], "potrace": shutil.which("potrace"),
                      "label_font": str(BUNDLED_LABEL_FONT) if BUNDLED_LABEL_FONT.is_file() else None,
                      "packages": {name: importlib.metadata.version(name) for name in
                                   ["numpy", "opencv-python-headless", "Pillow", "reportlab", "fonttools", "glyphsLib"]}}
            if result["potrace"] is None:
                raise ValueError("缺少 potrace，请运行 brew install potrace。")
            if result["label_font"] is None:
                raise ValueError("缺少 IBM Plex Sans SC，请检查随包字体或使用 --label-font。")
        elif args.command == "template":
            from .template import make_template
            result = make_template(args.charset, args.output, args.cell_mm, args.label_font,
                                   orientation=args.orientation)
        elif args.command == "process":
            from .scan import process_scans
            result = process_scans(args.templates, args.scans, args.output, args.dpi, args.threshold, args.label_font, args.photo)
        elif args.command == "build":
            from .build import build_run
            result = build_run(args.run, args.output, args.family, args.exclude)
        else:
            from .build import check_font
            result = check_font(args.font)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"handfont: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
