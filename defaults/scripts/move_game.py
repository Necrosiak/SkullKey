"""Move an installed game to another drive, for the stores whose install
location SkullKey records: GOG, Amazon and Epic (game database + the store
tool's own record), the Classics and Discs & Installers (remembered drive).

The copy is made first; records are switched only once it succeeded, and the
old folder is removed last. The Steam shortcut is then refreshed by the
interface from the store's own launch options."""

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "shared"))

RUNTIME = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", os.path.expanduser("~/homebrew/data/SkullKey")))
HOME = Path(os.environ.get("HOME", os.path.expanduser("~")))
DB_STORES = {"GOGActions": ("gog.db", "gog"), "AmazonActions": ("amazon.db", "amazon"), "EpicActions": ("epic.db", "epic")}
MOVABLE = set(DB_STORES) | {"PortsActions", "DisksActions"}
# Store tools that keep their own record of where a game lives.
TOOL_RECORDS = [HOME / ".config" / "legendary" / "installed.json",
                HOME / ".var" / "app" / "com.github.derrod.legendary" / "config" / "legendary" / "installed.json",
                HOME / ".config" / "nile" / "installed.json"]


class MoveError(Exception):
    pass


def _drives():
    import drives
    return drives


def _db_row(set_name, shortname):
    """(db file, install path) — the account database holding this game."""
    name, _ = DB_STORES[set_name]
    for db in sorted(RUNTIME.glob(f"accounts/*/{name}")) + [RUNTIME / name]:
        if not db.exists():
            continue
        try:
            row = sqlite3.connect(db).execute(
                "SELECT InstallPath FROM Game WHERE ShortName=? AND InstallPath IS NOT NULL AND InstallPath<>''",
                (shortname,)).fetchone()
        except sqlite3.Error:
            continue
        if row:
            return db, row[0]
    return None, None


def current_path(set_name, shortname):
    if set_name in DB_STORES:
        return _db_row(set_name, shortname)[1]
    if set_name == "PortsActions":
        return _ports_dir(shortname)
    if set_name == "DisksActions":
        g = json.loads((RUNTIME / "disks" / "state.json").read_text())["games"].get(shortname)
        return g and g.get("root")
    return None


def _ports_dir(shortname):
    import ports
    port = ports.APPS.get(shortname)
    return str(ports.port_dir(port)) if port else None


def target_base(store_key, drive):
    old = os.environ.get("SK_INSTALL_ROOT")
    os.environ["SK_INSTALL_ROOT"] = drive or ""
    try:
        base = _drives().install_dir(store_key, "")
    finally:
        if old is None:
            os.environ.pop("SK_INSTALL_ROOT", None)
        else:
            os.environ["SK_INSTALL_ROOT"] = old
    return base


def _rewrite(obj, old, new):
    if isinstance(obj, dict):
        return {k: _rewrite(v, old, new) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rewrite(v, old, new) for v in obj]
    if isinstance(obj, str) and (obj == old or obj.startswith(old + "/")):
        return new + obj[len(old):]
    return obj


def tool_records():
    return TOOL_RECORDS + sorted(RUNTIME.glob("accounts/*/nile/installed.json")) +         sorted(RUNTIME.glob("accounts/*/legendary/installed.json"))


def rewrite_tool_records(old, new, files=None):
    for f in files or tool_records():
        try:
            data = json.loads(Path(f).read_text())
        except (OSError, ValueError):
            continue
        updated = _rewrite(data, old, new)
        if updated != data:
            tmp = Path(str(f) + ".skullkey")
            tmp.write_text(json.dumps(updated, indent=2))
            tmp.replace(f)


def move(set_name, shortname, drive, default_base):
    """Returns the new path. drive "" = the store's usual folder."""
    if set_name not in MOVABLE:
        raise MoveError("This platform cannot move games.")
    old = current_path(set_name, shortname)
    if not old or not Path(old).is_dir():
        raise MoveError("The game folder was not found.")
    store_key = {"PortsActions": "ports", "DisksActions": "Disques"}.get(set_name) or DB_STORES[set_name][1]
    base = target_base(store_key, drive) or str(default_base) + "/"
    new = str(Path(base) / Path(old).name)
    if os.path.realpath(new) == os.path.realpath(old):
        return old
    if Path(new).exists():
        raise MoveError("A folder with this name already exists on that drive.")
    Path(new).parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(old, new, symlinks=True)
    except Exception as e:
        shutil.rmtree(new, ignore_errors=True)
        raise MoveError(f"The game could not be copied ({type(e).__name__}).") from e
    if set_name in DB_STORES:
        db, _ = _db_row(set_name, shortname)
        con = sqlite3.connect(db)
        con.execute("UPDATE Game SET InstallPath=? WHERE ShortName=?", (new, shortname))
        con.commit()
        rewrite_tool_records(old, new)
    elif set_name == "PortsActions":
        data = _drives()._load_paths()
        data.setdefault("ports", {})[shortname] = new
        _drives()._save_paths(data)
        state_file = RUNTIME / "ports_state.json"
        try:
            state = json.loads(state_file.read_text())
            app = state.get("apps", {}).get(shortname, {})
            if isinstance(app.get("exe"), str) and app["exe"].startswith(old):
                app["exe"] = new + app["exe"][len(old):]
                state_file.write_text(json.dumps(state, indent=1))
        except (OSError, ValueError):
            pass
    elif set_name == "DisksActions":
        state_file = RUNTIME / "disks" / "state.json"
        state = json.loads(state_file.read_text())
        state["games"][shortname]["root"] = new
        for key in ("exe", "installer"):
            v = state["games"][shortname].get(key)
            if isinstance(v, str) and v.startswith(old):
                state["games"][shortname][key] = new + v[len(old):]
        state_file.write_text(json.dumps(state, indent=1))
        data = _drives()._load_paths()
        data.setdefault("Disques", {})[shortname] = new
        _drives()._save_paths(data)
    shutil.rmtree(old, ignore_errors=True)
    return new
