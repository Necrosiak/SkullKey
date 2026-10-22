"""Downloads in progress across every store, for the Downloads page.

Each store already writes its own progress (JSON files, or gogdl/legendary/
nile logs). This only reads them: an entry is "active" while it is not
finished and its file changed recently, or its worker process is alive.
Prints a JSON list: [{store, id, title, pct, desc, error}]"""

import glob
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "shared"))
RUNTIME = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", os.path.expanduser("~/homebrew/data/SkullKey")))
LOGS = Path(os.environ.get("DECKY_PLUGIN_LOG_DIR", os.path.expanduser("~/homebrew/logs/SkullKey")))
RECENT = 120  # seconds without a progress update before an entry counts as stale


def _alive(pid):
    try:
        return bool(pid) and os.path.exists(f"/proc/{int(pid)}")
    except (TypeError, ValueError):
        return False


def _fresh(path):
    try:
        return time.time() - os.path.getmtime(path) < RECENT
    except OSError:
        return False


def _json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def _running(data, path):
    if not isinstance(data, dict) or data.get("Error") or data.get("error"):
        return False
    pct = data.get("Percentage", data.get("pct", 0)) or 0
    if pct >= 100 or data.get("done"):
        return False
    return _alive(data.get("pid")) or _fresh(path)


def _entry(store, gid, title, data):
    return {"store": store, "id": gid, "title": title or gid,
            "pct": float(data.get("Percentage", data.get("pct", 0)) or 0),
            "desc": data.get("Description", data.get("desc", "")) or ""}


def xbox():
    out = []
    state = _json(RUNTIME / "xbox" / "state.json") or {}
    names = {k: v.get("title") for k, v in {**(state.get("games") or {}), **(state.get("pending") or {})}.items()}
    for f in glob.glob(str(RUNTIME / "xbox" / "progress" / "*.json")):
        d = _json(f)
        if _running(d, f):
            gid = Path(f).stem
            out.append(_entry("xbox", gid, names.get(gid), d))
    return out


def ports():
    out = []
    try:
        import ports as p
        names = {k: v["title"] for k, v in p.APPS.items()}
    except Exception:
        names = {}
    for f in glob.glob(str(RUNTIME / "ports_progress" / "*.json")):
        d = _json(f)
        if _running(d, f):
            gid = Path(f).stem
            out.append(_entry("ports", gid, names.get(gid), d))
    return out


def mihoyo():
    out = []
    cat = _json(RUNTIME / "mihoyo_catalog.json") or {}
    names = {}
    for g in (cat.get("games") if isinstance(cat, dict) else cat) or []:
        if isinstance(g, dict) and g.get("biz"):
            names[g["biz"]] = (g.get("display") or {}).get("name") or g.get("name")
    for f in glob.glob(str(RUNTIME / "mihoyo_progress_*.json")):
        d = _json(f)
        if _running(d, f):
            gid = Path(f).stem.replace("mihoyo_progress_", "")
            out.append(_entry("mihoyo", gid, names.get(gid), d))
    return out


def disks():
    out = []
    state = _json(RUNTIME / "disks" / "state.json") or {}
    for f in glob.glob(str(RUNTIME / "disks" / "progress" / "*.json")):
        d = _json(f)
        if _running(d, f):
            gid = Path(f).stem
            out.append(_entry("disks", gid, ((state.get("games") or {}).get(gid) or {}).get("title"), d))
    return out


def ea():
    out = []
    for f in glob.glob(str(RUNTIME / "accounts" / "*" / "ea" / "job-*.json")):
        d = _json(f)
        if not d or not d.get("active"):
            continue
        if d.get("worker_pid") and not _alive(d["worker_pid"]):
            continue
        gid = Path(f).stem[4:]
        st = _json(Path(f).parent / "state.json") or {}
        title = next((g.get("name") for g in st.get("games") or [] if g.get("slug") == gid), None)
        out.append(_entry("ea", gid, title, d))
    return out


# legendary / gogdl / nile write "<shortname>.progress" logs in the log folder.
LOG_STORES = (("epic", "epic.db", "epic", "Epic"), ("gog", "gog.db", "gog", "Gog"), ("amazon", "amazon.db", "amazon", "Amazon"))


def _db_titles(dbname):
    names = {}
    for db in glob.glob(str(RUNTIME / "accounts" / "*" / dbname)) + [str(RUNTIME / dbname)]:
        try:
            for sn, title in sqlite3.connect(db).execute("SELECT ShortName, Name FROM Game"):
                names.setdefault(sn, title)
        except sqlite3.Error:
            pass
    return names


def log_stores():
    out = []
    files = [f for f in glob.glob(str(LOGS / "*.progress")) if _fresh(f)]
    if not files:
        return out
    for store, dbname, module, cls in LOG_STORES:
        names = _db_titles(dbname)
        mine = [f for f in files if Path(f).stem in names]
        if not mine:
            continue
        try:
            mod = __import__(module)
            parse = getattr(mod, {"Gog": "Gog", "Epic": "Epic", "Amazon": "Amazon"}[cls]).get_last_progress_update
        except Exception:
            continue
        for f in mine:
            try:
                d = parse(None, f) or {}
            except Exception:
                continue
            if _running(dict(d, pid=None), f):
                out.append(_entry(store, Path(f).stem, names[Path(f).stem], d))
    return out


# Folder each store installs a game into (where we can tell).
def _dest_path(store, gid):
    try:
        import drives
        if store == "xbox":
            st = _json(RUNTIME / "xbox" / "state.json") or {}
            g = (st.get("pending") or {}).get(gid) or (st.get("games") or {}).get(gid) or {}
            return g.get("root")
        if store == "ports":
            import ports as p
            return str(p.port_dir(p.APPS[gid])) if gid in p.APPS else None
        if store == "disks":
            st = _json(RUNTIME / "disks" / "state.json") or {}
            return ((st.get("games") or {}).get(gid) or {}).get("root")
        if store == "mihoyo":
            return drives.game_path("mihoyo", gid, os.path.expanduser(f"~/Games/mihoyo/{gid}"))
        if store in ("epic", "gog", "amazon", "ea"):
            key = {"epic": "epic", "gog": "gog", "amazon": "amazon", "ea": "ea"}[store]
            return drives.game_path(key, gid, os.path.expanduser(f"~/Games/{key}"))
    except Exception:
        return None
    return None


def dest_label(path):
    """Name of the drive holding path: its volume label, or "System"."""
    if not path:
        return ""
    try:
        import drives
        best = None
        for d in drives.list_drives():
            if path == d["path"] or path.startswith(d["path"].rstrip("/") + "/"):
                if best is None or len(d["path"]) > len(best["path"]):
                    best = d
        return best["label"] if best else ""
    except Exception:
        return ""


def active():
    out = []
    for fn in (xbox, ports, mihoyo, disks, ea, log_stores):
        try:
            out += fn()
        except Exception as e:  # one store failing never hides the others
            print(f"downloads: {fn.__name__}: {e!r}", file=sys.stderr)
    for e in out:
        e["dest"] = dest_label(_dest_path(e["store"], e["id"]))
    return out


if __name__ == "__main__":
    print(json.dumps(active()))
