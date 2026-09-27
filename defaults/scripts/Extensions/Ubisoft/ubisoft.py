#!/usr/bin/env python3
"""Ubisoft Connect store backend for SkullKey.

Ubisoft has no command-line client, so this extension drives the real
Ubisoft Connect (UPC) client, installed once into a single shared Proton
prefix where every Ubisoft game lives, like on Windows. Everything the store
page needs is read from files UPC writes in that prefix:

  catalog      AppData/Local/Ubisoft Game Launcher/cache/configuration/
               configurations: protobuf, repeated {1 product id, 3 YAML}.
               A YAML with root.start_game is a game (the rest are DLC,
               bundles, soundtracks…).
  owned        …/cache/ownership/<user id>: 264-byte header (version +
               signature), then protobuf, repeated {1 product id, …}.
               It also carries CD keys: never log or show its content.
  installed    registry HKLM\\…\\Ubisoft\\Launcher\\Installs\\<id>\\InstallDir,
               written when a download STARTS; a game is installed once it
               left UPC's download queue (ProgramData/…/cache/download/*)
               and its folder holds uplay_install.state.
  progress     bytes on disk vs the file sizes listed in the game folder's
               uplay_install.manifest (12-byte header, base64 signature,
               zlib-compressed protobuf).

Install and launch go through UPC's own URIs, which it only honours when it
is started by Steam with them (sent from outside Steam they are dropped):
`uplay://install/<id>` opens its install dialog (gamepad-driven),
`uplay://launch/<id>/0` starts the game with only UPC's small launch window.

Measured on this machine (Sep 2026): the UPC installer crashes under
GE-Proton10-34 but installs silently (/S, ~15 s) under GE-Proton11-7, while
under GE-Proton11-7 no gamepad reaches UPC or its games (10-34 is fine).
So the installer runs once under a Proton 11, everything else under the
user's default Proton.
"""

import base64
import glob
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
import zlib

RUNTIME_DIR = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                             os.path.expanduser("~/homebrew/data/SkullKey"))
LOG_DIR = os.environ.get("DECKY_PLUGIN_LOG_DIR",
                         os.path.expanduser("~/homebrew/logs/SkullKey"))
STATE_FILE = os.path.join(RUNTIME_DIR, "ubisoft_state.json")
ART_DIR = os.path.join(RUNTIME_DIR, "ubisoft_art")
ART_VERSION = "v2"

PREFIX = os.path.expanduser(
    os.environ.get("UBISOFT_PREFIX", "~/Games/ubisoft/prefix"))
PFX = os.path.join(PREFIX, "pfx")
DRIVE_C = os.path.join(PFX, "drive_c")
UPC_DIR = os.path.join(DRIVE_C, "Program Files (x86)", "Ubisoft",
                       "Ubisoft Game Launcher")
UPC_EXE = os.path.join(UPC_DIR, "UbisoftConnect.exe")
LOCAL_DATA = os.path.join(DRIVE_C, "users", "steamuser", "AppData", "Local",
                          "Ubisoft Game Launcher")
CONFIGURATIONS = os.path.join(LOCAL_DATA, "cache", "configuration",
                              "configurations")
OWNERSHIP_DIR = os.path.join(LOCAL_DATA, "cache", "ownership")
DOWNLOAD_QUEUE_DIR = os.path.join(DRIVE_C, "ProgramData", "Ubisoft",
                                  "Ubisoft Game Launcher", "cache", "download")
SYSTEM_REG = os.path.join(PFX, "system.reg")
SETTINGS_YAML = os.path.join(LOCAL_DATA, "settings.yaml")

SETUP_URL = ("https://static3.cdn.ubi.com/orbit/launcher_installer/"
             "UbisoftConnectInstaller.exe")
SETUP_EXE = os.path.join(RUNTIME_DIR, "ubisoft", "UbisoftConnectInstaller.exe")
ASSETS_URL = "https://static3.cdn.ubi.com/orbit/uplay_launcher_3_0/assets/"
STORE_URL = "https://store.ubisoft.com/"
# Name of the Steam shortcut that shows the client (found again by name).
CLIENT_SHORTCUT = "Ubisoft Connect (SkullKey)"
OWNERSHIP_HEADER = 264


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


_MSG = {
    "en": {
        "waiting": "Confirm the install in Ubisoft Connect (A) to start "
                   "the download",
        "installing": "Downloading in Ubisoft Connect… {done} / {total}",
        "installing_nosize": "Downloading in Ubisoft Connect…",
        "done": "Finished installation process",
        "not_ready": "{name} is not installed yet.",
        "not_installed": "Ubisoft Connect is not installed yet: sign in "
                         "first, SkullKey installs it then.",
        "uninstall": "Removed from Steam. To free the disk space, uninstall "
                     "{name} from Ubisoft Connect.",
        "client_updates": "Ubisoft Connect updates its games by itself.",
        "owned": "In your Ubisoft library",
        "installed_at": "Installed in",
        "dev": "Publisher",
        "note": "Installs and updates go through Ubisoft Connect, which "
                "opens its install window (use A to confirm).",
        "user": "Ubisoft account",
    },
    "fr": {
        "waiting": "Valide l'installation dans Ubisoft Connect (A) pour "
                   "lancer le téléchargement",
        "installing": "Téléchargement dans Ubisoft Connect… {done} / {total}",
        "installing_nosize": "Téléchargement dans Ubisoft Connect…",
        "done": "Finished installation process",
        "not_ready": "{name} n'est pas encore installé.",
        "not_installed": "Ubisoft Connect n'est pas encore installé : "
                         "connecte-toi d'abord, SkullKey l'installe alors.",
        "uninstall": "Retiré de Steam. Pour libérer l'espace disque, "
                     "désinstalle {name} depuis Ubisoft Connect.",
        "client_updates": "Ubisoft Connect met ses jeux à jour tout seul.",
        "owned": "Dans ta bibliothèque Ubisoft",
        "installed_at": "Installé dans",
        "dev": "Éditeur",
        "note": "Les installations et mises à jour passent par Ubisoft "
                "Connect, qui ouvre sa fenêtre d'installation (valide avec A).",
        "user": "Compte Ubisoft",
    },
}


def msg(key, **kw):
    table = _MSG.get(machine_lang_code(), _MSG["en"])
    return table.get(key, _MSG["en"][key]).format(**kw)


def _human(nbytes):
    n = float(nbytes or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"games": {}}


def save_state(state):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)


def _win_to_unix(path):
    """'C:/Program Files (x86)/…' → path inside our drive_c."""
    p = path.replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = p[2:]
    return os.path.join(DRIVE_C, p.lstrip("/"))


def _log(line):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "ubisoft.log"), "a") as f:
            f.write(time.strftime("%F %T ") + line + "\n")
    except OSError:
        pass


# ── protobuf ──────────────────────────────────────────────────────────────────
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


# ── catalog / ownership ───────────────────────────────────────────────────────
def _parse_yaml(text):
    """The few keys we need from a UPC product YAML. PyYAML when present;
    otherwise a line scan, enough for root.name / images / start_game."""
    try:
        import yaml
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    root, loc, section = {}, {}, None
    for line in text.splitlines():
        if line.startswith("root:"):
            section = "root"
        elif line.startswith("localizations:"):
            section = "loc"
        elif line and not line.startswith(" "):
            section = None
        m = re.match(r"  ([a-z_]+):\s*(.*)$", line)
        if section == "root" and m:
            root[m.group(1)] = m.group(2).strip().strip('"') or True
        m2 = re.match(r"    ([A-Za-z0-9_]+):\s*(.+)$", line)
        if section == "loc" and m2:
            loc[m2.group(1)] = m2.group(2).strip().strip('"')
    return {"root": root, "localizations": {"default": loc}}


def load_catalog():
    """{product id: {"name", "images": {slot: file}}} for the GAMES of the
    catalog UPC cached (DLC and bundles have no root.start_game)."""
    try:
        with open(CONFIGURATIONS, "rb") as f:
            data = f.read()
    except OSError:
        return {}
    games = {}
    for field, wt, rec in _pb(data):
        if field != 1 or wt != 2:
            continue
        pid, text = None, b""
        for f, t, v in _pb(rec):
            if f == 1 and t == 0:
                pid = v
            elif f == 3 and t == 2:
                text = v
        if pid is None or b"start_game" not in text:
            continue
        info = _parse_yaml(text.decode("utf-8", "replace"))
        root = info.get("root") or {}
        if not root.get("start_game"):
            continue
        loc = (info.get("localizations") or {}).get("default") or {}

        def resolve(val):
            return loc.get(val, val) if isinstance(val, str) else None
        games[pid] = {
            "id": pid,
            "name": resolve(root.get("name")) or str(pid),
            "images": {k: resolve(root.get(k)) for k in
                       ("background_image", "logo_image", "thumb_image",
                        "splash_image") if resolve(root.get(k))},
        }
    return games


def owned_ids():
    files = sorted(glob.glob(os.path.join(OWNERSHIP_DIR, "*")),
                   key=os.path.getmtime, reverse=True)
    if not files:
        return set()
    with open(files[0], "rb") as f:
        data = f.read()
    # The record list follows a 264-byte header; if a future client changes
    # its size, look for the first offset that parses as the list.
    starts = [OWNERSHIP_HEADER] + [i for i in range(8, 1024) if data[i:i + 1] == b"\n"]
    for start in starts:
        try:
            ids = set()
            for field, wt, rec in _pb(data[start:]):
                if field == 1 and wt == 2:
                    for f, t, v in _pb(rec):
                        if f == 1 and t == 0:
                            ids.add(v)
                            break
            if ids:
                return ids
        except (ValueError, IndexError):
            continue
    return set()


def owned_games():
    catalog = load_catalog()
    ids = owned_ids()
    games = [g for pid, g in catalog.items() if pid in ids]
    return sorted(games, key=lambda g: g["name"].lower())


def _game(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    return load_catalog().get(pid)


# ── installed state ───────────────────────────────────────────────────────────
def _install_dirs():
    """{product id: InstallDir} from the prefix registry."""
    out = {}
    try:
        with open(SYSTEM_REG, errors="replace") as f:
            text = f.read()
    except OSError:
        return out
    for m in re.finditer(r'\[Software\\\\Wow6432Node\\\\Ubisoft\\\\Launcher\\\\'
                         r'Installs\\\\(\d+)\][^\[]*?"InstallDir"="([^"]*)"',
                         text):
        out[int(m.group(1))] = m.group(2).replace("\\\\", "\\")
    return out


def _download_queue():
    """Product ids UPC still has to download."""
    ids = set()
    for path in glob.glob(os.path.join(DOWNLOAD_QUEUE_DIR, "*")):
        try:
            with open(path, "rb") as f:
                data = f.read()
            (size,) = struct.unpack("<I", data[:4])
            for field, wt, rec in _pb(data[4:4 + size]):
                if field == 2 and wt == 2:
                    for f2, t2, v in _pb(rec):
                        if f2 == 1 and t2 == 0:
                            ids.add(v)
        except (OSError, ValueError, IndexError, struct.error):
            continue
    return ids


def _manifest_size(game_dir):
    """Total size of the game files listed in uplay_install.manifest."""
    try:
        with open(os.path.join(game_dir, "uplay_install.manifest"), "rb") as f:
            data = f.read()
        _ver, siglen, _usize = struct.unpack("<III", data[:12])
        body = zlib.decompress(data[12 + siglen:])
        total = 0
        for field, wt, chunk in _pb(body):
            if field != 4 or wt != 2:
                continue
            for f2, t2, entry in _pb(chunk):
                if f2 != 3 or t2 != 2:
                    continue
                for f3, t3, v in _pb(entry):
                    if f3 == 2 and t3 == 0:
                        total += v
        return total
    except (OSError, ValueError, IndexError, struct.error, zlib.error):
        return 0


def _dir_size(path):
    total = 0
    for root, _d, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def install_state(pid):
    """None (not installed), or {"dir", "done"}."""
    win_dir = _install_dirs().get(int(pid))
    if not win_dir:
        return None
    game_dir = _win_to_unix(win_dir)
    done = (int(pid) not in _download_queue()
            and os.path.exists(os.path.join(game_dir, "uplay_install.state")))
    return {"dir": game_dir, "win_dir": win_dir, "done": done}


# ── artwork ───────────────────────────────────────────────────────────────────
def _asset(name):
    """Download (once) a catalog image from Ubisoft's CDN."""
    if not name:
        return None
    path = os.path.join(ART_DIR, "src", os.path.basename(name))
    if os.path.exists(path):
        return path
    try:
        req = urllib.request.Request(ASSETS_URL + name,
                                     headers={"User-Agent": "SkullKey"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "wb") as f:
            f.write(data)
        os.replace(path + ".tmp", path)
        return path
    except Exception as e:
        print(f"ubisoft asset {name} failed: {e}", file=sys.stderr)
        return None


def _build_art(game, W, H, with_logo=True):
    """Background cropped to a Steam slot, logo on top for grids; cached."""
    path = os.path.join(ART_DIR, f"{game['id']}_{W}x{H}"
                        f"{'' if with_logo else '_nologo'}_{ART_VERSION}.jpg")
    if os.path.exists(path):
        return path
    src = _asset(game["images"].get("background_image")) or \
        _asset(game["images"].get("splash_image"))
    if not src:
        return None
    try:
        from PIL import Image, ImageFilter
        img = Image.open(src).convert("RGBA")
        scale = max(W / img.width, H / img.height)
        img = img.resize((max(1, round(img.width * scale)),
                          max(1, round(img.height * scale))), Image.LANCZOS)
        left, top = (img.width - W) // 2, (img.height - H) // 2
        img = img.crop((left, top, left + W, top + H))
        logo_src = _asset(game["images"].get("logo_image")) if with_logo else None
        if logo_src:
            # Some backgrounds already carry the game's logo (Origins, Siege…)
            # and cropping cuts it: blur the background and darken it so only
            # the real logo, drawn on top, reads.
            img = img.filter(ImageFilter.GaussianBlur(max(W, H) / 90))
            img = Image.alpha_composite(img, Image.new("RGBA", (W, H),
                                                       (0, 0, 0, 90)))
            logo = Image.open(logo_src).convert("RGBA")
            bbox = logo.getchannel("A").getbbox()
            logo = logo.crop(bbox) if bbox else logo
            lw = round(W * (0.86 if H > W else 0.56))
            lh = round(logo.height * lw / logo.width)
            max_lh = round(H * (0.35 if H > W else 0.55))
            if lh > max_lh:
                lh = max_lh
                lw = round(logo.width * lh / logo.height)
            logo = logo.resize((max(1, lw), max(1, lh)), Image.LANCZOS)
            y = (H - lh) // 2
            img.alpha_composite(logo, ((W - lw) // 2, y))
        os.makedirs(ART_DIR, exist_ok=True)
        img.convert("RGB").save(path + ".tmp", "JPEG", quality=88)
        os.replace(path + ".tmp", path)
        return path
    except Exception as e:
        print(f"ubisoft art failed for {game['id']}: {e}", file=sys.stderr)
        return None


def _logo_png(game):
    src = _asset(game["images"].get("logo_image"))
    if not src:
        return None
    path = os.path.join(ART_DIR, f"{game['id']}_logo_{ART_VERSION}.png")
    if os.path.exists(path):
        return path
    try:
        from PIL import Image
        logo = Image.open(src).convert("RGBA")
        bbox = logo.getchannel("A").getbbox()
        logo = logo.crop(bbox) if bbox else logo
        os.makedirs(ART_DIR, exist_ok=True)
        logo.save(path + ".tmp", "PNG")
        os.replace(path + ".tmp", path)
        return path
    except Exception:
        return None


def _data_uri(path):
    if not path:
        return None
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


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
        if re.search(r"\\upc\.exe(\s|$)", cmd, re.I):
            return pid, env
    return None, None


def stop_client():
    """Close UPC (and anything else in the prefix): it must be started
    fresh by Steam for a URI to be honoured and for the gamepad to reach it."""
    pid, env = client_process()
    if not pid:
        return False
    tools = env.get(b"STEAM_COMPAT_TOOL_PATHS", b"").decode().split(":")
    for tool in tools:
        server = os.path.join(tool, "files", "bin", "wineserver")
        if os.path.exists(server):
            subprocess.run([server, "-k"], env=dict(os.environ, WINEPREFIX=PFX),
                           timeout=30, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            break
    # Steam considers the app running until our launcher script exits: a
    # restart requested before that would be ignored.
    for _ in range(30):
        if not client_process()[0] and not _launcher_running():
            break
        time.sleep(0.5)
    return True


def _launcher_running():
    for d in glob.glob("/proc/[0-9]*"):
        try:
            with open(d + "/cmdline", "rb") as f:
                if b"ubisoft-launcher.sh" in f.read():
                    return True
        except OSError:
            continue
    return False


def disable_overlay():
    """Turn UPC's in-game overlay off, and its "enable the overlay?" prompt.
    Measured: while the overlay is on, no gamepad input reaches the game
    (it navigates the overlay instead); the prompt would stop every launch.
    UPC rewrites settings.yaml when it exits, so this runs with UPC closed."""
    try:
        with open(SETTINGS_YAML, newline="") as f:
            text = f.read()
    except OSError:
        return
    m = re.search(r"^overlay:\r?\n((?:[ \t]+.*\r?\n)*)", text, re.M)
    if not m:
        return
    block = m.group(1)
    new = re.sub(r"^(\s+enabled:\s*)true", r"\1false", block, flags=re.M)
    new = re.sub(r"^(\s+warning_enabled:\s*)true", r"\1false", new, flags=re.M)
    if new == block:
        return
    text = text[:m.start(1)] + new + text[m.end(1):]
    with open(SETTINGS_YAML + ".tmp", "w", newline="") as f:
        f.write(text)
    os.replace(SETTINGS_YAML + ".tmp", SETTINGS_YAML)


def hide_client_window():
    """Hide UPC's full window if it shows up over a running game.
    Measured: UPC's embedded browser (CEF) sometimes crashes right after it
    launched the game; UPC then restarts itself WITHOUT the launch URI and
    opens its full window in front of the game. Only large windows of our
    own Steam app are touched (told apart by size, titles are translated)."""
    display = os.environ.get("DISPLAY")
    appid = os.environ.get("SteamAppId", "")
    if not display or not appid or not shutil.which("xdotool") \
            or not shutil.which("xwininfo"):
        return
    env = dict(os.environ)
    try:
        tree = subprocess.run(["xwininfo", "-root", "-tree"], env=env,
                              capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return
    for line in tree.splitlines():
        m = re.match(r'\s*(0x[0-9a-f]+) "(.*)": \("steam_app_(\d+)" "[^"]*"\)'
                     r'\s+(\d+)x(\d+)', line)
        if not m or m.group(3) != appid:
            continue
        w, h = int(m.group(4)), int(m.group(5))
        # UPC's main window (~1450×930) — not the game (fullscreen) nor
        # UPC's small launch/progress windows.
        if not (1000 <= w < 1900 and 700 <= h < 1060):
            continue
        try:
            stats = subprocess.run(["xwininfo", "-id", m.group(1), "-stats"],
                                   env=env, capture_output=True, text=True,
                                   timeout=5).stdout
            if "IsViewable" in stats:
                # Minimise/activate requests are ignored under gamescope;
                # unmapping it hands the screen back to the game.
                subprocess.run(["xdotool", "windowunmap", m.group(1)],
                               env=env, timeout=5, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                _log(f"hid the client window over the game ({w}x{h})")
        except (OSError, subprocess.SubprocessError):
            continue


def game_running(pid):
    st = install_state(pid)
    if not st:
        return False
    needle = st["win_dir"].replace("/", "\\").lower().rstrip("\\") + "\\"
    for _p, cmd, _env in _our_wine_processes():
        if needle in cmd.lower().replace("/", "\\"):
            return True
    return False


def _steam_compat_tools():
    """Internal names of the compatibility tools Steam knows about."""
    names = []
    for base in (os.path.expanduser("~/.local/share/Steam/compatibilitytools.d"),
                 os.path.expanduser("~/.steam/root/compatibilitytools.d")):
        for vdf in glob.glob(os.path.join(base, "*", "compatibilitytool.vdf")):
            try:
                with open(vdf, errors="replace") as f:
                    m = re.search(r'"compat_tools"\s*\{\s*"([^"]+)"', f.read())
                if m and m.group(1) not in names:
                    names.append(m.group(1))
            except OSError:
                continue
    return names


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


def installer_compat_tool():
    """A Proton that runs the UPC installer (crashes under GE-Proton10-34):
    the newest GE-Proton 11+ found, else the user's default."""
    def version(name):
        m = re.search(r"GE-Proton(\d+)-(\d+)", name)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    ge = [n for n in _steam_compat_tools() if version(n)[0] >= 11]
    return max(ge, key=version) if ge else default_compat_tool()


def _launcher():
    return os.environ.get("LAUNCHER", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ubisoft-launcher.sh"))


def _ensure_setup():
    if os.path.exists(SETUP_EXE) and os.path.getsize(SETUP_EXE) > 50_000_000:
        return SETUP_EXE
    os.makedirs(os.path.dirname(SETUP_EXE), exist_ok=True)
    req = urllib.request.Request(SETUP_URL, headers={"User-Agent": "SkullKey"})
    with urllib.request.urlopen(req, timeout=60) as r, \
            open(SETUP_EXE + ".tmp", "wb") as out:
        head = r.read(2)
        if head != b"MZ":
            raise RuntimeError("Ubisoft Connect installer is not an .exe")
        out.write(head)
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            out.write(block)
    os.replace(SETUP_EXE + ".tmp", SETUP_EXE)
    return SETUP_EXE


def _client_launch_options(mode="client"):
    """Launch options of the helper shortcut showing UPC. On first use it
    runs the silent installer (under a Proton that can) then UPC's sign-in."""
    if os.path.exists(UPC_EXE):
        exe, wdir, tool = UPC_EXE, UPC_DIR, default_compat_tool()
    else:
        exe = _ensure_setup()
        wdir, tool, mode = os.path.dirname(exe), installer_compat_tool(), "setup"
    return {
        "Exe": f"\"{exe}\"",
        "Options": f"{_launcher()} {mode} %command%",
        "WorkingDir": wdir,
        "Name": CLIENT_SHORTCUT,
        "Compatibility": True,
        "CompatToolName": tool,
    }


# ── actions ───────────────────────────────────────────────────────────────────
def action_loginstatus(*_):
    logged = os.path.exists(UPC_EXE) and bool(glob.glob(
        os.path.join(OWNERSHIP_DIR, "*")))
    return {"Type": "LoginStatus",
            "Content": {"Username": msg("user") if logged else "<not logged in>",
                        "LoggedIn": logged}}


def action_login(*_):
    return {"Type": "RunExe", "Content": _client_launch_options()}


def action_login_launch_options(*_):
    return {"Type": "LaunchOptions", "Content": _client_launch_options()}


def action_logout(*_):
    """Forget the account: UPC asks to sign in again on next start."""
    for name in ("user.dat", "ConnectSecureStorage.dat"):
        try:
            os.remove(os.path.join(LOCAL_DATA, name))
        except OSError:
            pass
    for path in glob.glob(os.path.join(OWNERSHIP_DIR, "*")):
        try:
            os.remove(path)
        except OSError:
            pass
    return action_loginstatus()


def action_getgames(filter_str="", installed="false", *_):
    logged = action_loginstatus()["Content"]["LoggedIn"]
    state = load_state()
    games_out = []
    if logged:
        for idx, g in enumerate(owned_games(), start=1):
            if filter_str and filter_str.lower() not in g["name"].lower():
                continue
            st = state["games"].get(str(g["id"]), {})
            if installed.lower() == "true":
                inst = install_state(g["id"])
                if not (st.get("steamClientID") and inst and inst["done"]):
                    continue
            cover = _data_uri(_build_art(g, 600, 900))
            games_out.append({
                "ID": idx,
                "Name": g["name"],
                "Images": [cover] if cover else [],
                "ShortName": str(g["id"]),
                "SteamClientID": st.get("steamClientID"),
            })
    return {"Type": "GameGrid",
            "Content": {"NeedsLogin": "false" if logged else "true",
                        "Games": games_out, "storeURL": STORE_URL}}


def action_getgamedetails(pid, *_):
    g = _game(pid) or {"id": pid, "name": str(pid), "images": {}}
    inst = install_state(pid)
    facts = [f"{msg('dev')}: Ubisoft"]
    if inst and inst["done"]:
        facts.append(f"{msg('installed_at')}: {inst['win_dir']}")
    parts = [f"<b>{msg('owned')}</b>", "<br />".join(facts),
             f"<i>{msg('note')}</i>"]
    desc = "<br /><br />".join(parts)
    hero = _data_uri(_build_art(g, 1920, 620, False)) if g["images"] else None
    return {"Type": "GameDetails",
            "Content": {
                "Name": g["name"],
                "Description": f"<div><p style='white-space: pre-wrap;'>{desc}</p></div>",
                "ShortName": str(pid),
                "SteamClientID": load_state()["games"].get(str(pid), {})
                .get("steamClientID"),
                "Images": [hero] if hero else [],
                "Editors": [],
            }}


def action_getgamesize(pid, installed="false", *_):
    inst = install_state(pid)
    if inst and inst["done"]:
        return {"Type": "GameSize",
                "Content": {"Size": _human(_dir_size(inst["dir"]))}}
    return {"Type": "GameSize", "Content": {"Size": "Ubisoft Connect"}}


def action_getjsonimages(pid="", *_):
    g = _game(pid)
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    if g:
        def b64(path):
            if not path:
                return None
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        content["Grid"] = b64(_build_art(g, 600, 900))
        content["GridH"] = b64(_build_art(g, 920, 430))
        content["Hero"] = b64(_build_art(g, 1920, 620, False))
        content["Logo"] = b64(_logo_png(g))
    return {"Type": "Images", "Content": content}


def action_download(pid, *_):
    """Open UPC's install dialog for the game. UPC only honours a URI when
    Steam starts it with one, so a running client is closed first and the
    frontend (re)starts the helper shortcut with the install URI."""
    if not os.path.exists(UPC_EXE):
        return {"Type": "Error", "Content": {"Message": msg("not_installed")}}
    inst = install_state(pid)
    if inst and inst["done"]:
        # Already installed (e.g. from the client itself): the progress poll
        # reports 100 % at once and the frontend creates the shortcut.
        return {"Type": "Progress", "Content": {"Message": "Installed"}}
    stop_client()
    return {"Type": "LaunchOptions",
            "Content": _client_launch_options(f"install:{pid}")}


def action_getprogress(pid="", *_):
    inst = install_state(pid)
    if inst and inst["done"]:
        return {"Type": "ProgressUpdate",
                "Content": {"Percentage": 100, "Description": msg("done")}}
    if inst:
        total = _manifest_size(inst["dir"])
        done = _dir_size(inst["dir"])
        if total:
            pct = max(1, min(99, int(done * 100 / total)))
            desc = msg("installing", done=_human(done), total=_human(total))
        else:
            pct, desc = 1, msg("installing_nosize")
        return {"Type": "ProgressUpdate",
                "Content": {"Percentage": pct, "Description": desc}}
    return {"Type": "ProgressUpdate",
            "Content": {"Percentage": 0, "Description": msg("waiting")}}


def action_cancelinstall(*_):
    return {"Type": "Success", "Content": {"Message": "OK", "Toast": False}}


def _launch_options(pid):
    g = _game(pid)
    inst = install_state(pid)
    if not (inst and inst["done"]):
        return {"Type": "Error", "Content": {
            "Message": msg("not_ready", name=g["name"] if g else pid)}}
    return {"Type": "LaunchOptions", "Content": {
        "Exe": f"\"{UPC_EXE}\"",
        "Options": f"{_launcher()} game:{pid} %command%",
        "WorkingDir": UPC_DIR,
        "Compatibility": True,
        "Name": g["name"] if g else str(pid),
    }}


def action_install(pid, steam_client_id="", *_):
    if steam_client_id:
        state = load_state()
        state["games"].setdefault(str(pid), {})["steamClientID"] = steam_client_id
        save_state(state)
    return _launch_options(pid)


def action_uninstall(pid, *_):
    g = _game(pid)
    state = load_state()
    state["games"].pop(str(pid), None)
    save_state(state)
    return {"Type": "Success", "Content": {
        "Message": msg("uninstall", name=g["name"] if g else pid)}}


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

    # plain-text verbs for ubisoft-launcher.sh
    if action == "prefix-dir":
        print(PREFIX)
        return
    if action == "upc-exe":
        print(UPC_EXE)
        return
    if action == "client-running":
        sys.exit(0 if client_process()[0] else 1)
    if action == "stop-client":
        stop_client()
        disable_overlay()
        return
    if action == "game-running":
        sys.exit(0 if game_running(*args) else 1)
    if action == "hide-client-window":
        hide_client_window()
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
