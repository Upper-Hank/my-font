"""Local GUI for the first three handwriting production steps."""
from __future__ import annotations

import base64
from datetime import datetime
import io
import json
import mimetypes
from email import policy
from email.parser import BytesParser
import re
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import signal
import socket
import time
from urllib.parse import parse_qs, unquote, urlencode, urlparse
import uuid
import zipfile
import threading

import cv2
from PIL import Image

from .storage import data_dir, migrate_storage, file_path
from .common import BUNDLED_LABEL_FONT, PRODUCT_EN, PRODUCT_ZH, OutputDirectory, digest, parse_cells, read_json, validate_manifest, write_json
from .adjust import adjust_glyph, adjustment_options, preview_svg
from .build import build_run, compile_glyphs
from .photo import PHOTO_SUFFIXES, open_photo, photo_to_scan
from .project import (bootstrap_live, ensure_live, load_live, sample_library, select_sample, export_selection, archive_item, save_live, member_from, import_run, migrate_samples, cleanup_history, delete_samples, trash_samples, manage_characters, review_run, resolve_glyph, set_adjustment, font_pending, export_member_snapshot)
from .scan import align_photo_cells, page_identity, process_scans
from .template import SYSTEM_PAPER_ID, SYSTEM_PAPER_TITLE, ensure_system_paper, grid_geometry, locked_template_mode, make_template, plan_template, render_page

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_BODY = 100 * 1024 * 1024
STATIC = Path(__file__).parent / "static"
ALLOWED = {".png", ".tif", ".tiff", ".pdf", ".csv", ".txt", ".json", ".otf", ".glyphs", ".svg", ".jpg", ".jpeg", ".webp", ".zip", ".ico"}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def host_name(value):
    value = (value or "").strip().lower()
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end != -1 else value
    return value.split(":")[0]


def origin_allowed(origin, host):
    if not origin:
        return True
    origin_netloc = urlparse(origin).netloc
    if origin_netloc == host:
        return True
    return host_name(origin_netloc) in LOCAL_HOSTS and host_name(host) in LOCAL_HOSTS


def fresh(prefix):
    return f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


def safe(name):
    name = (name or "").strip()
    if not NAME.fullmatch(name):
        raise ValueError("无效的记录编号。")
    return name


def flagged(fields, name):
    value = fields.get(name)
    return value is True or value == "true" or value == "1"


def inside(work, rel):
    target = file_path(work, unquote(rel).lstrip("/")).resolve()
    if not target.is_relative_to(work.resolve()) or not target.is_file():
        raise ValueError("文件不存在。")
    return target


def named_dirs(folder, marker):
    return sorted((p.name for p in folder.iterdir() if p.is_dir() and (p / marker).is_file()),
                  key=lambda n: (folder / n / marker).stat().st_mtime, reverse=True) if folder.is_dir() else []


def parse_post(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    if not 0 < length <= MAX_BODY:
        raise ValueError("请选择文件；每批文件合计不能超过 100 MB。")
    body = handler.rfile.read(length)
    ctype = handler.headers.get("Content-Type", "")
    if "application/json" in ctype:
        fields = json.loads(body)
        if not isinstance(fields, dict):
            raise ValueError("无效的表单。")
        return fields, []
    if "multipart/form-data" not in ctype.lower():
        values = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        return {k: v[-1] for k, v in values.items()}, []
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body)
    if not message.is_multipart():
        raise ValueError("上传表单不完整。")
    fields, files = {}, []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        data = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is None:
            fields[name] = data.decode("utf-8")
        elif filename:
            files.append((name, filename, data))
    return fields, files


def match_template(work, qr, selected=""):
    names = [safe(selected)] if selected else named_dirs(data_dir(work, "templates"), "index.json")
    for name in names:
        for path in (data_dir(work, "templates") / name).glob("*.json"):
            manifest = read_json(path)
            if manifest.get("qr") == qr:
                validate_manifest(manifest)
                return name, manifest
    raise ValueError("这张照片的二维码没有匹配到所选模板。请选「自动识别」，并保留原模板记录。")


def make_server(root, host="127.0.0.1", port=8787):
    root = Path(root).resolve()
    work = root / "work"
    if not (root / "charset/mvp.txt").is_file():
        raise ValueError("请在项目根目录启动网页。")
    migrate_storage(work)
    for name in ("templates", "runs", "builds", "uploads", "staging", "live"):
        data_dir(work, name).mkdir(parents=True, exist_ok=True)
    ensure_live(work)
    bootstrap_live(work)
    migrate_samples(work)
    ensure_system_paper(work)
    live = load_live(work)
    archived = [name for name in live.get("archived_template", []) if name != SYSTEM_PAPER_ID]
    if archived != live.get("archived_template", []):
        live["archived_template"] = archived
        save_live(work, live)
    font_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                self.get()
            except (ValueError, OSError, KeyError) as error:
                if self.wants_json():
                    self.json(404, {"error": str(error)})
                else:
                    self.spa(404)

        def do_POST(self):
            try:
                # A local tool must not accept write requests from unrelated websites.
                origin = self.headers.get("Origin")
                if not origin_allowed(origin, self.headers.get("Host")):
                    raise ValueError("请从本机工作台提交操作。")
                self.post()
            except (ValueError, OSError, KeyError, subprocess.SubprocessError, cv2.error) as error:
                if self.wants_json():
                    self.json(400, {"error": str(error)})
                else:
                    self.json(400, {"error": str(error)})

        def wants_json(self):
            path = urlparse(self.path).path
            return path.startswith("/api/") or "application/json" in self.headers.get("Accept", "")

        def get(self):
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            if path.startswith("/api/"):
                return self.api_get(root, work, path, query)
            if path == "/font":
                return self.send_file(BUNDLED_LABEL_FONT)
            if path in ("/favicon.ico", "/favicon.svg", "/apple-touch-icon.png", "/favicon-32.png"):
                return self.send_file(STATIC / "app" / Path(path).name)
            if path.startswith("/static/"):
                return self.send_file(inside(STATIC, path[8:]))
            if path.startswith("/files/"):
                return self.send_file(inside(work, path[7:]))
            if path == "/download":
                return self.send_file(inside(work, (query.get("p") or [""])[0]), True)
            if path.startswith("/bundle/"):
                name = safe(path[8:])
                folder = data_dir(work, "live") if name == "live" else data_dir(work, "builds") / name
                inside(work, f"{folder.relative_to(work)}/Candidates.glyphs")
                content = io.BytesIO()
                with zipfile.ZipFile(content, "w", zipfile.ZIP_DEFLATED) as bundle:
                    for file in [folder / "Candidates.glyphs", *sorted((folder / "images").glob("*.png"))]:
                        bundle.write(file, file.relative_to(folder))
                return self.send_bytes(content.getvalue(), "application/zip", f"{PRODUCT_EN}.zip")
            return self.spa(200)

        def post(self):
            fields, files = parse_post(self)
            path = urlparse(self.path).path
            if path in ("/strokes/generate", "/strokes/edit", "/strokes/publish"):
                return self.json(410, {"error": "笔画与部件计划在后续版本提供，MVP 不支持。"})
            if path == "/api/template-preview":
                chars = parse_cells(fields.get("charset", ""))
                orientation = fields.get("orientation") or "portrait"
                manifests = plan_template(chars, float(fields.get("cell_mm", 16)), orientation)
                number = max(1, min(int(fields.get("page", 1)), len(manifests)))
                preview = render_page(manifests[number-1], number, len(manifests))
                preview.thumbnail((960, 960))
                stream = io.BytesIO()
                preview.save(stream, format="PNG")
                return self.json(200, {"image": "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode(),
                                       "characters": len(chars), "pages": len(manifests), "page": number,
                                       "orientation": orientation,
                                       "per_page": len(manifests[0]["cells"])})
            if path == "/template":
                existing = (fields.get("id") or "").strip()
                name = safe(existing) if existing else fresh("template")
                dest = data_dir(work, "templates") / name
                if existing and not dest.is_dir():
                    raise ValueError("找不到这个模板。")
                mode, system = locked_template_mode(work, existing, fields.get("mode", "assigned"))
                text = fields.get("charset", "")
                if fields.get("editor_pages") is None and mode != "generic":
                    parse_cells(text)
                orientation = fields.get("orientation") or "portrait"
                title = SYSTEM_PAPER_TITLE if system else (fields.get("title") or "我的书写模板").strip()[:80]
                with OutputDirectory(data_dir(work, "uploads") / fresh("charset")) as tmp:
                    charset = tmp / "charset.txt"
                    charset.write_text(text, encoding="utf-8")
                    make_template(charset, dest, float(fields.get("cell_mm", 16)),
                                  title=title, orientation=orientation, editor_pages=fields.get("editor_pages"),
                                  editor_library=fields.get("editor_library", []), replace=bool(existing),
                                  mode=mode, system=system)
                with font_lock:
                    block_library_payload(work)
                return self.redirect(f"/template/{name}")
            if path == "/prepare":
                run = fresh("photo")
                dpi = int(fields.get("dpi", 300))
                if dpi not in (300, 600):
                    raise ValueError("分辨率只能是 300 或 600。")
                photos = [p for p in files if p[0] == "photos"]
                if not photos or len(photos) > 8:
                    raise ValueError("请选择 1–8 张照片。")
                selected = fields.get("template", "")
                pages, matched_template, seen = [], None, set()
                with OutputDirectory(data_dir(work, "staging") / run) as staging:
                    for index, (_, filename, data) in enumerate(photos, 1):
                        suffix = Path(filename).suffix.lower()
                        if suffix not in PHOTO_SUFFIXES:
                            raise ValueError("请上传 JPEG、PNG、WEBP、HEIC 或 TIFF。")
                        original = staging / f"{index:02d}-original{suffix}"
                        original.write_bytes(data)
                        with open_photo(original) as photo:
                            page, info = photo_to_scan(photo, dpi)
                            qr = page_identity(page, dpi)
                            template, manifest = match_template(work, qr, selected)
                            if matched_template and template != matched_template:
                                raise ValueError("一次请上传同一套模板的照片。")
                            if manifest["page_id"] in seen:
                                raise ValueError("同一模板页上传了两次，请只保留一张。")
                            seen.add(manifest["page_id"])
                            matched_template = template
                            snapshot = staging / "template"
                            snapshot.mkdir(exist_ok=True)
                            write_json(snapshot / (manifest["page_id"] + ".json"), manifest)
                            align_photo_cells(page, manifest, dpi)
                            photo.thumbnail((900, 1200))
                            photo.convert("RGB").save(staging / f"{index:02d}-photo.jpg", quality=85)
                        Image.fromarray(page).save(staging / f"{index:02d}-scan.png")
                        pages.append({"photo": f"{index:02d}-photo.jpg", "scan": f"{index:02d}-scan.png",
                                      "original": original.name, "source_name": Path(filename).name,
                                      "characters": len(manifest["cells"]), "page_id": manifest["page_id"], **info})
                    write_json(staging / "preview.json", {"run": run, "template": matched_template,
                               "dpi": dpi, "pages": pages, "return_char": fields.get("return_char", ""), "threshold": fields.get("threshold", "").strip()})
                return self.redirect(f"/preview/{run}")
            if path == "/confirm":
                run = safe(fields.get("run", ""))
                staging = data_dir(work, "staging") / run
                preview = read_json(staging / "preview.json")
                if fields.get("action") != "convert":
                    return self.redirect("/photos")  # Never discard the user's original photos.
                if (data_dir(work, "runs") / run / "run.json").is_file():
                    with font_lock:
                        import_run(work, run)
                    return self.redirect(f"/run/{run}")
                originals = [staging / p["original"] for p in preview["pages"] if p.get("original")]
                if len(originals) != len(preview["pages"]):
                    raise ValueError("这是旧版预览，没有保留原照片。请重新上传原照片。")
                threshold = int(preview["threshold"]) if preview.get("threshold") else None
                template_folder = staging / "template"
                if not template_folder.is_dir():
                    template_folder = data_dir(work, "templates") / preview["template"]
                process_scans(template_folder, originals, data_dir(work, "runs") / run,
                              preview["dpi"], threshold, photo_mode=True, review_pending=True)
                with font_lock:
                    from .matching import suggest_run
                    suggest_run(work, run)
                    import_run(work, run)
                return self.redirect(f"/run/{run}")
            if path == "/history/cleanup":
                with font_lock:
                    kind = fields.get("kind")
                    if kind == "completed":
                        for name in named_dirs(data_dir(work, "runs"), "run.json"):
                            if not read_json(data_dir(work, "runs") / name / "run.json").get("review_pending"):
                                cleanup_history(work, "run", name)
                    elif kind in ("template-trash", "preview-trash"):
                        item_kind = kind.split('-')[0]
                        for name in list(load_live(work).get('archived_' + item_kind, [])):
                            cleanup_history(work, item_kind, name)
                    else:
                        cleanup_history(work, kind, fields.get("id") or "")
                return self.json(200, {"ok": True})
            if path == "/blocks/add":
                with font_lock:
                    manage_characters(work, fields.get("characters"))
                    payload = block_library_payload(work)
                return self.json(200, payload)
            if path in ("/characters/add", "/characters/delete"):
                with font_lock:
                    manage_characters(work, fields.get("characters"), remove=path.endswith('/delete'))
                    payload = live_payload(work)
                return self.json(200, payload)
            if path == "/run/review":
                with font_lock:
                    name = fields.get("run", "")
                    review_run(work, name, fields.get("choices"), flagged(fields, "commit"))
                    payload = run_payload(work, name)
                return self.json(200, payload)
            if path == "/library/trash":
                with font_lock:
                    trash_samples(work, fields.get("ids"))
                    payload = live_payload(work)
                return self.json(200, payload)
            if path == "/library/delete":
                with font_lock:
                    ids = fields.get("ids")
                    delete_samples(work, ids)
                    payload = live_payload(work)
                return self.json(200, payload)
            if path == "/library/archive":
                with font_lock:
                    archive_item(work, fields.get("kind"), fields.get("id") or "", flagged(fields, "restore"))
                    payload = live_payload(work)
                return self.json(200, payload)
            if path == "/font/select-unique":
                with font_lock:
                    project = load_live(work)
                    hidden = set(project.get("archived_sample", []))
                    groups = {}
                    for sample in sample_library(work):
                        if sample["id"] not in hidden and sample["usable"]:
                            groups.setdefault(sample["char"], []).append(sample)
                    existing = {m["char"] for m in project["members"]}
                    requested = fields.get("ids", [])
                    if not isinstance(requested, list):
                        raise ValueError("样本列表无效。")
                    for candidates in groups.values():
                        if len(candidates) == 1:
                            sample = candidates[0]
                            if sample["id"] in requested and sample["char"] not in existing:
                                project["members"].append(member_from(sample, sample["run"]))
                    save_live(work, project)
                    payload = live_payload(work)
                return self.json(200, payload)
            if path == "/font/adjust":
                with font_lock:
                    set_adjustment(work, fields.get("ids"), fields.get("adjustment"))
                    payload = live_payload(work)
                return self.json(200, payload)
            if path == "/font/select":
                with font_lock:
                    select_sample(work, fields.get("sample", ""), flagged(fields, "remove"))
                    payload = live_payload(work)
                return self.json(200, payload)
            if path == "/font/export":
                with font_lock:
                    export_selection(work)
                    payload = live_payload(work)
                return self.json(200, payload)
            raise ValueError("未知操作，请刷新页面后重试。")

        def redirect(self, location):
            if self.wants_json():
                return self.json(200, {"redirect": location})
            self.send_response(303)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def api_get(self, root, work, path, query):
            if path == "/api/strokes":
                return self.json(410, {"error": "笔画与部件计划在后续版本提供，MVP 不支持。"})
            if path == "/api/glyph-preview":
                sample = (query.get('sample') or [''])[0]
                parts = sample.split('/')
                if len(parts) != 2:
                    raise ValueError('字形编号无效。')
                name, sample_id = [safe(part) for part in parts]
                custom = (query.get('adjustment') or [''])[0]
                if (query.get('source') or [''])[0] == 'run':
                    run = read_json(data_dir(work, 'runs') / name / 'run.json')
                    row = next((g for g in run['glyphs'] if g['sample_id'] == sample_id), None)
                    if row is None:
                        raise ValueError('字形不存在。')
                    choices = {c['sample_id']: c for c in run.get('review_choices', [])}
                    choice = choices.get(sample_id, {})
                    row = {**row, 'char': (query.get('char') or [choice.get('char', row['char'])])[0]}
                    row = adjust_glyph(row, json.loads(custom) if custom else choice.get('adjustment'))
                else:
                    member = {'run': name, 'sample_id': sample_id, 'char': ''}
                    row = resolve_glyph(work, member, adjusted=not bool(custom))
                    if custom:
                        row = adjust_glyph(row, json.loads(custom))
                return self.send_bytes(preview_svg(row).encode(), 'image/svg+xml')
            if path == "/api/template-layout":
                return self.json(200, grid_geometry(float((query.get("cell_mm") or ["16"])[0]),
                                                    (query.get("orientation") or ["portrait"])[0]))
            if path == "/api/blocks":
                with font_lock:
                    payload = block_library_payload(work)
                return self.json(200, payload)
            if path == "/api/templates":
                selected = (query.get("id") or [""])[0]
                return self.json(200, template_payload(root, work, safe(selected) if selected else None))
            if path == "/api/photos":
                return self.json(200, photos_payload(work, (query.get("template") or [""])[0]))
            if path.startswith("/api/previews/"):
                return self.json(200, preview_payload(work, safe(path[14:])))
            if path.startswith("/api/runs/"):
                return self.json(200, run_payload(work, safe(path[10:])))
            if path == "/api/font":
                with font_lock:
                    payload = live_payload(work)
                return self.json(200, payload)
            if path.startswith("/api/builds/"):
                return self.json(200, build_payload(work, safe(path[12:])))
            raise ValueError("未知接口。")

        def spa(self, status=200):
            index = STATIC / "app" / "index.html"
            if not index.is_file():
                raise ValueError("请先在 web/ 目录运行 npm run build，生成 React 界面。")
            self.send_file(index)

        def json(self, status, data):
            self.send_bytes(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", status=status)

        def send_file(self, path, download=False):
            if path.suffix.lower() not in ALLOWED | {".css", ".js", ".html", ".map", ".woff", ".woff2"}:
                raise ValueError("不支持这个文件格式。")
            self.send_bytes(path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                            path.name if download else None)

        def send_bytes(self, data, content_type, download=None, status=200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # An aborted live preview must not crash a request thread.

    return ThreadingHTTPServer((host, port), Handler)


def serve(root, host="127.0.0.1", port=8788, announce=True):
    server = make_server(root, host, port)
    if announce:
        print(f"{PRODUCT_ZH}：http://{host}:{port}/ （本机 · {PRODUCT_EN}）", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def wait_port(host, port, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise OSError(f"接口没有在 {host}:{port} 启动。")


def ui_command(host, port):
    return ["npm", "run", "dev", "--", "--host", host, "--port", str(port), "--strictPort"]


def _stop_process(proc):
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        proc.wait(timeout=2)


def serve_stack(root, host="127.0.0.1", port=8788, ui_port=5173, ui=True):
    root = Path(root).resolve()
    web = root / "web"
    npm = shutil.which("npm")
    use_ui = ui and (web / "package.json").is_file() and npm
    if not use_ui:
        if ui and not npm:
            print("未找到 npm，只启动接口。前端开发请先安装 Node.js。", flush=True)
        serve(root, host, port)
        return
    if not (web / "node_modules").is_dir():
        print("正在安装前端依赖…", flush=True)
        subprocess.run([npm, "install"], cwd=web, check=True)
    api = threading.Thread(target=serve, args=(root, host, port, False), daemon=True)
    api.start()
    wait_port(host, port)
    env = os.environ.copy()
    env["HANDFONT_API"] = f"http://{host}:{port}"
    print(f"{PRODUCT_ZH}：http://{host}:{ui_port}/", flush=True)
    print(f"接口：http://{host}:{port}/  （Ctrl+C 同时停止）", flush=True)
    proc = subprocess.Popen(ui_command(host, ui_port), cwd=web, env=env, start_new_session=True)
    try:
        code = proc.wait()
    except KeyboardInterrupt:
        _stop_process(proc)
        raise SystemExit(0) from None
    if code:
        raise SystemExit(code)


def run_template(work, run_name):
    folder = data_dir(work, "runs") / run_name
    run = read_json(folder / "run.json")
    for page in run.get("pages", []):
        manifest = folder / f'{page["page_id"]}.json'
        if manifest.is_file():
            data = read_json(manifest)
            try:
                name, _ = match_template(work, data.get("qr"))
                return name
            except ValueError:
                pass
    return ""


def list_templates(work, archived=False):
    items = []
    hidden = set(load_live(work).get("archived_template", []))
    for name in named_dirs(data_dir(work, "templates"), "index.json"):
        if (name in hidden) != archived:
            continue
        info = read_json(data_dir(work, "templates") / name / "index.json")
        system = bool(info.get("system")) or name == SYSTEM_PAPER_ID
        items.append({"id": name, "title": info.get("title") or name, "mode": info.get("mode", "assigned"),
                      "system": system, "characters": info["characters"], "pages": len(info["pages"])})
    items.sort(key=lambda item: (not item["system"],))
    return items


def template_info(work, name):
    folder = data_dir(work, "templates") / name
    index = read_json(folder / "index.json")
    manifests = [read_json(folder / (p["page_id"] + ".json")) for p in index["pages"]]
    return index, manifests


def template_payload(root, work, selected=None):
    ensure_system_paper(work)
    default = (root / "charset/mvp.txt").read_text(encoding="utf-8")
    visible = list_templates(work)
    paper = next((item for item in visible if item.get("system")), None)
    payload = {"preset": default, "id": selected, "title": "我的书写模板", "charset": "",
               "cell_mm": 16, "orientation": "portrait", "saved": False, "pages": [],
               "paper": paper,
               "records": [item for item in visible if not item.get("system")],
               "archived": [item for item in list_templates(work, archived=True) if not item.get("system")]}
    if selected:
        index, manifests = template_info(work, selected)
        chars = "".join(c["char"] for m in manifests for c in m["cells"])
        pages = [f'/files/templates/{selected}/{p["page_id"]}.png' for p in index["pages"]]
        payload.update({"title": index.get("title") or selected, "charset": chars,
                        "cell_mm": manifests[0]["cell_mm"],
                        "orientation": index.get("orientation") or manifests[0].get("orientation") or "portrait",
                        "saved": True, "mode": index.get("mode", "assigned"),
                        "system": bool(index.get("system")) or selected == SYSTEM_PAPER_ID,
                        "pages": pages, "editor_library": index.get("editor_library", []),
                        "editor_pages": [{"paper_format": m.get("paper_format", "A4"), "cell_mm": m["cell_mm"], "orientation": m.get("orientation", "portrait"),
                                          "cells": [{"slot": c["id"] - 1, "char": c["char"]} for c in m["cells"] if c["char"]]} for m in manifests]})
    return payload


def listed_records(work, folder, marker, hidden):
    names = named_dirs(data_dir(work, folder), marker)
    visible = [{"id": n} for n in names if n not in hidden]
    archived = [{"id": n} for n in names if n in hidden]
    return visible, archived


def photos_payload(work, selected=""):
    ensure_system_paper(work)
    project = load_live(work)
    previews, archived_previews = listed_records(work, "staging", "preview.json", set(project.get("archived_preview", [])))
    runs, archived_runs = listed_records(work, "runs", "run.json", set(project.get("archived_run", [])))
    completed = {p.name for p in (data_dir(work, "runs")).iterdir() if (p / "run.json").is_file()}
    previews = [p for p in previews if p["id"] not in completed]
    archived_previews = [p for p in archived_previews if p["id"] not in completed]
    pending = [r for r in runs if read_json(data_dir(work, "runs") / r["id"] / "run.json").get("review_pending")]
    runs = [r for r in runs if r not in pending]
    return {
        "pending": pending,
        "template": selected,
        "templates": list_templates(work),
        "previews": previews,
        "runs": runs,
        "archived_previews": archived_previews,
        "archived_runs": archived_runs,
    }


def preview_payload(work, name):
    info = read_json(data_dir(work, "staging") / name / "preview.json")
    pages = []
    for p in info["pages"]:
        pages.append({**p, "photo_url": f"/files/staging/{name}/{p['photo']}",
                      "scan_url": f"/files/staging/{name}/{p['scan']}"})
    return {"id": name, "pages": pages, "template": info.get("template")}


def run_payload(work, name):
    run = read_json(data_dir(work, "runs") / name / "run.json")
    glyphs = []
    for g in run["glyphs"]:
        base = f"/files/runs/{name}/{g['sample_id']}"
        glyphs.append({"char": g["char"], "sample_id": g["sample_id"], "status": g["status"],
                       "matching_required": g.get("matching_required", False), "candidates": g.get("candidates", []),
                       "cell_id": g["cell_id"], "usable": g["status"] == "review", "has_vector": bool(g.get("commands")),
                       "gray": f"{base}/gray.png", "binary": f"{base}/binary.png",
                       "vector": f"{base}/outline.svg"})
    staging = data_dir(work, "staging") / name / "preview.json"
    return_char = read_json(staging).get("return_char", "") if staging.is_file() else ""
    return {"return_char": return_char, "id": name, "glyphs": glyphs, "review_pending": run.get("review_pending", False), "choices": run.get("review_choices")}


def live_payload(work):
    all_samples = sample_library(work)
    project = load_live(work)
    hidden = set(project.get("archived_sample", []))
    samples = [s for s in all_samples if s["id"] not in hidden]
    archived = [s for s in all_samples if s["id"] in hidden]
    exported = project.get("export")
    build = build_payload(work, exported["id"]) if exported else None
    members = project.get("members") or []
    snapshot = exported.get("members") if exported else None
    dirty_digest = bool(exported and exported["selection"] != digest(members))
    if exported and snapshot is None and not dirty_digest:
        snapshot = export_member_snapshot(members)
        exported = {**exported, "members": snapshot}
        project["export"] = exported
        save_live(work, project)
    pending = font_pending(members, snapshot, project.get("adjustments") or {})
    dirty = bool(pending["added"] or pending["removed"] or pending["replaced"]) if snapshot is not None else dirty_digest
    return {"characters": project.get("characters", []), "samples": samples, "archived": archived, "members": members,
            "sample_count": len(samples), "character_count": len(project.get("characters", [])),
            "export": build, "pending": pending,
            "dirty": dirty}


def build_payload(work, name):
    info = read_json(data_dir(work, "builds") / name / "build.json")
    characters = info["characters"]
    sample = "字记，我的生活。" if all(c in characters for c in "字记我的生活") else characters.strip()
    return {"id": name, "unicode_count": info["unicode_count"], "characters": characters, "sample": sample,
            "font": f"/files/builds/{name}/Preview.otf", "proof": f"/files/builds/{name}/proof.png"}


def block_library_payload(work):
    """One character catalog; template placement never consumes a library entry."""
    samples = sample_library(work)
    project = load_live(work)
    indexed = set(project.get('indexed_templates', []))
    used = set(project.get('template_characters', []))
    characters = dict.fromkeys(project.get('characters', []))
    changed = False
    for record in sorted(data_dir(work, 'templates').glob('*/index.json')):
        if record.parent.name in indexed:
            continue
        index, manifests = template_info(work, record.parent.name)
        placed = [c['char'] for m in manifests for c in m['cells'] if c['char']]
        characters.update(dict.fromkeys(placed + index.get('editor_library', [])))
        used.update(placed)
        indexed.add(record.parent.name)
        changed = True
    if changed:
        project['characters'] = list(characters)
        project['indexed_templates'] = sorted(indexed)
        project['template_characters'] = sorted(used)
        save_live(work, project)
    hidden = set(project.get('archived_sample', []))
    formal = {s['char'] for s in samples if s['usable'] and s['id'] not in hidden}
    return {'characters': [{'char': c, 'has_glyph': c in formal, 'used_in_template': c in used}
                           for c in characters]}
