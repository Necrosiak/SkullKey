#!/usr/bin/env python3
"""Discs & Installers: install Windows games from the user's own discs, disc
images, offline installers or ready-to-play folders, and turn each into a
Steam shortcut (Proton, shortcut prefix).

⚖️ Légalité — l'onglet installe ce que l'utilisateur possède (son disque, son
image, son installeur hors ligne). Aucune gestion de crack, d'émulateur Steam,
de patch « no-CD » ni de contournement de protection anticopie : ne jamais en
ajouter ici.

Flow: add (worker: extract or copy) → install (installer runs as the game's
Steam shortcut) → finalize (exe candidates from the prefix diff) → setexe →
install again (shortcut repointed to the game exe)."""

import json
import os
import pwd
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "shared"))

import disks_exe
import disks_extract
import disks_scan

HOME = Path(os.path.expanduser("~"))
RUNTIME_DIR = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                                  str(HOME / "homebrew/data/SkullKey")))
DATA_DIR = RUNTIME_DIR / "disks"
STATE_FILE = DATA_DIR / "state.json"
PROGRESS_DIR = DATA_DIR / "progress"
STORE = "Disques"
DEFAULT_BASE = HOME / "Games" / STORE
PYEXE = sys.executable or "/usr/bin/python3"


def emit(kind, content):
    print(json.dumps({"Type": kind, "Content": content}))


def error(message):
    emit("Error", {"Message": message})


# ── state ────────────────────────────────────────────────────────────────────

def load_state():
    try:
        state = json.loads(STATE_FILE.read_text())
    except Exception:
        state = {}
    state.setdefault("games", {})
    state.setdefault("last_scan_dir", "")
    return state


def save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(STATE_FILE)


def update_game(slug, **fields):
    state = load_state()
    if slug in state["games"]:
        state["games"][slug].update(fields)
        save_state(state)


def write_progress(slug, pct, desc, error_text=None):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    (PROGRESS_DIR / f"{slug}.json").write_text(json.dumps(
        {"Percentage": pct, "Description": desc, "Error": error_text, "pid": os.getpid()}))


# ── paths, ownership, prefixes ───────────────────────────────────────────────

def _drives():
    import drives
    return drives


def _user_ids():
    try:
        user = pwd.getpwnam(os.path.basename(str(HOME)))
        return user.pw_uid, user.pw_gid
    except KeyError:
        return None


def give_to_user(path):
    """Decky actions run as root, games as the player: hand our files over."""
    ids = _user_ids()
    if not ids or os.geteuid() != 0:
        return
    for dirpath, dirnames, filenames in os.walk(path):
        for name in [dirpath] + [os.path.join(dirpath, n) for n in dirnames + filenames]:
            try:
                os.lchown(name, *ids)
            except OSError:
                pass


def game_root(slug):
    return Path(_drives().assign(STORE, slug, DEFAULT_BASE / slug))


def compat_dir(steam_id):
    override = os.environ.get("SK_DISKS_COMPAT_ROOT")
    if override:
        return Path(override) / str(steam_id)
    import prefixes
    return Path(prefixes.compat_dir(steam_id))


def prefix_env(slug):
    if os.environ.get("SK_DISKS_COMPAT_ROOT"):
        return ""
    import prefixes
    return prefixes.env_for(STORE, slug)


def _inside(path, base):
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except ValueError:
        return False


# ── sources ──────────────────────────────────────────────────────────────────

def action_sources():
    state = load_state()
    emit("DiskSources", {"optical": disks_scan.optical_volumes(),
                         "unmounted": disks_scan.unmounted_optical_devices(),
                         "last_scan_dir": state["last_scan_dir"]})


def action_mount(device):
    point = disks_scan.mount_optical(device)
    if point:
        emit("Success", {"Message": point})
    else:
        error("This disc could not be mounted.")


def action_scan(folder):
    if not os.path.isdir(folder):
        return error("This folder does not exist.")
    state = load_state()
    state["last_scan_dir"] = folder
    save_state(state)
    emit("DiskScan", {"entries": disks_scan.scan_folder(folder)})


# ── add + worker ─────────────────────────────────────────────────────────────

def action_add(payload):
    req = json.loads(payload)
    kind, path = req.get("kind"), req.get("path", "")
    if kind not in ("image", "optical", "installer", "folder", "ready") or not os.path.exists(path):
        return error("This source cannot be found.")
    title = (req.get("title") or disks_scan.clean_title(path)).strip()
    state = load_state()
    slug = disks_scan.make_slug(title, set(state["games"]))
    root = game_root(slug)
    state["games"][slug] = {"title": title, "slug": slug, "source_kind": kind, "source": path,
                            "parts": req.get("parts") or [path], "root": str(root),
                            "installer": "", "exe": "", "steamClientID": "", "stage": "preparing",
                            "snapshot": [], "created": time.time()}
    save_state(state)
    write_progress(slug, 0, "Preparing…")
    subprocess.Popen([PYEXE, os.path.abspath(__file__), "worker", slug], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ.copy())
    emit("Progress", {"Message": "Preparing", "ShortName": slug})


def _copy_tree(src, dest, slug):
    files = [Path(d) / f for d, _, fs in os.walk(src) for f in fs]
    total = max(len(files), 1)
    for i, f in enumerate(files, start=1):
        target = Path(dest) / f.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        if i % 20 == 0 or i == total:
            write_progress(slug, round(90 * i / total), "Copying game files…")


def worker(slug):
    g = load_state()["games"][slug]
    root = Path(g["root"])
    try:
        root.mkdir(parents=True, exist_ok=True)
        kind, source = g["source_kind"], Path(g["source"])
        installer = ""
        if kind == "installer":
            installer = str(source)
        elif kind == "image":
            dirs = disks_extract.extract_images(
                g["parts"], str(root / "_extract"),
                progress=lambda p: write_progress(slug, round(p * 0.9), "Extracting disc image…"))
            found = disks_scan.find_installers(dirs[0])
            if found:
                installer = found[0]
            else:
                _copy_tree(dirs[0], root / "game", slug)
        elif kind == "ready":               # ready to play: never run a setup
            found = []
            _copy_tree(source, root / "game", slug)
        else:                               # optical disc or folder
            found = disks_scan.find_installers(source)
            if found:
                installer = found[0]
            else:
                _copy_tree(source, root / "game", slug)
        give_to_user(root)
        update_game(slug, installer=installer, stage="needs-installer" if installer else "ready")
        write_progress(slug, 100, "Ready")
    except disks_extract.NotEnoughSpace as e:
        _fail(slug, root, f"Not enough free space: {e.needed // (1 << 20)} MB needed, "
                          f"{e.free // (1 << 20)} MB free.")
    except Exception as e:  # noqa: BLE001 — reported to the UI, cleaned up
        _fail(slug, root, str(e) or "Preparation failed.")


def _fail(slug, root, message):
    shutil.rmtree(root, ignore_errors=True)
    state = load_state()
    state["games"].pop(slug, None)
    save_state(state)
    write_progress(slug, 0, "Failed", message)


# ── install / finalize / setexe ──────────────────────────────────────────────

def _launch(g, exe):
    env = prefix_env(g["slug"])
    emit("LaunchOptions", {"Exe": f'"{exe}"', "Options": f"{env}%command%" if env else "",
                           "WorkingDir": str(Path(exe).parent), "Compatibility": True,
                           "Name": g["title"]})


def action_install(slug, steam_id=""):
    state = load_state()
    g = state["games"].get(slug)
    if not g:
        return error("Unknown game.")
    if steam_id:
        g["steamClientID"] = str(steam_id)
        if not os.environ.get("SK_DISKS_COMPAT_ROOT"):
            import prefixes
            prefixes.assign(STORE, slug, steam_id)
    if g["stage"] == "needs-installer":
        if not g["steamClientID"]:
            return error("The Steam shortcut is missing.")
        g["snapshot"] = sorted(disks_exe.snapshot_exes(compat_dir(g["steamClientID"]) / "pfx" / "drive_c"))
        save_state(state)
        return _launch(g, g["installer"])
    save_state(state)
    if not g.get("exe"):
        return error("Choose the game's executable first.")
    _launch(g, g["exe"])


def _sizes(paths):
    out = {}
    for p in paths:
        try:
            out[p] = os.path.getsize(p)
        except OSError:
            pass
    return out


def action_finalize(slug):
    g = load_state()["games"].get(slug)
    if not g:
        return error("Unknown game.")
    lnk = []
    if g["source_kind"] != "installer" and Path(g["root"], "game").is_dir() and not g["installer"]:
        base = Path(g["root"]) / "game"
        new = [str(base / p) for p in disks_exe.snapshot_exes(base)]
        new = [_real_case(base, p) for p in new]
    else:
        drive_c = compat_dir(g["steamClientID"]) / "pfx" / "drive_c"
        before = set(g.get("snapshot") or [])
        new = [_real_case(drive_c, str(drive_c / p))
               for p in disks_exe.snapshot_exes(drive_c) - before]
        lnk = disks_exe.lnk_targets(drive_c)
    new = [p for p in new if p]
    emit("ExeCandidates", {"candidates": disks_exe.rank_candidates(new, lnk, g["title"], _sizes(new))})


def _real_case(base, lowered):
    """snapshot_exes lowercases paths: find the real spelling on disk."""
    cur = Path(base)
    for part in Path(lowered).relative_to(base).parts:
        match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None) \
            if cur.is_dir() else None
        if match is None:
            return None
        cur = match
    return str(cur)


def action_setexe(slug, exe):
    if not os.path.isfile(exe):
        return error("This file does not exist.")
    update_game(slug, exe=exe, stage="installed")
    emit("Success", {"Message": "OK"})


# ── progress / cancel ────────────────────────────────────────────────────────

def action_getprogress(slug):
    try:
        data = json.loads((PROGRESS_DIR / f"{slug}.json").read_text())
    except Exception:
        data = {"Percentage": 0, "Description": "Waiting…", "Error": None}
    data.pop("pid", None)
    emit("ProgressUpdate", data)


def action_cancelinstall(slug):
    try:
        pid = json.loads((PROGRESS_DIR / f"{slug}.json").read_text()).get("pid")
        if pid and pid != os.getpid():
            os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass
    state = load_state()
    g = state["games"].pop(slug, None)
    save_state(state)
    if g and g.get("root"):
        shutil.rmtree(g["root"], ignore_errors=True)
    try:
        (PROGRESS_DIR / f"{slug}.json").unlink()
    except OSError:
        pass
    emit("Success", {"Message": "Cancelled"})


# ── artwork & details ────────────────────────────────────────────────────────

STEAM_LANG = {"en": "english", "fr": "french", "de": "german", "es": "spanish", "it": "italian",
              "pt": "brazilian", "nl": "dutch", "pl": "polish", "ru": "russian"}
CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/{name}"
ART_SLOTS = (("Grid", "library_600x900_2x.jpg", (600, 900)), ("GridH", "header.jpg", (920, 430)),
             ("Hero", "library_hero.jpg", (1920, 620)), ("Logo", "logo.png", None))


def _http(url, timeout=20):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "SkullKey-disks/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _norm(text):
    return "".join(c for c in text.lower() if c.isalnum())


def steam_appid(title):
    """Exact-title Steam match (only the title leaves the machine)."""
    import re
    import urllib.parse
    clean = re.sub(r"[™®©]", "", title).strip()
    data = json.loads(_http("https://store.steampowered.com/api/storesearch/?l=english&cc=US&term="
                            + urllib.parse.quote(clean)))
    for item in data.get("items", []):
        if _norm(item.get("name", "")) == _norm(clean):
            return item["id"]
    return None


def fetch_b64(url):
    import base64
    data = _http(url)
    return base64.b64encode(data).decode(), ("png" if url.endswith(".png") else "jpg")


def text_tile(slug, title, w, h):
    """Title tile like the Classics' fallback (Pillow when available)."""
    try:
        import ports
        port = {"shortname": f"disks-{slug}", "title": title, "color": "#5a6a7a", "logo": ""}
        path = ports.compose(port, w, h)
        if path:
            return ports.b64_file(path), ports._img_type(path)
    except Exception as e:  # noqa: BLE001
        print(f"tile failed: {type(e).__name__}", file=sys.stderr)
    return None


def _cached_appid(slug, title):
    cache = DATA_DIR / "art.json"
    try:
        data = json.loads(cache.read_text())
    except Exception:
        data = {}
    if slug not in data:
        try:
            data[slug] = steam_appid(title)
        except Exception as e:  # noqa: BLE001 — offline: no artwork, no cache
            print(f"steam lookup failed: {type(e).__name__}", file=sys.stderr)
            return None
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
    return data[slug]


def action_getjsonimages(slug):
    g = load_state()["games"].get(slug)
    if not g:
        return error("Unknown game.")
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    appid = _cached_appid(slug, g["title"])
    for key, name, size in ART_SLOTS:
        got = None
        if appid:
            try:
                got = fetch_b64(CDN.format(id=appid, name=name))
            except Exception as e:  # noqa: BLE001
                print(f"art {key} failed: {type(e).__name__}", file=sys.stderr)
        if not got and size:
            got = text_tile(slug, g["title"], *size)
        if got:
            content[key], content[key + "Type"] = got
    emit("Images", content)


def _steam_description(appid):
    try:
        from ports_i18n import machine_lang_code
        lang = STEAM_LANG.get(machine_lang_code(), "english")
        data = json.loads(_http(f"https://store.steampowered.com/api/appdetails?appids={appid}&l={lang}"))
        return (data.get(str(appid), {}).get("data") or {}).get("short_description", "")
    except Exception:
        return ""


def _label(path):
    home = str(HOME)
    return "~" + path[len(home):] if path.startswith(home) else path


def action_getgamedetails(slug):
    g = load_state()["games"].get(slug)
    if not g:
        return error("Unknown game.")
    appid = _cached_appid(slug, g["title"])
    desc = _steam_description(appid) if appid else ""
    lines = [desc] if desc else []
    lines.append(f"Source: {g['source_kind']}")
    if g.get("exe"):
        lines.append(f"Executable: {os.path.basename(g['exe'])}")
    lines.append(f"Location: {_label(g['root'])}")
    emit("GameDetails", {
        "Name": g["title"], "Description": "<br><br>".join(lines),
        "ApplicationPath": "", "ManualPath": "", "RootFolder": "", "DatabaseID": slug,
        "ConfigurationPath": "", "Images": [], "ShortName": slug,
        "SteamClientID": g.get("steamClientID", ""), "HasDosConfig": False,
        "HasBatFiles": False, "Editors": []})


def action_getgamesize(slug):
    g = load_state()["games"].get(slug) or {}
    size = sum(f.stat().st_size for f in Path(g.get("root", "/nonexistent")).rglob("*") if f.is_file()) \
        if g.get("root") and Path(g["root"]).is_dir() else 0
    emit("GameSize", {"Size": f"Size: {size / (1 << 20):.0f} MB" if size else ""})


# ── saves & uninstall ────────────────────────────────────────────────────────

SAVE_DIRS = ("Documents", "Saved Games", "AppData")


def _save_dirs(g):
    if not g.get("steamClientID"):
        return []
    users = compat_dir(g["steamClientID"]) / "pfx" / "drive_c" / "users"
    found = []
    for user in sorted(users.glob("*")) if users.is_dir() else []:
        for top in SAVE_DIRS:
            for d in sorted((user / top).glob("*")) if (user / top).is_dir() else []:
                if not d.is_dir():
                    continue
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                if size:
                    found.append((d, f"{top}/{d.name}", size))
    return found


def action_savecheck(slug):
    g = load_state()["games"].get(slug)
    if not g:
        return error("Unknown game.")
    emit("SaveCheck", {"dirs": [{"path_label": label, "bytes": size}
                                for _, label, size in _save_dirs(g)]})


def action_uninstall(slug, keep=""):
    state = load_state()
    g = state["games"].get(slug)
    if not g:
        return error("Unknown game.")
    root = Path(g["root"])
    if keep == "keep":
        dest = root.parent / "_sauvegardes" / slug
        for d, label, _ in _save_dirs(g):
            target = dest / label
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(target))
        if dest.exists():
            give_to_user(dest)
    if g.get("steamClientID"):
        compat = compat_dir(g["steamClientID"])
        if compat.name in (str(g["steamClientID"]), f"disques-{slug}"):
            shutil.rmtree(compat, ignore_errors=True)
    if root.is_dir() and root.name == slug:
        shutil.rmtree(root, ignore_errors=True)
    _drives().forget(STORE, slug)
    state["games"].pop(slug, None)
    save_state(state)
    emit("Success", {"Message": "Uninstalled"})


# ── grid ─────────────────────────────────────────────────────────────────────

def action_getgames(filter_str="", installed="false"):
    games = []
    for i, (slug, g) in enumerate(sorted(load_state()["games"].items()), start=1):
        if filter_str and filter_str.lower() not in g.get("title", "").lower():
            continue
        if installed.lower() == "true" and not g.get("steamClientID"):
            continue
        games.append({"ID": i, "Name": g.get("title", slug), "Images": [],
                      "ShortName": slug, "SteamClientID": g.get("steamClientID", "")})
    emit("GameGrid", {"Games": games, "NeedsLogin": "false"})


ACTIONS = {
    "getgames": lambda a: action_getgames(a[1] if len(a) > 1 else "", a[2] if len(a) > 2 else "false"),
    "sources": lambda a: action_sources(),
    "mount": lambda a: action_mount(a[0]),
    "scan": lambda a: action_scan(a[0]),
    "add": lambda a: action_add(a[0]),
    "worker": lambda a: worker(a[0]),
    "install": lambda a: action_install(a[0], a[1] if len(a) > 1 else ""),
    "finalize": lambda a: action_finalize(a[0]),
    "setexe": lambda a: action_setexe(a[0], a[1]),
    "getprogress": lambda a: action_getprogress(a[0]),
    "cancelinstall": lambda a: action_cancelinstall(a[0]),
    "getjsonimages": lambda a: action_getjsonimages(a[0]),
    "getgamedetails": lambda a: action_getgamedetails(a[0]),
    "getgamesize": lambda a: action_getgamesize(a[0]),
    "savecheck": lambda a: action_savecheck(a[0]),
    "title": lambda a: emit("Success", {"Message": disks_scan.clean_title(a[0])}),
    "stage": lambda a: emit("Success", {"Message": load_state()["games"].get(a[0], {}).get("stage", "")}),
    "uninstall": lambda a: action_uninstall(a[0], a[1] if len(a) > 1 else ""),
}


def main():
    argv = sys.argv[1:]
    if not argv:
        return error("no action")
    handler = ACTIONS.get(argv[0])
    if handler is None:
        return error(f"unknown action {argv[0]}")
    handler(argv[1:])


if __name__ == "__main__":
    main()
