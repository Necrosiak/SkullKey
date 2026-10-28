#!/usr/bin/env python3
"""Find installed games again when their drive comes back at another mount
point.

On Bazzite an extra drive is normally mounted at /run/media/system/<label>,
but Steam's own automount can win the race at boot and use
/run/media/<user>/<label> instead: same drive, new path, and every stored
install folder on it is suddenly missing. When a stored folder is missing and
a drive with the same label is mounted elsewhere with that exact folder on it,
the stored paths are moved to where the drive is now.

Shell usage:  remount.py   → prints the moved mount points as JSON
"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HOME = Path(os.environ.get("DECKY_USER_HOME") or os.path.expanduser("~"))
RUNTIME = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", str(HOME / "homebrew/data/SkullKey")))
# <mount>/<label> as removable-drive managers lay them out.
DRIVE = re.compile(r"^(/run/media/[^/]+|/media/[^/]+|/media|/mnt|/var/mnt)/([^/]+)(/.+)$")
MOUNT_ROOTS = ("/run/media/", "/media/", "/mnt/", "/var/mnt/")
MAX_JSON = 8 << 20


def _mounts():
    out = []
    try:
        with open("/proc/mounts") as f:
            for line in f:
                target = line.split()[1].replace("\\040", " ")
                if target.startswith(MOUNT_ROOTS):
                    out.append(target)
    except OSError:
        pass
    return out


def mounts_signature():
    return "\n".join(sorted(_mounts()))


def _files():
    """State files that keep install folders (SkullKey and its store tools)."""
    found = list(RUNTIME.glob("*.json")) + list(RUNTIME.glob("*/state.json"))
    found += list(RUNTIME.glob("accounts/*/*/*.json")) + list(RUNTIME.glob("accounts/*/*/data/*/*.json"))
    found += [HOME / ".config/legendary/installed.json", HOME / ".config/nile/installed.json",
              HOME / ".var/app/com.github.derrod.legendary/config/legendary/installed.json"]
    return [f for f in dict.fromkeys(found) if f.is_file() and f.stat().st_size < MAX_JSON]


def _strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, str):
        yield obj


def _db_paths(db):
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
        try:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='Game'").fetchone():
                return []
            cols = [r[1] for r in con.execute("PRAGMA table_info(Game)")]
            if "InstallPath" not in cols:
                return []
            return [r[0] for r in con.execute("SELECT InstallPath FROM Game WHERE InstallPath LIKE '/%'")]
        finally:
            con.close()
    except sqlite3.Error:
        return []


def relocation(path, mounts):
    """(old base, new base) when path's drive is now mounted elsewhere."""
    m = DRIVE.match(path)
    if not m or os.path.exists(path):
        return None
    root, label, rest = m.groups()
    old = f"{root}/{label}"
    if os.path.ismount(old):
        return None  # the drive is still there: the folder is really gone
    hits = [t for t in mounts if os.path.basename(t) == label and t != old and os.path.exists(t + rest)]
    return (old, hits[0]) if len(hits) == 1 else None


def _rewrite(obj, moves):
    if isinstance(obj, dict):
        return {k: _rewrite(v, moves) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rewrite(v, moves) for v in obj]
    if isinstance(obj, str):
        for old, new in moves.items():
            if obj == old or obj.startswith(old + "/"):
                return new + obj[len(old):]
    return obj


def heal():
    """Rewrite stored paths of drives that moved. Returns {old: new}."""
    mounts = _mounts()
    if not mounts:
        return {}
    files = _files()
    dbs = sorted(RUNTIME.glob("*.db"))
    loaded, moves = {}, {}
    for f in files:
        try:
            loaded[f] = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
    for source in [list(_strings(d)) for d in loaded.values()] + [_db_paths(db) for db in dbs]:
        for s in source:
            if s.startswith(MOUNT_ROOTS) and not any(s == o or s.startswith(o + "/") for o in moves):
                hit = relocation(s, mounts)
                if hit:
                    moves[hit[0]] = hit[1]
    if not moves:
        return {}
    for f, data in loaded.items():
        updated = _rewrite(data, moves)
        if updated != data:
            st = f.stat()
            tmp = Path(str(f) + ".skullkey")
            tmp.write_text(json.dumps(updated, indent=2))
            os.chmod(tmp, st.st_mode & 0o7777)
            if os.geteuid() == 0:
                os.chown(tmp, st.st_uid, st.st_gid)
            tmp.replace(f)
    for db in dbs:
        if not _db_paths(db):
            continue
        try:
            con = sqlite3.connect(db, timeout=5)
            with con:
                for old, new in moves.items():
                    con.execute("UPDATE Game SET InstallPath=?||substr(InstallPath, ?) "
                                "WHERE InstallPath=? OR InstallPath LIKE ? ESCAPE '\\'",
                                (new, len(old) + 1, old, old.replace("%", r"\%").replace("_", r"\_") + "/%"))
            con.close()
        except sqlite3.Error:
            pass
    return moves


if __name__ == "__main__":
    json.dump(heal(), sys.stdout)
    print()
