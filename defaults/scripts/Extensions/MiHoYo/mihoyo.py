#!/usr/bin/env python3
"""miHoYo / HoYoverse store backend for SkullKey.

Talks to the public HoYoPlay "hyp-connect" launcher API (the same one the
official launcher and Collapse/Twintail use) to list the games, and downloads
them through the "sophon" chunk channel (getGameBranches → getBuild →
manifest + chunks). The legacy full-zip channel (getGamePackages) is stale —
HoYo stopped refreshing it — so versions and files MUST come from sophon.
No login is needed to browse or download — HoYoverse serves everything from a
public CDN; the account login only happens in-game.

Self-contained (stdlib only) so the catalogue needs no extra dependencies.
Install state (Steam shortcut id, install path) is kept in a small JSON file,
mirroring the approach used by media.py rather than a sqlite DB.
"""

import base64
import hashlib
import http.client
import io
import json
import os
import platform
import re
import shutil
import signal
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from compression import zstd as _zstd     # stdlib since python 3.14
except ImportError:
    _zstd = None                              # falls back to the zstd binary

# ── HoYoPlay API (global / overseas region) ───────────────────────────────────
API_BASE = "https://sg-hyp-api.hoyoverse.com/hyp/hyp-connect/api"
LAUNCHER_ID = "VYTpXlbWo8"          # global launcher
STORE_URL = "https://hoyoplay.hoyoverse.com/"

# HoYoPlay (overseas) supported UI languages, keyed by the machine locale's
# 2-letter code. Locales HoYo doesn't offer (e.g. nl, pl) fall back to English.
_HOYO_LANGS = {
    "en": "en-us", "fr": "fr-fr", "de": "de-de", "es": "es-es", "it": "it-it",
    "pt": "pt-pt", "ru": "ru-ru", "ja": "ja-jp", "ko": "ko-kr", "zh": "zh-cn",
    "id": "id-id", "th": "th-th", "tr": "tr-tr", "vi": "vi-vn",
}


def machine_lang_code():
    """2-letter language code of the machine locale. Checks the usual env
    vars first, then /etc/locale.conf — plugin_loader (systemd) runs with no
    LANG in its environment, so the file is the reliable source in-game."""
    def _code(val):
        return val.replace("-", "_").split(":")[0].split(".")[0].split("_")[0].lower()
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        val = os.environ.get(var)
        if val:
            return _code(val)
    try:
        with open("/etc/locale.conf") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("LANG="):
                    return _code(line.split("=", 1)[1].strip().strip('"'))
    except OSError:
        pass
    return "en"


def hoyo_language():
    """Pick the HoYo language from the machine locale (like the rest of the
    plugin follows the machine config), falling back to English."""
    return _HOYO_LANGS.get(machine_lang_code(), "en-us")

RUNTIME_DIR = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                             os.path.expanduser("~/homebrew/data/SkullKey"))
STATE_FILE = os.path.join(RUNTIME_DIR, "mihoyo_state.json")
CATALOG_TTL = 6 * 3600  # refresh the catalogue at most every 6h

INSTALL_DIR = os.path.expanduser(
    os.environ.get("MIHOYO_INSTALL_DIR", "~/Games/mihoyo/"))


def _ssl_context():
    for ca in ("/etc/pki/tls/certs/ca-bundle.crt",
               "/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem"):
        if os.path.exists(ca):
            try:
                return ssl.create_default_context(cafile=ca)
            except Exception:
                pass
    try:
        return ssl.create_default_context()
    except Exception:
        return None


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SkullKey-MiHoYo"})
    with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as r:
        return json.loads(r.read().decode("utf-8"))


def _api_get(endpoint, params):
    return _get_json(f"{API_BASE}/{endpoint}?"
                     + urllib.parse.urlencode(params, doseq=True))


# ── state ─────────────────────────────────────────────────────────────────────
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


# ── catalogue (getGames) ──────────────────────────────────────────────────────
def fetch_catalog():
    """Return the list of games from the API in the machine's language, cached
    to disk (per language) with a TTL so the grid is fast and still works when
    offline after the first fetch."""
    lang = hoyo_language()
    cache = os.path.join(RUNTIME_DIR, f"mihoyo_catalog_{lang}.json")
    try:
        st = os.stat(cache)
        if time.time() - st.st_mtime < CATALOG_TTL:
            with open(cache) as f:
                return json.load(f)
    except Exception:
        pass
    data = _api_get("getGames", {"launcher_id": LAUNCHER_ID, "language": lang})
    games = data.get("data", {}).get("games", [])
    try:
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with open(cache, "w") as f:
            json.dump(games, f)
    except Exception:
        pass
    return games


def _images_for(game, keys=("background", "logo", "icon", "thumbnail")):
    disp = game.get("display", {}) or {}
    imgs = []
    for key in keys:
        u = (disp.get(key) or {}).get("url")
        if u:
            imgs.append(u)
    return imgs


# ── portrait cover compositing ────────────────────────────────────────────────
# HoYo only ships a square icon and a wide 16:9 keyart, but the store grid slot
# is portrait (120x165). Build a proper vertical cover per game — keyart
# cover-cropped + a bottom scrim + the game's transparent logo — so the cards
# look like real box art. Cached on disk and served as a base64 data URI.
ART_DIR = os.path.join(RUNTIME_DIR, "mihoyo_art")
COVER_VERSION = "v3"


def _download_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SkullKey-MiHoYo"})
    with urllib.request.urlopen(req, timeout=25, context=_ssl_context()) as r:
        return r.read()


def _trimmed_logo(disp):
    """Game logo as an alpha-trimmed RGBA Image, or None. HoYo logo PNGs
    carry big transparent margins: without trimming, any 'percent of width'
    sizing renders a visually small logo."""
    from PIL import Image
    logo_url = (disp.get("logo") or {}).get("url")
    if not logo_url:
        return None
    logo = Image.open(io.BytesIO(_download_bytes(logo_url))).convert("RGBA")
    bbox = logo.getchannel("A").getbbox()
    return logo.crop(bbox) if bbox else logo


def _build_cover(game, W=600, H=900, with_logo=True):
    """Compose keyart(+logo) artwork at any Steam slot size (portrait grid
    600x900, wide grid 920x430, hero 1920x620). Cached per size.
    with_logo=False for the HERO slot: Steam overlays the 'Logo' slot image
    on top of the hero itself, so baking it in would show the logo twice."""
    biz = game.get("biz", "")
    suffix = "" if with_logo else "_nologo"
    path = os.path.join(ART_DIR, f"{biz}_{W}x{H}{suffix}_{COVER_VERSION}.jpg")
    if os.path.exists(path):
        return path
    try:
        from PIL import Image
        disp = game.get("display", {}) or {}
        bg_url = (disp.get("background") or {}).get("url")
        if not bg_url:
            return None
        bg = Image.open(io.BytesIO(_download_bytes(bg_url))).convert("RGBA")
        scale = max(W / bg.width, H / bg.height)
        bg = bg.resize((max(1, round(bg.width * scale)),
                        max(1, round(bg.height * scale))), Image.LANCZOS)
        left = (bg.width - W) // 2
        top = (bg.height - H) // 2
        bg = bg.crop((left, top, left + W, top + H))
        # bottom-weighted dark scrim so the logo reads on any keyart
        col = Image.new("L", (1, H))
        for y in range(H):
            t = max(0.0, (y - H * 0.42) / (H * 0.58))
            col.putpixel((0, y), int(210 * (t ** 1.4)))
        scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        scrim.putalpha(col.resize((W, H)))
        bg = Image.alpha_composite(bg, scrim)
        logo = _trimmed_logo(disp) if with_logo else None
        if logo:
            if H > W:      # portrait: (almost) full width, anchored bottom
                lw = round(W * 0.94)
                lh = round(logo.height * lw / logo.width)
                max_lh = round(H * 0.45)      # guard tall/stacked logos
            else:          # landscape banners: keep the logo discreet
                lw = round(W * 0.46)
                lh = round(logo.height * lw / logo.width)
                max_lh = round(H * 0.52)
            if lh > max_lh:
                lh = max_lh
                lw = round(logo.width * lh / logo.height)
            logo = logo.resize((max(1, lw), max(1, lh)), Image.LANCZOS)
            bottom_pad = round(H * 0.06)
            bg.alpha_composite(logo, ((W - lw) // 2, H - lh - bottom_pad))
        os.makedirs(ART_DIR, exist_ok=True)
        tmp = path + ".tmp"
        bg.convert("RGB").save(tmp, "JPEG", quality=88)
        os.replace(tmp, path)
        return path
    except Exception as e:
        print(f"mihoyo cover build failed for {biz} {W}x{H}: {e}",
              file=sys.stderr)
        return None


def _logo_file(game):
    """Alpha-trimmed transparent logo PNG (Steam 'Logo' slot). Cached."""
    biz = game.get("biz", "")
    path = os.path.join(ART_DIR, f"{biz}_logo_{COVER_VERSION}.png")
    if os.path.exists(path):
        return path
    try:
        logo = _trimmed_logo(game.get("display", {}) or {})
        if not logo:
            return None
        os.makedirs(ART_DIR, exist_ok=True)
        tmp = path + ".tmp"
        logo.save(tmp, "PNG")
        os.replace(tmp, path)
        return path
    except Exception as e:
        print(f"mihoyo logo build failed for {biz}: {e}", file=sys.stderr)
        return None


def _cover_uri(game):
    """Portrait cover as a base64 data URI, or None (caller falls back)."""
    path = _build_cover(game)
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return None


def action_getgames(filter_str="", installed="false", limit="false"):
    state = load_state()
    games_out = []
    for idx, game in enumerate(fetch_catalog(), start=1):
        disp = game.get("display", {}) or {}
        name = disp.get("name") or game.get("biz") or "Unknown"
        if filter_str and filter_str.lower() not in name.lower():
            continue
        biz = game.get("biz", "")
        st = state["games"].get(biz, {})
        if installed.lower() == "true" and not st.get("steamClientID"):
            continue
        # portrait cover first (composited), keyart/icon as fallbacks
        images = _images_for(game)
        cover = _cover_uri(game)
        if cover:
            images = [cover] + images
        games_out.append({
            "ID": idx,
            "Name": name,
            "Images": images,
            "ShortName": biz,
            "SteamClientID": st.get("steamClientID"),
        })
    return {
        "Type": "GameGrid",
        "Content": {
            "NeedsLogin": False,
            "Games": games_out,
            "storeURL": STORE_URL,
        },
    }


def _game_by_biz(biz):
    for game in fetch_catalog():
        if game.get("biz") == biz:
            return game
    return None


def _human(nbytes):
    n = float(nbytes or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.2f} {unit}"
        n /= 1024


def action_getgamesize(biz, installed="false"):
    try:
        build = _sophon_build(biz)
        stats = [(_build_category(build, f) or {}).get("stats", {})
                 for f in _install_fields(biz)]
        dl = sum(int(s.get("compressed_size", 0)) for s in stats)
        disk = sum(int(s.get("uncompressed_size", 0)) for s in stats)
        size = ""
        if disk:
            size = f"Install Size: {_human(disk)}"
        if dl:
            size += (f" (Download Size: {_human(dl)})" if size
                     else f"Download Size: {_human(dl)}")
    except Exception as e:
        print(f"mihoyo getgamesize failed: {e}", file=sys.stderr)
        size = ""
    return {"Type": "GameSize", "Content": {"Size": size}}


# Labels of the details fact-sheet, in the plugin's 9 UI languages (same rule
# as the rest of SkullKey: everything we author is either EN or all 9).
_DETAIL_LABELS = {
    "en": {"dev": "Developer", "ver": "Latest version", "voice": "Voice-over",
           "genre": "Free-to-play — account created in game on first launch."},
    "fr": {"dev": "Développeur", "ver": "Dernière version", "voice": "Doublage",
           "genre": "Free-to-play — compte créé en jeu au premier lancement."},
    "de": {"dev": "Entwickler", "ver": "Neueste Version", "voice": "Sprachausgabe",
           "genre": "Free-to-play — Konto wird beim ersten Start im Spiel erstellt."},
    "es": {"dev": "Desarrollador", "ver": "Última versión", "voice": "Voces",
           "genre": "Free-to-play — la cuenta se crea en el juego al iniciarlo."},
    "it": {"dev": "Sviluppatore", "ver": "Ultima versione", "voice": "Doppiaggio",
           "genre": "Free-to-play — l'account si crea nel gioco al primo avvio."},
    "pt": {"dev": "Desenvolvedor", "ver": "Última versão", "voice": "Dublagem",
           "genre": "Free-to-play — a conta é criada no jogo ao iniciar."},
    "nl": {"dev": "Ontwikkelaar", "ver": "Nieuwste versie", "voice": "Stemmen",
           "genre": "Free-to-play — account wordt in de game aangemaakt bij de eerste start."},
    "pl": {"dev": "Deweloper", "ver": "Najnowsza wersja", "voice": "Dubbing",
           "genre": "Free-to-play — konto tworzone w grze przy pierwszym uruchomieniu."},
    "ru": {"dev": "Разработчик", "ver": "Последняя версия", "voice": "Озвучка",
           "genre": "Free-to-play — аккаунт создаётся в игре при первом запуске."},
}

# Shown on every miHoYo game's details page (before install): the login/
# gateway screen is mouse-driven (inherent to HoYo games), so navigate it with
# keyboard/mouse, then enable the controller config in-game once logged in.
_CONTROLLER_NOTE = {
    "en": "🎮 At launch, navigate the login screen with keyboard/mouse; once logged in and in-game, enable the controller layout in the settings.",
    "fr": "🎮 Au lancement, navigue l'écran de connexion au clavier/souris ; une fois connecté et en jeu, active la configuration manette dans les paramètres.",
    "de": "🎮 Navigiere den Login-Bildschirm beim Start mit Tastatur/Maus; sobald du eingeloggt und im Spiel bist, aktiviere das Controller-Layout in den Einstellungen.",
    "es": "🎮 Al iniciar, navega la pantalla de inicio de sesión con teclado/ratón; una vez dentro del juego, activa la configuración de mando en los ajustes.",
    "it": "🎮 All'avvio, naviga la schermata di accesso con tastiera/mouse; una volta effettuato l'accesso e in gioco, attiva la configurazione del controller nelle impostazioni.",
    "pt": "🎮 Ao iniciar, navegue o ecrã de login com teclado/rato; depois de entrar no jogo, ative a configuração de comando nas definições.",
    "nl": "🎮 Navigeer bij het opstarten het inlogscherm met toetsenbord/muis; zodra je bent ingelogd en in het spel bent, schakel je de controllerindeling in de instellingen in.",
    "pl": "🎮 Przy uruchomieniu poruszaj się po ekranie logowania klawiaturą/myszą; po zalogowaniu i w grze włącz konfigurację pada w ustawieniach.",
    "ru": "🎮 При запуске перемещайтесь по экрану входа мышью/клавиатурой; после входа и в самой игре включите настройку геймпада в параметрах.",
}

# Shown on the ZZZ details page: the anti-cheat is handled automatically (EGS
# channel config), no jadeite needed; a recent Proton is recommended.
_ZZZ_NOTE = {
    "en": "Anti-cheat handled automatically — no jadeite needed. Use a recent Proton (GE-Proton recommended).",
    "fr": "Anti-triche géré automatiquement — pas besoin de jadeite. Utilisez un Proton récent (GE-Proton recommandé).",
    "de": "Anti-Cheat wird automatisch gehandhabt — kein jadeite nötig. Verwende ein aktuelles Proton (GE-Proton empfohlen).",
    "es": "Anti-trampas gestionado automáticamente — no hace falta jadeite. Usa un Proton reciente (GE-Proton recomendado).",
    "it": "Anti-cheat gestito automaticamente — niente jadeite. Usa un Proton recente (GE-Proton consigliato).",
    "pt": "Anti-cheat tratado automaticamente — sem jadeite. Use um Proton recente (GE-Proton recomendado).",
    "nl": "Anti-cheat wordt automatisch afgehandeld — geen jadeite nodig. Gebruik een recente Proton (GE-Proton aanbevolen).",
    "pl": "Anti-cheat obsługiwany automatycznie — jadeite niepotrzebne. Użyj najnowszego Protona (zalecany GE-Proton).",
    "ru": "Античит обрабатывается автоматически — jadeite не нужен. Используйте свежий Proton (рекомендуется GE-Proton).",
}

# Voice-pack languages shown in their own language — universal, no i18n needed.
_VOICE_NAMES = {"zh-cn": "中文", "en-us": "English", "ja-jp": "日本語",
                "ko-kr": "한국어"}


def action_getgamedetails(biz):
    game = _game_by_biz(biz) or {}
    disp = game.get("display", {}) or {}
    name = disp.get("name") or biz
    lab = _DETAIL_LABELS.get(machine_lang_code(), _DETAIL_LABELS["en"])

    version, voices = "", []
    try:
        version = (_branch_info(biz) or {}).get("tag", "")
        voices = [_VOICE_NAMES[m["matching_field"]]
                  for m in (_sophon_build(biz) or {}).get("manifests", [])
                  if m.get("matching_field") in _VOICE_NAMES]
    except Exception:
        pass

    parts = []
    tagline = disp.get("subtitle") or disp.get("title") or ""
    if tagline and tagline != name:
        parts.append(f"<b><i>{tagline}</i></b>")
    intro = disp.get("introduction") or ""
    if intro:
        parts.append(intro.replace("\n", "<br />"))

    facts = [f"{lab['dev']}: HoYoverse"]
    if version:
        facts.append(f"{lab['ver']}: {version}")
    if voices:
        facts.append(f"{lab['voice']}: {', '.join(v for v in voices if v)}")
    parts.append("<br />".join(facts))
    parts.append(f"<i>{lab['genre']}</i>")
    parts.append(f"<i>{_CONTROLLER_NOTE.get(machine_lang_code(), _CONTROLLER_NOTE['en'])}</i>")
    if biz in NEEDS_EGS_CONFIG:
        parts.append(f"<i>{_ZZZ_NOTE.get(machine_lang_code(), _ZZZ_NOTE['en'])}</i>")

    desc = "<br /><br />".join(parts)
    return {
        "Type": "GameDetails",
        "Content": {
            "Name": name,
            "Description": f"<div><p style='white-space: pre-wrap;'>{desc}</p></div>",
            "ShortName": biz,
            "SteamClientID": load_state()["games"].get(biz, {}).get("steamClientID"),
            "Images": _images_for(game),
            "Editors": [],
        },
    }


def action_loginstatus(*_):
    # Browsing/downloading never needs a login for HoYoverse.
    return {"Type": "Init", "Content": {"Actions": []}}


def action_getjsonimages(biz=""):
    """Steam shortcut artwork: the frontend expects the four slots as raw
    base64 (SetCustomArtworkForApp), exactly like media.py — NOT an URL list."""
    game = _game_by_biz(biz) or {}

    def b64(path):
        if not path:
            return None
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    try:
        content["Grid"] = b64(_build_cover(game, 600, 900))
        content["GridH"] = b64(_build_cover(game, 920, 430))
        # hero WITHOUT baked logo: Steam overlays the Logo slot on the hero
        content["Hero"] = b64(_build_cover(game, 1920, 620, with_logo=False))
        content["Logo"] = b64(_logo_file(game))
    except Exception as e:
        print(f"mihoyo artwork failed: {e}", file=sys.stderr)
    return {"Type": "Images", "Content": content}


# ── sophon channel (branches → build → manifest → chunks) ────────────────────
# The only channel HoYo still refreshes. getGameBranches gives the CURRENT
# version tag plus the package_id/password for getBuild; getBuild lists one
# manifest per category ("game" + voice packs); the manifest is a
# zstd-compressed protobuf describing every file as a list of ~1 MiB
# zstd-compressed chunks on the CDN. Files are assembled chunk-by-chunk at
# their offsets, so a version update only downloads the chunks of the files
# whose md5 changed.
SOPHON_API = ("https://sg-public-api.hoyoverse.com/downloader/sophon_chunk"
              "/api/getBuild")
BRANCHES_TTL = 3600


def _branch_info(biz):
    """Current main-branch descriptor {tag, package_id, password, diff_tags}.
    bh3_global has several regional variants sharing the biz, so the match is
    on the catalogue's game id first. Cached like the catalogue; falls back to
    a stale cache when offline."""
    cache = os.path.join(RUNTIME_DIR, "mihoyo_branches.json")
    branches = None
    try:
        if time.time() - os.stat(cache).st_mtime < BRANCHES_TTL:
            with open(cache) as f:
                branches = json.load(f)
    except Exception:
        pass
    if branches is None:
        try:
            data = _api_get("getGameBranches", {"launcher_id": LAUNCHER_ID})
            branches = data.get("data", {}).get("game_branches", [])
            os.makedirs(RUNTIME_DIR, exist_ok=True)
            with open(cache, "w") as f:
                json.dump(branches, f)
        except Exception:
            with open(cache) as f:      # offline: stale beats nothing
                branches = json.load(f)
    game_id = (_game_by_biz(biz) or {}).get("id")
    for b in branches:
        g = b.get("game", {}) or {}
        if g.get("id") == game_id or (not game_id and g.get("biz") == biz):
            m = b.get("main", {}) or {}
            return {"tag": m.get("tag", ""),
                    "package_id": m.get("package_id", ""),
                    "password": m.get("password", ""),
                    "diff_tags": m.get("diff_tags", []),
                    "categories": m.get("categories", [])}
    return None


def _install_fields(biz):
    """matching_fields of the manifests that make up a FULL install, like the
    official launcher: resource categories with the FULL scenario. Voice packs
    are CATEGORY_TYPE_AUDIO — excluded, they stay in-game-managed. HI3 splits
    the game into 'game'+'asb'; ZZZ adds ~110 resource categories."""
    fields = []
    for cat in (_branch_info(biz) or {}).get("categories", []):
        f = cat.get("matching_field", "")
        if (f and cat.get("type") == "CATEGORY_TYPE_RESOURCE"
                and "CATEGORY_SCENARIO_FULL" in (cat.get("scenarios") or [])):
            fields.append(f)
    return fields or ["game"]


def _sophon_build(biz):
    """getBuild response (manifest descriptors + stats per category) for the
    game's CURRENT version, cached per tag."""
    info = _branch_info(biz)
    if not info or not info.get("tag"):
        return None
    cache = os.path.join(RUNTIME_DIR, f"mihoyo_build_{biz}.json")
    try:
        with open(cache) as f:
            c = json.load(f)
        if c.get("tag") == info["tag"]:
            return c["build"]
    except Exception:
        pass
    data = _get_json(SOPHON_API + "?" + urllib.parse.urlencode(
        {"branch": "main", "package_id": info["package_id"],
         "password": info["password"], "tag": info["tag"]}))
    if data.get("retcode") != 0:
        raise RuntimeError(f"sophon getBuild: {data.get('message')}")
    build = data.get("data") or {}
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(cache, "w") as f:
        json.dump({"tag": info["tag"], "build": build}, f)
    return build


def _build_category(build, field="game"):
    for man in (build or {}).get("manifests", []):
        if man.get("matching_field") == field:
            return man
    return None


# ── delta patches (sophon getPatchBuild + hpatchz) ───────────────────────────
# A version update normally re-downloads every changed file in full. HoYo also
# ships DELTA patches: getPatchBuild returns, per category, a manifest listing
# for each file a tiny hdiff patch (HDiffPatch "HDIFF13" format) that turns the
# OLD file into the NEW one. Patches for many files are packed into shared
# "diff blobs" (each file = a [offset, offset+len) slice of a blob). Applying
# them with hpatchz downloads only the diff (~16 GB) instead of the changed
# files in full (~74 GB) for a Genshin version bump. Reverse-engineered live;
# schema documented in the mihoyo-sophon-patch memory. Fully additive: whatever
# can't be patched (new files, missing source, any failure) falls back to the
# normal chunk download, so the result is always a correct install.
PATCH_API = ("https://sg-public-api.hoyoverse.com/downloader/sophon_chunk"
             "/api/getPatchBuild")
HPATCHZ_DIR = os.path.join(RUNTIME_DIR, "hpatchz")
HDIFFPATCH_REL = ("https://github.com/sisong/HDiffPatch/releases/download/"
                  "v5.0.1/hdiffpatch_v5.0.1_bin_{arch}.zip")


def _hdiff_arch():
    m = (platform.machine() or "").lower()
    if m in ("aarch64", "arm64"):
        return "linux_arm64", "linux_arm64/hpatchz"
    if m in ("armv7l", "armv7", "arm"):
        return "linux_arm32", "linux_arm32/hpatchz"
    return "linux64", "linux64/hpatchz"      # x86_64 default


def ensure_hpatchz():
    """Provision the static hpatchz binary (HDiffPatch) for this CPU arch, so
    delta patching works on any distro. Cached in RUNTIME_DIR. Returns the path
    or None if it couldn't be obtained (caller falls back to full download)."""
    exe = os.path.join(HPATCHZ_DIR, "hpatchz")
    if os.path.exists(exe) and os.access(exe, os.X_OK):
        return exe
    arch, inner = _hdiff_arch()
    try:
        zbytes = _download_bytes(HDIFFPATCH_REL.format(arch=arch))
    except Exception as e:
        print(f"hpatchz download failed: {e}", file=sys.stderr)
        return None
    os.makedirs(HPATCHZ_DIR, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        with z.open(inner) as src, open(exe, "wb") as dst:
            shutil.copyfileobj(src, dst)
    os.chmod(exe, 0o755)
    return exe if os.path.exists(exe) else None


def _sophon_patch_build(biz):
    """getPatchBuild response (patch manifests per category) for the game's
    current target version, cached per tag. POST + JSON body (GET → 405)."""
    info = _branch_info(biz)
    if not info or not info.get("tag"):
        return None
    cache = os.path.join(RUNTIME_DIR, f"mihoyo_patch_{biz}.json")
    try:
        with open(cache) as f:
            c = json.load(f)
        if c.get("tag") == info["tag"]:
            return c["build"]
    except Exception:
        pass
    body = json.dumps({"branch": "main", "package_id": info["package_id"],
                       "password": info["password"], "tag": info["tag"]}
                      ).encode()
    req = urllib.request.Request(
        PATCH_API, data=body, method="POST",
        headers={"User-Agent": "SkullKey-MiHoYo",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25, context=_ssl_context()) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("retcode") != 0:
        raise RuntimeError(f"getPatchBuild: {data.get('message')}")
    build = data.get("data") or {}
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(cache, "w") as f:
        json.dump({"tag": info["tag"], "build": build}, f)
    return build


def _parse_patch_manifest(pb, source_ver):
    """Patch manifest protobuf → {target_path: diff} for files patchable from
    `source_ver`. Schema (reverse-engineered):
      entry(field 1): 1=target_path 2=new_size 3=new_md5
                      4=diff(repeated, per source version):
                          1=source_ver  2=descriptor{
                              1=blob_name 4=blob_size 5=blob_md5
                              6=offset(def 0) 7=length
                              8=src_path 9=src_size 10=src_md5}"""
    out = {}
    for fno, _, raw in _pb_fields(pb):
        if fno != 1:
            continue
        path = new_size = new_md5 = None
        diffs = []
        for f2, _, v in _pb_fields(raw):
            if f2 == 1:
                path = v.decode()
            elif f2 == 2:
                new_size = v
            elif f2 == 3:
                new_md5 = v.decode().lower()
            elif f2 == 4:
                diffs.append(v)
        if path is None:
            continue
        for dv in diffs:
            sv = None
            desc = None
            for f3, _, w in _pb_fields(dv):
                if f3 == 1:
                    sv = w.decode()
                elif f3 == 2:
                    desc = w
            if sv != source_ver or desc is None:
                continue
            d = {"blob": "", "blob_size": 0, "offset": 0, "length": 0,
                 "src_size": 0, "src_md5": "", "new_size": new_size,
                 "new_md5": new_md5}
            for f4, _, x in _pb_fields(desc):
                if f4 == 1:
                    d["blob"] = x.decode()
                elif f4 == 4:
                    d["blob_size"] = x
                elif f4 == 6:
                    d["offset"] = x
                elif f4 == 7:
                    d["length"] = x
                elif f4 == 9:
                    d["src_size"] = x
                elif f4 == 10:
                    d["src_md5"] = x.decode().lower()
            if d["blob"] and d["length"]:
                out[path] = d
            break
    return out


def _zstd_decompress(data):
    if _zstd:
        return _zstd.decompress(data)
    p = subprocess.run(["zstd", "-d", "-c"], input=data, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("zstd failed: "
                           + p.stderr.decode("utf-8", "replace")[:200])
    return p.stdout


def _pb_fields(buf):
    """Minimal protobuf wire-format reader → [(field_no, wire_type, value)].
    The manifest schema was reverse-engineered from live manifests and
    validated against the API's stats block (file/chunk counts and sizes)."""
    i, n, out = 0, len(buf), []

    def varint():
        nonlocal i
        x = s = 0
        while True:
            b = buf[i]
            i += 1
            x |= (b & 0x7f) << s
            if not b & 0x80:
                return x
            s += 7

    while i < n:
        key = varint()
        fno, wt = key >> 3, key & 7
        if wt == 0:
            v = varint()
        elif wt == 2:
            ln = varint()
            v = buf[i:i + ln]
            i += ln
        elif wt == 1:
            v = buf[i:i + 8]
            i += 8
        elif wt == 5:
            v = buf[i:i + 4]
            i += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wt}")
        out.append((fno, wt, v))
    return out


def _parse_manifest(pb):
    """Sophon manifest protobuf → list of assets.
    Asset: 1=path 2=chunk(repeated) 4=size 5=md5(file).
    Chunk: 1=cdn name 2=md5(decompressed) 3=offset 4=compressed size
    5=decompressed size (6/7 = xxhash + md5 of the compressed blob, unused)."""
    assets = []
    for fno, _, raw in _pb_fields(pb):
        if fno != 1:
            continue
        a = {"name": "", "size": 0, "md5": "", "chunks": []}
        for f2, _, v in _pb_fields(raw):
            if f2 == 1:
                a["name"] = v.decode()
            elif f2 == 4:
                a["size"] = v
            elif f2 == 5:
                a["md5"] = v.decode().lower()
            elif f2 == 2:
                c = {"name": "", "md5": "", "offset": 0, "csize": 0,
                     "usize": 0}
                for f3, _, w in _pb_fields(v):
                    if f3 == 1:
                        c["name"] = w.decode()
                    elif f3 == 2:
                        c["md5"] = w.decode().lower()
                    elif f3 == 3:
                        c["offset"] = w
                    elif f3 == 4:
                        c["csize"] = w
                    elif f3 == 5:
                        c["usize"] = w
                a["chunks"].append(c)
        assets.append(a)
    return assets


def _fetch_manifest(biz, man):
    """Download+decompress the category manifest into _pkg (cached by id, so
    resumes don't refetch). Returns the raw protobuf bytes."""
    mid = man["manifest"]["id"]
    path = os.path.join(_pkg_dir(biz), mid + ".pb")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    raw = _download_bytes(man["manifest_download"]["url_prefix"] + "/" + mid)
    pb = _zstd_decompress(raw)
    want = (man["manifest"].get("checksum") or "").lower()
    if want and want not in (hashlib.md5(pb).hexdigest(),
                             hashlib.md5(raw).hexdigest()):
        raise RuntimeError("manifest checksum mismatch")
    os.makedirs(_pkg_dir(biz), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(pb)
    os.replace(tmp, path)
    return pb


class _ChunkFetcher:
    """Per-thread keep-alive connection to the chunk CDN — a fresh TLS
    handshake for every ~1 MiB chunk would cap the throughput. Retries with
    a new connection on any transport error."""

    def __init__(self, prefix):
        u = urllib.parse.urlsplit(prefix)
        self._scheme, self._host, self._dir = u.scheme, u.netloc, u.path
        self._prefix = prefix
        self._local = threading.local()

    def get(self, name):
        if self._scheme not in ("http", "https"):    # file:// (test rigs)
            return _download_bytes(self._prefix + "/" + name)
        last = None
        for attempt in range(3):
            conn = getattr(self._local, "conn", None)
            try:
                if conn is None:
                    if self._scheme == "https":
                        conn = http.client.HTTPSConnection(
                            self._host, timeout=60, context=_ssl_context())
                    else:
                        conn = http.client.HTTPConnection(self._host,
                                                          timeout=60)
                    self._local.conn = conn
                conn.request("GET", f"{self._dir}/{name}",
                             headers={"User-Agent": "SkullKey-MiHoYo"})
                resp = conn.getresponse()
                data = resp.read()
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return data
            except Exception as e:
                last = e
                try:
                    if conn:
                        conn.close()
                except Exception:
                    pass
                self._local.conn = None
                time.sleep(1 + attempt)
        raise RuntimeError(f"chunk {name}: {last}")


# ── install pipeline (milestone 2) ────────────────────────────────────────────
# Flow (mirrors GOG/Epic): frontend Download → we spawn a DETACHED worker and
# reply {"Type":"Progress"} immediately (a blocking reply would hide the
# progress bar — same lesson as the GOG stdio-detach fix). The frontend then
# polls GetProgress; when it reports 100% it calls Install, which replies with
# LaunchOptions for the Steam shortcut (Proton, like GOG games).
#
# Files are downloaded through the sophon chunk channel and assembled in
# place; a per-game registry of finished files (name → md5) makes reruns —
# resume after a reboot, or a version update — skip everything unchanged.

# sys.executable is EMPTY in Decky's minimal env (PermissionError on Popen) —
# same pitfall as media.py.
PYEXE = sys.executable or shutil.which("python3") or "/usr/bin/python3"
LOG_DIR = os.environ.get("DECKY_PLUGIN_LOG_DIR",
                         os.path.expanduser("~/homebrew/logs/SkullKey"))

# Main game executable per biz (fallback: scan for the biggest top-level exe).
_KNOWN_EXES = {
    "hk4e_global": "GenshinImpact.exe",
    "hkrpg_global": "StarRail.exe",
    "nap_global": "ZenlessZoneZero.exe",
    "bh3_global": "BH3.exe",
}

CHUNK_THREADS = 8        # concurrent chunk downloads (CDN throttles per conn)


def _game_dir(biz):
    return os.path.join(INSTALL_DIR, biz)


def _pkg_dir(biz):
    return os.path.join(_game_dir(biz), "_pkg")


def _progress_path(biz):
    return os.path.join(RUNTIME_DIR, f"mihoyo_progress_{biz}.json")


def _read_progress(biz):
    try:
        with open(_progress_path(biz)) as f:
            return json.load(f)
    except Exception:
        return None


def _write_progress(biz, pct, desc, error=None, done=False, pid=None):
    cur = _read_progress(biz) or {}
    if pid is None:
        pid = cur.get("pid")
    data = {"pct": round(pct, 1), "desc": desc, "error": error,
            "done": done, "pid": pid, "ts": time.time()}
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    tmp = _progress_path(biz) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, _progress_path(biz))


def _files_reg_path(biz):
    return os.path.join(RUNTIME_DIR, f"mihoyo_files_{biz}.json")


def _load_files_reg(biz):
    """Registry of finished files (manifest path → md5). Survives installs so
    the next update can skip unchanged files without re-hashing them."""
    try:
        with open(_files_reg_path(biz)) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_files_reg(biz, reg):
    tmp = _files_reg_path(biz) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(reg, f)
    os.replace(tmp, _files_reg_path(biz))


def _md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _Part:
    """In-flight file being assembled from chunks (<target>.skpart)."""
    __slots__ = ("asset", "target", "path", "fd", "left", "lock", "fetcher")

    def __init__(self, asset, target, fetcher):
        self.asset = asset
        self.target = target
        self.path = target + ".skpart"
        self.fd = None                    # opened lazily by the first chunk
        self.left = len(asset["chunks"])
        self.lock = threading.Lock()
        self.fetcher = fetcher            # each category has its own CDN dir


def _patch_manifest_bytes(biz, man):
    """Fetch + zstd-decompress a patch category manifest (cached in _pkg)."""
    mid = man["manifest"]["id"]
    path = os.path.join(_pkg_dir(biz), "patch_" + mid + ".pb")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    raw = _download_bytes(man["manifest_download"]["url_prefix"] + "/" + mid)
    pb = _zstd_decompress(raw)
    want = (man["manifest"].get("checksum") or "").lower()
    if want and want not in (hashlib.md5(pb).hexdigest(),
                             hashlib.md5(raw).hexdigest()):
        raise RuntimeError("patch manifest checksum mismatch")
    os.makedirs(_pkg_dir(biz), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(pb)
    os.replace(tmp, path)
    return pb


def _try_delta_patch(biz, source_ver, target_ver):
    """Patch changed files from the INSTALLED version instead of re-downloading
    them. Additive + best-effort: every file it can't patch (new file, missing
    or mismatched source, any error) is simply left for the full chunk pipeline
    that runs afterwards, which sees the registry and skips whatever this phase
    already produced. Returns the number of files successfully patched."""
    hpz = ensure_hpatchz()
    if not hpz:
        return 0
    try:
        build = _sophon_patch_build(biz)
    except Exception as e:            # API/network error → skip delta cleanly
        print(f"getPatchBuild failed, full download: {e}", file=sys.stderr)
        return 0
    if not build or not build.get("manifests"):
        return 0

    out_root = _game_dir(biz)
    root_prefix = os.path.normpath(out_root) + os.sep
    # Collect patchable files across every install category.
    jobs_by_blob = {}          # (prefix, blob, blob_size) -> [(path, diff)]
    for field in _install_fields(biz):
        man = _build_category(build, field)
        if not man:
            continue
        try:
            diffs = _parse_patch_manifest(
                _patch_manifest_bytes(biz, man), source_ver)
        except Exception as e:
            print(f"patch manifest {field}: {e}", file=sys.stderr)
            continue
        prefix = man["diff_download"]["url_prefix"]
        for path, d in diffs.items():
            target = os.path.normpath(
                os.path.join(out_root, path.replace("\\", "/")))
            if not target.startswith(root_prefix):
                continue
            # The OLD file must be on disk and match the patch's source md5.
            if not (os.path.isfile(target)
                    and os.path.getsize(target) == d["src_size"]
                    and (not d["src_md5"] or _md5_file(target) == d["src_md5"])):
                continue
            jobs_by_blob.setdefault(
                (prefix, d["blob"], d["blob_size"]), []).append(
                    (target, path, d))
    if not jobs_by_blob:
        return 0

    reg = _load_files_reg(biz)
    reg_lock = threading.Lock()
    total = sum(d["new_size"] for lst in jobs_by_blob.values()
                for _, _, d in lst) or 1
    done = [0]
    patched = [0]
    plock = threading.Lock()
    game = _game_by_biz(biz) or {}
    name = (game.get("display", {}) or {}).get("name", biz)

    def do_blob(key, files):
        prefix, blob, _bsize = key
        # Download the shared blob once (its files are contiguous slices) and
        # slice it in memory — HoYo blobs are chunk-sized (~64-100 MB).
        data = _download_bytes(prefix + "/" + blob)
        for target, path, d in files:
            slice_ = data[d["offset"]:d["offset"] + d["length"]]
            if len(slice_) != d["length"]:
                continue
            pf = target + ".skpatch"
            nf = target + ".sknew"
            try:
                with open(pf, "wb") as f:
                    f.write(slice_)
                r = subprocess.run([hpz, target, pf, nf],
                                   capture_output=True, timeout=300)
                if (r.returncode == 0 and os.path.exists(nf)
                        and (not d["new_md5"]
                             or _md5_file(nf) == d["new_md5"])):
                    os.replace(nf, target)
                    with reg_lock:
                        reg[path] = d["new_md5"]
                    with plock:
                        patched[0] += 1
            finally:
                for p in (pf, nf):
                    try:
                        os.path.exists(p) and os.remove(p)
                    except OSError:
                        pass
                with plock:
                    done[0] += d["new_size"]
                    _write_progress(
                        biz, 40.0 * done[0] / total,
                        f"Patching {name} ({source_ver}→{target_ver}) — "
                        f"{_human(done[0])}/{_human(total)}")

    _write_progress(biz, 0, f"Delta update {source_ver}→{target_ver}…")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(do_blob, k, v) for k, v in jobs_by_blob.items()]
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                print(f"delta blob error: {e}", file=sys.stderr)
    with reg_lock:
        _save_files_reg(biz, reg)
    return patched[0]


def worker_install(biz):
    """Detached worker: fetch the sophon manifest, download the chunks of
    every missing/changed file in parallel, assemble+verify in place. Reruns
    (resume after a reboot, or a version update) only fetch what changed.
    On a version bump it first tries DELTA patches (getPatchBuild + hpatchz)
    from the installed version, so only the diff is downloaded."""
    try:
        game = _game_by_biz(biz) or {}
        name = (game.get("display", {}) or {}).get("name", biz)
        binfo = _branch_info(biz)
        version = (binfo or {}).get("tag", "")
        if not version:
            _write_progress(biz, 0, "Installation Failed.",
                            error=f"No sophon branch found for {biz}")
            return

        # Idempotence guard: already installed at this exact version with the
        # exe still on disk → nothing to do (a second click on "Install" or a
        # boot-time resume of a finished download must stay a no-op).
        st0 = load_state()["games"].get(biz, {})
        if (st0.get("installed") and st0.get("exe")
                and os.path.exists(st0["exe"])
                and st0.get("version") == version):
            _write_progress(biz, 100, "Finished installation process",
                            done=True)
            return

        # ── delta phase: on a version bump, patch changed files from the
        #    installed version (getPatchBuild + hpatchz) so only the diff is
        #    downloaded. Purely additive — the full pipeline below then only
        #    has to fetch what wasn't (or couldn't be) patched. ──────────────
        installed_ver = st0.get("version")
        diff_tags = (binfo or {}).get("diff_tags", [])
        if (st0.get("installed") and installed_ver
                and installed_ver != version and installed_ver in diff_tags):
            try:
                n = _try_delta_patch(biz, installed_ver, version)
                if n:
                    print(f"delta: patched {n} files "
                          f"{installed_ver}→{version}", file=sys.stderr)
            except Exception as e:
                print(f"delta patch skipped: {e}", file=sys.stderr)

        _write_progress(biz, 0, f"Fetching manifests ({version})…")
        build = _sophon_build(biz)
        mans = [m for f in _install_fields(biz)
                for m in [_build_category(build, f)] if m]
        if not mans:
            _write_progress(biz, 0, "Installation Failed.",
                            error=f"No install manifests for {biz}")
            return
        assets = []                      # (asset, its category's fetcher)
        seen = set()
        for i, man in enumerate(mans, 1):
            if len(mans) > 1:
                _write_progress(biz, 0, f"Fetching manifests ({version}) — "
                                        f"{i}/{len(mans)}")
            fetcher = _ChunkFetcher(man["chunk_download"]["url_prefix"])
            for a in _parse_manifest(_fetch_manifest(biz, man)):
                if a["name"] in seen:    # categories may overlap on a path
                    continue
                seen.add(a["name"])
                assets.append((a, fetcher))
        total_comp = max(sum(c["csize"] for a, _ in assets
                             for c in a["chunks"]), 1)
        out_root = _game_dir(biz)

        # ── phase 1: prescan — skip files already good on disk ───────────
        # Registry hit = trust (written after md5 verify); otherwise a file
        # matching name+size is hashed once so an update reuses it.
        reg = _load_files_reg(biz)
        reg_lock = threading.Lock()
        root_prefix = os.path.normpath(out_root) + os.sep
        todo, done_comp, lastw = [], 0, 0.0
        for a, fetcher in assets:
            target = os.path.normpath(
                os.path.join(out_root, a["name"].replace("\\", "/")))
            if not target.startswith(root_prefix):
                _write_progress(biz, 0, "Installation Failed.",
                                error=f"Unsafe path in manifest: {a['name']}")
                return
            comp = sum(c["csize"] for c in a["chunks"])
            good = False
            if os.path.isfile(target) and os.path.getsize(target) == a["size"]:
                if reg.get(a["name"]) == a["md5"]:
                    good = True
                elif _md5_file(target) == a["md5"]:
                    good = True
                    reg[a["name"]] = a["md5"]
            if good:
                done_comp += comp
            else:
                todo.append((a, target, fetcher))
            now = time.time()
            if now - lastw >= 1.0:
                lastw = now
                _write_progress(biz, 99.0 * done_comp / total_comp,
                                f"Checking existing files — "
                                f"{_human(done_comp)} reusable")
        _save_files_reg(biz, reg)

        free = shutil.disk_usage(out_root).free
        need = sum(a["size"] for a, _, _ in todo) + (1 << 30)
        if free < need:
            _write_progress(
                biz, 0, "Installation Failed.",
                error=(f"Not enough disk space: need {_human(need)} free, "
                       f"only {_human(free)} available."))
            return

        # ── phase 2: download + assemble chunks in parallel (→ 99 %) ─────
        done_bytes = done_comp
        lock = threading.Lock()
        last = {"t": time.time(), "b": done_bytes, "write": 0.0}

        def on_bytes(delta):
            nonlocal done_bytes
            with lock:
                done_bytes += delta
                now = time.time()
                if now - last["write"] < 1.0:
                    return
                dt = max(now - last["t"], 0.001)
                speed = (done_bytes - last["b"]) / dt / (1 << 20)
                last.update(t=now, b=done_bytes, write=now)
                _write_progress(
                    biz, 99.0 * done_bytes / total_comp,
                    f"Downloading {name} — "
                    f"{_human(done_bytes)}/{_human(total_comp)}"
                    f"\nSpeed: {speed:.1f} MB/s")

        def finalize(part):
            os.close(part.fd)
            part.fd = None
            a = part.asset
            if a["md5"] and _md5_file(part.path) != a["md5"]:
                os.remove(part.path)
                raise RuntimeError(f"checksum mismatch: {a['name']} "
                                   "— run Install again to redownload it.")
            os.replace(part.path, part.target)
            with reg_lock:
                reg[a["name"]] = a["md5"]
                _save_files_reg(biz, reg)

        def run_chunk(part, c):
            raw = part.fetcher.get(c["name"])
            if len(raw) != c["csize"]:
                raise RuntimeError(f"chunk size mismatch ({c['name']})")
            dec = _zstd_decompress(raw)
            if c["md5"] and hashlib.md5(dec).hexdigest() != c["md5"]:
                raise RuntimeError(f"chunk checksum mismatch ({c['name']})")
            with part.lock:
                if part.fd is None:      # first chunk creates the .skpart
                    os.makedirs(os.path.dirname(part.path), exist_ok=True)
                    with open(part.path, "wb") as f:
                        f.truncate(part.asset["size"])
                    part.fd = os.open(part.path, os.O_WRONLY)
            os.pwrite(part.fd, dec, c["offset"])
            with part.lock:
                part.left -= 1
                if part.left == 0:
                    finalize(part)
            on_bytes(c["csize"])

        jobs = []
        for a, target, fetcher in todo:
            if not a["chunks"]:          # zero-byte file
                os.makedirs(os.path.dirname(target), exist_ok=True)
                open(target, "wb").close()
                reg[a["name"]] = a["md5"]
                continue
            part = _Part(a, target, fetcher)
            jobs.extend((part, c) for c in a["chunks"])
        _save_files_reg(biz, reg)

        failed = None
        with ThreadPoolExecutor(max_workers=CHUNK_THREADS) as pool:
            futures = [pool.submit(run_chunk, p, c) for p, c in jobs]
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as e:
                    failed = e
                    for f in futures:
                        f.cancel()
                    break
        if failed:
            _write_progress(biz, 0, "Installation Failed.", error=str(failed))
            return

        # ── phase 3: locate exe, persist state, clean up ─────────────────
        exe = None
        known = _KNOWN_EXES.get(biz)
        for root, dirs, files in os.walk(out_root):
            dirs[:] = [d for d in dirs if d != "_pkg"]
            for f in files:              # stale parts of removed files
                if f.endswith(".skpart"):
                    try:
                        os.remove(os.path.join(root, f))
                    except OSError:
                        pass
            for f in files:
                if known and f == known:
                    exe = os.path.join(root, f)
                    break
            if exe:
                break
        if not exe:  # fallback: biggest top-level .exe
            cands = []
            for root, dirs, files in os.walk(out_root):
                dirs[:] = [d for d in dirs if d != "_pkg"]
                cands += [os.path.join(root, f) for f in files
                          if f.lower().endswith(".exe")]
            exe = max(cands, key=os.path.getsize) if cands else None
        if not exe:
            _write_progress(biz, 0, "Installation Failed.",
                            error="No game executable found after extraction.")
            return

        state = load_state()
        st = state["games"].setdefault(biz, {})
        st.update({"installed": True, "version": version, "exe": exe,
                   "dir": os.path.dirname(exe)})
        save_state(state)
        shutil.rmtree(_pkg_dir(biz), ignore_errors=True)
        if biz in NEEDS_JADEITE:      # best-effort: game still launches plain
            try:
                ensure_jadeite()
            except Exception as e:
                print(f"jadeite fetch failed: {e}", file=sys.stderr)
        _apply_egs_config(biz)        # ZZZ: EGS channel so it runs on Proton
        _write_progress(biz, 100, "Finished installation process", done=True)
    except Exception as e:
        _write_progress(biz, 0, "Installation Failed.", error=str(e))


def _spawn_worker(biz):
    log = open(os.path.join(LOG_DIR, f"mihoyo_{biz}.log"), "ab")
    proc = subprocess.Popen(
        [PYEXE, os.path.abspath(__file__), "worker-install", biz],
        stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        start_new_session=True, cwd=os.path.dirname(os.path.abspath(__file__)))
    return proc.pid


def action_download(biz, *_):
    os.makedirs(LOG_DIR, exist_ok=True)
    cur = _read_progress(biz)
    if cur and not cur.get("done") and not cur.get("error") \
            and cur.get("pid") and _pid_alive(cur["pid"]):
        return {"Type": "Progress", "Content": {"Message": "Downloading"}}
    _write_progress(biz, 0, "Starting download…", pid=0)
    pid = _spawn_worker(biz)
    _write_progress(biz, 0, "Starting download…", pid=pid)
    return {"Type": "Progress", "Content": {"Message": "Downloading"}}


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def action_getprogress(biz=""):
    p = _read_progress(biz)
    if not p:
        return {"Type": "ProgressUpdate",
                "Content": {"Percentage": 0, "Description": "Idle"}}
    if p.get("error"):
        return {"Type": "ProgressUpdate",
                "Content": {"Percentage": 0, "Description": p["desc"],
                            "Error": p["error"]}}
    if p.get("done"):
        return {"Type": "ProgressUpdate",
                "Content": {"Percentage": 100,
                            "Description": "Finished installation process"}}
    # worker crashed without reporting? (no heartbeat for 120 s and pid gone)
    if p.get("pid") and not _pid_alive(p["pid"]) \
            and time.time() - p.get("ts", 0) > 120:
        return {"Type": "ProgressUpdate",
                "Content": {"Percentage": 0, "Description": "Installation Failed.",
                            "Error": "Install worker stopped unexpectedly — "
                                     f"see mihoyo_{biz}.log"}}
    return {"Type": "ProgressUpdate",
            "Content": {"Percentage": int(p["pct"]), "Description": p["desc"]}}


def action_cancelinstall(biz, *_):
    p = _read_progress(biz) or {}
    pid = p.get("pid")
    if pid:
        try:
            os.killpg(pid, signal.SIGTERM)   # worker is its own session/pgroup
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    try:
        os.remove(_progress_path(biz))       # segments stay → resume later
    except OSError:
        pass
    return {"Type": "Success",
            "Content": {"Message": f"{biz} installation cancelled"}}


def _launch_options(biz):
    state = load_state()
    st = state["games"].get(biz, {})
    exe = st.get("exe", "")
    if not (exe and os.path.exists(exe)):
        return {"Type": "Error",
                "Content": {"Message": f"{biz} is not installed yet."}}
    name = ((_game_by_biz(biz) or {}).get("display", {}) or {}).get("name", biz)
    launcher = os.environ.get(
        "LAUNCHER",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "mihoyo-launcher.sh"))
    return {
        "Type": "LaunchOptions",
        "Content": {
            "Exe": f"\"{exe}\"".replace("$", "\\\\\\$"),
            # same glued "<id>%command%" shape as the other stores (proven in prod)
            "Options": f"{launcher} {biz}%command%",
            "WorkingDir": st.get("dir") or os.path.dirname(exe),
            "Compatibility": True,           # run through Steam's Proton
            "Name": name,
        },
    }


def action_install(biz, steam_client_id="", *_):
    state = load_state()
    st = state["games"].setdefault(biz, {})
    if steam_client_id:
        st["steamClientID"] = steam_client_id
        save_state(state)
    try:
        os.remove(_progress_path(biz))
    except OSError:
        pass
    return _launch_options(biz)


def action_getlaunchoptions(biz, *_):
    return _launch_options(biz)


def action_uninstall(biz, *_):
    gdir = _game_dir(biz)
    # safety: only ever delete inside our own install root
    if os.path.isdir(gdir) and os.path.realpath(gdir).startswith(
            os.path.realpath(INSTALL_DIR)):
        shutil.rmtree(gdir, ignore_errors=True)
    state = load_state()
    st = state["games"].setdefault(biz, {})
    st.pop("installed", None)
    st.pop("version", None)
    st.pop("exe", None)
    st.pop("dir", None)
    save_state(state)
    for path in (_progress_path(biz), _files_reg_path(biz)):
        try:
            os.remove(path)
        except OSError:
            pass
    return {"Type": "Success", "Content": {"Message": f"{biz} uninstalled"}}


def action_update(biz, *_):
    # An update is a re-run of the install worker: the file registry makes it
    # only download the files whose md5 changed in the new manifest.
    return action_download(biz)


def action_gamedir(biz):
    """Plain-text helper for mihoyo-launcher.sh (not a JSON action)."""
    st = load_state()["games"].get(biz, {})
    print(st.get("dir") or _game_dir(biz))


# ── anti-cheat loader (jadeite) for HI3 / HSR ────────────────────────────────
# Their anti-cheat refuses to start under Wine/Proton ("Anti-cheat system
# works error"). jadeite (codeberg.org/mkrsym1/jadeite) is the community
# loader-autopatcher used by the Linux launchers; the game launcher rewrites
# the command to `jadeite.exe <game.exe> --` when it's available.
NEEDS_JADEITE = {"bh3_global", "hkrpg_global"}
JADEITE_DIR = os.path.join(RUNTIME_DIR, "jadeite")
JADEITE_EXE = os.path.join(JADEITE_DIR, "jadeite.exe")
JADEITE_API = ("https://codeberg.org/api/v1/repos/mkrsym1/jadeite/"
               "releases?limit=1")


def ensure_jadeite():
    """Download the latest jadeite release (exe + payload DLLs) if missing."""
    if os.path.exists(JADEITE_EXE):
        return JADEITE_EXE
    rel = json.loads(_download_bytes(JADEITE_API))[0]
    asset = next(a for a in rel.get("assets", [])
                 if a.get("name", "").endswith(".zip"))
    zbytes = _download_bytes(asset["browser_download_url"])
    os.makedirs(JADEITE_DIR, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        z.extractall(JADEITE_DIR)
    state = load_state()
    state["jadeite_tag"] = rel.get("tag_name", "")
    save_state(state)
    return JADEITE_EXE if os.path.exists(JADEITE_EXE) else None


def action_jadeitepath(biz):
    """Plain-text helper for the launcher: jadeite.exe path when this game
    needs it AND it's already on disk (never blocks on the network)."""
    print(JADEITE_EXE
          if biz in NEEDS_JADEITE and os.path.exists(JADEITE_EXE) else "")


def action_gameexe(biz):
    """Plain-text helper for the launcher."""
    print(load_state()["games"].get(biz, {}).get("exe", ""))


def action_ensurejadeite(*_):
    try:
        p = ensure_jadeite()
        return {"Type": "Success",
                "Content": {"Message": f"jadeite ready: {p}"}}
    except Exception as e:
        return {"Type": "Error",
                "Content": {"Message": f"jadeite download failed: {e}"}}


# ── ZZZ anti-cheat: Epic Games Store channel config ──────────────────────────
# Zenless Zone Zero (nap_global) is NOT supported by jadeite. Its GLOBAL build
# launches on Proton with NO anti-cheat bypass at all when the game's
# config.ini uses the Epic Games Store channel (channel=1, sub_channel=3,
# cps=pcepic) — that build skips the check that otherwise blocks Wine. We merge
# those keys into config.ini (keeping any other keys) at install and before
# every launch. Community-established fix (jadeite issue #58 → notabug/Krock).
NEEDS_EGS_CONFIG = {"nap_global"}


def _apply_egs_config(biz):
    """Set the EGS channel keys in the game's config.ini (ZZZ only). Idempotent
    and non-destructive: other keys are preserved. No-op for other games."""
    if biz not in NEEDS_EGS_CONFIG:
        return
    st = load_state()["games"].get(biz, {})
    gdir = st.get("dir") or _game_dir(biz)
    overrides = {
        "channel": "1",
        "sub_channel": "3",
        "cps": "pcepic",
        "uapc": '{"hyp":{"uapc":""},"nap_global":{"uapc":""}}',
    }
    if st.get("version"):
        overrides["game_version"] = st["version"]
    cfg = os.path.join(gdir, "config.ini")
    try:
        with open(cfg) as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    if not any(x.strip().lower() == "[general]" for x in lines):
        lines = ["[general]"] + lines
    seen = set()
    out = []
    for line in lines:
        s = line.strip()
        key = (s.split("=", 1)[0].strip().lower()
               if "=" in s and not s.startswith("[") else None)
        if key in overrides:
            out.append(f"{key}={overrides[key]}")
            seen.add(key)
        else:
            out.append(line)
    for k, v in overrides.items():
        if k not in seen:
            for i, line in enumerate(out):
                if line.strip().lower() == "[general]":
                    out.insert(i + 1, f"{k}={v}")
                    break
    try:
        os.makedirs(gdir, exist_ok=True)
        with open(cfg, "w") as f:
            f.write("\n".join(out) + "\n")
    except OSError as e:
        print(f"ZZZ config.ini write failed: {e}", file=sys.stderr)


def action_applylaunchconfig(biz):
    """Launcher hook (plain text): apply any pre-launch game config. Currently
    the ZZZ EGS channel config; a harmless no-op for every other game."""
    try:
        _apply_egs_config(biz)
    except Exception as e:
        print(f"apply-launch-config: {e}", file=sys.stderr)


def action_autoupdate(*_):
    """Unattended daily update: for every installed game, compare the
    installed version with the live sophon branch tag; when it changed,
    respawn the install worker (parallel + resumable — the idempotence guard
    passes because the version differs, and only changed files are fetched).
    Also refreshes jadeite when a new release is tagged."""
    state = load_state()
    started = []
    # jadeite refresh (only when already present and the tag moved)
    try:
        if os.path.exists(JADEITE_EXE):
            rel = json.loads(_download_bytes(JADEITE_API))[0]
            tag = rel.get("tag_name", "")
            if tag and tag != state.get("jadeite_tag"):
                shutil.rmtree(JADEITE_DIR, ignore_errors=True)
                ensure_jadeite()
                started.append(f"jadeite→{tag}")
    except Exception as e:
        print(f"jadeite refresh failed: {e}", file=sys.stderr)

    for biz, st in (state.get("games") or {}).items():
        if not st.get("installed"):
            continue
        try:
            live = (_branch_info(biz) or {}).get("tag", "")
        except Exception as e:
            print(f"version check failed for {biz}: {e}", file=sys.stderr)
            continue
        if not live or live == st.get("version"):
            continue
        cur = _read_progress(biz)
        if cur and not cur.get("done") and not cur.get("error") \
                and cur.get("pid") and _pid_alive(cur["pid"]):
            continue                      # an install/update is already running
        os.makedirs(LOG_DIR, exist_ok=True)
        _write_progress(biz, 0, f"Updating to {live}…", pid=0)
        pid = _spawn_worker(biz)
        _write_progress(biz, 0, f"Updating to {live}…", pid=pid)
        started.append(f"{biz} {st.get('version')}→{live}")
    return {"Type": "Success",
            "Content": {"Message": ", ".join(started) or "all up to date"}}


def action_resumepending(*_):
    """Respawn workers for downloads interrupted by a reboot/crash. Called at
    plugin start (main.py) — safe: the worker resumes from finished segments
    and is a no-op for finished installs (idempotence guard)."""
    resumed = []
    try:
        for f in os.listdir(RUNTIME_DIR):
            m = re.fullmatch(r"mihoyo_progress_(.+)\.json", f)
            if not m:
                continue
            biz = m.group(1)
            p = _read_progress(biz) or {}
            if p.get("done") or p.get("error"):
                continue
            if p.get("pid") and _pid_alive(p["pid"]):
                continue                      # still running
            os.makedirs(LOG_DIR, exist_ok=True)
            pid = _spawn_worker(biz)
            _write_progress(biz, p.get("pct", 0),
                            p.get("desc", "Resuming…"), pid=pid)
            resumed.append(biz)
    except Exception as e:
        return {"Type": "Error", "Content": {"Message": str(e)}}
    return {"Type": "Success",
            "Content": {"Message": f"resumed: {', '.join(resumed) or 'none'}"}}


# Verbs we deliberately don't support (kept harmless for the shared UI).
_NOOP = {"protontricks", "run-exe", "get-exe-list", "update-umu-id",
         "move", "import"}


def main():
    argv = sys.argv[1:]
    if not argv:
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": "no action"}}))
        return
    action, args = argv[0], argv[1:]

    # non-JSON verbs (worker entrypoint + launcher helpers)
    if action == "worker-install":
        worker_install(*args)
        return
    if action == "game-dir":
        action_gamedir(*args)
        return
    if action == "game-exe":
        action_gameexe(*args)
        return
    if action == "jadeite-path":
        action_jadeitepath(*args)
        return
    if action == "apply-launch-config":
        action_applylaunchconfig(*args)
        return

    try:
        if action == "getgames":
            out = action_getgames(*args)
        elif action == "getgamesize":
            out = action_getgamesize(*args)
        elif action == "getgamedetails":
            out = action_getgamedetails(*args)
        elif action == "getjsonimages":
            out = action_getjsonimages(*args)
        elif action == "getprogress":
            out = action_getprogress(*args)
        elif action in ("loginstatus", "login-launch-options"):
            out = action_loginstatus(*args)
        elif action == "download":
            out = action_download(*args)
        elif action == "install":
            out = action_install(*args)
        elif action == "getlaunchoptions":
            out = action_getlaunchoptions(*args)
        elif action == "cancelinstall":
            out = action_cancelinstall(*args)
        elif action == "uninstall":
            out = action_uninstall(*args)
        elif action in ("update", "repair", "repair_and_update", "verify"):
            out = action_update(*args)
        elif action == "ensure-jadeite":
            out = action_ensurejadeite(*args)
        elif action == "resume-pending":
            out = action_resumepending(*args)
        elif action == "autoupdate":
            out = action_autoupdate(*args)
        elif action in _NOOP:
            out = {"Type": "Success", "Content": {"Message": "Not applicable"}}
        else:
            out = {"Type": "Error",
                   "Content": {"Message": f"unknown action: {action}"}}
    except Exception as e:
        out = {"Type": "Error", "Content": {"Message": str(e)}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
