"""Independent sample library and a persistent export selection."""
from __future__ import annotations

import re
import shutil
import threading

from pathlib import Path

from .storage import data_dir
from .adjust import adjust_glyph, adjustment_options
from .common import PRODUCT_EN, PRODUCT_ZH, OutputDirectory, read_json, write_json, digest, parse_cells, parse_one_cell, glyph_name
from .template import SYSTEM_PAPER_ID

_IMPORT_LOCK = threading.RLock()
_ARCHIVE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
_ARCHIVE_FILES = {
    'template': ('templates', 'index.json', '模板'),
    'preview': ('staging', 'preview.json', '照片预览'),
    'run': ('runs', 'run.json', '切字批次'),
}


def empty_project(title, family=PRODUCT_EN):
    return {"schema": 1, "title": (title or PRODUCT_ZH).strip()[:80] or PRODUCT_ZH,
            "family": (family or PRODUCT_EN).strip()[:64] or PRODUCT_EN,
            "members": []}


def member_from(glyph, run_name, template=""):
    return {"char": glyph["char"], "unicode": glyph["unicode"], "run": run_name,
            "sample_id": glyph["sample_id"], "template": template,
            **({"adjustment": glyph["adjustment"]} if glyph.get("adjustment") else {})}


def resolve_glyph(work, member, adjusted=True):
    import_run(work, member["run"])
    run_folder = data_dir(work, "glyphs") / member["run"]
    run = read_json(run_folder / "run.json")
    for glyph in run["glyphs"]:
        if glyph["sample_id"] == member["sample_id"]:
            row = dict(glyph)
            row["run_folder"] = str(run_folder)
            row["run_id"] = run["run_id"]
            row["cell_mm"] = run["cell_mm"]
            if adjusted:
                identifier = f"{member['run']}/{member['sample_id']}"
                options = load_live(work).get('adjustments', {}).get(identifier, row.get('adjustment'))
                return adjust_glyph(row, options)
            return row
    raise ValueError(f"项目里的字「{member['char']}」找不到对应字形文件。")


def live_dir(work):
    return data_dir(work, "live")


def ensure_live(work):
    folder = live_dir(work)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "font.json"
    if not path.is_file():
        write_json(path, empty_project(PRODUCT_ZH))
    return folder


def load_live(work):
    project = read_json(ensure_live(work) / "font.json")
    if project.get("title") == "字己":
        project["title"] = PRODUCT_ZH
        save_live(work, project)
    return project


def save_live(work, project):
    folder = ensure_live(work)
    temporary = folder / "font.json.tmp"
    write_json(temporary, project)
    temporary.replace(folder / "font.json")


def bootstrap_live(work):
    """If the live font is empty, adopt members from the newest leftover project."""
    live = load_live(work)
    if live.get("library_migrated"):
        return live
    live["library_migrated"] = True
    save_live(work, live)
    if live["members"]:
        return live
    projects = data_dir(work, "projects")
    if not projects.is_dir():
        return live
    choices = sorted((p for p in projects.iterdir() if (p / "project.json").is_file()),
                     key=lambda p: (p / "project.json").stat().st_mtime, reverse=True)
    if not choices:
        return live
    data = read_json(choices[0] / "project.json")
    if data.get("members"):
        live["members"] = data["members"]
        save_live(work, live)
    return live


def import_run(work, name):
    with _IMPORT_LOCK:
        return _import_run(work, name)


def _import_run(work, name):
    """Copy sample assets once; retained IDs are identities, not run dependencies."""
    if not _ARCHIVE_ID.fullmatch(name):
        raise ValueError("字形编号无效。")
    source = data_dir(work, "runs") / name
    target = data_dir(work, "glyphs") / name
    if (target / "run.json").is_file():
        return target
    run = read_json(source / "run.json")
    if run.get("review_pending"):
        return target
    run["glyphs"] = reviewed_glyphs(run)
    deleted = set(load_live(work).get("deleted_sample", []))
    run["glyphs"] = [g for g in run["glyphs"] if f"{name}/{g['sample_id']}" not in deleted]
    with OutputDirectory(target) as output:
        for glyph in run["glyphs"]:
            sample = glyph["sample_id"]
            if not _ARCHIVE_ID.fullmatch(sample):
                raise ValueError("字形编号无效。")
            assets = source / sample
            if not assets.is_dir() or not (assets / "gray.png").is_file():
                raise ValueError(f"字形 {sample} 的图片缺失，未清理转换记录。")
            shutil.copytree(assets, output / sample)
        write_json(output / "run.json", {"schema": 1, "run_id": run["run_id"],
                   "cell_mm": run["cell_mm"], "glyphs": run["glyphs"]})
    return target


def migrate_samples(work):
    pending = load_live(work).get("pending_sample_deletions", [])
    if pending:
        delete_samples(work, pending)
    for source in sorted((data_dir(work, "runs")).glob("*/run.json")):
        import_run(work, source.parent.name)


def sample_library(work):
    """The library owns its images and outlines independently of tool history."""
    migrate_samples(work)
    samples = []
    live = load_live(work)
    overrides = live.get("adjustments", {})
    deleted = set(live.get("deleted_sample", []))
    for record in sorted((data_dir(work, "glyphs")).glob("*/run.json"), reverse=True):
        folder = record.parent
        run = read_json(record)
        for glyph in run["glyphs"]:
            if f"{folder.name}/{glyph['sample_id']}" in deleted:
                continue
            base = f"/files/glyphs/{folder.name}/{glyph['sample_id']}"
            samples.append({**member_from(glyph, folder.name),
                "id": f"{folder.name}/{glyph['sample_id']}",
                "status": glyph["status"],
                "usable": glyph["status"] == "review" and bool(glyph.get("commands")),
                "gray": base + "/gray.png", "binary": base + "/binary.png",
                "adjustment": adjustment_options(overrides.get(f"{folder.name}/{glyph['sample_id']}", glyph.get('adjustment'))),
                "vector": "/api/glyph-preview?sample=" + f"{folder.name}/{glyph['sample_id']}" + "&v=" + digest(overrides.get(f"{folder.name}/{glyph['sample_id']}", glyph.get("adjustment")))})
    project = load_live(work)
    hidden = set(project.get('archived_sample', []))
    chars = list(dict.fromkeys(project.get('characters', []) + [s['char'] for s in samples if s['id'] not in hidden]))
    if project.get('characters') != chars:
        project['characters'] = chars
        save_live(work, project)
    return samples


def _retain_run_assets(work, name):
    """Copy conversion samples into the glyph library, then the conversion can be deleted."""
    source = data_dir(work, "runs") / name
    target = data_dir(work, "glyphs") / name
    run = read_json(source / "run.json")
    if run.get("review_pending"):
        return target
    run["glyphs"] = reviewed_glyphs(run)
    deleted = set(load_live(work).get("deleted_sample", []))
    glyphs = [g for g in run["glyphs"] if f"{name}/{g['sample_id']}" not in deleted]
    target.mkdir(parents=True, exist_ok=True)
    for glyph in glyphs:
        sample = glyph["sample_id"]
        assets = source / sample
        if not assets.is_dir() or not (assets / "gray.png").is_file():
            raise ValueError(f"字形 {sample} 的图片缺失，未清理转换记录。")
        dest = target / sample
        # Refresh source images without deleting library-owned stroke drafts.
        shutil.copytree(assets, dest, dirs_exist_ok=True)
    temporary = target / "run.json.tmp"
    write_json(temporary, {"schema": 1, "run_id": run["run_id"], "cell_mm": run["cell_mm"], "glyphs": glyphs})
    temporary.replace(target / "run.json")
    return target


def cleanup_history(work, kind, identifier):
    """Delete a template, unfinished photo task, or completed conversion after confirmation."""
    work = Path(work)
    if kind not in _ARCHIVE_FILES or not _ARCHIVE_ID.fullmatch(identifier):
        raise ValueError("历史记录编号无效。")
    if kind == "template" and identifier == SYSTEM_PAPER_ID:
        raise ValueError("通用书写纸是系统模板，不能删除。")
    folder, marker, _ = _ARCHIVE_FILES[kind]
    source = data_dir(work, folder) / identifier
    project = load_live(work)
    archived = set(project.get('archived_' + kind, []))
    if not (source / marker).is_file():
        project['archived_' + kind] = sorted(archived - {identifier})
        save_live(work, project)
        return
    if kind == "run":
        if not read_json(source / marker).get("review_pending"):
            _retain_run_assets(work, identifier)
        staging = data_dir(work, "staging") / identifier
        if staging.is_dir():
            shutil.rmtree(staging)
    elif kind == "template":
        for record in (data_dir(work, "staging")).glob("*/preview.json"):
            preview = read_json(record)
            if preview.get("template") == identifier:
                snapshot = record.parent / "template"
                if not snapshot.exists():
                    with OutputDirectory(snapshot) as output:
                        for path in source.glob("*.json"):
                            shutil.copyfile(path, output / path.name)
    shutil.rmtree(source)
    project = load_live(work)
    project['archived_' + kind] = [value for value in project.get('archived_' + kind, []) if value != identifier]
    save_live(work, project)


def _sample_ids(identifiers):
    if not isinstance(identifiers, list) or not identifiers or len(identifiers) > 10000:
        raise ValueError('请选择要删除的字形。')
    picked = []
    for identifier in identifiers:
        if not isinstance(identifier, str):
            raise ValueError('字形编号无效。')
        parts = identifier.split('/')
        if len(parts) != 2 or not all(_ARCHIVE_ID.fullmatch(p) for p in parts):
            raise ValueError('字形编号无效。')
        picked.append(identifier)
    return set(picked)


def trash_samples(work, identifiers):
    picked = _sample_ids(identifiers)
    if not picked.issubset({s['id'] for s in sample_library(work)}):
        raise ValueError('字形不存在，请刷新后重试。')
    project = load_live(work)
    project['archived_sample'] = sorted(set(project.get('archived_sample', [])) | picked)
    project['members'] = [m for m in project['members'] if f"{m['run']}/{m['sample_id']}" not in picked]
    save_live(work, project)


def _purge_sample_files(work, picked):
    for name in {identifier.split('/')[0] for identifier in picked}:
        for kind in ('glyphs', 'runs'):
            folder = data_dir(work, kind) / name
            record = folder / 'run.json'
            if record.is_file():
                data = read_json(record)
                data['glyphs'] = [g for g in data['glyphs'] if f"{name}/{g['sample_id']}" not in picked]
                temporary = folder / 'run.json.tmp'
                write_json(temporary, data)
                temporary.replace(record)
            for identifier in picked:
                batch, sample = identifier.split('/')
                if batch == name and (folder / sample).exists():
                    shutil.rmtree(folder / sample)
            if kind == 'glyphs' and record.is_file() and not read_json(record).get('glyphs'):
                shutil.rmtree(folder)


def delete_samples(work, identifiers):
    """Purge only trashed samples. Tombstones prevent reimport after interruption."""
    picked = _sample_ids(identifiers)
    project = load_live(work)
    trash = set(project.get('archived_sample', []))
    deleted = set(project.get('deleted_sample', []))
    for identifier in picked:
        if identifier not in trash and identifier not in deleted:
            raise ValueError('请先将字形移入回收站，再永久删除。')
    project['deleted_sample'] = sorted(deleted | picked)
    project['pending_sample_deletions'] = sorted(set(project.get('pending_sample_deletions', [])) | picked)
    project['members'] = [m for m in project['members'] if f"{m['run']}/{m['sample_id']}" not in picked]
    # Publish deletion intent first; interrupted file deletion can be retried safely.
    save_live(work, project)
    _purge_sample_files(work, picked)
    project = load_live(work)
    project['archived_sample'] = sorted(set(project.get('archived_sample', [])) - picked)
    project['pending_sample_deletions'] = [value for value in project.get('pending_sample_deletions', []) if value not in picked]
    save_live(work, project)


def select_sample(work, sample_id, remove=False):
    samples = {s["id"]: s for s in sample_library(work)}
    if sample_id not in samples:
        raise ValueError("字形样本不存在。")
    sample = samples[sample_id]
    if not remove and sample_id in load_live(work).get("archived_sample", []):
        raise ValueError("请先从回收站恢复这个样本。")
    if not remove and not sample["usable"]:
        raise ValueError("这个样本不能导出，请检查切字结果。")
    project = load_live(work)
    members = [m for m in project["members"]
               if (f"{m['run']}/{m['sample_id']}" != sample_id if remove else m["char"] != sample["char"])]
    if not remove:
        member = member_from(sample, sample["run"])
        ident = f"{member['run']}/{member['sample_id']}"
        adj = (project.get("adjustments") or {}).get(ident)
        if adj:
            member["adjustment"] = adj
        members.append(member)
    project["members"] = members
    save_live(work, project)


def export_selection(work):
    """Publish a completed immutable build by atomically updating its pointer."""
    from .build import compile_glyphs
    from .common import digest
    import uuid
    project = load_live(work)
    if not project["members"]:
        raise ValueError("请先选择至少一个字形用于导出。")
    rows = [resolve_glyph(work, m) for m in project["members"]]
    stamp = digest(project["members"])
    name = "export-" + uuid.uuid4().hex[:12]
    folder = data_dir(work, "builds") / name
    compile_glyphs(rows, folder, project.get("family") or PRODUCT_EN, stamp)
    project["export"] = {"id": name, "selection": stamp, "members": export_member_snapshot(project["members"])}
    save_live(work, project)
    return name


def export_member_snapshot(members):
    return [{"char": m["char"], "run": m["run"], "sample_id": m["sample_id"],
             **({"adjustment": m["adjustment"]} if m.get("adjustment") else {})} for m in members]


def font_pending(members, exported_members, adjustments=None):
    if not exported_members:
        return {"added": [], "removed": [], "replaced": []}
    current = {m["char"]: m for m in members}
    previous = {m["char"]: m for m in exported_members}
    added = sorted(char for char in current if char not in previous)
    removed = sorted(char for char in previous if char not in current)
    if not any("sample_id" in item for item in exported_members):
        return {"added": added, "removed": removed, "replaced": []}
    replaced = sorted(char for char in current if char in previous
                      and member_sig(current[char], adjustments) != member_sig(previous[char]))
    return {"added": added, "removed": removed, "replaced": replaced}


def member_sig(member, adjustments=None):
    ident = f"{member.get('run')}/{member.get('sample_id')}"
    if adjustments is not None and ident in adjustments:
        adj = adjustments.get(ident) or {}
    else:
        adj = member.get("adjustment") or {}
    return (member.get("run"), member.get("sample_id"), adjustment_options(adj))


def archive_item(work, kind, identifier, restore=False):
    """Reversible visibility changes; original files stay intact."""
    project = load_live(work)
    if kind == 'sample':
        if identifier not in {s['id'] for s in sample_library(work)}:
            raise ValueError('样本不存在。')
    elif kind in _ARCHIVE_FILES:
        folder, marker, label = _ARCHIVE_FILES[kind]
        if not _ARCHIVE_ID.fullmatch(identifier):
            raise ValueError(f'{label}编号无效。')
        if kind == 'template' and identifier == SYSTEM_PAPER_ID:
            raise ValueError('通用书写纸是系统模板，不能删除。')
        if not (data_dir(work, folder) / identifier / marker).is_file():
            raise ValueError(f'{label}不存在。')
    else:
        raise ValueError('不支持的回收类型。')
    project = load_live(work)
    key = 'archived_' + kind
    archived = set(project.get(key, []))
    if restore:
        archived.discard(identifier)
    else:
        archived.add(identifier)
        if kind == 'sample':
            project['members'] = [m for m in project['members']
                                  if f"{m['run']}/{m['sample_id']}" != identifier]
    project[key] = sorted(archived)
    save_live(work, project)


def manage_characters(work, text, remove=False):
    if not isinstance(text, str) or len(text) > 50000:
        raise ValueError('字符列表无效或过长。')
    chars = list(dict.fromkeys(parse_cells(text)))
    samples = sample_library(work)
    project = load_live(work)
    if remove:
        picked = set(chars)
        ids = {s['id'] for s in samples if s['char'] in picked}
        project['archived_sample'] = sorted(set(project.get('archived_sample', [])) | ids)
        project['characters'] = [c for c in project.get('characters', []) if c not in picked]
        project['members'] = [m for m in project['members'] if m['char'] not in picked]
    else:
        project['characters'] = list(dict.fromkeys(project.get('characters', []) + chars))
    save_live(work, project)


def reviewed_glyphs(run):
    choices = run.get('review_choices')
    if choices is None:
        return run['glyphs']
    by_id = {c['sample_id']: c for c in choices if c['keep']}
    rows = [{**g, 'char': by_id[g['sample_id']]['char'],
             'unicode': f"{ord(by_id[g['sample_id']]['char']):04X}",
             'glyph_name': glyph_name(by_id[g['sample_id']]['char']),
             'adjustment': adjustment_options(by_id[g['sample_id']].get('adjustment'))}
            for g in run['glyphs'] if g['sample_id'] in by_id]
    # Generic crops have no Latin spacing until their character is confirmed.
    from .trace import bounds, shift
    for row in rows:
        if row.get('matching_required') and row.get('commands') and ord(row['char']) < 128:
            box = bounds(row['commands'])
            if box:
                dx = 60 - box[0]
                row['commands'] = shift(row['commands'], dx)
                row['width'] = round(box[2] - box[0] + 120)
                row['spacing_shift'] = dx
                row['image_transform'] = list(row['image_transform'])
                row['image_transform'][4] += dx
        row['matching_required'] = False
    return rows


def review_run(work, name, choices, commit=False):
    if not isinstance(name, str) or not _ARCHIVE_ID.fullmatch(name):
        raise ValueError('转换编号无效。')
    record = data_dir(work, 'runs') / name / 'run.json'
    run = read_json(record)
    if not run.get('review_pending'):
        # A repeated confirmation must never create duplicate glyphs.
        import_run(work, name)
        return
    if not isinstance(choices, list) or len(choices) != len(run['glyphs']):
        raise ValueError('请检查完整的转换结果。')
    expected = {g['sample_id'] for g in run['glyphs']}
    checked = []
    for choice in choices:
        if not isinstance(choice, dict) or choice.get('sample_id') not in expected or not isinstance(choice.get('keep'), bool):
            raise ValueError('整理结果无效。')
        expected.remove(choice['sample_id'])
        char = choice.get('char')
        if not isinstance(char, str):
            raise ValueError('请填写对应字符。')
        glyph = next(g for g in run['glyphs'] if g['sample_id'] == choice['sample_id'])
        if commit and choice['keep'] and glyph.get('matching_required') and choice.get('confirmed') is not True:
            raise ValueError('请逐字确认匹配结果后再加入字符库。')
        if commit and choice['keep'] and not glyph.get('commands'):
            raise ValueError('空白字格不能加入字符库。')
        normalized = parse_one_cell(char) if char else ''
        if commit and choice['keep'] and not normalized:
            raise ValueError('请填写要保留字形的对应字符。')
        checked.append({**choice, 'char': normalized, **({'adjustment': adjustment_options(choice['adjustment'])} if 'adjustment' in choice else {})})
    run['review_choices'] = checked
    run['review_pending'] = not commit
    temporary = record.with_suffix('.json.tmp')
    write_json(temporary, run)
    temporary.replace(record)
    if commit:
        import_run(work, name)
        sample_library(work)


def set_adjustment(work, identifiers, options):
    picked = _sample_ids(identifiers)
    opts = adjustment_options(options)
    samples = {s['id']: s for s in sample_library(work)}
    project = load_live(work)
    hidden = set(project.get('archived_sample', []))
    if any(identifier not in samples or identifier in hidden or not samples[identifier]['usable'] for identifier in picked):
        raise ValueError('请选择可用的正式字形进行修正。')
    project.setdefault('adjustments', {}).update({identifier: opts for identifier in picked})
    for member in project['members']:
        if f"{member['run']}/{member['sample_id']}" in picked:
            member['adjustment'] = opts
    save_live(work, project)
