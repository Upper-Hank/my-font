"""One on-disk layout for application data, with a one-way legacy migration."""
from pathlib import Path
import threading

# Logical names stay in URLs and APIs. Physical folders are grouped by role.
_LAYOUT = {
    'glyphs': 'assets/glyphs',
    'templates': 'assets/templates',
    'runs': 'history/conversions',
    'staging': 'history/previews',
    'builds': 'exports',
    'live': 'state',
    'uploads': 'cache/uploads',
    'projects': 'legacy/projects',
}
_EXPERIMENTS = ('demo', 'web-demo', 'photo-trial')
_LOCK = threading.RLock()


def _move(source, target):
    if source.is_symlink() or target.is_symlink():
        raise ValueError('数据目录不能是符号链接。')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        source.rename(target)
        return
    if source.is_file() or target.is_file():
        raise ValueError(f'数据迁移发现同名文件，未覆盖：{target}')
    for child in source.iterdir():
        _move(child, target / child.name)
    source.rmdir()


def data_dir(work, kind):
    work = Path(work)
    target = work / _LAYOUT[kind]
    with _LOCK:
        old = work / kind
        if old.exists() or old.is_symlink():
            _move(old, target)
    return target


def migrate_storage(work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    for kind in _LAYOUT:
        data_dir(work, kind).mkdir(parents=True, exist_ok=True)
    for name in _EXPERIMENTS:
        old = work / name
        if old.exists():
            _move(old, work / 'legacy/experiments' / name)
    extra = work / 'web-verification.json'
    if extra.exists():
        _move(extra, work / 'legacy' / extra.name)


def file_path(work, relative):
    """Resolve existing logical download URLs into the on-disk layout."""
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or '..' in parts:
        raise ValueError('文件路径无效。')
    if parts[0] in _LAYOUT:
        return data_dir(work, parts[0]).joinpath(*parts[1:])
    return Path(work).joinpath(*parts)
