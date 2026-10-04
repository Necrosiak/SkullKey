#!/usr/bin/env python3
"""Battle.net store backend for SkullKey.

Blizzard offers no command-line client, so this extension drives the real
Windows Battle.net client, installed once into a single shared Proton prefix
(every Battle.net game lives in it, like on Windows). Nothing here talks to a
Blizzard web API: everything the store page needs is read from files the
client itself writes inside that prefix, once the user has signed in.

  owned games   CachedData.db (key_value_store → features_cached_data_points
                → licenses) evaluated against the entitlement rules of the
                catalog fragments the client caches under Cache/**, plus the
                game accounts the client logs (free-to-play / subscription
                titles are granted by a game account, not by a licence).
  names, art    the same catalog fragments; the images they reference are
                cached by the client under Cache/<h0h1>/<h2h3>/<hash>.
  installed     ProgramData/Battle.net/Agent/product.db (protobuf).

Measured on client 2.53 (Sep 2026): `--exec="install <CODE>"` is ignored, but
`--exec="launch <CODE>"` opens the game's page with "Install" focused, so an
install is one button press in the client. Launch goes through the same verb.

Self-contained (stdlib + Pillow, already used by the miHoYo extension).
"""

import base64
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request

RUNTIME_DIR = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                             os.path.expanduser("~/homebrew/data/SkullKey"))
LOG_DIR = os.environ.get("DECKY_PLUGIN_LOG_DIR",
                         os.path.expanduser("~/homebrew/logs/SkullKey"))
STATE_FILE = os.path.join(RUNTIME_DIR, "battlenet_state.json")
ART_DIR = os.path.join(RUNTIME_DIR, "battlenet_art")
ART_VERSION = "v1"

PREFIX = os.path.expanduser(
    os.environ.get("BATTLENET_PREFIX", "~/Games/battlenet/prefix"))
PFX = os.path.join(PREFIX, "pfx")
DRIVE_C = os.path.join(PFX, "drive_c")
CLIENT_DIR = os.path.join(DRIVE_C, "Program Files (x86)", "Battle.net")
CLIENT_LAUNCHER = os.path.join(CLIENT_DIR, "Battle.net Launcher.exe")
LOCAL_APPDATA = os.path.join(DRIVE_C, "users", "steamuser", "AppData", "Local",
                             "Battle.net")
CACHED_DATA_DB = os.path.join(LOCAL_APPDATA, "CachedData.db")
CATALOG_CACHE = os.path.join(LOCAL_APPDATA, "Cache")
CLIENT_LOGS = os.path.join(LOCAL_APPDATA, "Logs")
ROAMING_CONFIG = os.path.join(DRIVE_C, "users", "steamuser", "AppData",
                              "Roaming", "Battle.net", "Battle.net.config")
PRODUCT_DB = os.path.join(DRIVE_C, "ProgramData", "Battle.net", "Agent",
                          "product.db")

SETUP_URL = ("https://downloader.battle.net/download/getInstallerForGame"
             "?os=win&gameProgram=BATTLENET_APP&version=Live")
SETUP_EXE = os.path.join(RUNTIME_DIR, "battlenet", "Battle.net-Setup.exe")
STORE_URL = "https://shop.battle.net/"
# Name of the Steam shortcut that shows the client (found again by name).
CLIENT_SHORTCUT = "Battle.net (SkullKey)"

# Program ids the client runs through its own "launch" verb but that are not
# games (the client itself, the agent, test realms).
_NOT_GAMES = {"BNA", "AGENT", "BATTLE.NET"}


# ── small helpers ─────────────────────────────────────────────────────────────
def machine_lang_code():
    """2-letter code of the machine locale (plugin_loader runs without LANG,
    so /etc/locale.conf is the reliable source in game mode)."""
    def _code(val):
        return val.replace("-", "_").split(":")[0].split(".")[0].split("_")[0].lower()
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        if os.environ.get(var):
            return _code(os.environ[var])
    try:
        with open("/etc/locale.conf") as fh:
            for line in fh:
                if line.strip().startswith("LANG="):
                    return _code(line.split("=", 1)[1].strip().strip('"'))
    except OSError:
        pass
    return "en"


# Blizzard locale keys for the catalog strings; English lives under "default".
_BLIZZ_LOCALES = {"fr": "frFR", "de": "deDE", "es": "esES", "it": "itIT",
                  "ja": "jaJP", "ko": "koKR", "pl": "plPL", "pt": "ptBR",
                  "ru": "ruRU", "th": "thTH", "zh": "zhCN"}

_MSG = {
    "en": {
        "not_installed": "Battle.net is not installed yet: sign in first, "
                         "SkullKey installs the client then.",
        "client_closed": "Open Battle.net first (Sign in button at the top of "
                         "the tab), then press Install again.",
        "waiting": "Press Install in Battle.net to start the download",
        "installing": "Installing in Battle.net…",
        "done": "Finished installation process",
        "not_ready": "{name} is not installed yet.",
        "uninstall": "Removed from Steam. To free the disk space, uninstall "
                     "{name} from its page in Battle.net.",
        "client_updates": "Battle.net updates its games by itself.",
        "owned": "In your Battle.net library",
        "installed_at": "Installed in",
        "dev": "Publisher",
        "genre": "Genre",
        "note": "Installs and updates go through the Battle.net client, "
                "which opens on the game's page.",
    },
    "fr": {
        "not_installed": "Battle.net n'est pas encore installé : connecte-toi "
                         "d'abord, SkullKey installe alors le client.",
        "client_closed": "Ouvre d'abord Battle.net (bouton Connexion en haut "
                         "de l'onglet), puis appuie à nouveau sur Installer.",
        "waiting": "Appuie sur Installer dans Battle.net pour lancer le "
                   "téléchargement",
        "installing": "Installation dans Battle.net…",
        "done": "Finished installation process",
        "not_ready": "{name} n'est pas encore installé.",
        "uninstall": "Retiré de Steam. Pour libérer l'espace disque, "
                     "désinstalle {name} depuis sa page dans Battle.net.",
        "client_updates": "Battle.net met ses jeux à jour tout seul.",
        "owned": "Dans ta bibliothèque Battle.net",
        "installed_at": "Installé dans",
        "dev": "Éditeur",
        "genre": "Genre",
        "note": "Les installations et mises à jour passent par le client "
                "Battle.net, qui s'ouvre sur la page du jeu.",
    },
}


def msg(key, **kw):
    table = _MSG.get(machine_lang_code(), _MSG["en"])
    return table.get(key, _MSG["en"][key]).format(**kw)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"games": {}, "game_accounts": []}


def save_state(state):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)


def _win_to_unix(path):
    """'C:/Program Files (x86)/StarCraft' → path inside our drive_c."""
    p = path.replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = p[2:]
    return os.path.join(DRIVE_C, p.lstrip("/"))


# ── protobuf (product.db) ─────────────────────────────────────────────────────
def _varint(buf, i):
    val = shift = 0
    while True:
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        shift += 7
        if b < 0x80:
            return val, i


def _pb(buf):
    """Yield (field, wire_type, value) for one protobuf message."""
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        field, wt = key >> 3, key & 7
        if wt == 0:
            val, i = _varint(buf, i)
        elif wt == 1:
            val, i = buf[i:i + 8], i + 8
        elif wt == 2:
            n, i = _varint(buf, i)
            val, i = buf[i:i + n], i + n
        elif wt == 5:
            val, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"wire type {wt}")
        yield field, wt, val


def _first(buf, field):
    for f, _, v in _pb(buf):
        if f == field:
            return v
    return None


def read_product_db():
    """{uid: {code, path, installed, playable, version, progress}} from the
    Agent's product.db. Layout measured on Agent 2.41:
      1 (repeated) install { 1 uid, 2 product_code, 3 settings { 1 path },
                             4 state { 1 base { 1 installed, 2 playable,
                                                7 version },
                                       4 progress { 2 double 0..1 } } }"""
    out = {}
    try:
        with open(PRODUCT_DB, "rb") as f:
            data = f.read()
    except OSError:
        return out
    try:
        for field, wt, inst in _pb(data):
            if field != 1 or wt != 2:
                continue
            uid = (_first(inst, 1) or b"").decode(errors="replace")
            code = (_first(inst, 2) or b"").decode(errors="replace")
            settings = _first(inst, 3) or b""
            path = (_first(settings, 1) or b"").decode(errors="replace")
            state = _first(inst, 4) or b""
            base = _first(state, 1) or b""
            prog = _first(state, 4) or b""
            progress = 0.0
            raw = _first(prog, 2) if prog else None
            if isinstance(raw, (bytes, bytearray)) and len(raw) == 8:
                import struct
                progress = struct.unpack("<d", raw)[0]
            out[uid] = {
                "code": code, "path": path,
                "installed": bool(_first(base, 1) or 0),
                "playable": bool(_first(base, 2) or 0),
                "version": (_first(base, 7) or b"").decode(errors="replace"),
                "progress": progress,
            }
    except Exception as e:
        print(f"battlenet: product.db unreadable: {e}", file=sys.stderr)
    return out


# ── catalog (fragments cached by the client) ──────────────────────────────────
def _load_fragments():
    frags = []
    for path in glob.glob(os.path.join(CATALOG_CACHE, "*", "*", "*")):
        try:
            if os.path.getsize(path) > 4 * 1024 * 1024:
                continue
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            continue
        if b'"fragment_id"' not in raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("fragment_id"):
            frags.append(d)
    return frags


def load_catalog():
    """Merge the cached fragments into {program_id: entry}. A title is kept
    only when a fragment declares both its product (base.program_id) and its
    installs — the other fragments are regional/feature variants."""
    lang = _BLIZZ_LOCALES.get(machine_lang_code(), "default")
    frags = _load_fragments()
    strings = {"default": {}, lang: {}}
    files = {}
    for d in frags:
        for loc in ("default", lang):
            strings[loc].update((d.get("strings") or {}).get(loc) or {})
        files.update((d.get("files") or {}).get("default") or {})

    def text(key):
        return strings[lang].get(key) or strings["default"].get(key)

    games = {}
    rules = []
    product_program = {}
    for d in frags:
        for prog, cfg in (d.get("program_configuration") or {}).items():
            rules.append((prog, cfg))
        for pr in d.get("products") or []:
            base = pr.get("base") or {}
            prog = base.get("program_id")
            if not prog:
                continue
            product_program[pr.get("id") or prog] = prog
            if "installs" not in d or (pr.get("id") or prog) != prog:
                continue
            if prog.upper() in _NOT_GAMES:
                continue
            ptype = base.get("default_product_type") or "retail"
            uid = ((base.get("types") or {}).get(ptype) or {}).get("uid")
            installs = [u for u in (d.get("installs") or {})
                        if not re.search(r"(ptr|beta|alpha|test|vendor)", u)]
            if not uid:
                uid = prog.lower() if prog.lower() in installs else \
                    (installs[0] if installs else prog.lower())
            art = {}
            for slot in ("key_art", "background", "logo", "icon_medium",
                         "install_background"):
                ref = base.get(slot)
                if ref and ref in files:
                    art[slot] = files[ref].get("hash")
            games[prog] = {
                "program": prog,
                "uid": uid,
                "name": text(base.get("name")) or prog,
                "genre": text(base.get("genre")) or "",
                "free": "play_for_free" in (base.get("misc_flags") or []),
                "art": art,
            }
    return games, rules, product_program


def _match(cond, facts):
    """Evaluate one entitlement match. Unknown keys are False: inventing
    ownership is worse than missing it."""
    if not isinstance(cond, dict):
        return False
    for key, val in cond.items():
        if key == "license_id":
            ids = val if isinstance(val, list) else [val]
            if not any(int(x) in facts["licenses"] for x in ids):
                return False
        elif key == "game_account":
            prog = (val or {}).get("program_id") if isinstance(val, dict) else val
            if prog not in facts["accounts"]:
                return False
        elif key == "all_of":
            if not all(_match(c, facts) for c in val):
                return False
        elif key == "any_of":
            if not any(_match(c, facts) for c in val):
                return False
        elif key == "not":
            if _match(val, facts):
                return False
        else:
            return False
    return True


def _run_rules(rules, facts, granted, first_only=False):
    for rule in rules or []:
        if not _match(rule.get("match") or {}, facts):
            continue
        actions = rule.get("actions")
        if isinstance(actions, dict):
            actions = [actions]
        for act in actions or []:
            pid = ((act or {}).get("add_product") or {}).get("product_id") or {}
            if pid.get("id"):
                granted.add(pid["id"])
            if (act or {}).get("run_first_rule"):
                _run_rules(act["run_first_rule"], facts, granted, True)
            if (act or {}).get("run_each_rule"):
                _run_rules(act["run_each_rule"], facts, granted)
        if first_only:
            return


def read_account():
    """(battle_tag, licences) from the client's CachedData.db, or (None, set())
    when nobody is signed in."""
    if not os.path.exists(CACHED_DATA_DB):
        return None, set()
    try:
        con = sqlite3.connect(f"file:{CACHED_DATA_DB}?mode=ro", uri=True,
                              timeout=2)
        try:
            row = con.execute("select value from key_value_store where "
                              "key='features_cached_data_points'").fetchone()
            tag = con.execute("select battle_tag from login_cache "
                              "limit 1").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return None, set()
    licenses = set()
    if row:
        try:
            licenses = {int(x) for x in json.loads(row[0]).get("licenses", [])}
        except (ValueError, TypeError):
            pass
    return (tag[0] if tag else None), licenses


def refresh_game_accounts(state):
    """The client logs every game account of the signed-in user
    ("GameAccount(Pro:retail region=EU)"). It also logs a placeholder for
    every title of the catalog, marked "unbound" (or "hidden", or the test
    region XX): those are not accounts and grant nothing. Logs rotate, so the
    programs seen are remembered in the state file."""
    seen = set(state.get("game_accounts") or [])
    for path in glob.glob(os.path.join(CLIENT_LOGS, "battle.net-*.log")):
        try:
            with open(path, errors="replace") as f:
                for m in re.finditer(r"GameAccount\(([A-Za-z0-9_]+):([^)]*)\)",
                                     f.read()):
                    detail = m.group(2)
                    if re.search(r"\bunbound\b|\bhidden\b|region=XX\b", detail):
                        continue
                    seen.add(m.group(1))
        except OSError:
            continue
    if seen != set(state.get("game_accounts") or []):
        state["game_accounts"] = sorted(seen)
        save_state(state)
    return seen


def owned_games():
    """{program: entry} for the games the account can play, installed ones
    always included."""
    games, rules, product_program = load_catalog()
    state = load_state()
    _, licenses = read_account()
    facts = {"licenses": licenses, "accounts": refresh_game_accounts(state)}
    granted = set()
    for _prog, cfg in rules:
        _run_rules(cfg.get("run_each_rule"), facts, granted)
        _run_rules(cfg.get("run_first_rule"), facts, granted, True)
    programs = {product_program.get(p, p) for p in granted}
    programs |= {p for p in facts["accounts"] if p in games}
    installed = read_product_db()
    for prog, g in games.items():
        if installed.get(g["uid"], {}).get("installed"):
            programs.add(prog)
    return {p: games[p] for p in sorted(programs, key=lambda p: games[p]["name"]
                                        if p in games else p) if p in games}


# ── artwork ───────────────────────────────────────────────────────────────────
def _cached_image(h):
    if not h:
        return None
    path = os.path.join(CATALOG_CACHE, h[0:2], h[2:4], h)
    return path if os.path.exists(path) else None


def _build_art(game, W, H, slot_order, with_logo=True):
    """Crop/scale a cached client image into a Steam artwork slot; cached."""
    path = os.path.join(ART_DIR, f"{game['program']}_{W}x{H}"
                        f"{'' if with_logo else '_nologo'}_{ART_VERSION}.jpg")
    if os.path.exists(path):
        return path
    src = next((p for p in (_cached_image(game["art"].get(s))
                            for s in slot_order) if p), None)
    if not src:
        return None
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        # Pas de Pillow (Python de SteamOS d'origine, SkullKey #4) : l'image
        # brute du client, que Steam recadre lui-même, plutôt qu'aucune.
        return src
    try:
        src_img = Image.open(src).convert("RGBA")

        def cover(im):
            scale = max(W / im.width, H / im.height)
            im = im.resize((max(1, round(im.width * scale)),
                            max(1, round(im.height * scale))), Image.LANCZOS)
            left, top = (im.width - W) // 2, (im.height - H) // 2
            return im.crop((left, top, left + W, top + H))

        src_ratio, ratio = src_img.width / src_img.height, W / H
        if H > W and src_ratio > ratio * 1.05:
            # The client's key art is 3:4 with the logo spanning its width:
            # cropping it to Steam's 2:3 cuts the logo. Keep the full width
            # and fill above/below with a blurred copy instead.
            img = cover(src_img).filter(ImageFilter.GaussianBlur(24))
            fh = round(src_img.height * W / src_img.width)
            fit = src_img.resize((W, fh), Image.LANCZOS)
            img.alpha_composite(fit, (0, (H - fh) // 2))
        else:
            img = cover(src_img)
        logo_src = _cached_image(game["art"].get("logo")) if with_logo else None
        if logo_src and W > H:
            logo = Image.open(logo_src).convert("RGBA")
            bbox = logo.getchannel("A").getbbox()
            logo = logo.crop(bbox) if bbox else logo
            lw = round(W * 0.42)
            lh = round(logo.height * lw / logo.width)
            if lh > H * 0.5:
                lh = round(H * 0.5)
                lw = round(logo.width * lh / logo.height)
            logo = logo.resize((max(1, lw), max(1, lh)), Image.LANCZOS)
            img.alpha_composite(logo, ((W - lw) // 2, (H - lh) // 2))
        os.makedirs(ART_DIR, exist_ok=True)
        tmp = path + ".tmp"
        img.convert("RGB").save(tmp, "JPEG", quality=88)
        os.replace(tmp, path)
        return path
    except Exception as e:
        print(f"battlenet art failed for {game['program']}: {e}",
              file=sys.stderr)
        return None


def _logo_png(game):
    src = _cached_image(game["art"].get("logo"))
    if not src:
        return None
    path = os.path.join(ART_DIR, f"{game['program']}_logo_{ART_VERSION}.png")
    if os.path.exists(path):
        return path
    try:
        from PIL import Image
    except ImportError:
        return src                                # logo brut, sans rognage
    try:
        logo = Image.open(src).convert("RGBA")
        bbox = logo.getchannel("A").getbbox()
        logo = logo.crop(bbox) if bbox else logo
        os.makedirs(ART_DIR, exist_ok=True)
        logo.save(path + ".tmp", "PNG")
        os.replace(path + ".tmp", path)
        return path
    except Exception:
        return None


_PORTRAIT = ("key_art", "background", "install_background")
_LANDSCAPE = ("install_background", "background", "key_art")


def _data_uri(path):
    if not path:
        return None
    # Le repli sans Pillow peut rendre un PNG du client tel quel.
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


# ── client process helpers ────────────────────────────────────────────────────
def _our_wine_processes():
    """(pid, cmdline, environ) of the wine processes running in OUR prefix."""
    out = []
    real_pfx = os.path.realpath(PFX)
    for d in glob.glob("/proc/[0-9]*"):
        try:
            with open(d + "/environ", "rb") as f:
                env = dict(kv.split(b"=", 1) for kv in f.read().split(b"\0")
                           if b"=" in kv)
            pfx = env.get(b"WINEPREFIX", b"").decode(errors="replace")
            if not pfx or os.path.realpath(pfx) != real_pfx:
                continue
            with open(d + "/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace")
            out.append((int(d[6:]), cmd, env))
        except (OSError, ValueError):
            continue
    return out


def client_process():
    for pid, cmd, env in _our_wine_processes():
        # The main client process, whatever its arguments (--exec=… may come
        # before --from-launcher); its helpers carry --type=.
        if re.search(r"\\Battle\.net\.exe(\s|$)", cmd) and "--type=" not in cmd:
            return pid, env
    return None, None


def _wine_for(env):
    """wine binary of the Proton the running client uses."""
    tools = env.get(b"STEAM_COMPAT_TOOL_PATHS", b"").decode().split(":")
    for tool in tools:
        wine = os.path.join(tool, "files", "bin", "wine")
        if os.path.exists(wine):
            return wine
    return None


def send_to_client(program):
    """Ask the running client to open/launch `program`. Returns True when a
    client was running and got the command."""
    pid, env = client_process()
    if not pid:
        return False
    wine = _wine_for(env)
    if not wine:
        return False
    child_env = dict(os.environ)
    child_env.update({"WINEPREFIX": PFX, "WINEDEBUG": "-all"})
    subprocess.Popen([wine, "C:\\Program Files (x86)\\Battle.net\\Battle.net "
                      "Launcher.exe", f"--exec=launch {program}"],
                     env=child_env, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return True


def hide_client():
    """Make a client started with --autostarted stay in the tray: it then
    shows no window at all while a game is launched through it."""
    try:
        with open(ROAMING_CONFIG) as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return
    client = cfg.setdefault("Client", {})
    if client.get("AutoStartMinimized") == "true":
        return
    client["AutoStartMinimized"] = "true"
    with open(ROAMING_CONFIG + ".tmp", "w") as f:
        json.dump(cfg, f, indent=4)
    os.replace(ROAMING_CONFIG + ".tmp", ROAMING_CONFIG)


def game_running(program):
    """True while a process of the installed game runs in our prefix."""
    games, _, _ = load_catalog()
    g = games.get(program)
    if not g:
        return False
    inst = read_product_db().get(g["uid"])
    if not inst or not inst["path"]:
        return False
    needle = inst["path"].replace("/", "\\").lower().rstrip("\\") + "\\"
    for _pid, cmd, _env in _our_wine_processes():
        low = cmd.lower().replace("/", "\\")
        if needle in low and "battle.net" not in low.split(needle)[0][-40:]:
            return True
    return False


def default_compat_tool():
    """Steam's global default compatibility tool (config.vdf mapping "0")."""
    for cfg in (os.path.expanduser("~/.local/share/Steam/config/config.vdf"),
                os.path.expanduser("~/.steam/steam/config/config.vdf")):
        try:
            with open(cfg, errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        m = re.search(r'"CompatToolMapping"\s*\{\s*"0"\s*\{\s*"name"\s*"([^"]*)"',
                      text)
        if m and m.group(1):
            return m.group(1)
    return "proton_experimental"


def _launcher():
    return os.environ.get("LAUNCHER", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "battlenet-launcher.sh"))


def _ensure_setup():
    if os.path.exists(SETUP_EXE) and os.path.getsize(SETUP_EXE) > 1_000_000:
        return SETUP_EXE
    os.makedirs(os.path.dirname(SETUP_EXE), exist_ok=True)
    req = urllib.request.Request(SETUP_URL, headers={"User-Agent": "SkullKey"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if not data.startswith(b"MZ"):
        raise RuntimeError("Battle.net installer download is not an .exe")
    with open(SETUP_EXE + ".tmp", "wb") as f:
        f.write(data)
    os.replace(SETUP_EXE + ".tmp", SETUP_EXE)
    return SETUP_EXE


def _client_launch_options(program=""):
    """Launch options of the helper shortcut that shows the client: the
    installer on first use, the client afterwards."""
    if os.path.exists(CLIENT_LAUNCHER):
        exe, wdir = CLIENT_LAUNCHER, CLIENT_DIR
    else:
        exe = _ensure_setup()
        wdir = os.path.dirname(exe)
    mode = f"client:{program}" if program else "client"
    return {
        "Exe": f"\"{exe}\"",
        "Options": f"{_launcher()} {mode} %command%",
        "WorkingDir": wdir,
        "Name": CLIENT_SHORTCUT,
        "Compatibility": True,
        "CompatToolName": default_compat_tool(),
    }


# ── actions ───────────────────────────────────────────────────────────────────
def action_loginstatus(*_):
    tag, licenses = read_account()
    logged = bool(tag) and os.path.exists(CLIENT_LAUNCHER)
    return {"Type": "LoginStatus",
            "Content": {"Username": tag or "<not logged in>",
                        "LoggedIn": logged}}


def action_login(*_):
    return {"Type": "RunExe", "Content": _client_launch_options()}


def action_login_launch_options(*_):
    return {"Type": "LaunchOptions", "Content": _client_launch_options()}


def action_logout(*_):
    """Forget the account: the client signs in again on next start."""
    try:
        with open(ROAMING_CONFIG) as f:
            cfg = json.load(f)
        client = cfg.setdefault("Client", {})
        client["AutoLogin"] = "false"
        client.pop("SavedAccountNames", None)
        with open(ROAMING_CONFIG + ".tmp", "w") as f:
            json.dump(cfg, f, indent=4)
        os.replace(ROAMING_CONFIG + ".tmp", ROAMING_CONFIG)
    except (OSError, ValueError):
        pass
    try:
        os.remove(CACHED_DATA_DB)
    except OSError:
        pass
    return action_loginstatus()


def action_getgames(filter_str="", installed="false", *_):
    logged = action_loginstatus()["Content"]["LoggedIn"]
    state = load_state()
    games_out = []
    if logged:
        inst = read_product_db()
        for idx, (prog, g) in enumerate(owned_games().items(), start=1):
            if filter_str and filter_str.lower() not in g["name"].lower():
                continue
            st = state["games"].get(prog, {})
            if installed.lower() == "true" and not st.get("steamClientID"):
                continue
            if installed.lower() == "true" and \
                    not inst.get(g["uid"], {}).get("installed"):
                continue
            images = []
            cover = _data_uri(_build_art(g, 600, 900, _PORTRAIT, False))
            if cover:
                images.append(cover)
            games_out.append({
                "ID": idx,
                "Name": g["name"],
                "Images": images,
                "ShortName": prog,
                "SteamClientID": st.get("steamClientID"),
            })
    return {"Type": "GameGrid",
            "Content": {"NeedsLogin": "false" if logged else "true",
                        "Games": games_out, "storeURL": STORE_URL}}


def _game(program):
    games, _, _ = load_catalog()
    return games.get(program)


def action_getgamedetails(program, *_):
    g = _game(program) or {"program": program, "name": program, "genre": "",
                           "art": {}, "uid": program.lower()}
    inst = read_product_db().get(g["uid"], {})
    facts = [f"{msg('dev')}: Blizzard Entertainment"]
    if g.get("genre"):
        facts.append(f"{msg('genre')}: {g['genre']}")
    if inst.get("installed"):
        facts.append(f"{msg('installed_at')}: {inst['path']}")
        if inst.get("version"):
            facts.append(f"Version: {inst['version']}")
    parts = [f"<b>{msg('owned')}</b>", "<br />".join(facts),
             f"<i>{msg('note')}</i>"]
    desc = "<br /><br />".join(parts)
    images = [u for u in (_data_uri(_build_art(g, 1920, 620, _LANDSCAPE,
                                               False)),) if u] if g["art"] else []
    return {"Type": "GameDetails",
            "Content": {
                "Name": g["name"],
                "Description": f"<div><p style='white-space: pre-wrap;'>{desc}</p></div>",
                "ShortName": program,
                "SteamClientID": load_state()["games"].get(program, {})
                .get("steamClientID"),
                "Images": images,
                "Editors": [],
            }}


def action_getgamesize(program, installed="false", *_):
    g = _game(program)
    inst = read_product_db().get(g["uid"], {}) if g else {}
    if inst.get("installed") and inst.get("path"):
        total = 0
        for root, _d, files in os.walk(_win_to_unix(inst["path"])):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        n = float(total)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024 or unit == "TB":
                return {"Type": "GameSize",
                        "Content": {"Size": f"{n:.1f} {unit}"}}
            n /= 1024
    return {"Type": "GameSize", "Content": {"Size": "Battle.net"}}


def action_getjsonimages(program="", *_):
    g = _game(program)
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    if g:
        def b64(path):
            if not path:
                return None
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        content["Grid"] = b64(_build_art(g, 600, 900, _PORTRAIT, False))
        content["GridH"] = b64(_build_art(g, 920, 430, _LANDSCAPE))
        content["Hero"] = b64(_build_art(g, 1920, 620, _LANDSCAPE, False))
        content["Logo"] = b64(_logo_png(g))
    return {"Type": "Images", "Content": content}


def action_download(program, *_):
    """Open the game's page in the client with Install focused. When the
    client already runs, send it the command directly; otherwise hand the
    frontend the helper shortcut to start (the client must be started by
    Steam to be visible in gamescope)."""
    g = _game(program)
    inst = read_product_db().get(g["uid"]) if g else None
    if inst and inst["installed"] and inst["playable"]:
        # Already installed (e.g. from the client itself): the progress poll
        # reports 100 % at once and the frontend creates the shortcut.
        return {"Type": "Progress", "Content": {"Message": "Installed"}}
    state = load_state()
    state.setdefault("pending", {})[program] = time.time()
    save_state(state)
    if send_to_client(program):
        return {"Type": "Progress", "Content": {"Message": "Downloading",
                                                "Focus": CLIENT_SHORTCUT}}
    if not os.path.exists(CLIENT_LAUNCHER):
        return {"Type": "Error", "Content": {"Message": msg("not_installed")}}
    return {"Type": "LaunchOptions",
            "Content": _client_launch_options(program)}


def action_getprogress(program="", *_):
    g = _game(program)
    inst = read_product_db().get(g["uid"]) if g else None
    if inst and inst["installed"] and inst["playable"]:
        state = load_state()
        state.get("pending", {}).pop(program, None)
        save_state(state)
        return {"Type": "ProgressUpdate",
                "Content": {"Percentage": 100, "Description": msg("done")}}
    if inst:
        pct = max(1, min(99, int(inst["progress"] * 100)))
        return {"Type": "ProgressUpdate",
                "Content": {"Percentage": pct,
                            "Description": msg("installing")}}
    return {"Type": "ProgressUpdate",
            "Content": {"Percentage": 0, "Description": msg("waiting")}}


def action_cancelinstall(program, *_):
    state = load_state()
    state.get("pending", {}).pop(program, None)
    save_state(state)
    return {"Type": "Success", "Content": {"Message": "OK", "Toast": False}}


def _launch_options(program):
    g = _game(program)
    inst = read_product_db().get(g["uid"]) if g else None
    if not (inst and inst["installed"]):
        return {"Type": "Error", "Content": {
            "Message": msg("not_ready", name=g["name"] if g else program)}}
    return {"Type": "LaunchOptions", "Content": {
        "Exe": f"\"{CLIENT_LAUNCHER}\"",
        "Options": f"{_launcher()} game:{program} %command%",
        "WorkingDir": CLIENT_DIR,
        "Compatibility": True,
        "Name": g["name"],
    }}


def action_install(program, steam_client_id="", *_):
    if steam_client_id:
        state = load_state()
        state["games"].setdefault(program, {})["steamClientID"] = steam_client_id
        save_state(state)
    return _launch_options(program)


def action_uninstall(program, *_):
    g = _game(program)
    state = load_state()
    state["games"].pop(program, None)
    save_state(state)
    return {"Type": "Success", "Content": {
        "Message": msg("uninstall", name=g["name"] if g else program)}}


def action_getsetting(name="", *_):
    value = load_state().get("settings", {}).get(name, "")
    return {"Type": "Setting", "Content": {"name": name, "value": value}}


def action_savesetting(name="", value="", *_):
    state = load_state()
    state.setdefault("settings", {})[name] = value
    save_state(state)
    return {"Type": "Success", "Content": {"Message": "OK", "Toast": False}}


def action_client_updates(*_):
    return {"Type": "Success", "Content": {"Message": msg("client_updates")}}


def main():
    argv = sys.argv[1:]
    if not argv:
        print(json.dumps({"Type": "Error", "Content": {"Message": "no action"}}))
        return
    action, args = argv[0], argv[1:]

    # plain-text verbs for battlenet-launcher.sh
    if action == "prefix-dir":
        print(PREFIX)
        return
    if action == "client-running":
        sys.exit(0 if client_process()[0] else 1)
    if action == "game-running":
        sys.exit(0 if game_running(*args) else 1)
    if action == "send-launch":
        sys.exit(0 if send_to_client(*args) else 1)
    if action == "hide-client":
        hide_client()
        return

    table = {
        "getgames": action_getgames,
        "getgamedetails": action_getgamedetails,
        "getgamesize": action_getgamesize,
        "getjsonimages": action_getjsonimages,
        "getprogress": action_getprogress,
        "loginstatus": action_loginstatus,
        "login": action_login,
        "login-launch-options": action_login_launch_options,
        "logout": action_logout,
        "getsetting": action_getsetting,
        "savesetting": action_savesetting,
        "download": action_download,
        "install": action_install,
        "getlaunchoptions": lambda p, *_: _launch_options(p),
        "cancelinstall": action_cancelinstall,
        "uninstall": action_uninstall,
        "update": action_client_updates,
        "verify": action_client_updates,
        "repair": action_client_updates,
        "repair_and_update": action_client_updates,
    }
    try:
        fn = table.get(action)
        out = fn(*args) if fn else {"Type": "Error", "Content": {
            "Message": f"unknown action: {action}"}}
    except Exception as e:
        out = {"Type": "Error", "Content": {"Message": str(e)}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
