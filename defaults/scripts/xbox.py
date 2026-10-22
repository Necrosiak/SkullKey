#!/usr/bin/env python3
"""Xbox (experimental): PC games from the Microsoft Store / Xbox account —
owned games, Game Pass games while the subscription is active, and free
games — installed and launched with the Xodus engine, without Xodus Nexus.

Flow: download (worker: tools → xodus-cli streaming) → install (Steam
shortcut on a launch script) → run (access check, prefix, xodus-cli run).

Only what the Microsoft account is entitled to can be installed or played:
the engine checks the licence, and the access rules hide or lock the rest."""

import base64
import contextlib
import fcntl
import json
import os
import pwd
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "shared"))

import xbox_access
import xbox_catalog
import xbox_cli
import xbox_prefix
import xbox_service
import xbox_tools

HOME = Path(os.path.expanduser("~"))
XBOX_DIR = xbox_tools.XBOX_DIR
STATE_FILE = XBOX_DIR / "state.json"
PROGRESS_DIR = XBOX_DIR / "progress"
LAUNCH_DIR = XBOX_DIR / "launch"
STORE = "Xbox"
DEFAULT_BASE = HOME / "Games" / STORE
PYEXE = sys.executable or "/usr/bin/python3"
PROFILE_TTL = 24 * 3600
MARKETS = {"fr": ("FR", "fr-fr"), "de": ("DE", "de-de"), "es": ("ES", "es-es"), "it": ("IT", "it-it"),
           "pt": ("PT", "pt-pt"), "nl": ("NL", "nl-nl"), "pl": ("PL", "pl-pl"), "ru": ("US", "ru-ru")}


def emit(kind, content):
    print(json.dumps({"Type": kind, "Content": content}))


def error(message):
    emit("Error", {"Message": message})


def market():
    try:
        from ports_i18n import machine_lang_code
        return MARKETS.get(machine_lang_code(), ("US", "en-us"))
    except Exception:
        return ("US", "en-us")


# ── state ────────────────────────────────────────────────────────────────────

def load_state():
    try:
        state = json.loads(STATE_FILE.read_text())
    except Exception:
        state = {}
    state.setdefault("games", {})
    return state


def save_state(state):
    XBOX_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(STATE_FILE)


@contextlib.contextmanager
def locked_state():
    XBOX_DIR.mkdir(parents=True, exist_ok=True)
    with open(XBOX_DIR / "state.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state()
        yield state
        save_state(state)


def write_progress(pid_, pct, desc, err=None, pid=None):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"Percentage": pct, "Description": desc, "Error": err}
    if pid:
        data["pid"] = pid
    (PROGRESS_DIR / f"{pid_}.json").write_text(json.dumps(data))


def _user_ids():
    try:
        u = pwd.getpwnam(os.path.basename(str(HOME)))
        return u.pw_uid, u.pw_gid
    except KeyError:
        return None


def give_to_user(path):
    ids = _user_ids()
    if not ids or os.geteuid() != 0:
        return
    for dirpath, dirnames, filenames in os.walk(path):
        for name in [dirpath] + [os.path.join(dirpath, n) for n in dirnames + filenames]:
            try:
                os.lchown(name, *ids)
            except OSError:
                pass


def _drives():
    import drives
    return drives


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (OSError, ValueError, TypeError):
        return False


# ── account & catalogue ──────────────────────────────────────────────────────

def signed_in():
    try:
        return xbox_cli.account()["stored"]
    except xbox_cli.CliError:
        return False


def account_view(refresh=False):
    """{"profile": {...}, "entitlements": [...]} cached in the state for 24 h."""
    state = load_state()
    cached = state.get("account") or {}
    if not refresh and cached and time.time() - cached.get("t", 0) < PROFILE_TTL:
        return cached
    m, _ = market()
    try:
        view = {"t": time.time(), "profile": xbox_cli.profile(), "entitlements": xbox_cli.library(m)}
    except xbox_cli.CliError:
        return cached or {"profile": {}, "entitlements": []}
    with locked_state() as st:
        st["account"] = view
    return view


def catalogue(query="", refresh=False):
    """[(id, info, access)] for the grid. info: title, publisher, art, contentId."""
    m, lang = market()
    state = load_state()
    installed = state["games"]
    view = account_view(refresh) if signed_in() else {"profile": {}, "entitlements": []}
    sub = xbox_access.subscription_active(view["profile"])
    ents = {e["productId"].upper(): e for e in view["entitlements"] if e.get("productId")}
    info = {pid: dict(d) for pid, d in xbox_catalog.details(list(ents), m, lang).items() if d.get("game")}
    store = {}
    for g in (xbox_catalog.search(query, m, lang, owned=set(ents)) if query else xbox_catalog.free_games(m, lang)):
        store[g["id"]] = g
        info.setdefault(g["id"], {"title": g["title"], "publisher": g["publisher"], "art": g["art"]})
        info[g["id"]]["contentId"] = g.get("contentId")
    deadline = time.monotonic() + xbox_catalog.RESOLVE_BUDGET
    unchecked = []
    out = []
    for pid in list(info):
        if query and pid not in store and query.lower() not in info[pid]["title"].lower():
            continue
        ent = ents.get(pid)
        st = store.get(pid)
        if ent and not st:
            content = xbox_catalog.installable(pid, m, deadline)
            if content is None and pid not in installed:
                unchecked.append(pid)
                continue
            st = {"price": "paid", "installable": bool(content)}
            info[pid]["contentId"] = content or None
        access = xbox_access.classify(ent, st, pid in installed, sub)
        if access["access"] == "hidden" and pid not in installed:
            continue
        out.append((pid, info[pid], access))
    for pid, g in installed.items():
        if pid not in info:
            out.append((pid, {"title": g.get("title", pid), "art": g.get("art") or {}},
                        xbox_access.classify(ents.get(pid), None, True, sub)))
    out.sort(key=lambda x: (x[0] not in installed, x[1]["title"].lower()))
    if unchecked:
        _start_prefetch(unchecked)
    return out


def _start_prefetch(pids):
    """Check the remaining games in the background (once, then cached 24 h):
    they appear in the grid the next time it loads."""
    lock = XBOX_DIR / "locks" / "prefetch"
    try:
        if _alive(lock.read_text().strip()):
            return
    except OSError:
        pass
    XBOX_DIR.mkdir(parents=True, exist_ok=True)
    todo = XBOX_DIR / "cache" / "prefetch.json"
    todo.parent.mkdir(parents=True, exist_ok=True)
    todo.write_text(json.dumps(pids))
    subprocess.Popen([PYEXE, os.path.abspath(__file__), "prefetch"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ.copy())


def prefetch(pids=None):
    if pids is None:
        try:
            pids = json.loads((XBOX_DIR / "cache" / "prefetch.json").read_text())
        except (OSError, ValueError):
            return
    m, _ = market()
    with xbox_tools.hold("prefetch"):
        for pid in pids:
            xbox_catalog.installable(pid, m)


# ── games installed by Xodus Nexus ───────────────────────────────────────────

NEXUS_GAMES = HOME / "Games" / "Xodus Nexus"
NEXUS_STATE = HOME / ".config" / "xodus-nexus" / "launcher-state.json"


def import_nexus_games():
    """Games already installed by Xodus Nexus show up as installed here, so
    nothing has to be downloaded again."""
    candidates = [d for d in NEXUS_GAMES.iterdir() if d.is_dir()] if NEXUS_GAMES.is_dir() else []
    try:
        candidates += [Path(g["path"]) for g in json.loads(NEXUS_STATE.read_text()).get("games", [])
                       if isinstance(g, dict) and g.get("path")]
    except (OSError, ValueError):
        pass
    found = {}
    for d in candidates:
        if not d.is_dir() or d.name.startswith("."):
            continue
        info = xbox_cli.inspect_game(d)
        pid = (info.get("storeId") or "").upper()
        if pid and info.get("executable"):
            found.setdefault(pid, (d, info))
    known = load_state()["games"]
    if all(pid in known for pid in found):
        return
    with locked_state() as st:
        for pid, (d, info) in found.items():
            st["games"].setdefault(pid, {"title": info["title"], "root": str(d), "art": {},
                                         "executable": info["executable"], "steamClientID": "",
                                         "imported": True})


# ── anti-cheat ───────────────────────────────────────────────────────────────

# Folders shipped by kernel or Windows-only anti-cheats. Easy Anti-Cheat and
# BattlEye work only when the publisher enabled their Proton support.
ANTICHEAT_DIRS = {"anticheatexpert": "AntiCheatExpert (ACE)", "easyanticheat": "Easy Anti-Cheat",
                  "easyanticheat_eos": "Easy Anti-Cheat", "battleye": "BattlEye",
                  "be": None, "vanguard": "Vanguard", "xigncode": "XIGNCODE3", "gameguard": "nProtect GameGuard"}
# Known before download (tested): product id -> anti-cheat.
ANTICHEAT_KNOWN = {"9N1BZS0V3K0C": "AntiCheatExpert (ACE)"}  # Mecha BREAK, 22/10/2026
ANTICHEAT_LABELS = {
    "en": "⚠️ Anti-cheat {name}: this game will probably not run on Linux.",
    "fr": "⚠️ Anti-triche {name} : ce jeu ne fonctionnera probablement pas sous Linux.",
    "de": "⚠️ Anti-Cheat {name}: Dieses Spiel läuft unter Linux wahrscheinlich nicht.",
    "es": "⚠️ Antitrampas {name}: probablemente este juego no funcione en Linux.",
    "it": "⚠️ Anti-cheat {name}: probabilmente questo gioco non funzionerà su Linux.",
    "pt": "⚠️ Antitrapaça {name}: este jogo provavelmente não funcionará no Linux.",
    "nl": "⚠️ Anti-cheat {name}: deze game werkt waarschijnlijk niet op Linux.",
    "pl": "⚠️ Anti-cheat {name}: ta gra prawdopodobnie nie zadziała w systemie Linux.",
    "ru": "⚠️ Античит {name}: игра, вероятно, не запустится в Linux.",
}


SLOW_START = {
    "en": "ℹ️ Slower start: the Xbox engine decrypts the game each time it starts, and the very first launch also prepares its Proton prefix.",
    "fr": "ℹ️ Démarrage plus long : le moteur Xbox déchiffre le jeu à chaque lancement, et le tout premier lancement prépare aussi son préfixe Proton.",
    "de": "ℹ️ Längerer Start: Die Xbox-Engine entschlüsselt das Spiel bei jedem Start, beim ersten Start wird außerdem das Proton-Präfix vorbereitet.",
    "es": "ℹ️ Inicio más lento: el motor de Xbox descifra el juego en cada inicio, y el primer inicio también prepara su prefijo de Proton.",
    "it": "ℹ️ Avvio più lento: il motore Xbox decifra il gioco a ogni avvio, e il primo avvio prepara anche il suo prefisso Proton.",
    "pt": "ℹ️ Início mais lento: o motor Xbox descriptografa o jogo a cada início, e o primeiro início também prepara o prefixo Proton.",
    "nl": "ℹ️ Langzamere start: de Xbox-engine ontsleutelt de game bij elke start, en de allereerste start maakt ook de Proton-prefix klaar.",
    "pl": "ℹ️ Wolniejsze uruchamianie: silnik Xbox odszyfrowuje grę przy każdym uruchomieniu, a pierwsze uruchomienie przygotowuje też prefiks Proton.",
    "ru": "ℹ️ Долгий запуск: движок Xbox расшифровывает игру при каждом запуске, а первый запуск ещё и готовит префикс Proton.",
}


# ── game language ────────────────────────────────────────────────────────────
# Adapted from Xodus Nexus src/main/game-locale.ts and proton.ts (MIT).

REGIONS = {"en": "en-US", "fr": "fr-FR", "de": "de-DE", "es": "es-ES", "it": "it-IT", "pt": "pt-PT",
           "nl": "nl-NL", "pl": "pl-PL", "ru": "ru-RU"}


STEAM_LANGUAGES = {
    "english": "en-US", "french": "fr-FR", "german": "de-DE", "spanish": "es-ES", "latam": "es-MX",
    "italian": "it-IT", "brazilian": "pt-BR", "portuguese": "pt-PT", "polish": "pl-PL", "russian": "ru-RU",
    "dutch": "nl-NL", "japanese": "ja-JP", "koreana": "ko-KR", "tchinese": "zh-TW", "schinese": "zh-CN",
    "arabic": "ar-SA", "turkish": "tr-TR", "czech": "cs-CZ", "swedish": "sv-SE", "danish": "da-DK",
    "finnish": "fi-FI", "norwegian": "nb-NO", "hungarian": "hu-HU", "ukrainian": "uk-UA",
}


def steam_locale():
    """The Steam (SteamOS) interface language, like the EA tab."""
    import re
    try:
        text = (HOME / ".steam" / "registry.vdf").read_text(errors="replace")
    except OSError:
        return None
    match = re.search(r'"language"\s+"([a-z]+)"', text)
    return STEAM_LANGUAGES.get(match[1]) if match else None


def game_locale(root):
    """The package language matching the machine language, or None."""
    import re
    import xml.etree.ElementTree as ET
    root = Path(root)
    entries = {p.name.lower(): p for p in root.iterdir()} if root.is_dir() else {}
    langs = []
    for name in ("microsoftgame.config", "appxmanifest.xml"):
        if name not in entries:
            continue
        try:
            tree = ET.fromstring(entries[name].read_text(errors="ignore"))
        except ET.ParseError:
            continue
        for el in tree.iter():
            lang = el.get("Language")
            if el.tag.rsplit("}", 1)[-1] == "Resource" and lang and re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", lang):
                langs.append(lang)
    want = steam_locale() or REGIONS.get(_lang(), "en-US")
    exact = next((l for l in langs if l.lower() == want.lower()), None)
    return exact or next((l for l in langs if l.lower().split("-")[0] == want.split("-")[0]), None)


def locale_env(env, locale):
    env = dict(env)
    if not locale:
        return env
    env.update(XODUS_PACKAGE_LOCALE=locale, WINEUSERLOCALE=locale)
    parts = locale.split("-")
    if len(parts) == 2 and len(parts[1]) == 2:
        unix = f"{parts[0].lower()}_{parts[1].upper()}.UTF-8"
        for key in ("LANG", "LC_ALL", "LC_MESSAGES", "LC_CTYPE", "LC_TIME", "LC_COLLATE", "LC_MONETARY",
                    "LC_NUMERIC", "LC_PAPER"):
            env[key] = unix
        env["LANGUAGE"] = f"{parts[0].lower()}_{parts[1].upper()}:{parts[0].lower()}"
    return env


def sync_prefix_locale(pid, runner, locale, env):
    """Wine fixes the Windows user locale when the prefix is created; drop the
    key once per language so Wine rebuilds it from the launch environment."""
    if not locale or "-" not in locale:
        return
    mark = xbox_prefix.prefix_dir(pid) / ".skullkey-locale"
    try:
        if mark.read_text().strip() == locale:
            return
    except OSError:
        pass
    code = subprocess.call([str(runner), "reg", "delete", "HKCU\\Control Panel\\International", "/f"],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if code == 0:
        mark.write_text(locale)


def anticheat(pid):
    g = load_state()["games"].get(pid) or {}
    root = Path(g.get("root", "/nonexistent"))
    if root.is_dir():
        for d in root.iterdir():
            name = ANTICHEAT_DIRS.get(d.name.lower())
            if d.is_dir() and name:
                return name
    return ANTICHEAT_KNOWN.get(pid)


# ── grid & details ───────────────────────────────────────────────────────────

def action_getgames(filter_str="", installed="false"):
    # The engine is small: install/refresh it when the tab opens. The runtime
    # (hundreds of MB) waits for the first game install.
    xbox_tools.ensure(update=True, components=("backend",))
    import_nexus_games()
    games = []
    for i, (pid, info, access) in enumerate(catalogue(filter_str), start=1):
        if installed.lower() == "true" and pid not in load_state()["games"]:
            continue
        cover = (info.get("art") or {}).get("cover")
        games.append({"ID": i, "Name": info["title"], "Images": [cover] if cover else [], "ShortName": pid,
                      "SteamClientID": load_state()["games"].get(pid, {}).get("steamClientID", "")})
    # "true" keeps the account bar (gamertag, sign in/out) above the grid,
    # like EA; the bar itself shows whether the account is connected.
    emit("GameGrid", {"Games": games, "NeedsLogin": "true"})


def _entry(pid):
    for p, info, access in catalogue(refresh=False):
        if p == pid:
            return info, access
    g = load_state()["games"].get(pid)
    if g:
        return {"title": g.get("title", pid), "art": g.get("art") or {}}, xbox_access.classify(None, None, True, False)
    return None, None


def action_getgamedetails(pid):
    m, lang = market()
    info, access = _entry(pid)
    if not info:
        return error("Unknown game.")
    d = xbox_catalog.details([pid], m, lang).get(pid) or {}
    labels = {"owned": "Owned", "gamepass": "Game Pass", "free": "Free"}
    lines = [d.get("description", "")] if d.get("description") else []
    lines.append(labels.get(access["access"], ""))
    ac = anticheat(pid)
    if ac:
        lines.append(ANTICHEAT_LABELS.get(_lang(), ANTICHEAT_LABELS["en"]).format(name=ac))
    lines.append(SLOW_START.get(_lang(), SLOW_START["en"]))
    if access["reason"] == "subscription-required":
        lines.append("Game Pass subscription required to play.")
    g = load_state()["games"].get(pid) or {}
    if g.get("root"):
        lines.append("Location: " + g["root"].replace(str(HOME), "~"))
    cover = (info.get("art") or {}).get("cover")
    emit("GameDetails", {
        "Name": info["title"], "Description": "<br><br>".join(l for l in lines if l),
        "ApplicationPath": "", "ManualPath": "", "RootFolder": "", "DatabaseID": pid,
        "ConfigurationPath": "", "Images": [cover] if cover else [], "ShortName": pid,
        "SteamClientID": g.get("steamClientID", ""), "HasDosConfig": False, "HasBatFiles": False,
        "Editors": []})


def _b64(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "SkullKey"})
    with urllib.request.urlopen(req, timeout=20, context=xbox_tools._ssl()) as r:
        data = r.read()
    kind = "png" if data[:4] == b"\x89PNG" else "jpg"
    return base64.b64encode(data).decode(), kind


def action_getjsonimages(pid):
    m, lang = market()
    art = (xbox_catalog.details([pid], m, lang).get(pid) or {}).get("art") or \
        ((_entry(pid)[0] or {}).get("art") or {})
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    for key, slot in (("Grid", "cover"), ("GridH", "wide"), ("Hero", "hero"), ("Logo", "logo")):
        url = art.get(slot) or (art.get("hero") if slot == "wide" else None)
        if not url:
            continue
        try:
            content[key], content[key + "Type"] = _b64(url)
        except Exception as e:  # noqa: BLE001
            print(f"art {key} failed: {type(e).__name__}", file=sys.stderr)
    emit("Images", content)


def action_getgamesize(pid):
    g = load_state()["games"].get(pid) or {}
    root = Path(g.get("root", "/nonexistent"))
    size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file()) if root.is_dir() else 0
    emit("GameSize", {"Size": f"Size: {size / (1 << 30):.1f} GB" if size else ""})


# ── download ─────────────────────────────────────────────────────────────────

def action_download(pid):
    if pid in load_state()["games"]:
        # Already on disk (e.g. picked up from Xodus Nexus): only the Steam
        # shortcut is missing, which the Install step that follows creates.
        write_progress(pid, 100, "Installed")
        return emit("Progress", {"Message": "Installing"})
    info, access = _entry(pid)
    if not info:
        return error("Unknown game.")
    if not access["playable"]:
        return error("A Game Pass subscription is required for this game.")
    root = Path(_drives().assign(STORE, pid, DEFAULT_BASE / pid))
    with locked_state() as st:
        st.setdefault("pending", {})[pid] = {"title": info["title"], "root": str(root),
                                             "art": info.get("art") or {}, "contentId": info.get("contentId")}
    write_progress(pid, 0, "Starting…")
    subprocess.Popen([PYEXE, os.path.abspath(__file__), "worker", pid], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ.copy())
    emit("Progress", {"Message": "Installing"})


STEPS = {
    "en": ("Step", {"engine": "Preparing the Xbox engine", "metadata": "Reading the game package",
                    "downloading": "Downloading", "finalizing": "Finalizing"}, "GB", "MB/s", "."),
    "fr": ("Étape", {"engine": "Préparation du moteur Xbox", "metadata": "Lecture du paquet du jeu",
                     "downloading": "Téléchargement", "finalizing": "Finalisation"}, "Go", "Mo/s", ","),
    "de": ("Schritt", {"engine": "Xbox-Engine wird vorbereitet", "metadata": "Spielpaket wird gelesen",
                       "downloading": "Download", "finalizing": "Abschluss"}, "GB", "MB/s", ","),
    "es": ("Paso", {"engine": "Preparando el motor de Xbox", "metadata": "Leyendo el paquete del juego",
                    "downloading": "Descargando", "finalizing": "Finalizando"}, "GB", "MB/s", ","),
    "it": ("Passo", {"engine": "Preparazione del motore Xbox", "metadata": "Lettura del pacchetto di gioco",
                     "downloading": "Download", "finalizing": "Completamento"}, "GB", "MB/s", ","),
    "pt": ("Passo", {"engine": "Preparando o motor Xbox", "metadata": "Lendo o pacote do jogo",
                     "downloading": "Baixando", "finalizing": "Finalizando"}, "GB", "MB/s", ","),
    "nl": ("Stap", {"engine": "Xbox-engine voorbereiden", "metadata": "Spelpakket lezen",
                    "downloading": "Downloaden", "finalizing": "Afronden"}, "GB", "MB/s", ","),
    "pl": ("Krok", {"engine": "Przygotowanie silnika Xbox", "metadata": "Odczyt pakietu gry",
                    "downloading": "Pobieranie", "finalizing": "Finalizowanie"}, "GB", "MB/s", ","),
    "ru": ("Шаг", {"engine": "Подготовка движка Xbox", "metadata": "Чтение пакета игры",
                   "downloading": "Загрузка", "finalizing": "Завершение"}, "ГБ", "МБ/с", ","),
}
STEP_ORDER = ("engine", "metadata", "downloading", "finalizing")


def step_text(phase, p=None, elapsed=None):
    """The engine gives no measure while it reads the package: show the time
    spent instead, so the step visibly moves."""
    word, names, gb, mbs, dec = STEPS.get(_lang(), STEPS["en"])
    phase = phase if phase in names else "downloading"
    text = f"{word} {STEP_ORDER.index(phase) + 1}/4 · {names[phase]}"
    if phase == "downloading" and p and p.get("total"):
        fmt = lambda v: f"{v / 2**30:.1f}".replace(".", dec)
        text += f" · {int(p['done'] * 100 / p['total'])} % · {fmt(p['done'])} / {fmt(p['total'])} {gb}"
        rate = p.get("rate") or 0
        if rate > 0:
            left = (p["total"] - p["done"]) / rate / 60
            text += f" · {rate / 2**20:.0f} {mbs} · ~{max(1, round(left))} min"
    elif elapsed is not None:
        text += f" · {int(elapsed) // 60}:{int(elapsed) % 60:02d}"
    return text


def worker(pid):
    st = load_state()
    job = (st.get("pending") or {}).get(pid)
    if not job:
        return
    root = Path(job["root"])
    write_progress(pid, 0, step_text("engine"), pid=os.getpid())
    proc = None

    def stop(*_):
        if proc:
            xbox_cli.cancel(proc)
        raise SystemExit(130)
    signal.signal(signal.SIGTERM, stop)
    try:
        with xbox_tools.hold(f"install-{pid}"):
            res = xbox_tools.ensure(update=False)
            if not xbox_tools.cli_path() or not xbox_tools.wine_path():
                raise RuntimeError("; ".join(res["errors"]) or "The Xbox engine could not be installed.")
            root.parent.mkdir(parents=True, exist_ok=True)
            give_to_user(root.parent)
            m, _ = market()
            proc = xbox_cli.start_streaming(pid, root, m, job.get("contentId"))
            last = None
            started = time.time()
            write_progress(pid, 0, step_text("metadata", elapsed=0), pid=os.getpid())
            stop_ticker = threading.Event()

            def tick():
                # No progress records while the package is read: refresh the
                # elapsed time every second until real numbers arrive.
                while not stop_ticker.wait(1):
                    write_progress(pid, 0, step_text("metadata", elapsed=time.time() - started), pid=os.getpid())
            threading.Thread(target=tick, daemon=True).start()
            for line in proc.stdout:
                p = xbox_cli.parse_progress(line)
                if not p:
                    continue
                last = p
                pct = int(p["percent"] or 0)
                phase = {"initializing": "metadata", "complete": "finalizing"}.get(p["phase"], p["phase"])
                if phase == "metadata" and not p.get("total"):
                    continue
                stop_ticker.set()
                write_progress(pid, min(pct, 99), step_text(phase, p, time.time() - started), pid=os.getpid())
            stop_ticker.set()
            code = proc.wait()
            if code != 0 or not last or last["phase"] != "complete":
                raise RuntimeError("The download did not complete (licence, network or disk space).")
        game = xbox_cli.inspect_game(root)
        give_to_user(root)
        with locked_state() as s:
            s.get("pending", {}).pop(pid, None)
            s["games"][pid] = {"title": game["title"] or job["title"], "root": str(root), "art": job["art"],
                               "executable": game["executable"], "steamClientID": ""}
        write_progress(pid, 100, "Installed")
    except SystemExit:
        _cleanup_partial(pid, root)
        raise
    except Exception as e:  # noqa: BLE001
        _cleanup_partial(pid, root)
        write_progress(pid, 0, "Failed", str(e)[:200])


def _cleanup_partial(pid, root):
    if root.is_dir() and root.name == pid:
        shutil.rmtree(root, ignore_errors=True)
    _drives().forget(STORE, pid)
    with locked_state() as s:
        s.get("pending", {}).pop(pid, None)


def action_getprogress(pid):
    try:
        data = json.loads((PROGRESS_DIR / f"{pid}.json").read_text())
    except Exception:
        data = {"Percentage": 0, "Description": "Waiting…", "Error": None}
    if data.get("pid") and not _alive(data["pid"]) and data.get("Percentage", 0) < 100 and not data.get("Error"):
        data["Error"] = "The download stopped unexpectedly. Try again."
    data.pop("pid", None)
    emit("ProgressUpdate", data)


def action_cancelinstall(pid):
    try:
        wpid = json.loads((PROGRESS_DIR / f"{pid}.json").read_text()).get("pid")
        if wpid and _alive(wpid) and str(pid) in Path(f"/proc/{wpid}/cmdline").read_bytes().decode(errors="ignore"):
            os.kill(int(wpid), signal.SIGTERM)
            for _ in range(100):
                if not _alive(wpid):
                    break
                time.sleep(0.1)
    except Exception:
        pass
    (PROGRESS_DIR / f"{pid}.json").unlink(missing_ok=True)
    emit("Success", {"Message": "Cancelled"})


# ── shortcut & launch ────────────────────────────────────────────────────────

def launch_script(pid):
    LAUNCH_DIR.mkdir(parents=True, exist_ok=True)
    script = LAUNCH_DIR / f"{pid}.sh"
    script.write_text(f"#!/bin/sh\nexec {PYEXE} {os.path.abspath(__file__)!s} run {pid}\n")
    script.chmod(0o755)
    give_to_user(LAUNCH_DIR)
    return script


def action_install(pid, steam_id=""):
    with locked_state() as st:
        g = st["games"].get(pid)
        if g and steam_id:
            g["steamClientID"] = str(steam_id)
    if not g:
        return error("This game is not installed yet.")
    emit("LaunchOptions", {"Exe": str(launch_script(pid)), "Options": "", "WorkingDir": g["root"],
                           "Compatibility": False, "Name": g["title"]})


def action_run(pid):
    g = load_state()["games"].get(pid)
    if not g:
        return error("This game is not installed.")
    view = account_view()
    ents = {e["productId"].upper(): e for e in view["entitlements"] if e.get("productId")}
    access = xbox_access.classify(ents.get(pid), {"price": "free", "installable": True}, True,
                                  xbox_access.subscription_active(view["profile"]))
    if not access["playable"]:
        print("A Game Pass subscription is required to play this game.", file=sys.stderr)
        return 3
    xbox_tools.ensure(update=True)
    runner = None
    with xbox_tools.hold(f"run-{pid}"):
        xbox_prefix.ensure_prefix(pid)
        runner = xbox_prefix.write_runner(pid)
        exe = g.get("executable") or xbox_cli.inspect_game(g["root"])["executable"]
        if not exe:
            print("The game's executable was not found in its package.", file=sys.stderr)
            return 4
        m, _ = market()
        locale = game_locale(g["root"])
        env = locale_env(xbox_cli._env(), locale)
        sync_prefix_locale(pid, runner, locale, env)
        # In-game Xbox sign-in, Store licence checks and cloud saves go
        # through the account service, reached over its loopback bridge.
        session = xbox_service.start(env)
        try:
            env.update(session.env)
            cmd = [str(xbox_tools.cli_path()), "run", g["root"], str(runner), "--exe", exe,
                   "--materialize-chain", "--market", m]
            # Keep the engine output of the last launch: licence and Store
            # errors only show up there. No account data is printed by it.
            logs = XBOX_DIR / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            with open(logs / f"{pid}.log", "w") as log:
                code = subprocess.call(cmd, env=env, cwd=g["root"], stdout=log, stderr=subprocess.STDOUT)
                log.write(f"\nSkullKey: the game exited with code {code}\n")
                ac = anticheat(pid)
                if ac and code:
                    log.write(f"SkullKey: this game ships {ac}, which usually blocks Linux.\n")
                return code
        finally:
            session.stop()


# ── uninstall ────────────────────────────────────────────────────────────────

def _running(pid):
    lock = XBOX_DIR / "locks" / f"run-{pid}"
    try:
        return _alive(lock.read_text().strip())
    except OSError:
        return False


def action_uninstall(pid, keep=""):
    g = load_state()["games"].get(pid)
    if not g:
        return error("Unknown game.")
    if _running(pid):
        return error("Quit the game before uninstalling it.")
    users = xbox_prefix.prefix_dir(pid) / "pfx" / "drive_c" / "users"
    if keep == "keep" and users.is_dir():
        dest = XBOX_DIR / "saves" / pid
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(str(users), str(dest))
    root = Path(g["root"])
    if root.is_dir() and (root.name == pid or g.get("imported")):
        shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(xbox_prefix.prefix_dir(pid), ignore_errors=True)
    (LAUNCH_DIR / f"{pid}.sh").unlink(missing_ok=True)
    _drives().forget(STORE, pid)
    with locked_state() as st:
        st["games"].pop(pid, None)
    emit("Success", {"Message": "Uninstalled"})


# ── account actions ──────────────────────────────────────────────────────────

def action_loginstatus():
    if not signed_in():
        return emit("LoginStatus", {"Username": "<not logged in>", "LoggedIn": False})
    view = account_view()
    name = view["profile"].get("gamertag") or "Xbox"
    active = xbox_access.subscription_active(view["profile"])
    emit("LoginStatus", {"Username": f"{name} · {_sub_label(active)}", "LoggedIn": True})


SUB_LABELS = {
    "en": ("Game Pass: active", "Game Pass: inactive"), "fr": ("Game Pass : actif", "Game Pass : inactif"),
    "de": ("Game Pass: aktiv", "Game Pass: inaktiv"), "es": ("Game Pass: activo", "Game Pass: inactivo"),
    "it": ("Game Pass: attivo", "Game Pass: non attivo"), "pt": ("Game Pass: ativo", "Game Pass: inativo"),
    "nl": ("Game Pass: actief", "Game Pass: niet actief"), "pl": ("Game Pass: aktywny", "Game Pass: nieaktywny"),
    "ru": ("Game Pass: активен", "Game Pass: не активен"),
}


def _lang():
    try:
        from ports_i18n import machine_lang_code
        return machine_lang_code()
    except Exception:
        return "en"


def _sub_label(active):
    on, off = SUB_LABELS.get(_lang(), SUB_LABELS["en"])
    return on if active else off


def action_logout():
    try:
        xbox_cli.logout()
    except xbox_cli.CliError:
        pass
    with locked_state() as st:
        st.pop("account", None)
    emit("Success", {"Message": "Logged out"})


def action_getsetting(name, *_):
    value = (load_state().get("settings") or {}).get(name, "")
    emit("Setting", {"name": name, "value": value})


def action_savesetting(name, value="", *_):
    with locked_state() as st:
        st.setdefault("settings", {})[name] = value
    emit("Success", {"Message": "Saved"})


def action_refresh():
    account_view(refresh=True)
    emit("Success", {"Message": "Refreshed"})


ACTIONS = {
    "getgames": lambda a: action_getgames(a[1] if len(a) > 1 else "", a[2] if len(a) > 2 else "false"),
    "getgamedetails": lambda a: action_getgamedetails(a[0]),
    "getjsonimages": lambda a: action_getjsonimages(a[0]),
    "getgamesize": lambda a: action_getgamesize(a[0]),
    "download": lambda a: action_download(a[0]),
    "worker": lambda a: worker(a[0]),
    "prefetch": lambda a: prefetch(),
    "getprogress": lambda a: action_getprogress(a[0]),
    "cancelinstall": lambda a: action_cancelinstall(a[0]),
    "install": lambda a: action_install(a[0], a[1] if len(a) > 1 else ""),
    "getlaunchoptions": lambda a: action_install(a[0]),
    "run": lambda a: sys.exit(action_run(a[0]) or 0),
    "uninstall": lambda a: action_uninstall(a[0], a[1] if len(a) > 1 else ""),
    "loginstatus": lambda a: action_loginstatus(),
    "login": lambda a: emit("Success", {"Message": "Use the Steam browser sign-in."}),
    "logout": lambda a: action_logout(),
    "refresh": lambda a: action_refresh(),
    "getsetting": lambda a: action_getsetting(*(a or [""])),
    "savesetting": lambda a: action_savesetting(*(a or [""])),
}


def main():
    argv = sys.argv[1:]
    if not argv:
        return error("no action")
    handler = ACTIONS.get(argv[0])
    if not handler:
        return error(f"unknown action {argv[0]}")
    handler(argv[1:])


if __name__ == "__main__":
    main()
