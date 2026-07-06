#!/usr/bin/env python3
"""SkullKey Media extension backend.

Curated catalog of streaming / media / cloud-gaming / utility apps installable
from Game Mode, mirroring what Bazzite's `ujust get-media-app` offers and more:
  - kind "ssl":      web app rendered by StreamingServiceLauncher (AppImage,
                     Widevine + gamepad support, one shared AppImage)
  - kind "flatpak":  Flathub app installed per-user (no root/polkit needed)
  - kind "appimage": standalone AppImage from a GitHub release

Standalone by design: no GameSet/sqlite inheritance, state lives in a small
JSON file. Steam artwork is composed locally with Pillow (brand-color gradient
+ official logo) so shortcuts look clean in the library.

Updates: AppImages are re-downloaded when their GitHub release tag changes,
user flatpaks get `flatpak update`; both silently at most once a day (checked
on plugin init) or on demand via the per-app Update action.
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from io import BytesIO
from pathlib import Path

# Rich localized descriptions + controller-support lines (sibling module,
# deployed next to this file). Soft dependency: fall back to the short
# CATALOG descs if it's ever missing.
try:
    from media_i18n import desc_for, pad_line
except ImportError:
    desc_for = lambda app: app.get("desc", "")   # noqa: E731
    pad_line = lambda app: ""                     # noqa: E731

# The plugin runs subprocesses with a minimal env (no PATH). Restore a sane
# PATH so flatpak / the AppImages resolve, whether launched by the backend or
# by hand.
os.environ["PATH"] = os.pathsep.join(
    dict.fromkeys(
        (os.environ.get("PATH", "").split(os.pathsep))
        + ["/usr/bin", "/bin", "/usr/local/bin",
           os.path.expanduser("~/.local/bin")]
    ).keys()
).strip(os.pathsep)

# When decky launches this script through `#!/usr/bin/env python3` in its
# minimal environment, `sys.executable` can come back empty — spawning a worker
# with `Popen([sys.executable, ...])` then dies with "Permission denied: ''".
# Resolve a real interpreter path (PATH was restored just above).
import shutil
PYEXE = sys.executable or shutil.which("python3") or "/usr/bin/python3"

HOME = Path(os.path.expanduser("~"))
RUNTIME_DIR = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", str(HOME / "homebrew/data/SkullKey")))
STATE_FILE = RUNTIME_DIR / "media_state.json"
ART_DIR = RUNTIME_DIR / "media_art"
PROGRESS_DIR = RUNTIME_DIR / "media_progress"
SCRIPTS_DIR = RUNTIME_DIR / "media_scripts"
APPS_DIR = HOME / "Applications"

SSL_REPO = "aarron-lee/StreamingServiceLauncher"
SSL_APPIMAGE = APPS_DIR / "StreamingServiceLauncher.AppImage"

UA = {"User-Agent": "SkullKey-media/1.0"}
WM = "https://commons.wikimedia.org/wiki/Special:FilePath"
FH = "https://dl.flathub.org/repo/appstream/x86_64/icons/128x128"
GFAV = "https://www.google.com/s2/favicons?domain={d}&sz=256"

# shortname, title, category, kind, ref, logo url, brand color, description
CATALOG = [
    # ── TV & video ─────────────────────────────────────────────────────────
    ("youtube", "YouTube", "tv", "flatpak", "rocks.shy.VacuumTube",
     f"{FH}/rocks.shy.VacuumTube.png", "#ff0000",
     "YouTube with the TV interface (VacuumTube) — full gamepad support."),
    ("netflix", "Netflix", "tv", "ssl", "netflix",
     f"{WM}/Netflix_2015_logo.svg?width=512", "#e50914",
     "Netflix web app with Widevine DRM and gamepad support."),
    ("disney-plus", "Disney+", "tv", "ssl", "disneyPlus",
     f"{WM}/Disney%2B_logo.svg?width=512", "#113ccf",
     "Disney+ web app with Widevine DRM and gamepad support."),
    ("prime-video", "Prime Video", "tv", "ssl", "amazonPrimeVideo",
     f"{WM}/Amazon_Prime_Video_logo.svg?width=512", "#00a8e1",
     "Amazon Prime Video web app with Widevine DRM and gamepad support."),
    ("apple-tv", "Apple TV+", "tv", "ssl", "appleTv",
     f"{WM}/Apple_TV_Plus_Logo.svg?width=512", "#3a3a3c",
     "Apple TV+ web app with Widevine DRM and gamepad support."),
    ("hbo-max", "HBO Max", "tv", "ssl", "hboMax",
     f"{WM}/HBO_Max_Logo.svg?width=512", "#7b2bf9",
     "HBO Max web app with Widevine DRM and gamepad support."),
    ("hulu", "Hulu", "tv", "ssl", "hulu",
     f"{WM}/Hulu_Logo.svg?width=512", "#1ce783",
     "Hulu web app with Widevine DRM and gamepad support."),
    ("paramount-plus", "Paramount+", "tv", "ssl", "paramountPlus",
     f"{WM}/Paramount_Plus.svg?width=512", "#0064ff",
     "Paramount+ web app with Widevine DRM and gamepad support."),
    ("peacock", "Peacock", "tv", "ssl", "peacock",
     f"{WM}/NBCUniversal_Peacock_Logo.svg?width=512", "#000000",
     "Peacock web app with Widevine DRM and gamepad support."),
    ("crunchyroll", "Crunchyroll", "tv", "appimage", "aarron-lee/crunchyroll-linux",
     f"{WM}/Crunchyroll_Logo.svg?width=512", "#f47521",
     "Crunchyroll standalone app (community AppImage)."),
    ("curiosity-stream", "Curiosity Stream", "tv", "ssl", "curiosityStream",
     f"{WM}/CuriosityStream.svg?width=512", "#f5b921",
     "Curiosity Stream web app with gamepad support."),
    ("sling-tv", "Sling TV", "tv", "ssl", "slingTV",
     f"{WM}/Sling_TV_logo.svg?width=512", "#00b9ff",
     "Sling TV web app with Widevine DRM and gamepad support."),
    ("vimeo", "Vimeo", "tv", "ssl", "vimeo",
     f"{WM}/Vimeo_Logo.svg?width=512", "#1ab7ea",
     "Vimeo web app with gamepad support."),
    ("youtube-tv", "YouTube TV", "tv", "ssl", "youTubeTV",
     f"{WM}/YouTube_TV_logo.svg?width=512", "#ff0000",
     "YouTube TV web app with gamepad support."),
    ("plex", "Plex HTPC", "tv", "flatpak", "tv.plex.PlexHTPC",
     f"{FH}/tv.plex.PlexHTPC.png", "#e5a00d",
     "Plex HTPC — the couch interface for your Plex server."),
    ("jellyfin", "Jellyfin", "tv", "flatpak", "org.jellyfin.JellyfinDesktop",
     f"{FH}/org.jellyfin.JellyfinDesktop.png", "#aa5cc3",
     "Jellyfin Desktop — couch client for your Jellyfin server."),
    ("kodi", "Kodi", "tv", "flatpak", "tv.kodi.Kodi",
     f"{FH}/tv.kodi.Kodi.png", "#17b2e7",
     "Kodi media center."),
    ("stremio", "Stremio", "tv", "flatpak", "com.stremio.Stremio",
     f"{FH}/com.stremio.Stremio.png", "#7b5bf5",
     "Stremio — media hub with addons."),
    # ── Music ──────────────────────────────────────────────────────────────
    ("spotify", "Spotify", "music", "ssl", "spotify",
     f"{WM}/Spotify_logo_with_text.svg?width=512", "#1db954",
     "Spotify web player with gamepad support."),
    ("youtube-music", "YouTube Music", "music", "ssl", "youtubeMusic",
     f"{WM}/Youtube_Music_icon.svg?width=512", "#ff0000",
     "YouTube Music web app with gamepad support."),
    ("tidal", "TIDAL", "music", "flatpak", "com.mastermindzh.tidal-hifi",
     f"{FH}/com.mastermindzh.tidal-hifi.png", "#00d4d4",
     "TIDAL Hi-Fi desktop client."),
    ("deezer", "Deezer", "music", "flatpak", "dev.aunetx.deezer",
     f"{FH}/dev.aunetx.deezer.png", "#a238ff",
     "Deezer desktop client."),
    # ── Cloud gaming & remote play ─────────────────────────────────────────
    ("geforce-now", "GeForce NOW", "cloud", "ssl", "geForceNow",
     GFAV.format(d="play.geforcenow.com"), "#76b900",
     "NVIDIA GeForce NOW cloud gaming (web app, gamepad support)."),
    ("xbox-cloud", "Xbox Cloud Gaming", "cloud", "ssl", "xboxGamePassStreaming",
     GFAV.format(d="xbox.com"), "#107c10",
     "Xbox Game Pass cloud gaming (web app, gamepad support)."),
    ("amazon-luna", "Amazon Luna", "cloud", "ssl", "amazonLuna",
     f"{WM}/Amazon_Luna_logo.svg?width=512", "#7a4bdb",
     "Amazon Luna cloud gaming (web app, gamepad support)."),
    ("moonlight", "Moonlight", "cloud", "flatpak", "com.moonlight_stream.Moonlight",
     f"{FH}/com.moonlight_stream.Moonlight.png", "#7d5eb2",
     "Moonlight — stream games from your own PC (NVIDIA GameStream / Sunshine)."),
    ("chiaki", "chiaki-ng", "cloud", "flatpak", "io.github.streetpea.Chiaki4deck",
     f"{FH}/io.github.streetpea.Chiaki4deck.png", "#0072ce",
     "chiaki-ng — PlayStation 4/5 Remote Play client."),
    ("greenlight", "Greenlight", "cloud", "flatpak", "io.github.unknownskl.greenlight",
     f"{FH}/io.github.unknownskl.greenlight.png", "#107c10",
     "Greenlight — Xbox console streaming (xCloud & home console)."),
    ("parsec", "Parsec", "cloud", "flatpak", "com.parsecgaming.parsec",
     f"{FH}/com.parsecgaming.parsec.png", "#7b68ee",
     "Parsec — low-latency remote desktop and game streaming."),
    # ── Apps & tools ───────────────────────────────────────────────────────
    ("lutris", "Lutris", "apps", "flatpak", "net.lutris.Lutris",
     f"{FH}/net.lutris.Lutris.png", "#ff9600",
     "Lutris — open gaming platform (GOG, emulators, wine…)."),
    ("bottles", "Bottles", "apps", "flatpak", "com.usebottles.bottles",
     f"{FH}/com.usebottles.bottles.png", "#3584e4",
     "Bottles — run Windows software in managed wine prefixes."),
    ("retrodeck", "RetroDECK", "apps", "flatpak", "net.retrodeck.retrodeck",
     f"{FH}/net.retrodeck.retrodeck.png", "#e63c2e",
     "RetroDECK — all-in-one retro gaming (EmulationStation + RetroArch)."),
    ("protonup-qt", "ProtonUp-Qt", "apps", "flatpak", "net.davidotek.pupgui2",
     f"{FH}/net.davidotek.pupgui2.png", "#8e7cc3",
     "ProtonUp-Qt — install GE-Proton and other compatibility tools."),
    ("flatseal", "Flatseal", "apps", "flatpak", "com.github.tchx84.Flatseal",
     f"{FH}/com.github.tchx84.Flatseal.png", "#26a269",
     "Flatseal — manage Flatpak permissions."),
]

FIELDS = ("shortname", "title", "cat", "kind", "ref", "image", "color", "desc")
APPS = {row[0]: dict(zip(FIELDS, row)) for row in CATALOG}


# ── state ────────────────────────────────────────────────────────────────────

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"apps": {}, "ssl_tag": "", "last_check": 0}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1))


def app_state(state, shortname):
    return state["apps"].setdefault(shortname, {"steamClientID": "", "installed": False, "tag": ""})


# ── helpers ──────────────────────────────────────────────────────────────────

def urlopen_retry(url, timeout=20, tries=4):
    """urlopen with backoff on transient failures (Wikimedia/Flathub sometimes
    answer 429/5xx under load). Logos are cached after the first success so this
    only ever matters on install."""
    import urllib.error
    delay = 1.5
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as e:
            last = e
            if attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise last


def http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def gh_latest(repo):
    rel = http_json(f"https://api.github.com/repos/{repo}/releases/latest")
    url = ""
    for a in rel.get("assets", []):
        if a.get("name", "").lower().endswith(".appimage"):
            url = a.get("browser_download_url", "")
            break
    return rel.get("tag_name", ""), url


def flatpak(*args, timeout=1800):
    return subprocess.run(["flatpak", *args], capture_output=True, text=True, timeout=timeout)


_FLATPAK_SCOPES = None


def flatpak_scope(ref):
    """Where `ref` is installed: 'user', 'system', or '' (not installed).

    Cached with a single `flatpak list` per scope so scanning a whole grid
    stays cheap, and honest about apps installed outside the plugin (user OR
    system) so the tool can offer to uninstall them."""
    global _FLATPAK_SCOPES
    if _FLATPAK_SCOPES is None:
        _FLATPAK_SCOPES = {}
        for scope in ("system", "user"):  # user wins if both (listed last)
            try:
                r = flatpak("list", f"--{scope}", "--app", "--columns=application", timeout=30)
                if r.returncode == 0:
                    for line in r.stdout.splitlines():
                        app_ref = line.strip()
                        if app_ref:
                            _FLATPAK_SCOPES[app_ref] = scope
            except Exception:
                pass
    return _FLATPAK_SCOPES.get(ref, "")


def flatpak_installed(ref):
    return flatpak_scope(ref) != ""


def is_installed(state, app):
    st = state["apps"].get(app["shortname"], {})
    if app["kind"] == "flatpak":
        # Reflect reality: installed via the plugin OR already present on the
        # system (any scope), so the app shows up as installed / uninstallable.
        return bool(st.get("installed")) or flatpak_installed(app["ref"])
    if app["kind"] == "ssl":
        return bool(st.get("installed")) and SSL_APPIMAGE.exists()
    if app["kind"] == "appimage":
        return (APPS_DIR / f"{app['title'].replace(' ', '')}.AppImage").exists()
    return False


def write_progress(shortname, pct, desc, error=None, pid=None):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"Percentage": pct, "Description": desc, "Error": error}
    if pid:
        data["pid"] = pid
    (PROGRESS_DIR / f"{shortname}.json").write_text(json.dumps(data))


def download_file(url, dest, shortname, lo, hi, desc):
    """Download url to dest, mapping byte progress onto [lo, hi] percent."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        tmp = Path(str(dest) + ".part")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    write_progress(shortname, lo + (hi - lo) * done / total, desc, pid=os.getpid())
        tmp.rename(dest)
    os.chmod(dest, 0o755)


# ── artwork (Pillow) ─────────────────────────────────────────────────────────

def fetch_logo(app):
    ART_DIR.mkdir(parents=True, exist_ok=True)
    cache = ART_DIR / f"{app['shortname']}_logo.png"
    if not cache.exists():
        from PIL import Image
        raw = urlopen_retry(app["image"], timeout=20)
        img = Image.open(BytesIO(raw)).convert("RGBA")
        img.save(cache)
    return cache


def compose(app, w, h):
    """Brand-color vertical gradient + centered logo, cached on disk."""
    from PIL import Image
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out = ART_DIR / f"{app['shortname']}_{w}x{h}.png"
    if out.exists():
        return out
    c = app["color"].lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    top = (int(r * 0.50), int(g * 0.50), int(b * 0.50))
    bottom = (10, 12, 16)
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        row = (int(top[0] + (bottom[0] - top[0]) * t),
               int(top[1] + (bottom[1] - top[1]) * t),
               int(top[2] + (bottom[2] - top[2]) * t))
        for x in range(w):
            px[x, y] = row
    logo = Image.open(fetch_logo(app)).convert("RGBA")
    max_w, max_h = int(w * 0.68), int(h * 0.42)
    scale = min(max_w / logo.width, max_h / logo.height)
    logo = logo.resize((max(1, int(logo.width * scale)), max(1, int(logo.height * scale))), Image.LANCZOS)
    img.paste(logo, ((w - logo.width) // 2, (h - logo.height) // 2), logo)
    img.save(out)
    return out


def b64_file(path):
    import base64
    return base64.b64encode(Path(path).read_bytes()).decode()


# ── actions ──────────────────────────────────────────────────────────────────

def action_getgames(cat, filter_str="", installed="false"):
    state = load_state()
    refresh_installed_launch_scripts(state)
    games = []
    for app in APPS.values():
        if app["cat"] != cat:
            continue
        if filter_str and filter_str.lower() not in app["title"].lower():
            continue
        inst = is_installed(state, app)
        st = state["apps"].get(app["shortname"], {})
        if installed.lower() == "true" and not st.get("steamClientID"):
            continue
        games.append({
            "ID": list(APPS).index(app["shortname"]) + 1,
            "Name": app["title"],
            "Images": [app["image"]],
            "ShortName": app["shortname"],
            "SteamClientID": st.get("steamClientID", ""),
        })
    print(json.dumps({"Type": "GameGrid", "Content": {"Games": games, "NeedsLogin": "false"}}))


def action_getgamedetails(shortname):
    app = APPS[shortname]
    state = load_state()
    st = state["apps"].get(shortname, {})
    kind_label = {"ssl": "Web app (StreamingServiceLauncher)",
                  "flatpak": f"Flatpak — {app['ref']}",
                  "appimage": "AppImage (GitHub release)"}[app["kind"]]
    tag = st.get("tag") or state.get("ssl_tag") if app["kind"] in ("ssl", "appimage") else ""
    desc = desc_for(app)
    pad = pad_line(app)
    if pad:
        desc += f"<br><br>{pad}"
    desc += f"<br><br><i>{kind_label}</i>"
    if tag and is_installed(state, app):
        desc += f"<br><i>Build: {tag}</i>"
    print(json.dumps({"Type": "GameDetails", "Content": {
        "Name": app["title"],
        "Description": desc,
        "ApplicationPath": "", "ManualPath": "", "RootFolder": "",
        "DatabaseID": shortname, "ConfigurationPath": "",
        "Images": [app["image"]],
        "ShortName": shortname,
        "SteamClientID": st.get("steamClientID", ""),
        "HasDosConfig": False, "HasBatFiles": False,
        "Editors": [],
    }}))


def action_getjsonimages(shortname):
    app = APPS[shortname]
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    try:
        content["Grid"] = b64_file(compose(app, 600, 900))
        content["GridH"] = b64_file(compose(app, 920, 430))
        content["Hero"] = b64_file(compose(app, 1920, 620))
        content["Logo"] = b64_file(fetch_logo(app))
    except Exception as e:
        print(f"artwork failed: {e}", file=sys.stderr)
    print(json.dumps({"Type": "Images", "Content": content}))


def worker_install(shortname):
    app = APPS[shortname]
    state = load_state()
    try:
        write_progress(shortname, 2, f"Preparing {app['title']}…", pid=os.getpid())
        if app["kind"] == "flatpak":
            write_progress(shortname, 5, "Configuring Flathub…", pid=os.getpid())
            flatpak("remote-add", "--user", "--if-not-exists", "flathub",
                    "https://dl.flathub.org/repo/flathub.flatpakrepo", timeout=120)
            if flatpak_installed(app["ref"]):
                write_progress(shortname, 60, f"Updating {app['title']}…", pid=os.getpid())
                flatpak("update", "--user", "-y", app["ref"])
            else:
                write_progress(shortname, 15, f"Installing {app['title']} (Flatpak)…", pid=os.getpid())
                r = flatpak("install", "--user", "-y", "flathub", app["ref"])
                if r.returncode != 0:
                    raise RuntimeError((r.stderr or r.stdout).strip()[-400:])
            st = app_state(state, shortname)
            st["installed"] = True
        elif app["kind"] == "ssl":
            write_progress(shortname, 5, "Checking StreamingServiceLauncher release…", pid=os.getpid())
            tag, url = gh_latest(SSL_REPO)
            if not SSL_APPIMAGE.exists() or (tag and tag != state.get("ssl_tag")):
                if not url:
                    raise RuntimeError("no AppImage asset in latest release")
                download_file(url, SSL_APPIMAGE, shortname, 10, 90,
                              f"Downloading StreamingServiceLauncher {tag}…")
                state["ssl_tag"] = tag
            st = app_state(state, shortname)
            st["installed"] = True
            st["tag"] = tag or state.get("ssl_tag", "")
        elif app["kind"] == "appimage":
            write_progress(shortname, 5, f"Checking {app['title']} release…", pid=os.getpid())
            tag, url = gh_latest(app["ref"])
            if not url:
                raise RuntimeError("no AppImage asset in latest release")
            dest = APPS_DIR / f"{app['title'].replace(' ', '')}.AppImage"
            download_file(url, dest, shortname, 10, 90, f"Downloading {app['title']} {tag}…")
            st = app_state(state, shortname)
            st["installed"] = True
            st["tag"] = tag
        write_launch_script(app)
        save_state(state)
        write_progress(shortname, 100, "Done")
    except Exception as e:
        write_progress(shortname, 0, "Installation failed", error=str(e))


def write_launch_script(app):
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / f"{app['shortname']}.sh"
    if app["kind"] == "flatpak":
        inner = f'flatpak run {app["ref"]} "$@"'
    elif app["kind"] == "ssl":
        inner = f'"{SSL_APPIMAGE}" --appname={app["ref"]} --no-sandbox'
    else:
        dest = APPS_DIR / f"{app['title'].replace(' ', '')}.AppImage"
        inner = f'"{dest}" --no-sandbox'
    # Run the media app directly, in Game Mode and on the desktop alike. We used
    # to wrap it in a nested gamescope (gamescope-in-gamescope) so the Steam
    # on-screen keyboard (STEAM+X) would attach to these native / flatpak /
    # Chromium apps. On the BC-250 that nesting is broken both ways: with the
    # FROG WSI layer enabled, the parent session's ENABLE_GAMESCOPE_WSI=1 makes
    # the nested gamescope throw a blocking "Gamescope WSI Layer Error" popup;
    # disabling the layer (DISABLE_GAMESCOPE_WSI=1) on the gamescope process
    # kills the popup but then the nested gamescope can't sustain presentation to
    # the parent Steam session and the app dies a few seconds after launch.
    # Neither variant is usable, so we drop the nesting entirely. Trade-off: no
    # STEAM+X on-screen keyboard inside these apps.
    body = "#!/usr/bin/env bash\n" f"exec {inner}\n"
    path.write_text(body)
    os.chmod(path, 0o755)
    return path


def refresh_installed_launch_scripts(state):
    # Rewrite the launch scripts of already-installed apps (cheap, idempotent) so
    # any change to write_launch_script — e.g. dropping the nested-gamescope
    # wrapper — is picked up live, without the user having to reinstall the app.
    for shortname, st in state.get("apps", {}).items():
        app = APPS.get(shortname)
        if app and st.get("installed"):
            try:
                write_launch_script(app)
            except Exception:
                pass


def action_download(shortname):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    write_progress(shortname, 0, "Starting…")
    subprocess.Popen([PYEXE, os.path.abspath(__file__), "worker", shortname],
                     start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env=os.environ.copy())
    print(json.dumps({"Type": "Progress", "Content": {"Message": "Installing"}}))


def action_getprogress(shortname):
    try:
        data = json.loads((PROGRESS_DIR / f"{shortname}.json").read_text())
    except Exception:
        data = {"Percentage": 0, "Description": "Waiting…", "Error": None}
    data.pop("pid", None)
    print(json.dumps({"Type": "ProgressUpdate", "Content": data}))


def action_cancelinstall(shortname):
    try:
        data = json.loads((PROGRESS_DIR / f"{shortname}.json").read_text())
        pid = data.get("pid")
        if pid:
            os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass
    try:
        (PROGRESS_DIR / f"{shortname}.json").unlink()
    except Exception:
        pass
    print(json.dumps({"Type": "Success", "Content": {"Message": "Cancelled"}}))


def action_install(shortname, steam_client_id=""):
    app = APPS[shortname]
    state = load_state()
    st = app_state(state, shortname)
    if steam_client_id:
        st["steamClientID"] = str(steam_client_id)
    save_state(state)
    script = write_launch_script(app)
    print(json.dumps({"Type": "LaunchOptions", "Content": {
        "Exe": str(script),
        "Options": "",
        "WorkingDir": str(HOME),
        "Compatibility": False,
        "Name": app["title"],
    }}))


def action_uninstall(shortname):
    app = APPS[shortname]
    state = load_state()
    try:
        if app["kind"] == "flatpak":
            # Uninstall from wherever it actually lives. A system flatpak needs
            # privileges the user backend may not have (polkit) — surface that
            # rather than silently doing nothing.
            scope = flatpak_scope(app["ref"]) or "user"
            r = flatpak("uninstall", f"--{scope}", "-y", app["ref"], timeout=600)
            if r.returncode != 0:
                msg = (r.stderr or r.stdout).strip()
                if scope == "system":
                    raise RuntimeError(
                        "This app is installed system-wide and removing it needs "
                        "admin rights. Uninstall it from Discover or the desktop. "
                        + msg[-200:])
                raise RuntimeError(msg[-300:])
        elif app["kind"] == "appimage":
            dest = APPS_DIR / f"{app['title'].replace(' ', '')}.AppImage"
            dest.unlink(missing_ok=True)
        # ssl: the shared AppImage stays for the other web apps
    except Exception as e:
        print(json.dumps({"Type": "Error", "Content": {"Message": str(e)}}))
        return
    state["apps"].pop(shortname, None)
    save_state(state)
    try:
        (SCRIPTS_DIR / f"{shortname}.sh").unlink()
    except Exception:
        pass
    print(json.dumps({"Type": "Success", "Content": {"Message": "Uninstalled"}}))


def worker_autoupdate():
    """Silent daily maintenance: refresh AppImages when their release tag
    changed and update user flatpaks that we installed."""
    state = load_state()
    try:
        installed_ssl = [s for s, st in state["apps"].items()
                         if st.get("installed") and APPS.get(s, {}).get("kind") == "ssl"]
        if installed_ssl and SSL_APPIMAGE.exists():
            tag, url = gh_latest(SSL_REPO)
            if tag and url and tag != state.get("ssl_tag"):
                download_file(url, SSL_APPIMAGE, installed_ssl[0], 0, 0, "update")
                state["ssl_tag"] = tag
                for s in installed_ssl:
                    state["apps"][s]["tag"] = tag
        for s, st in list(state["apps"].items()):
            app = APPS.get(s)
            if not app or not st.get("installed"):
                continue
            if app["kind"] == "appimage":
                tag, url = gh_latest(app["ref"])
                if tag and url and tag != st.get("tag"):
                    dest = APPS_DIR / f"{app['title'].replace(' ', '')}.AppImage"
                    download_file(url, dest, s, 0, 0, "update")
                    st["tag"] = tag
            elif app["kind"] == "flatpak":
                flatpak("update", "--user", "-y", app["ref"])
    except Exception as e:
        print(f"autoupdate: {e}", file=sys.stderr)
    state["last_check"] = int(time.time())
    save_state(state)


def action_init():
    state = load_state()
    refresh_installed_launch_scripts(state)
    if time.time() - state.get("last_check", 0) > 86400 and any(
            st.get("installed") for st in state["apps"].values()):
        subprocess.Popen([PYEXE, os.path.abspath(__file__), "autoupdate"],
                         start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=os.environ.copy())
    print(json.dumps({"Type": "Success", "Content": {"Message": "Initialized"}}))


def main():
    argv = sys.argv[1:]
    if not argv:
        print(json.dumps({"Type": "Error", "Content": {"Message": "no action"}}))
        return
    action, args = argv[0], argv[1:]
    if action == "getgames":
        action_getgames(args[0], args[1] if len(args) > 1 else "",
                        args[2] if len(args) > 2 else "false")
    elif action == "getgamedetails":
        action_getgamedetails(args[0])
    elif action == "getjsonimages":
        action_getjsonimages(args[0])
    elif action == "download":
        action_download(args[0])
    elif action == "worker":
        worker_install(args[0])
    elif action == "autoupdate":
        worker_autoupdate()
    elif action == "getprogress":
        action_getprogress(args[0])
    elif action == "cancelinstall":
        action_cancelinstall(args[0])
    elif action == "install":
        action_install(args[0], args[1] if len(args) > 1 else "")
    elif action == "uninstall":
        action_uninstall(args[0])
    elif action == "init":
        action_init()
    elif action == "getgamesize":
        print(json.dumps({"Type": "GameSize", "Content": {"Size": ""}}))
    else:
        print(json.dumps({"Type": "Error", "Content": {"Message": f"unknown action {action}"}}))


if __name__ == "__main__":
    main()
