#!/usr/bin/env python3
"""Experimental Maxima adapter. No automatic login; no secrets in plugin output."""
import fcntl
from contextlib import contextmanager
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import selectors
import signal
import tempfile
import time
import uuid
import urllib.parse
import urllib.request

# Maxima v0.14.3 (Starkka15/Maxima, GPL-3.0) rebuilt with the small patch in
# maxima-patches/: game language over LSX via MAXIMA_LOCALE, and the 32-bit
# Origin registry key games need to reach LSX at all. The binary is attached
# to the SkullKey release that introduced it and pinned by digest.
VERSION = "v0.14.3-skullkey2"
SHA256 = "873e2c10364086142568e95b652965a10dfe26684c21baf909683a1da199a199"
URL = "https://github.com/Necrosiak/SkullKey/releases/download/v1.21.3/maxima-cli-skullkey-linux-x86_64"
# maxima-cli pads slug/name/offer to 35/35/25 columns as a MINIMUM: a slug or
# title of 35+ characters is followed by a single space. Parse from the right
# instead (slug has no spaces, offer has none, the title may contain " - ").
ROW = re.compile(r"^\s*(?P<slug>\S+)\s+-\s(?P<name>.+)\s-\s(?P<offer>\S+)\s+-\sInstalled:\s(?P<installed>true|false)\s*$")


def root():
    account = os.environ.get("SK_ACCOUNT_DIR")
    if not account or not Path(account).is_absolute():
        raise RuntimeError("EA requires the current SkullKey Steam-account directory.")
    path = Path(account) / "ea"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def env():
    result = os.environ.copy()
    # Browser/protocol resolution belongs to the desktop session, not Maxima's
    # account-isolated storage. Preserve only these non-secret XDG overrides.
    for key in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        result.pop("SK_EA_BROWSER_" + key, None)
        if key in os.environ:
            result["SK_EA_BROWSER_" + key] = os.environ[key]
    result["XDG_DATA_HOME"] = str(root() / "data")
    result["XDG_CONFIG_HOME"] = str(root() / "config")
    result["XDG_CACHE_HOME"] = str(root() / "cache")
    # v0.14.3 accepts only maxima-qrc.desktop and otherwise tries to create a
    # missing bootstrap handler inside the isolated data directory. SkullKey
    # installs its own callback explicitly; upstream must not replace it.
    result["MAXIMA_DISABLE_QRC"] = "1"
    result["BROWSER"] = str(Path(__file__).with_name("open_browser.py").resolve())
    # Never pass arbitrary runtime overrides or tracing into the EA process.
    for key in ("MAXIMA_WINE_COMMAND", "RUST_LOG", "RUST_BACKTRACE", "LD_PRELOAD", "MAXIMA_LOG_LEVEL"):
        result.pop(key, None)
    # Decky starts store actions with an almost empty environment (measured
    # 11/10/2026: no PATH, USER, XDG_RUNTIME_DIR or DISPLAY). umu-run is a
    # `#!/usr/bin/env python3` script, so the post-download Touchup.exe step
    # failed silently and maxima-cli then waited forever at 99 %.
    import pwd
    uid = os.getuid()
    defaults = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "XDG_RUNTIME_DIR": f"/run/user/{uid}"}
    try:
        defaults["USER"] = defaults["LOGNAME"] = pwd.getpwuid(uid).pw_name
    except KeyError:
        pass
    if not (result.get("DISPLAY") or result.get("WAYLAND_DISPLAY")):
        defaults["DISPLAY"] = ":0"
    for key, value in defaults.items():
        if not result.get(key):
            result[key] = value
    # Maxima v0.14.3 hard-codes en_US as the game locale; our bootstrap
    # stand-in replaces it with the language picked in the EA tab settings.
    result["SK_EA_LOCALE"] = game_locale()
    result["MAXIMA_LOCALE"] = result["SK_EA_LOCALE"]
    return result


STEAM_LANGUAGES = {
    "english": "en_US", "french": "fr_FR", "german": "de_DE", "spanish": "es_ES",
    "latam": "es_MX", "italian": "it_IT", "brazilian": "pt_BR", "polish": "pl_PL",
    "russian": "ru_RU", "dutch": "nl_NL", "japanese": "ja_JP", "koreana": "ko_KR",
    "tchinese": "zh_TW", "schinese": "zh_CN", "arabic": "ar_SA",
}


def steam_locale():
    # Default: the Steam (= SteamOS/SkullKey) UI language, like the EA app
    # defaulting to the system language when it asks before an install.
    try:
        text = Path(os.path.expanduser("~/.steam/registry.vdf")).read_text(errors="replace")
        match = re.search(r'"language"\s+"([a-z]+)"', text)
        if match:
            return STEAM_LANGUAGES.get(match[1], "en_US")
    except OSError:
        pass
    return "en_US"


def game_locale():
    # Steam shortcuts run without Decky's variables: the runtime dir is also
    # two levels above the account dir (<runtime>/accounts/<steam id>).
    account = os.environ.get("SK_ACCOUNT_DIR")
    runtime = str(Path(account).parent.parent) if account else None
    for base in (os.environ.get("DECKY_PLUGIN_RUNTIME_DIR"), runtime,
                 str(Path(__file__).resolve().parents[3])):
        if not base:
            continue
        try:
            config = json.loads((Path(base) / "conf_schemas/eatabconfig.json").read_text())
            for section in config.get("Sections", []):
                for option in section.get("Options", []):
                    if option.get("Key") == "Language":
                        if re.fullmatch(r"[a-z]{2}_[A-Z]{2}", option.get("Value", "")):
                            return option["Value"]
                        return steam_locale()  # "auto"
        except Exception:
            pass
    return steam_locale()


@contextmanager
def session_lock():
    # OAuth listens on one fixed machine-wide port, even across accounts.
    with (root().parent.parent / "skullkey-ea-session.lock").open("a") as shared, (root() / "session.lock").open("a") as account:
        fcntl.flock(shared, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(account, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def state():
    try:
        return json.loads((root() / "state.json").read_text())
    except (OSError, ValueError):
        return {"games": [], "settings": {}, "shortcuts": {}, "validated": False}


def save(value):
    with tempfile.NamedTemporaryFile(mode="w", dir=root(), delete=False) as stream:
        json.dump(value, stream)
        path = Path(stream.name)
    path.replace(root() / "state.json")


def client():
    # Pinned version, verified digest. No latest/auto-upgrade during a game.
    path = root() / "maxima-cli"
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == SHA256:
        return path
    part = root() / "maxima-cli.part"
    with urllib.request.urlopen(URL, timeout=60) as response, part.open("wb") as out:
        while data := response.read(1024 * 1024):
            out.write(data)
    if hashlib.sha256(part.read_bytes()).hexdigest() != SHA256:
        part.unlink()
        raise RuntimeError("Maxima download integrity check failed.")
    part.chmod(0o700)
    part.replace(path)
    return path


def localized_client(locale=None):
    # The patched build reads the game language from MAXIMA_LOCALE (env()).
    return client()


def parse_library(output):
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    if re.search(r"\bERROR\b", output) or "Owned games:" not in output:
        raise RuntimeError("EA library could not be validated. Sign in and retry.")
    games = []
    for line in output.splitlines():
        # Maxima log prefix precedes the fixed-width record.
        line = re.sub(r"^INFO\s+-\s+\[[^]]*\]\s+-\s+", "", line)
        match = ROW.match(line)
        if match:
            g = match.groupdict()
            games.append({"slug": g["slug"], "name": g["name"].strip(), "offer": g["offer"],
                          "installed": g["installed"] == "true"})
        elif " - Installed:" in line:
            raise RuntimeError("Unexpected Maxima library format; no partial import.")
    return games


def login_diagnostic(stage, error=None, **fields):
    # Whitelisted metadata only; neither exception text nor argv are safe.
    allowed = {"validated", "display_available", "exit_code", "elapsed_seconds",
               "failure_category"}
    data = {"stage": stage, "version": VERSION,
            **{k: v for k, v in fields.items() if k in allowed}}
    if error is not None:
        data["error_type"] = type(error).__name__
        if isinstance(error, subprocess.CalledProcessError):
            data["exit_code"] = error.returncode
    with tempfile.NamedTemporaryFile(mode="w", dir=root(), delete=False) as stream:
        json.dump(data, stream)
        temporary = Path(stream.name)
    temporary.replace(root() / "login-diagnostic.json")


def refresh():
    # Capture only in memory. Never log account-info/auth-env or raw CLI output.
    started = time.monotonic()
    login_diagnostic("cli-start", validated=False)
    try:
        result = subprocess.run([str(client()), "list-games"], env=env(),
                                capture_output=True, text=True, timeout=600)
    except Exception as error:
        login_diagnostic("cli-start", error, validated=False)
        raise
    # Diagnostic metadata only: never store raw CLI output, URLs or tokens.
    diagnostic = {"stage": "list-games", "version": VERSION, "exit_code": result.returncode,
                  "elapsed_seconds": round(time.monotonic() - started, 1), "validated": False}
    output = result.stdout + "\n" + result.stderr
    try:
        if result.returncode:
            raise RuntimeError("Maxima library request failed.")
        games = parse_library(output)
        diagnostic["validated"] = True
    except RuntimeError:
        # Fixed categories only. Upstream errors may contain URLs or tokens.
        lower = output.lower()
        diagnostic["failure_category"] = next((category for category, markers in (
            ("protocol-handler", ("qrc protocol", "mime type", "query mime")),
            ("filesystem", ("no such file or directory", "permission denied")),
            ("network", ("connection refused", "timed out", "dns error")),
            ("browser", ("xdg-open", "failed to open browser")),
        ) if any(marker in lower for marker in markers)), "upstream-or-library-format")
        raise
    finally:
        with tempfile.NamedTemporaryFile(mode="w", dir=root(), delete=False) as stream:
            json.dump(diagnostic, stream)
            temporary = Path(stream.name)
        temporary.replace(root() / "login-diagnostic.json")
    s = state()
    s.update(games=games, validated=True)
    save(s)


# Artwork works for any EA library, not a fixed list: Steam's official
# library art when the title matches a Steam store page exactly, otherwise
# GOG's public games database, which knows every Origin/EA offer ID (measured
# 11/10/2026: 38/38 offers found, 23/38 on Steam). Only public URLs are
# cached; nothing account-related is sent besides the game title/offer ID.
STEAM_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"
GAMESDB = "https://gamesdb.gog.com/platforms/origin/external_releases/"


def _http_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def _norm(text):
    return "".join(c for c in text.lower() if c.isalnum())


def _steam_appid(name):
    clean = re.sub(r"[™®©]", "", name).strip()
    try:
        url = "https://store.steampowered.com/api/storesearch/?l=english&cc=US&term=" + urllib.parse.quote(clean)
        for item in _http_json(url).get("items", []):
            if _norm(item.get("name", "")) == _norm(clean):
                return item["id"]
    except Exception as error:
        print(f"steam lookup failed: {type(error).__name__}", file=sys.stderr)
    return None


def _gamesdb_art(offer):
    try:
        data = _http_json(GAMESDB + urllib.parse.quote(offer, safe=""))
    except Exception as error:
        print(f"gamesdb lookup failed: {type(error).__name__}", file=sys.stderr)
        return {}
    info = data.get("game") or {}

    def url(*keys):
        for key in keys:
            fmt = (info.get(key) or {}).get("url_format")
            if fmt:
                return fmt.replace("{formatter}", "").replace("{ext}", "jpg")
        return None
    art = {"grid": url("vertical_cover", "cover"), "gridh": url("horizontal_artwork", "background"),
           "hero": url("background", "horizontal_artwork"), "icon": url("square_icon")}
    # gamesdb's "logo" is usually the box art; images() only keeps it when it
    # really looks like a logo (landscape PNG with transparency).
    logo = url("logo")
    if logo:
        art["logo"] = logo.replace(".jpg", ".png")
    art["title"] = (info.get("title") or {}).get("*")
    return {k: v for k, v in art.items() if v}


def _looks_like_logo(data):
    # PNG IHDR: width/height at 16..24, colour type 6 (RGBA) at 25. No Pillow.
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 26:
        return False
    width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return data[25] in (4, 6) and width > height * 1.3


def artwork(g):
    path = root() / "artwork.json"
    try:
        cache = json.loads(path.read_text())
    except Exception:
        cache = {}
    key = g.get("offer") or g["slug"]
    if key in cache:
        return cache[key]
    # Candidates per slot, best first; older Steam apps lack some library art.
    gamesdb = _gamesdb_art(g["offer"]) if g.get("offer") else {}
    art = {slot: [gamesdb[slot]] if slot in gamesdb else [] for slot in ("grid", "gridh", "hero", "logo", "icon")}
    # EA's library names are often short ("Command & Conquer 3"); gamesdb's
    # official title ("…: Tiberium Wars") finds more Steam pages.
    appid = _steam_appid(g["name"]) or (gamesdb.get("title") and _steam_appid(gamesdb["title"]))
    if appid:
        base = f"{STEAM_CDN}/{appid}"
        for slot, name in (("grid", "library_600x900_2x.jpg"), ("gridh", "header.jpg"),
                           ("hero", "library_hero.jpg"), ("logo", "logo.png")):
            art[slot].insert(0, f"{base}/{name}")
    cache[key] = art
    with tempfile.NamedTemporaryFile(mode="w", dir=root(), delete=False) as stream:
        json.dump(cache, stream)
        temporary = Path(stream.name)
    temporary.replace(path)
    return art


def images(g):
    # Steam-style slots, each downloaded and sent as base64 with its type.
    import base64
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    art = artwork(g)
    for slot, key in (("Grid", "grid"), ("GridH", "gridh"), ("Hero", "hero"), ("Logo", "logo")):
        for url in art.get(key, []):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = response.read()
                if slot == "Logo" and STEAM_CDN not in url and not _looks_like_logo(data):
                    continue
                content[slot] = base64.b64encode(data).decode()
                content[slot + "Type"] = "png" if url.split("?")[0].endswith(".png") else "jpg"
                break
            except Exception as error:
                print(f"artwork {slot} failed: {type(error).__name__}", file=sys.stderr)
    # Shortcut icon: Steam wants a local file path.
    for url in art.get("icon", []):
        icon = root() / "art" / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".png")
        try:
            if not icon.exists():
                icon.parent.mkdir(parents=True, exist_ok=True)
                request = urllib.request.Request(url.replace(".jpg", ".png"), headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(request, timeout=20) as response:
                    icon.write_bytes(response.read())
            content["IconPath"] = str(icon)
            break
        except Exception as error:
            print(f"artwork icon failed: {type(error).__name__}", file=sys.stderr)
    return content


def game_info(g):
    # Summary, developer, publisher, genres and release date for any EA game,
    # in the chosen language when possible: the Steam store page of the same
    # game (already matched for artwork) is localized; GOG's games database
    # (found by offer ID for every EA game) is the English fallback. Cached
    # per offer and language; only public store data, nothing account-related.
    locale = game_locale()
    path = root() / "info.json"
    try:
        cache = json.loads(path.read_text())
    except Exception:
        cache = {}
    key = (g.get("offer") or g["slug"]) + "|" + locale
    if key in cache:
        return cache[key]
    info = {}
    steam = next((re.search(r"/steam/apps/(\d+)/", u) for u in artwork(g).get("grid", []) if "/steam/apps/" in u), None)
    if steam:
        language = next((k for k, v in STEAM_LANGUAGES.items() if v == locale), "english")
        try:
            data = _http_json("https://store.steampowered.com/api/appdetails?appids=%s&l=%s" % (steam[1], language))
            d = (data.get(steam[1]) or {}).get("data") or {}
            info = {"summary": html.unescape(re.sub(r"<[^>]+>", "", d.get("short_description") or "")).strip(),
                    "developers": d.get("developers") or [], "publishers": d.get("publishers") or [],
                    "genres": [x.get("description") for x in d.get("genres") or [] if x.get("description")],
                    "released": (d.get("release_date") or {}).get("date") or ""}
        except Exception as error:
            print(f"steam details failed: {type(error).__name__}", file=sys.stderr)
    if not info.get("summary") and g.get("offer"):
        try:
            d = (_http_json(GAMESDB + urllib.parse.quote(g["offer"], safe="")).get("game") or {})
            name = lambda x: (x.get("name") or {}).get("*") if isinstance(x.get("name"), dict) else x.get("name")
            info = {"summary": html.unescape(re.sub(r"<[^>]+>", "", (d.get("summary") or {}).get("*") or "")).strip(),
                    "developers": [x["name"] for x in d.get("developers") or [] if x.get("name")],
                    "publishers": [x["name"] for x in d.get("publishers") or [] if x.get("name")],
                    "genres": [n for n in map(name, d.get("genres") or []) if n],
                    "released": (d.get("first_release_date") or "")[:10]}
        except Exception as error:
            print(f"gamesdb details failed: {type(error).__name__}", file=sys.stderr)
    cache[key] = info
    with tempfile.NamedTemporaryFile(mode="w", dir=root(), delete=False) as stream:
        json.dump(cache, stream)
        temporary = Path(stream.name)
    temporary.replace(path)
    return info


def description(g):
    # Same layout as the GOG/Epic game pages (shared/GameSet.py).
    info = game_info(g)
    esc = html.escape
    out = ("<div style=' width: 100%;'><p style='width:100%; white-space: pre-wrap;'>"
           + esc(info.get("summary") or g["name"]) + "</p></div><div>")
    for label, value in (("Publisher", ", ".join(info.get("publishers") or [])),
                         ("Developer", ", ".join(info.get("developers") or [])),
                         ("Genre", ", ".join(info.get("genres") or [])),
                         ("Release Date", info.get("released") or "")):
        if value:
            out += "<p>%s: %s</p>" % (label, esc(value))
    return out + "<p>EA / Maxima</p></div>"


def cover(g):
    # Grid tile in SkullKey: first candidate URL, no download needed.
    try:
        # Last candidate = gamesdb, which always exists; Steam's 2x capsule
        # is missing for some older apps and would show a broken tile.
        return (artwork(g).get("grid") or [None])[-1]
    except Exception:
        return None


def apply_locale_filter(directory, locale):
    # The EA app only installs the language files of the language picked at
    # install time: __Installer/installerdata.xml lists them per locale in
    # <localeFilters> (Jedi: Fallen Order: French = pakchunk3, English =
    # pakchunk2…). Maxima ignores that table and installs every language, and
    # games then start in the first one they find (measured 12/10/2026: same
    # install on Windows in French = only pakchunk3; Maxima = pakchunk1–10,
    # game in English). Remove files that belong to OTHER languages only.
    import fnmatch
    import xml.etree.ElementTree as ET
    manifest = directory / "__Installer" / "installerdata.xml"
    try:
        root_el = ET.parse(manifest).getroot()
    except (OSError, ET.ParseError):
        return 0
    filters = {}
    for inc in root_el.iter("includes"):
        loc = inc.get("locale")
        if loc:
            filters.setdefault(loc, []).extend(
                (i.text or "").strip().replace("\\", "/").lstrip("/").lower() for i in inc.iter("include"))
    if locale not in filters:
        return 0  # language not offered by this game: keep everything
    keep = [p for p in filters[locale] if p]
    other = {p for loc, pats in filters.items() if loc != locale for p in pats if p} - set(keep)
    removed = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix().lower()
        if any(fnmatch.fnmatch(rel, p) for p in other) and not any(fnmatch.fnmatch(rel, p) for p in keep):
            path.unlink()
            removed += 1
    return removed


def set_registry_locale(locale):
    # EA's Touchup.exe writes the game language to the registry at install
    # time ("Locale"="en_US" under the game's key, measured on Dead Space 2
    # and Jedi: Fallen Order) and Maxima always passes en_US to it. Games read
    # that value, so rewrite it to the chosen language before every launch.
    # Only plain xx_XX values are touched (Windows' own "Locale" entries are
    # "*", "" or hex codes).
    registry = root() / "data/maxima/wine/prefix/system.reg"
    if not re.fullmatch(r"[a-z]{2}_[A-Z]{2}", locale) or not registry.is_file():
        return
    text = registry.read_text(encoding="utf-8", errors="surrogateescape")
    updated = re.sub(r'^"Locale"="[a-z]{2}_[A-Z]{2}"$', f'"Locale"="{locale}"', text, flags=re.M)
    if updated != text:
        temporary = registry.with_suffix(".reg.skullkey")
        temporary.write_text(updated, encoding="utf-8", errors="surrogateescape")
        temporary.replace(registry)


def game_dir(slug):
    # Where this game is installed: the drive picked at install time
    # (<drive>/SkullKey/ea/<slug>, stored in state "paths") or the default.
    path = state().get("paths", {}).get(slug)
    return Path(path) if path else root() / "games" / slug


def clear_download_state(slug):
    # Maxima keeps per-offer resume state (data/maxima/temp/downloader/<offer>)
    # regardless of the install path. Resuming it into a fresh folder writes
    # chunks at the wrong offsets: measured 11/10/2026, a cancelled install
    # then restarted on another drive produced corrupt files (DirectX cab
    # "not trusted", Touchup stuck on an invisible error). Start clean.
    g = game(slug)
    offer = (g or {}).get("offer")
    if not offer or "/" in offer or offer in (".", ".."):
        return
    shutil.rmtree(root() / "data/maxima/temp/downloader" / offer, ignore_errors=True)


def choose_game_dir(slug):
    # Fresh install: honour the drive picked in SkullKey's install dialog.
    previous = game_dir(slug)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
    import drives
    base = Path(drives.install_dir("ea", str(root() / "games")))
    s = state()
    paths = s.setdefault("paths", {})
    if base.resolve() == (root() / "games").resolve():
        paths.pop(slug, None)
    else:
        paths[slug] = str(base / slug)
    save(s)
    if game_dir(slug) != previous or not any(game_dir(slug).glob("*")):
        clear_download_state(slug)


def merge_case_duplicates(directory):
    # EA builds come from Windows, where paths ignore case. Maxima writes each
    # file with the case its manifest uses, so one folder can end up split
    # (measured on Theme Hospital: data/Game/DOSBOX and data/Game/DOSBox) and
    # the game's own launcher is then "not found". Merge such siblings into
    # one folder; never overwrite a file that exists on both sides.
    if not directory.is_dir():
        return
    groups = {}
    for child in directory.iterdir():
        if child.is_dir() and not child.is_symlink():
            groups.setdefault(child.name.lower(), []).append(child)
    for folders in groups.values():
        folders.sort(key=lambda p: sum(1 for _ in p.rglob("*")), reverse=True)
        keep = folders[0]
        for other in folders[1:]:
            for item in list(other.iterdir()):
                target = next((c for c in keep.iterdir() if c.name.lower() == item.name.lower()), None)
                if target is None:
                    item.rename(keep / item.name)
                elif target.is_dir() and item.is_dir():
                    # Same subfolder on both sides: move its content across.
                    for sub in list(item.iterdir()):
                        if not any(c.name.lower() == sub.name.lower() for c in target.iterdir()):
                            sub.rename(target / sub.name)
            try:
                other.rmdir()
            except OSError:
                pass  # leftovers (true conflicts) stay where they were
    for child in directory.iterdir():
        if child.is_dir() and not child.is_symlink():
            merge_case_duplicates(child)


LAUNCH_ERRORS = {
    "not_entitled": {
        "en": "EA refused to start {name}: this account no longer owns it (for example a Game Pass or EA Play title that has ended). You can uninstall it from SkullKey.",
        "fr": "EA a refusé de lancer {name} : ce compte ne possède plus ce jeu (par exemple un jeu Game Pass ou EA Play terminé). Vous pouvez le désinstaller depuis SkullKey.",
        "de": "EA hat den Start von {name} verweigert: Dieses Konto besitzt das Spiel nicht mehr (z. B. ein beendetes Game-Pass- oder EA-Play-Spiel). Du kannst es in SkullKey deinstallieren.",
        "es": "EA se ha negado a iniciar {name}: esta cuenta ya no posee el juego (por ejemplo, un juego de Game Pass o EA Play que ha terminado). Puedes desinstalarlo desde SkullKey.",
        "it": "EA ha rifiutato di avviare {name}: questo account non possiede più il gioco (ad esempio un titolo Game Pass o EA Play terminato). Puoi disinstallarlo da SkullKey.",
        "pt": "A EA recusou iniciar {name}: esta conta já não possui o jogo (por exemplo, um jogo do Game Pass ou EA Play que terminou). Pode desinstalá-lo no SkullKey.",
        "nl": "EA weigert {name} te starten: dit account bezit het spel niet meer (bijvoorbeeld een beëindigde Game Pass- of EA Play-titel). Je kunt het verwijderen in SkullKey.",
        "pl": "EA odmówiło uruchomienia {name}: to konto nie posiada już tej gry (np. zakończony tytuł Game Pass lub EA Play). Możesz ją odinstalować w SkullKey.",
        "ru": "EA отказала в запуске {name}: этот аккаунт больше не владеет игрой (например, закончилась подписка Game Pass или EA Play). Игру можно удалить в SkullKey.",
    },
}


def show_error(name, kind):
    # Launched from a Steam shortcut: a zenity dialog is shown by gamescope
    # like the game window would be (zenity ships with SteamOS and Bazzite).
    text = LAUNCH_ERRORS[kind].get(game_locale()[:2], LAUNCH_ERRORS[kind]["en"]).format(name=name)
    print(text, file=sys.stderr)
    if shutil.which("zenity"):
        subprocess.run(["zenity", "--error", "--title", "SkullKey — EA", "--width", "600", "--text", text],
                       env=dict(os.environ, DISPLAY=os.environ.get("DISPLAY") or ":0"), check=False)


def game(slug):
    if not re.fullmatch(r"[\w-][\w.-]{0,119}", slug) or slug in (".", ".."):
        raise RuntimeError("Invalid EA game identifier.")
    return next((g for g in state()["games"] if g["slug"] == slug), None)


def job_path(slug):
    if not game(slug):
        raise RuntimeError("Game is not owned by this EA account.")
    return root() / f"job-{slug}.json"


def read_job(slug):
    try:
        data = json.loads(job_path(slug).read_text())
        if data.get("active"):
            pid = data.get("worker_pid")
            dead = (pid and process_identity(pid) != data.get("worker_start"))
            abandoned = not pid and time.time() - data.get("created", time.time()) > 30
            if dead or abandoned:
                data.update(active=False, Percentage=0, Description="Installation interrupted",
                            Error="Worker stopped; downloaded files kept")
        return data
    except (OSError, ValueError):
        return {"Percentage": 0, "Description": "Waiting…", "Error": None}


def process_identity(pid):
    try:
        # Field 22, after comm (which may itself contain spaces).
        return Path(f"/proc/{int(pid)}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, ValueError, IndexError):
        return None


def write_job(slug, data):
    with tempfile.NamedTemporaryFile(mode="w", dir=root(), delete=False) as stream:
        json.dump(data, stream)
        temporary = Path(stream.name)
    temporary.replace(job_path(slug))


def cancelled(slug, token):
    try:
        return (root() / f"cancel-{slug}").read_text() == token
    except OSError:
        return False


def installation_verified(slug, directory, output):
    # Maxima sometimes logs an error and exits zero. Require independent
    # installed metadata plus actual downloaded files, not its exit code.
    if re.search(r"\bERROR\b", output):
        return False
    records = []
    for line in output.splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            pass
    return (any(isinstance(item, dict) and item.get("slug") == slug
                and item.get("installed") is True for item in records)
            and directory.is_dir() and any(p.is_file() and p.stat().st_size > 0
                                          for p in directory.rglob("*")))


ERROR_KINDS = (("space", "disk-space"), ("no space", "disk-space"), ("permission", "permission"),
               ("timed out", "network"), ("timeout", "network"), ("connection", "network"),
               ("dns", "network"), ("certificate", "network"), ("hash", "checksum"),
               ("checksum", "checksum"), ("umu", "runtime"), ("proton", "runtime"), ("wine", "runtime"),
               ("steamrt", "runtime"), ("license", "license"), ("entitlement", "license"),
               ("auth", "auth"), ("token", "auth"), ("touchup", "installer"), ("download", "download"))


def error_kind(line):
    """A fixed category for an EA CLI error line; the line itself is never kept."""
    lower = line.lower()
    return next((kind for marker, kind in ERROR_KINDS if marker in lower), "other")

def installer_exit_code(slug):
    if not (game(slug) or {}).get("installed"):
        return None
    code = state().get("installer_warnings", {}).get(slug)
    if code is None:
        try:
            diagnostic = json.loads((root() / f"install-diagnostic-{slug}.json").read_text())
            if diagnostic.get("stage") == "done":
                code = diagnostic.get("touchup_exit")
        except (OSError, ValueError):
            pass
    return code if isinstance(code, int) and not isinstance(code, bool) and code != 0 else None


def launch_environment(slug):
    environment = env()
    if slug == "medal-of-honor-allied-assault":
        # Mesa documents extension-string overflow crashes in old OpenGL
        # games. Restrict this compatibility workaround to this game only.
        environment.setdefault("MESA_EXTENSION_MAX_YEAR", "2002")
    return environment


def launch_diagnostic(slug, started, result):
    """Fixed launch error categories only; never retain CLI text or CD keys."""
    output = (result.stdout + "\n" + result.stderr).lower()
    markers = {
        "opengl": ("could not load opengl", "couldn't load opengl", "glw_startopengl", "failed to initialize opengl"),
        "video-mode": ("couldn't set video mode", "could not set video mode", "failed to create window"),
        "missing-game-data": ("couldn't load default.cfg", "could not load default.cfg", "couldn't load pak"),
        "entitlement": ("not_entitled",),
        "activation": ("activation failed", "invalid cd key", "invalid cd-key", "cd key required"),
        "wine-exception": ("unhandled exception", "unhandled page fault"),
    }
    data = {"version": VERSION, "exit_code": result.returncode,
            "elapsed_seconds": round(max(0, time.monotonic() - started), 1),
            "categories": [kind for kind, words in markers.items() if any(word in output for word in words)]}
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=root(), delete=False) as stream:
            json.dump(data, stream)
            temporary = Path(stream.name)
        temporary.replace(root() / f"launch-diagnostic-{slug}.json")
    except OSError:
        pass


def install_diagnostic(slug, stage, started, **fields):
    """Allowlisted metadata only: never CLI output, paths, OAuth or job tokens."""
    allowed = {"progress", "cli_error_seen", "exit_code", "failure_category",
               "activity_hint", "umu_available", "python_available", "display_available", "failed_stage",
               "max_progress", "error_kind", "maxima_umu_present", "maxima_proton_present",
               "watchdog", "lingering", "touchup_exit"}
    now = time.time()
    data = {"version": VERSION, "stage": stage, "updated_at": now,
            "elapsed_seconds": round(max(0, now - started), 1),
            **{k: v for k, v in fields.items() if k in allowed}}
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=root(), delete=False) as stream:
            json.dump(data, stream)
            temporary = Path(stream.name)
        temporary.replace(root() / f"install-diagnostic-{slug}.json")
    except OSError:
        pass  # A diagnostic write must not stop the user's installation.


PREPARING_PROTON = "Preparing Proton for EA games (first install only, about 3 GB)…"


INSTALLER_WAITING = "The game's installer may be waiting for an answer: look for its window."
CLOSING_LEFTOVERS = "Closing what the game's installer left open…"
FINISHING_INSTALL = "Finishing the EA installation…"
WINE_INFRA = {"wineserver", "services.exe", "winedevice.exe", "plugplay.exe", "svchost.exe", "explorer.exe",
              "rpcss.exe", "tabtip.exe", "conhost.exe", "steam.exe", "start.exe", "wineboot.exe"}
REDISTRIBUTABLES = ("dxsetup", "dxwebsetup", "vcredist", "vc_redist", "dotnetfx", "ndp4", "physx", "oalinst",
                    "msiexec", "directx", "eareporter")


def prefix_processes(prefix):
    """(pid, exe name, lower-case command line) of the Wine processes in `prefix`."""
    real = os.path.realpath(prefix)
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            environ = Path("/proc", entry, "environ").read_bytes().split(b"\0")
            value = next((v[11:] for v in environ if v.startswith(b"WINEPREFIX=")), None)
            if value is None:
                continue
            path = os.path.realpath(value.decode("utf-8", "replace"))
            if path != real and not path.startswith(real + os.sep):
                continue
            binary = os.path.basename(os.readlink(f"/proc/{entry}/exe"))
            args = Path("/proc", entry, "cmdline").read_bytes().split(b"\0")
        except (OSError, ValueError):
            continue
        if binary == "wineserver":
            yield int(entry), "wineserver", ""
        elif binary.startswith("wine"):
            command = " ".join(a.decode("utf-8", "replace") for a in args if a).lower()
            name = re.split(r"[\\/]", command.split(" ", 1)[0])[-1] if command else ""
            yield int(entry), name if name.endswith(".exe") else name + ".exe", command


def installer_log(directory):
    try:
        installer = next((p for p in Path(directory).iterdir() if p.name.lower() == "__installer" and p.is_dir()), None)
        return next((p for p in installer.iterdir() if p.name.lower() == "installlog.txt" and p.is_file()), None) if installer else None
    except OSError:
        return None


def touchup_checkpoint(directory):
    log = installer_log(directory)
    try:
        stat = log.stat() if log else None
        return (stat.st_dev, stat.st_ino, stat.st_size) if stat else None
    except OSError:
        return None


def touchup_exit(directory, since, checkpoint=None):
    """Only new Touchup completions; bounded reads, never expose log text."""
    log = installer_log(directory)
    try:
        if log is None:
            return None
        with log.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            if stat.st_mtime < since:
                return None
            bom = stream.read(2)
            encoding = "utf-16-le" if bom == b"\xff\xfe" else "utf-16-be" if bom == b"\xfe\xff" else "utf-8"
            offset = 0
            if checkpoint and (stat.st_dev, stat.st_ino) == checkpoint[:2] and stat.st_size >= checkpoint[2]:
                offset = checkpoint[2]
            offset = max(offset, stat.st_size - (4 << 20))
            if encoding.startswith("utf-16"):
                offset += offset % 2
            stream.seek(offset)
            data = stream.read(4 << 20)
    except OSError:
        return None
    codes = re.findall(r"Installer finished with exit code: (-?\d+)", data.decode(encoding, "replace"))
    return int(codes[-1]) if codes else None


def sort_processes(processes, places):
    """Split prefix processes into Touchup, installer leftovers, Wine's own and anything else."""
    touchup, leftovers, infra, others = [], [], [], []
    for pid, name, command in processes:
        if name in WINE_INFRA:
            infra.append((pid, name))
        elif "touchup" in name:
            touchup.append((pid, name))
        elif any(place in command for place in places) or any(r in name for r in REDISTRIBUTABLES):
            leftovers.append((pid, name))
        else:
            others.append((pid, name))
    return touchup, leftovers, infra, others


class InstallActivity:
    """Repeated CLI progress is a heartbeat, not evidence of installer work."""

    def __init__(self):
        self.last_activity = time.monotonic()
        self.progress = -1.0
        self.signatures = []

    def observe(self, text):
        progress = re.findall(r"Progress:\s*(\d+(?:\.\d+)?)", text)
        if progress:
            value = max(float(value) for value in progress)
            if value <= self.progress:
                return
            self.progress = value
        else:
            # Log timestamps change even when the same status is repeated.
            stable = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?", "<time>", text)
            stable = " ".join(stable.split())
            if not stable:
                return
            signature = hashlib.sha256(stable.encode()).digest()
            if signature in self.signatures:
                return
            self.signatures.append(signature)
            del self.signatures[:-128]
        self.last_activity = time.monotonic()


class InstallWatchdog:
    """Maxima waits until every process in its Wine prefix has exited: umu-run's
    runtime reaps the whole tree (measured 29/10/2026, a background process kept
    umu-run alive 43 s instead of 5 s). A redistributable or helper left open
    after Touchup (an error box answered, a DirectX setup that failed) kept EA
    installs at 99 % forever (#10). Only what belongs to this installation is
    closed, and nothing while another program runs in the prefix."""

    def __init__(self, directory):
        self.prefix = root() / "data/maxima/wine/prefix"
        self.places = {"__installer"}
        for path in {str(directory), os.path.realpath(directory)}:
            self.places.add("z:" + path.replace("/", "\\").lower())
        self.directory = directory
        self.started = time.time()
        self.touchup_log = touchup_checkpoint(directory)
        self.action = None
        self.names = []
        self.noted_waiting = False
        self.signalled = set()
        self.idle_since = None
        self.touchup_exit = None
        self.stop_maxima = False

    def _stop(self, found):
        for pid, _ in found:
            try:
                os.kill(pid, signal.SIGKILL if pid in self.signalled else signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.signalled.add(pid)

    def check(self, silent, allow_cleanup=True):
        """A progress message when the watchdog stepped in, else None."""
        touchup, leftovers, infra, others = sort_processes(prefix_processes(self.prefix), self.places)
        if not (touchup or leftovers or infra or others):
            # Maxima treats any non-zero Touchup exit as an error, never
            # counts its last byte, and prints 99.99 % forever with nothing
            # left running (measured 29/10/2026: Battlefield 1942's Touchup
            # ended with code 3 over a Game Explorer entry, #10). Once Touchup
            # has logged its end and the prefix stays empty, Maxima is done.
            code = touchup_exit(self.directory, self.started, self.touchup_log)
            if code is None:
                return None
            self.idle_since = self.idle_since or time.monotonic()
            if time.monotonic() - self.idle_since < 60:
                return None
            self.action, self.touchup_exit, self.stop_maxima = "stopped-maxima", code, True
            return FINISHING_INSTALL
        self.idle_since = None
        if not allow_cleanup:
            return None
        if touchup:
            if silent >= 180 and not self.noted_waiting:
                self.noted_waiting, self.action = True, "installer-waiting"
                return INSTALLER_WAITING
            return None
        if others:
            if silent >= 300:
                self.names = sorted({name for _, name in others})[:5]
            return None
        if leftovers and silent >= 60:
            self.names = sorted({name for _, name in leftovers})[:5]
            self.action = "closed-leftovers"
            self._stop(leftovers)
            return CLOSING_LEFTOVERS
        if not leftovers and infra and silent >= 120:
            self.action = "closed-wine-services"
            self._stop(infra)
            return CLOSING_LEFTOVERS
        return None


def install_worker(slug, token):
    process = None
    job = read_job(slug)
    if job.get("token") != token:
        return
    started = time.time()
    phase = "starting"
    last_report = 0
    failed = False
    activity_hint = "unknown"
    tool_info = {}
    max_progress = 0.0
    first_error = None
    watchdog = None

    def report(stage, **fields):
        nonlocal phase, last_report
        wine = root() / "data/maxima/wine"
        phase = stage
        last_report = time.time()
        job["Stage"] = stage
        if watchdog is not None:
            fields = {"watchdog": watchdog.action, "lingering": watchdog.names,
                      "touchup_exit": watchdog.touchup_exit, **fields}
        install_diagnostic(slug, stage, started,
                           progress=job.get("Percentage", 0), cli_error_seen=failed,
                           activity_hint=activity_hint, max_progress=max_progress,
                           error_kind=first_error, maxima_umu_present=(wine / "umu/umu-run").is_file(),
                           maxima_proton_present=(wine / "proton").is_dir(), **tool_info, **fields)

    report("starting")
    job.update(worker_pid=os.getpid(), worker_start=process_identity(os.getpid()))
    write_job(slug, job)
    try:
        with session_lock():
            if not state().get("validated") or not (root() / "data/maxima/auth.toml").is_file():
                raise RuntimeError("Explicit EA authentication required")
            directory = game_dir(slug)
            directory.mkdir(parents=True, exist_ok=True)
            environment = env()
            tool_info.update(
                umu_available=bool(shutil.which("umu-run", path=environment.get("PATH", ""))),
                python_available=bool(shutil.which("python3", path=environment.get("PATH", ""))),
                display_available=bool(environment.get("DISPLAY") or environment.get("WAYLAND_DISPLAY")))
            # SkullKey hands Maxima one game at a time (its own download queue
            # orders them). Maxima keeps a cancelled install as the "current"
            # entry of download_queue.json and carries on with it after the
            # requested game, inside the same `install` command: measured
            # 29/10/2026, Battlefield 1942 went on with a Mass Effect install
            # cancelled four days earlier, the CLI never exited and SkullKey
            # showed the other game's progress at 93-99 % (#10).
            (root() / "data/maxima/download_queue.json").unlink(missing_ok=True)
            report("starting-cli")
            watchdog = InstallWatchdog(directory)
            process = subprocess.Popen([str(localized_client()), "install", slug, "--path", str(directory)],
                                       env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            report("cli-running")
            # Bounded streaming; raw logs and account identifiers never persist.
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            pending = b""
            failed = False
            deadline = time.monotonic() + 12 * 3600
            activity = InstallActivity()
            next_check = 0.0
            try:
                while selector.get_map() or process.poll() is None:
                    current = read_job(slug)
                    if current.get("token") != token or cancelled(slug, token):
                        raise InterruptedError("Cancelled")
                    if time.monotonic() > deadline:
                        raise TimeoutError("Installation timed out")
                    if time.time() - last_report >= 30:
                        report(phase)
                    for key, _ in selector.select(timeout=0.25):
                        chunk = os.read(key.fileobj.fileno(), 8192)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        pending += chunk
                        while b"\n" in pending or b"\r" in pending or len(pending) > 16384:
                            if b"\n" in pending or b"\r" in pending:
                                boundary = min(i for i in (pending.find(b"\n"), pending.find(b"\r")) if i >= 0)
                                line, pending = pending[:boundary], pending[boundary + 1:]
                            else:
                                line, pending = pending[:8192], pending[8192:]
                            text = re.sub(r"\x1b\[[0-9;]*m", "", line.decode("utf-8", "replace"))
                            activity.observe(text)
                            hint = next((label for marker, label in (
                                ("touchup", "touchup"), ("umu", "proton-setup"),
                                ("download complete", "download-complete")) if marker in text.lower()), None)
                            if hint and hint != activity_hint:
                                activity_hint = hint
                                if hint == "proton-setup" and max_progress < 1:
                                    # Maxima prints no progress while it fetches
                                    # Proton and the Steam runtime (~3 GB once).
                                    job["Description"] = PREPARING_PROTON
                                    write_job(slug, job)
                                report(phase)
                            was_failed = failed
                            failed |= bool(re.search(r"\bERROR\b", text))
                            if failed and first_error is None:
                                first_error = error_kind(text)
                            if failed and not was_failed:
                                report(phase)
                            progress = re.search(r"Progress:\s*(\d+(?:\.\d+)?)", text)
                            if progress:
                                max_progress = max(max_progress, float(progress[1]))
                                job["Percentage"] = min(99, float(progress[1]))
                                if float(progress[1]) >= 99:
                                    if watchdog.action not in {"installer-waiting", "closed-leftovers", "closed-wine-services", "stopped-maxima"}:
                                        job["Description"] = "Waiting for EA installation to finish…"
                                    report("waiting-for-cli-exit")
                                else:
                                    job["Description"] = "Downloading EA game…"
                                # Keep any cancellation request written during this read.
                                if cancelled(slug, token):
                                    raise InterruptedError("Cancelled")
                                write_job(slug, job)
                    if max_progress >= 99 and time.monotonic() >= next_check:
                        next_check = time.monotonic() + 15
                        note = watchdog.check(time.monotonic() - activity.last_activity,
                                              allow_cleanup=max_progress >= 100)
                        if note:
                            job["Description"] = note
                            write_job(slug, job)
                        if note or watchdog.names:
                            report(phase, watchdog=watchdog.action, lingering=watchdog.names,
                                   touchup_exit=watchdog.touchup_exit)
                        if watchdog.stop_maxima and process.poll() is None:
                            watchdog.stop_maxima = False
                            try:
                                os.killpg(process.pid, signal.SIGTERM)
                            except ProcessLookupError:
                                pass
                failed |= bool(re.search(rb"\bERROR\b", pending))
            finally:
                selector.close()
                process.stdout.close()
            exit_code = process.wait()
            report("cli-exited", exit_code=exit_code)
            # When the watchdog closed leftovers, Maxima's own verdict is not
            # reliable: the game-info check below decides.
            # Newer Maxima exits on a Touchup error instead of hanging. Permit
            # the same independent verification only with a fresh, nonzero
            # installer completion; unrelated CLI errors must still fail.
            completed = touchup_exit(directory, watchdog.started, watchdog.touchup_log)
            explicit_installer_error = (exit_code != 0 and watchdog.action is None
                                        and completed is not None and completed != 0)
            if completed is not None:
                watchdog.touchup_exit = completed
            if (exit_code or failed) and watchdog.action not in {
                    "stopped-maxima", "closed-leftovers", "closed-wine-services"} and not explicit_installer_error:
                raise RuntimeError("Maxima installation failed")
            report("verifying-installation")
            check = subprocess.run([str(client()), "game-info", slug], env=env(),
                                   capture_output=True, text=True, timeout=120)
            if check.returncode or not installation_verified(slug, directory, check.stdout + "\n" + check.stderr):
                raise RuntimeError("Installed metadata could not be confirmed")
            apply_locale_filter(directory, game_locale())
            report("refreshing-library")
            refresh()
            if not game(slug)["installed"]:
                raise RuntimeError("Library installation state not confirmed")
            # Keep an installer warning separate from installation failure.
            code = watchdog.touchup_exit
            if code is None:
                code = touchup_exit(directory, watchdog.started, watchdog.touchup_log)
                watchdog.touchup_exit = code
            saved = state()
            warnings = saved.setdefault("installer_warnings", {})
            if isinstance(code, int) and code != 0:
                warnings[slug] = code
                job["InstallerExitCode"] = code
            else:
                warnings.pop(slug, None)
                job.pop("InstallerExitCode", None)
            save(saved)
            job.update(Percentage=100, Description="Done", Error=None)
            report("done", exit_code=0)
    except InterruptedError:
        job.update(Percentage=0, Description="Cancelled — downloaded files kept", Error=None)  # a user cancel is not a failure: no error dialog
        report("cancelled")
    except Exception as error:
        job.update(Percentage=0, Description="EA installation could not be validated", Error="EA installation failed; no game files removed")
        report("failed", failed_stage=phase, failure_category="timeout" if isinstance(error, TimeoutError)
               else "session-busy" if isinstance(error, BlockingIOError) else "installation-not-validated")
    finally:
        if process is not None and process.poll() is None:
            # Only our own live child/session. Never trust a stored PID.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        job["active"] = False
        if read_job(slug).get("token") == token:
            write_job(slug, job)


def setup_callback():
    handler = subprocess.run(["xdg-mime", "query", "default", "x-scheme-handler/qrc"],
                             capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    if handler:
        # Preserve a pre-existing user's handler, including other Maxima apps.
        return
    directory = Path.home() / ".local/share/applications"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "skullkey-ea-qrc.desktop"
    helper = Path(__file__).with_name("qrc_callback.py").resolve()
    # Desktop Exec has its own quoting rules, not shell quoting. Escape percent
    # field-code markers in paths; only the final %u may expand.
    def quote(value):
        return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("`", "\\`").replace("$", "\\$") + '"'
    path.write_text("[Desktop Entry]\nType=Application\nName=SkullKey EA callback\nNoDisplay=true\n"
                    + f"Exec={quote(python_command())} {quote(helper)} %u\nMimeType=x-scheme-handler/qrc;\n")
    subprocess.run(["xdg-mime", "default", path.name, "x-scheme-handler/qrc"],
                   capture_output=True, check=True, timeout=10)


def python_command():
    # Decky's embedded interpreter can expose an empty sys.executable.
    executable = sys.executable or shutil.which("python3")
    if not executable or not Path(executable).is_file():
        raise RuntimeError("Python 3 is unavailable for the EA launcher")
    return executable


def launch_options(action, slug=""):
    path = root() / ("login-desktop.sh" if action == "_desktop-login" else "login.sh" if action == "_login" else f"launch-{slug}.sh")
    command = [python_command(), str(Path(__file__).resolve()), action]
    if slug:
        if not game(slug):
            raise RuntimeError("Game is not in this EA library.")
        command.append(slug)
    path.write_text("#!/usr/bin/env bash\nset -eu\numask 077\n"
                    + "export SK_ACCOUNT_DIR=" + shlex.quote(str(root().parent)) + "\n"
                    + "exec " + shlex.join(command) + "\n")
    path.chmod(0o700)
    return {"Exe": str(path), "Options": "", "WorkingDir": str(root()),
            "Compatibility": False, "Name": "EA / Maxima" if not slug else game(slug)["name"]}


def dispatch(action, args):
    slug = args[0] if args else ""
    if action == "_prepare":
        with session_lock():
            probe = dispatch("_probe", [])
            setup_callback()
            options = launch_options("_desktop-login")
            desktop = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True,
                                     text=True, timeout=10, check=True).stdout.strip()
            directory = Path(desktop)
            if not directory.is_absolute():
                raise RuntimeError("Desktop directory is not absolute")
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / "SkullKey-EA.desktop"
            marker = "# Managed by SkullKey EA preparation"
            if path.exists() and marker not in path.read_text():
                raise RuntimeError("Existing desktop shortcut must be preserved")
            exe = options["Exe"].replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("`", "\\`").replace("$", "\\$")
            path.write_text(marker + "\n[Desktop Entry]\nType=Application\n"
                            "Name=SkullKey — Connexion EA\nName[en]=SkullKey — EA Sign-in\n"
                            "Comment=Connect EA, then reopen the EA tab in SkullKey\n"
                            f'Exec="{exe}"\nIcon=applications-games\nTerminal=false\n')
            path.chmod(0o700)
            return {"Type": "Success", "Content": {"Message": probe["Content"]["Message"],
                    "DesktopShortcut": str(path), "AccountDirectory": str(root().parent),
                    "Authenticated": False}}
    if action == "_desktop-login":
        # Same single-window GTK/WebKit flow as GOG/Epic, also in Game Mode.
        started = time.monotonic()
        login_diagnostic("embedded-window-start", validated=False)
        result = subprocess.run([python_command(), str(Path(__file__).with_name("login_gui.py"))],
                                env=os.environ.copy(), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        if result.returncode:
            previous = json.loads((root() / "login-diagnostic.json").read_text())
            if previous.get("stage") == "embedded-window-start":
                login_diagnostic("embedded-window-exit", validated=False, exit_code=result.returncode,
                                 elapsed_seconds=round(time.monotonic() - started, 1))
        connected = (result.returncode == 0 and state().get("validated")
                     and (root() / "data/maxima/auth.toml").is_file())
        return {"Type": "RefreshContent" if connected else "Error", "Content": {
            "Message": "EA library refreshed" if connected else "Connexion EA non confirmée. Aucun fichier de jeu supprimé."}}
    if action == "_external-login":
        # Only reached when the user explicitly opens the prepared shortcut.
        login_diagnostic("desktop-entered", validated=False,
                         display_available=bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")))
        dialog = None
        try:
            if shutil.which("zenity"):
                dialog = subprocess.Popen(["zenity", "--progress", "--pulsate", "--no-cancel", "--auto-close",
                                       "--title=SkullKey — EA", "--text=Connexion EA : le navigateur va s’ouvrir. Au premier lancement, Maxima peut préparer Proton. Terminez la connexion dans le navigateur."],
                                          stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            result = dispatch("_login", [])
        except Exception as error:
            # Covers failures before list-games (e.g. desktop callback setup).
            try:
                previous = json.loads((root() / "login-diagnostic.json").read_text())
                stage = previous.get("stage", "desktop-login")
                login_diagnostic(stage, error, validated=False,
                                 **{k: previous[k] for k in ("exit_code", "elapsed_seconds", "failure_category")
                                    if k in previous})
            except (OSError, ValueError):
                pass
            result = {"Type": "Error", "Content": {"Message": "Connexion EA non confirmée. Aucun fichier de jeu supprimé."}}
        finally:
            if dialog is not None:
                try:
                    dialog.stdin.close()
                except BrokenPipeError:
                    pass
                try:
                    dialog.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    dialog.terminate()
                    dialog.wait(timeout=3)
        success = result["Type"] != "Error"
        if shutil.which("zenity"):
            subprocess.run(["zenity", "--info" if success else "--error", "--title=SkullKey — EA",
                        "--text=" + ("Connexion EA validée. Retournez en mode Jeu et rouvrez SkullKey → EA / Maxima pour voir vos jeux."
                                     if success else "Connexion EA non confirmée. Vérifiez que le navigateur a terminé la connexion, puis réessayez le raccourci. Aucun fichier de jeu supprimé.")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result
    if action == "_install-worker":
        install_worker(slug, args[1])
        return {"Type": "Success", "Content": {}}
    if action == "download":
        if not game(slug) or not state().get("validated") or not (root() / "data/maxima/auth.toml").is_file():
            raise RuntimeError("Sign in before installing an owned EA game")
        with (root() / "jobs.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Reserve session while the worker starts; a second worker will
            # fail safely rather than invoking Maxima concurrently.
            with session_lock():
                if read_job(slug).get("active"):
                    raise RuntimeError("Installation already active")
                if not game(slug)["installed"]:
                    choose_game_dir(slug)
                token = uuid.uuid4().hex
                write_job(slug, {"token": token, "active": True, "cancel": False,
                                "created": time.time(),
                                "Percentage": 0, "Description": "Starting EA installation…", "Error": None})
            # Release the reservation before spawning: the worker acquires it.
            try:
                subprocess.Popen([python_command(), str(Path(__file__).resolve()), "_install-worker", slug, token],
                                 env=os.environ.copy(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            except Exception:
                job = read_job(slug)
                job.update(active=False, Error="Unable to start installation worker")
                write_job(slug, job)
                raise
        return {"Type": "Progress", "Content": {"Message": "Installing"}}
    if action == "getprogress":
        data = read_job(slug)
        if data.get("Percentage", 0) >= 100 and not data.get("Error"):
            code = installer_exit_code(slug)
            if code is not None:
                data["InstallerExitCode"] = code
        return {"Type": "ProgressUpdate", "Content": {k: data[k] for k in ("Percentage", "Description", "Error", "InstallerExitCode") if k in data}}
    if action == "cancelinstall":
        with (root() / "jobs.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            job = read_job(slug)
            (root() / f"cancel-{slug}").write_text(job.get("token", ""))
        return {"Type": "Success", "Content": {"Message": "Cancellation requested; downloaded files kept"}}
    if action == "_probe":
        r = subprocess.run([str(client()), "--help"], env=env(), capture_output=True, text=True, timeout=20)
        if r.returncode or "list-games" not in r.stdout:
            raise RuntimeError("Maxima CLI startup failed.")
        return {"Type": "Success", "Content": {"Message": f"Maxima {VERSION}: help verified; no EA authentication."}}
    if action in ("_login", "_launch", "refresh"):
        if action == "refresh" and not (root() / "data/maxima/auth.toml").exists():
            raise RuntimeError("Sign in explicitly before refreshing the EA library.")
        if action == "_login":
            login_diagnostic("session-lock", validated=False)
        with session_lock():
            os.umask(0o077)
            if action == "_launch":
                if not game(slug) or not game(slug)["installed"]:
                    raise RuntimeError("This EA game is not installed.")
                # Maxima drives umu/Proton. The Steam shortcut stays native.
                # maxima-cli needs a `maxima-bootstrap` next to it to start the
                # game, which the release does not ship: install our stand-in.
                bootstrap = client().with_name("maxima-bootstrap")
                source = Path(__file__).with_name("maxima_bootstrap.py")
                if not bootstrap.exists() or bootstrap.read_bytes() != source.read_bytes():
                    shutil.copyfile(source, bootstrap)
                    bootstrap.chmod(0o700)
                merge_case_duplicates(game_dir(slug))
                set_registry_locale(game_locale())
                apply_locale_filter(game_dir(slug), game_locale())
                launch_started = time.monotonic()
                result = subprocess.run([str(localized_client()), "launch", slug], env=launch_environment(slug),
                                        capture_output=True, text=True, errors="replace")
                launch_diagnostic(slug, launch_started, result)
                # Maxima exits 0 even when EA refuses the licence (e.g. a Game
                # Pass / EA Play title that is no longer available): tell the
                # player instead of silently returning to Steam.
                if "NOT_ENTITLED" in result.stdout + result.stderr:
                    show_error(game(slug)["name"], "not_entitled")
            else:
                # Explicit action only. Browser OAuth callback requires desktop
                # qrc handler; do not change a global protocol handler silently.
                if not (root() / "data/maxima/auth.toml").exists():
                    login_diagnostic("callback-setup", validated=False)
                    setup_callback()
                refresh()
        return {"Type": "RefreshContent", "Content": {"Message": "EA library refreshed"}}
    if action in ("login", "login-launch-options"):
        return {"Type": "RunExe" if action == "login" else "LaunchOptions", "Content": launch_options("_desktop-login")}
    if action == "loginstatus":
        connected = state().get("validated", False) and (root() / "data/maxima/auth.toml").exists()
        return {"Type": "LoginStatus", "Content": {"Username": "EA / Maxima", "LoggedIn": connected}}
    if action == "getgames":
        s = state()
        games = [g for g in s["games"] if slug.lower() in g["name"].lower()
                 and (len(args) < 2 or args[1] != "true" or g["installed"])]
        return {"Type": "GameGrid", "Content": {"NeedsLogin": "true", "storeURL": "https://www.ea.com/",
                "Games": [{"ID": i, "Name": g["name"], "ShortName": g["slug"], "Images": [c] if (c := cover(g)) else [],
                           "SteamClientID": s.get("shortcuts", {}).get(g["slug"], "")} for i, g in enumerate(games, 1)]}}
    if action in ("install", "getlaunchoptions"):
        if not game(slug) or not game(slug)["installed"]:
            raise RuntimeError("Install this EA game first.")
        if action == "install" and len(args) > 1 and args[1]:
            s = state(); s.setdefault("shortcuts", {})[slug] = args[1]; save(s)
        return {"Type": "LaunchOptions", "Content": launch_options("_launch", slug)}
    if action == "getgamedetails":
        g = game(slug)
        if not g:
            raise RuntimeError("Unknown EA game.")
        return {"Type": "GameDetails", "Content": {"Name": g["name"], "ShortName": slug,
                "Description": description(g),
                "InstallerExitCode": installer_exit_code(slug),
                "FilesInstalled": bool(g["installed"]),
                "Images": [c] if (c := cover(g)) else [], "Editors": [],
                "SteamClientID": state().get("shortcuts", {}).get(slug, "")}}
    if action == "getjsonimages":
        g = game(slug)
        return {"Type": "Images", "Content": images(g) if g else {}}
    if action == "getgamesize":
        return {"Type": "GameSize", "Content": {"Size": "EA / Maxima"}}
    if action == "uninstall":
        # maxima-cli v0.14.3 has no uninstall command; it considers a game
        # installed while its executable exists. Remove only SkullKey's own
        # install folder for this game, never anything outside games/.
        g = game(slug)
        if not g:
            raise RuntimeError("Unknown EA game.")
        job = read_job(slug)
        if job and job.get("active"):
            raise RuntimeError("Cancel the running EA installation first.")
        # Only SkullKey's own EA folders: <account>/ea/games/<slug> or
        # <drive>/SkullKey/ea/<slug>.
        target = game_dir(slug).resolve()
        default = (root() / "games").resolve()
        if target.name == slug and target.is_dir() and (
                target.parent == default or target.parent.parts[-2:] == ("SkullKey", "ea")):
            shutil.rmtree(target)
        s = state()
        for entry in s["games"]:
            if entry["slug"] == slug:
                entry["installed"] = False
        s.get("shortcuts", {}).pop(slug, None)
        s.get("paths", {}).pop(slug, None)
        save(s)
        clear_download_state(slug)
        try:
            job_path(slug).unlink()
        except OSError:
            pass
        return {"Type": "Success", "Content": {"Message": f"{g['name']} uninstalled"}}
    if action == "getsetting":
        return {"Type": "Setting", "Content": {"name": slug, "value": state().get("settings", {}).get(slug, "")}}
    if action == "savesetting":
        s = state(); s.setdefault("settings", {})[slug] = args[1] if len(args) > 1 else ""; save(s)
        return dispatch("getsetting", [slug])
    if action == "logout":
        # Forget credentials only. Never delete the prefix, games or cloud saves.
        with session_lock():
            (root() / "data/maxima/auth.toml").unlink(missing_ok=True)
            s = state(); s.update(games=[], validated=False); save(s)
        return dispatch("loginstatus", [])
    raise RuntimeError("This EA action is not yet supported by the experimental adapter.")


if __name__ == "__main__":
    try:
        print(json.dumps(dispatch(sys.argv[1], sys.argv[2:])))
    except Exception:
        # Deliberately no raw exception/CLI output: it may contain EA secrets.
        print(json.dumps({"Type": "Error", "Content": {"Message": "EA / Maxima action failed. Check desktop OAuth setup, authentication and runtime; no game data was removed."}}))
