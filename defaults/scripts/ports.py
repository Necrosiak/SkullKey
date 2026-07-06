#!/usr/bin/env python3
"""SkullKey Ports extension backend.

Curated catalog of open-source NATIVE PC ports of console classics
(decompilations / recompilations / fan remasters), downloaded from each
project's official GitHub releases — never the game assets themselves: every
port needs files from a game copy YOU own (ROM, disc image, MPQ…), and the
game details explain exactly which file goes where (Desktop Mode required to
copy it).

Three install kinds:
  - "appimage": single AppImage asset, dropped into the port's folder
  - "archive":  zip / tar.* asset, extracted into the port's folder
  - "flatpak":  .flatpak bundle (possibly zipped), installed per-user with
                `flatpak install --user`; the port folder only keeps a marker
                and the Steam shortcut runs `flatpak run <appid>`. Ports may
                set "datadir" when the game files live outside the port folder
                (e.g. GeneralsX reads ~/GeneralsX/Generals) and "args" for
                extra fixed launch arguments.

Modeled on media.py: standalone (no GameSet/sqlite), JSON state, detached
install worker + progress file, Pillow-composed Steam artwork, and a daily
silent auto-update that re-downloads a port when its release tag changes
(user files — ROMs, saves — are left in place; only port files are
overwritten)."""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

try:
    from ports_i18n import desc_for, needs_line, howto_line
except ImportError:
    desc_for = lambda s: ""                       # noqa: E731
    needs_line = lambda p: ""                     # noqa: E731
    howto_line = lambda d: ""                     # noqa: E731

os.environ["PATH"] = os.pathsep.join(
    dict.fromkeys(
        (os.environ.get("PATH", "").split(os.pathsep))
        + ["/usr/bin", "/bin", "/usr/local/bin",
           os.path.expanduser("~/.local/bin")]
    ).keys()
).strip(os.pathsep)

PYEXE = sys.executable or shutil.which("python3") or "/usr/bin/python3"

HOME = Path(os.path.expanduser("~"))
RUNTIME_DIR = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                                  str(HOME / "homebrew/data/SkullKey")))
STATE_FILE = RUNTIME_DIR / "ports_state.json"
ART_DIR = RUNTIME_DIR / "ports_art"
PROGRESS_DIR = RUNTIME_DIR / "ports_progress"
SCRIPTS_DIR = RUNTIME_DIR / "ports_scripts"
PORTS_DIR = HOME / "Games" / "ports"

UA = {"User-Agent": "SkullKey-ports/1.0"}
RAW = "https://raw.githubusercontent.com/{repo}/HEAD/{path}"

# shortname, title, repo, kind, asset regex, exe hint (glob on filename),
# logo url, brand color, needs=(template, game, spec[, exact filename])
PORTS = [
    dict(shortname="dusklight", title="Dusklight (Zelda: Twilight Princess)",
         repo="TwilitRealm/dusklight", kind="appimage",
         asset=r"linux-x86_64\.appimage$", exe="",
         logo=RAW.format(repo="TwilitRealm/dusklight", path="res/icon.png"),
         color="#3f6f4f",
         needs=("pick", "The Legend of Zelda: Twilight Princess",
                "GameCube — .iso/.rvz/.gcz")),
    dict(shortname="soh", title="Ship of Harkinian (Zelda: OoT)",
         repo="HarbourMasters/Shipwright", kind="archive",
         asset=r"linux\.zip$", exe="soh.appimage",
         logo=RAW.format(repo="HarbourMasters/Shipwright",
                         path="soh/macosx/sohIcon.png"),
         color="#2f6fb0",
         needs=("folder", "The Legend of Zelda: Ocarina of Time",
                "N64 — .z64")),
    dict(shortname="2s2h", title="2 Ship 2 Harkinian (Zelda: MM)",
         repo="HarbourMasters/2ship2harkinian", kind="archive",
         asset=r"linux\.zip$", exe="2s2h.appimage",
         logo=RAW.format(repo="HarbourMasters/2ship2harkinian",
                         path="mm/macosx/2s2hIcon.png"),
         color="#6b3fa0",
         needs=("folder", "The Legend of Zelda: Majora's Mask",
                "N64 US — .z64")),
    dict(shortname="zelda64recomp", title="Zelda 64: Recompiled (MM)",
         repo="Zelda64Recomp/Zelda64Recomp", kind="archive",
         asset=r"linux-x64\.zip$", exe="Zelda64Recompiled",
         logo=RAW.format(repo="Zelda64Recomp/Zelda64Recomp",
                         path="icons/512.png"),
         color="#7a5cd6",
         needs=("pick", "The Legend of Zelda: Majora's Mask",
                "N64 US — .z64")),
    dict(shortname="starship", title="Starship (Star Fox 64)",
         repo="HarbourMasters/Starship", kind="archive",
         asset=r"linux\.zip$", exe="",
         logo=RAW.format(repo="HarbourMasters/Starship", path="logo.png"),
         color="#3050c0",
         needs=("folder", "Star Fox 64", "N64 US — .z64")),
    dict(shortname="spaghettikart", title="SpaghettiKart (Mario Kart 64)",
         repo="HarbourMasters/SpaghettiKart", kind="archive",
         asset=r"linux\.zip$", exe="",
         logo=RAW.format(repo="HarbourMasters/SpaghettiKart",
                         path="icon.png"),
         color="#f0a020",
         needs=("folder", "Mario Kart 64", "N64 US — .z64")),
    dict(shortname="sm64coopdx", title="sm64coopdx (Super Mario 64)",
         repo="coop-deluxe/sm64coopdx", kind="archive",
         asset=r"linux\.zip$", exe="sm64coopdx",
         logo=RAW.format(
             repo="coop-deluxe/sm64coopdx",
             path="textures/segment2/custom_coopdx_logo.rgba32.png"),
         color="#e03c3c",
         needs=("named", "Super Mario 64", "N64 US — .z64",
                "baserom.us.z64")),
    dict(shortname="perfect-dark", title="Perfect Dark",
         repo="perfect-dark-pc-port/perfect_dark", kind="archive",
         asset=r"pd-x86_64-linux\.tar\.gz$", exe="pd.x86_64",
         logo="https://github.com/perfect-dark-pc-port.png?size=256",
         color="#1f5c46",
         needs=("named", "Perfect Dark", "N64 NTSC — .z64",
                "pd.ntsc-final.z64")),
    dict(shortname="sonic3air", title="Sonic 3 – Angel Island Revisited",
         repo="Eukaryot/sonic3air", kind="archive",
         asset=r"sonic3air_game\.tar\.gz$", exe="sonic3air_linux",
         logo="https://github.com/Eukaryot.png?size=256",
         color="#1c66d6",
         needs=("pick", "Sonic 3 & Knuckles",
                "Steam/PC — Sonic_Knuckles_wSonic3.bin")),
    dict(shortname="devilutionx", title="DevilutionX (Diablo)",
         repo="diasurgical/devilutionX", kind="appimage",
         asset=r"linux-x86_64\.appimage$", exe="",
         logo=RAW.format(repo="diasurgical/devilutionX",
                         path="Packaging/resources/icon.png"),
         color="#8a1f1f",
         needs=("optional", "Diablo", "CD/GOG", "DIABDAT.MPQ")),
    dict(shortname="opengoal", title="OpenGOAL (Jak & Daxter)",
         repo="open-goal/launcher", kind="appimage",
         asset=r"amd64\.appimage$", exe="",
         logo=RAW.format(repo="open-goal/launcher",
                         path="src-tauri/icons/128x128@2x.png"),
         color="#e0862c",
         needs=("pick", "Jak & Daxter: The Precursor Legacy",
                "PS2 — .iso")),
    dict(shortname="fallout1-ce", title="Fallout Community Edition",
         repo="alexbatalov/fallout1-ce", kind="archive",
         asset=r"linux-x64\.tar\.gz$", exe="fallout-ce",
         logo=RAW.format(repo="alexbatalov/fallout1-ce",
                         path="os/windows/fallout-ce.ico"),
         color="#3fbf3f",
         needs=("files", "Fallout",
                "master.dat + critter.dat + data/ — Steam/GOG")),
    dict(shortname="fallout2-ce", title="Fallout 2 Community Edition",
         repo="alexbatalov/fallout2-ce", kind="archive",
         asset=r"linux-x64\.tar\.gz$", exe="fallout2-ce",
         logo=RAW.format(repo="alexbatalov/fallout2-ce",
                         path="os/windows/fallout2-ce.ico"),
         color="#b8873b",
         needs=("files", "Fallout 2",
                "master.dat + critter.dat + data/ — Steam/GOG")),
    dict(shortname="nxengine-evo", title="Cave Story (NXEngine-evo)",
         repo="nxengine/nxengine-evo", kind="appimage",
         asset=r"linux-x86_64\.appimage$", exe="",
         logo="https://github.com/nxengine.png?size=256",
         color="#4aa3df",
         needs=("free", "", "")),
    dict(shortname="openra-ra", title="OpenRA (Red Alert)",
         repo="OpenRA/OpenRA", kind="appimage",
         asset=r"red-alert-x86_64\.appimage$", exe="",
         logo="https://github.com/OpenRA.png?size=256",
         color="#c03a2b",
         needs=("free", "", "")),
    dict(shortname="corsixth", title="CorsixTH (Theme Hospital)",
         repo="CorsixTH/CorsixTH", kind="appimage",
         asset=r"x86_64\.appimage$", exe="",
         logo="https://github.com/CorsixTH.png?size=256",
         color="#2aa198",
         needs=("pick", "Theme Hospital", "GOG/EA")),
    dict(shortname="dhewm3", title="dhewm3 (Doom 3)",
         repo="dhewm/dhewm3", kind="archive",
         asset=r"^dhewm3-[\d.]+_linux_amd64\.tar\.gz$", exe="dhewm3",
         logo="https://github.com/dhewm.png?size=256",
         color="#8a2b1f",
         needs=("files", "Doom 3", "*.pk4 → base/ — Steam/GOG")),
    dict(shortname="vkquake", title="vkQuake (Quake)",
         repo="Novum/vkQuake", kind="archive",
         asset=r"linux_x64\.tar\.gz$", exe="vkquake",
         logo=RAW.format(repo="Novum/vkQuake", path="Misc/vkQuake_256.png"),
         color="#7a5a3a",
         needs=("files", "Quake", "id1/ — pak0.pak, shareware OK")),
    dict(shortname="redriver2", title="REDRIVER2 (Driver 2)",
         repo="OpenDriver2/REDRIVER2", kind="archive",
         asset=r"^redriver2_linux_release\.tar\.gz$", exe="redriver2",
         logo="https://github.com/OpenDriver2.png?size=256",
         color="#cfae2c",
         needs=("files", "Driver 2", "CD PS1 — Driver 2")),
    dict(shortname="daggerfall-unity", title="Daggerfall Unity",
         repo="Interkarma/daggerfall-unity", kind="archive",
         asset=r"dfu_linux_64bit.*\.zip$", exe="daggerfallunity.x86_64",
         logo="https://github.com/Interkarma.png?size=256",
         color="#7d6ca8",
         needs=("pick", "The Elder Scrolls II: Daggerfall",
                "freeware")),
    dict(shortname="fheroes2", title="fheroes2 (Heroes of M&M II)",
         repo="ihhub/fheroes2", kind="archive",
         asset=r"ubuntu_x86-64.*\.zip$", exe="fheroes2",
         logo=RAW.format(repo="ihhub/fheroes2",
                         path="src/resources/fheroes2.png"),
         color="#3f6fd0",
         needs=("files", "Heroes of Might and Magic II",
                "DATA/ + MAPS/ — GOG, demo OK")),
    dict(shortname="trx", title="TRX (Tomb Raider I & II)",
         repo="LostArtefacts/TRX", kind="archive",
         asset=r"^trx-.*-linux\.zip$", exe="tr1x",
         logo="https://github.com/LostArtefacts.png?size=256",
         color="#4c7d6d",
         needs=("files", "Tomb Raider I & II", "Steam/GOG")),
    # ── wave 2 (2026-07-06) ──────────────────────────────────────────────────
    dict(shortname="generalsx", title="GeneralsX (C&C Generals)",
         repo="fbraz3/GeneralsX", kind="flatpak",
         asset=r"^GeneralsX-linux\.flatpak$", exe="",
         appid="com.fbraz3.GeneralsX",
         datadir=str(HOME / "GeneralsX" / "Generals"),
         logo=RAW.format(repo="fbraz3/GeneralsX",
                         path="flatpak/generalsx_icon_512.png"),
         color="#b8860b",
         needs=("files", "Command & Conquer Generals", "Steam/EA")),
    dict(shortname="generalsx-zh", title="GeneralsX (C&C Zero Hour)",
         repo="fbraz3/GeneralsX", kind="flatpak",
         asset=r"^GeneralsXZH-linux\.flatpak$", exe="",
         appid="com.fbraz3.GeneralsXZH",
         datadir=str(HOME / "GeneralsX" / "GeneralsZH"),
         logo=RAW.format(repo="fbraz3/GeneralsX",
                         path="assets/generalsx-zh_icon.png"),
         color="#c23b22",
         needs=("files", "C&C Generals Zero Hour", "Steam/EA")),
    dict(shortname="openmw", title="OpenMW (Morrowind)",
         repo="OpenMW/openmw", kind="archive",
         asset=r"Linux-64Bit\.tar\.gz$", exe="openmw-launcher",
         logo=RAW.format(repo="OpenMW/openmw",
                         path="files/launcher/images/openmw.png"),
         color="#8b7a4d",
         needs=("pick", "The Elder Scrolls III: Morrowind",
                "Steam/GOG — Morrowind.esm")),
    dict(shortname="openrct2", title="OpenRCT2 (RollerCoaster Tycoon 2)",
         repo="OpenRCT2/OpenRCT2", kind="appimage",
         asset=r"linux-x86_64\.AppImage$", exe="",
         logo=RAW.format(repo="OpenRCT2/OpenRCT2",
                         path="resources/logo/icon_x128.png"),
         color="#e07020",
         needs=("pick", "RollerCoaster Tycoon 2", "GOG/Steam")),
    dict(shortname="augustus", title="Augustus (Caesar III)",
         repo="Keriew/augustus", kind="appimage",
         asset=r"linux\.AppImage$", exe="",
         logo=RAW.format(repo="Keriew/augustus", path="res/augustus_512.png"),
         color="#a03028",
         needs=("pick", "Caesar III", "GOG/Steam")),
    dict(shortname="vcmi", title="VCMI (Heroes of M&M III)",
         repo="vcmi/vcmi", kind="appimage",
         asset=r"Linux-x64\.AppImage$", exe="",
         logo=RAW.format(repo="vcmi/vcmi", path="clientapp/icons/vcmi.ico"),
         color="#6a3fa0",
         needs=("pick", "Heroes of Might and Magic III", "GOG — Complete")),
    dict(shortname="openjk", title="OpenJK (Jedi Academy)",
         repo="JACoders/OpenJK", kind="archive",
         asset=r"^OpenJK-linux-x86_64\.tar\.gz$", exe="openjk_sp.x86_64",
         logo=RAW.format(repo="JACoders/OpenJK",
                         path="shared/icons/PNG/mp256.png"),
         color="#39b54a",
         needs=("files", "Star Wars Jedi Knight: Jedi Academy",
                "base/*.pk3 — Steam/GOG")),
    dict(shortname="iortcw", title="iortcw (Return to Castle Wolfenstein)",
         repo="iortcw/iortcw", kind="archive",
         asset=r"linux-x86_64\.zip$", exe="iowolfsp.x86_64",
         logo="https://github.com/iortcw.png?size=256",
         color="#7a1f1f",
         needs=("files", "Return to Castle Wolfenstein",
                "main/ — Steam/GOG")),
    dict(shortname="dethrace", title="Dethrace (Carmageddon)",
         repo="dethrace-labs/dethrace", kind="archive",
         asset=r"linux-x64\.tar\.gz$", exe="dethrace",
         logo=RAW.format(repo="dethrace-labs/dethrace",
                         path="packaging/icon_source.png"),
         color="#c02020",
         needs=("files", "Carmageddon", "DATA/ — GOG")),
    dict(shortname="openmohaa", title="OpenMoHAA (Medal of Honor: AA)",
         repo="openmoh/openmohaa", kind="archive",
         asset=r"linux-amd64\.zip$", exe="",
         logo="https://github.com/openmoh.png?size=256",
         color="#4f6f3f",
         needs=("files", "Medal of Honor: Allied Assault",
                "main/ — GOG")),
    dict(shortname="ja2", title="JA2 Stracciatella (Jagged Alliance 2)",
         repo="ja2-stracciatella/ja2-stracciatella", kind="appimage",
         asset=r"x86-64\.AppImage$", exe="",
         logo=RAW.format(repo="ja2-stracciatella/ja2-stracciatella",
                         path="assets/icons/logo.png"),
         color="#8a7a2f",
         needs=("pick", "Jagged Alliance 2", "Steam/GOG")),
    dict(shortname="helion", title="Helion (Doom)",
         repo="Helion-Engine/Helion", kind="appimage",
         asset=r"^Helion\.AppImage$", exe="",
         logo="https://github.com/Helion-Engine.png?size=256",
         color="#a02818",
         needs=("files", "Doom / Doom II",
                "*.wad — doom1.wad shareware OK")),
    dict(shortname="openomf", title="OpenOMF (One Must Fall 2097)",
         repo="omf2097/openomf", kind="archive",
         asset=r"linux_amd64\.tar\.gz$", exe="openomf",
         logo=RAW.format(repo="omf2097/openomf",
                         path="resources/icons/openomf-128x128.png"),
         color="#c8442c",
         needs=("free", "", "")),
    dict(shortname="opensupaplex", title="OpenSupaplex",
         repo="sergiou87/open-supaplex", kind="archive",
         asset=r"^OpenSupaplex-linux\.zip$", exe="",
         logo=RAW.format(
             repo="sergiou87/open-supaplex",
             path="macos/OpenSupaplex/Assets.xcassets/AppIcon.appiconset/"
                  "murphy-1024.png"),
         color="#2a9d8f",
         needs=("free", "", "")),
    dict(shortname="descent3", title="Descent 3",
         repo="kevinbentley/Descent3", kind="archive",
         asset=r"^Descent3_Release_Linux-x64\.zip$", exe="Descent3",
         logo="https://github.com/kevinbentley.png?size=256",
         color="#606880",
         needs=("files", "Descent 3", "d3.hog + *.hog — GOG/Steam")),
    dict(shortname="opengothic", title="OpenGothic (Gothic II)",
         repo="Try/OpenGothic", kind="archive",
         asset=r"linux_x64\.zip$", exe="Gothic2Notr",
         args='-g "Gothic2"',
         logo=RAW.format(repo="Try/OpenGothic", path="icon.ico"),
         color="#7a5a2f",
         needs=("files", "Gothic II: Night of the Raven",
                "Gothic2/ — Steam/GOG")),
    dict(shortname="unleashedrecomp", title="Unleashed Recompiled (Sonic)",
         repo="hedge-dev/UnleashedRecomp", kind="flatpak",
         asset=r"^UnleashedRecomp-Flatpak\.zip$", exe="",
         appid="io.github.hedge_dev.unleashedrecomp",
         logo="https://github.com/hedge-dev.png?size=256",
         color="#2050c8",
         needs=("pick", "Sonic Unleashed", "Xbox 360 — dump + update")),
    # ── wave 3 (2026-07-06) ──────────────────────────────────────────────────
    dict(shortname="opentesarena", title="OpenTESArena (Elder Scrolls: Arena)",
         repo="afritz1/OpenTESArena", kind="archive",
         asset=r"linux_x86-64\.tar\.gz$", exe="opentesarena",
         logo="https://github.com/afritz1.png?size=256",
         color="#7a5a3a",
         needs=("files", "The Elder Scrolls: Arena", "freeware — full game data")),
    dict(shortname="bstone", title="BStone (Blake Stone)",
         repo="bibendovsky/bstone", kind="archive",
         asset=r"Linux\.zip$", exe="bstone",
         logo="https://github.com/bibendovsky.png?size=256",
         color="#8a3320",
         needs=("files", "Blake Stone: Aliens of Gold",
                "shareware OK / GOG — *.bs6/*.vsi")),
    dict(shortname="arx-libertatis", title="Arx Libertatis (Arx Fatalis)",
         repo="arx/ArxLibertatis", kind="archive",
         asset=r"^arx-libertatis-[\d.]+-linux\.tar\.xz$", exe="arx",
         logo="https://github.com/arx.png?size=256",
         color="#3a5a7a",
         needs=("files", "Arx Fatalis", "GOG/Steam — data/*.pak")),
    dict(shortname="openjazz", title="OpenJazz (Jazz Jackrabbit)",
         repo="AlisterT/openjazz", kind="archive",
         asset=r"linux-glibc.*x86_64\.zip$", exe="OpenJazz",
         logo="https://github.com/AlisterT.png?size=256",
         color="#2f9e44",
         needs=("files", "Jazz Jackrabbit", "shareware OK — game data")),
    dict(shortname="openbor", title="OpenBOR (Beats of Rage engine)",
         repo="DCurrent/openbor", kind="appimage",
         asset=r"Linux-x64.*\.AppImage$", exe="",
         logo="https://github.com/DCurrent.png?size=256",
         color="#c0392b",
         needs=("free", "", "")),
    dict(shortname="openra-td", title="OpenRA: Tiberian Dawn (C&C)",
         repo="OpenRA/OpenRA", kind="appimage",
         asset=r"Tiberian-Dawn-x86_64\.AppImage$", exe="",
         logo="https://github.com/OpenRA.png?size=256",
         color="#c8963a",
         needs=("free", "", "")),
    dict(shortname="openra-d2k", title="OpenRA: Dune 2000",
         repo="OpenRA/OpenRA", kind="appimage",
         asset=r"Dune-2000-x86_64\.AppImage$", exe="",
         logo="https://github.com/OpenRA.png?size=256",
         color="#b8860b",
         needs=("free", "", "")),
    dict(shortname="warzone2100", title="Warzone 2100",
         repo="Warzone2100/warzone2100", kind="flatpak",
         asset=r"^warzone2100_linux_x86_64\.flatpak$", exe="",
         appid="net.wz2100.wz2100",
         logo="https://github.com/Warzone2100.png?size=256",
         color="#5a7a3a",
         needs=("free", "", "")),
]

APPS = {p["shortname"]: p for p in PORTS}


# ── state ────────────────────────────────────────────────────────────────────

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"apps": {}, "releases": {}, "last_check": 0}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1))


def app_state(state, shortname):
    return state["apps"].setdefault(
        shortname, {"steamClientID": "", "installed": False, "tag": ""})


def port_dir(port):
    return PORTS_DIR / port["shortname"]


# ── GitHub releases (cached: shared by size / install / autoupdate) ─────────

def http_json(url, timeout=15):
    req = urllib.request.Request(
        url, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def release_info(state, port, max_age=6 * 3600):
    """{tag, url, size, name} of the port's latest matching release asset.
    Cached in state (state must be saved by the caller when it matters).
    The tag embeds the asset's updated_at date so rolling releases (e.g.
    Perfect Dark's 'ci-dev-build') still trigger updates."""
    cache = state.setdefault("releases", {}).get(port["shortname"])
    if cache and time.time() - cache.get("ts", 0) < max_age:
        return cache
    try:
        rels = [http_json(
            f"https://api.github.com/repos/{port['repo']}/releases/latest")]
    except Exception:
        # repos that only publish pre-releases (e.g. OpenGothic) 404 on
        # /latest — fall back to the newest entries of the release list
        rels = http_json(
            f"https://api.github.com/repos/{port['repo']}/releases?per_page=5")
    rx = re.compile(port["asset"], re.IGNORECASE)
    info = None
    for rel, a in ((rel, a) for rel in rels for a in rel.get("assets", [])):
        if rx.search(a.get("name", "")):
            info = {"tag": f"{rel.get('tag_name', '')}"
                           f"@{(a.get('updated_at') or '')[:10]}",
                    "url": a.get("browser_download_url", ""),
                    "size": int(a.get("size", 0)),
                    "name": a.get("name", ""),
                    "ts": int(time.time())}
            break
    if not info:
        raise RuntimeError(f"no Linux asset in latest {port['repo']} release")
    state["releases"][port["shortname"]] = info
    return info


# ── install/uninstall ────────────────────────────────────────────────────────

def write_progress(shortname, pct, desc, error=None, pid=None):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"Percentage": pct, "Description": desc, "Error": error}
    if pid:
        data["pid"] = pid
    (PROGRESS_DIR / f"{shortname}.json").write_text(json.dumps(data))


def download_file(url, dest, shortname, lo, hi, desc):
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
                    write_progress(shortname, lo + (hi - lo) * done / total,
                                   desc, pid=os.getpid())
        tmp.rename(dest)


def _extract(archive, dest, shortname, name):
    write_progress(shortname, 72, f"Extracting {name}…", pid=os.getpid())
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="data")


def _mark_executables(root):
    """zipfile drops the exec bit: restore it on AppImages and ELF binaries."""
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        low = p.name.lower()
        try:
            if low.endswith(".appimage") or low.endswith(".sh"):
                p.chmod(p.stat().st_mode | 0o755 & 0o777 | 0o100)
                continue
            with open(p, "rb") as f:
                if f.read(4) == b"\x7fELF":
                    p.chmod(p.stat().st_mode | 0o111)
        except OSError:
            pass


def find_exe(port):
    """Locate the port's main executable inside its folder: exact hint first,
    then the biggest AppImage, then the biggest ELF (excluding .so)."""
    root = port_dir(port)
    hint = (port.get("exe") or "").lower()
    appimages, elfs = [], []
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        low = p.name.lower()
        if hint and low == hint:
            return p
        if low.endswith(".appimage"):
            appimages.append(p)
        elif "." not in p.name or low.endswith((".x86_64", ".bin")):
            try:
                with open(p, "rb") as f:
                    if f.read(4) == b"\x7fELF":
                        elfs.append(p)
            except OSError:
                pass
    for group in (appimages, elfs):
        if group:
            return max(group, key=lambda p: p.stat().st_size)
    return None


def write_launch_script(port, exe):
    """Launcher for the Steam shortcut: run from the port's folder so ROMs
    dropped next to the binary are found (flatpak ports run by app id)."""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / f"{port['shortname']}.sh"
    args = (" " + port["args"]) if port.get("args") else ""
    if port["kind"] == "flatpak":
        path.write_text("#!/usr/bin/env bash\n"
                        f'exec flatpak run {port["appid"]}{args} "$@"\n')
    else:
        path.write_text("#!/usr/bin/env bash\n"
                        f'cd "{port_dir(port)}"\n'
                        f'exec "{exe}"{args} "$@"\n')
    os.chmod(path, 0o755)
    return path


def _flatpak_install_bundle(bundle):
    """Install/upgrade a .flatpak bundle for the current user. The flathub
    user remote is added first so the bundle's runtime dependency can be
    pulled (a bundle carries the app, not its runtime)."""
    subprocess.run(
        ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
         "https://dl.flathub.org/repo/flathub.flatpakrepo"],
        capture_output=True, timeout=120)
    r = subprocess.run(
        ["flatpak", "install", "--user", "--noninteractive", "--reinstall",
         "-y", str(bundle)],
        capture_output=True, text=True, timeout=7200)
    if r.returncode:
        tail = ((r.stderr or r.stdout or "").strip().splitlines() or ["?"])[-1]
        raise RuntimeError(f"flatpak install failed: {tail}")


def worker_install(shortname):
    port = APPS[shortname]
    state = load_state()
    try:
        write_progress(shortname, 2, f"Checking {port['title']} release…",
                       pid=os.getpid())
        info = release_info(state, port)
        pdir = port_dir(port)
        pdir.mkdir(parents=True, exist_ok=True)
        if port["kind"] == "appimage":
            dest = pdir / f"{shortname}.AppImage"
            download_file(info["url"], dest, shortname, 5, 95,
                          f"Downloading {port['title']} {info['tag']}…")
            os.chmod(dest, 0o755)
        elif port["kind"] == "flatpak":
            bundle = pdir / f"_dl_{info['name']}"
            download_file(info["url"], bundle, shortname, 5, 70,
                          f"Downloading {port['title']} {info['tag']}…")
            if zipfile.is_zipfile(bundle):
                _extract(bundle, pdir, shortname, port["title"])
                bundle.unlink(missing_ok=True)
                bundle = next(iter(sorted(pdir.rglob("*.flatpak"))), None)
                if not bundle:
                    raise RuntimeError("no .flatpak bundle in the archive")
            write_progress(shortname, 80,
                           "Installing Flatpak (runtime may download on "
                           "first install)…", pid=os.getpid())
            _flatpak_install_bundle(bundle)
            for f in list(pdir.rglob("*.flatpak")):
                f.unlink(missing_ok=True)
            (pdir / "flatpak-app-id.txt").write_text(port["appid"] + "\n")
        else:
            archive = pdir / f"_dl_{info['name']}"
            download_file(info["url"], archive, shortname, 5, 70,
                          f"Downloading {port['title']} {info['tag']}…")
            _extract(archive, pdir, shortname, port["title"])
            archive.unlink(missing_ok=True)
            _mark_executables(pdir)
        if port["kind"] == "flatpak":
            exe = port["appid"]
        else:
            exe = find_exe(port)
            if not exe:
                raise RuntimeError("no executable found in the downloaded "
                                   "release — please report this port")
        write_launch_script(port, exe)
        st = app_state(state, shortname)
        st["installed"] = True
        st["tag"] = info["tag"]
        st["exe"] = str(exe)
        save_state(state)
        write_progress(shortname, 100, "Done")
    except Exception as e:
        write_progress(shortname, 0, "Installation failed", error=str(e))


def worker_autoupdate():
    """Silent daily maintenance: re-download a port when its release tag (or
    rolling asset date) changed. User files in the folder are untouched."""
    state = load_state()
    for shortname, st in list(state.get("apps", {}).items()):
        port = APPS.get(shortname)
        if not port or not st.get("installed"):
            continue
        try:
            info = release_info(state, port, max_age=0)
            if info["tag"] and info["tag"] != st.get("tag"):
                worker_install(shortname)
                state = load_state()      # worker_install saved its own state
        except Exception as e:
            print(f"ports autoupdate {shortname}: {e}", file=sys.stderr)
    state["last_check"] = int(time.time())
    save_state(state)


# ── artwork (Pillow, media.py pattern) ───────────────────────────────────────

def urlopen_retry(url, timeout=20, tries=4):
    import urllib.error
    delay = 1.5
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            if attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise last


def _text_logo(port):
    """Fallback tile when the logo URL dies: the port's title rendered on a
    transparent background, so artwork never comes out blank."""
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for path in ("/usr/share/fonts/open-sans/OpenSans-Bold.ttf",
                 "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(path, 56)
            break
        except OSError:
            continue
    img = Image.new("RGBA", (640, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    title = port["title"].split(" (")[0]
    d.text((320, 100), title, fill=(255, 255, 255, 255), anchor="mm",
           font=font or ImageFont.load_default())
    return img


def fetch_logo(port):
    ART_DIR.mkdir(parents=True, exist_ok=True)
    cache = ART_DIR / f"{port['shortname']}_logo.png"
    if not cache.exists():
        from PIL import Image
        try:
            raw = urlopen_retry(port["logo"], timeout=20)
            img = Image.open(BytesIO(raw)).convert("RGBA")
        except Exception as e:
            print(f"logo fetch failed for {port['shortname']}: {e}",
                  file=sys.stderr)
            img = _text_logo(port)
        img.save(cache)
    return cache


def compose(port, w, h):
    from PIL import Image
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out = ART_DIR / f"{port['shortname']}_{w}x{h}.png"
    if out.exists():
        return out
    c = port["color"].lstrip("#")
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
    logo = Image.open(fetch_logo(port)).convert("RGBA")
    max_w, max_h = int(w * 0.68), int(h * 0.42)
    scale = min(max_w / logo.width, max_h / logo.height)
    logo = logo.resize((max(1, int(logo.width * scale)),
                        max(1, int(logo.height * scale))), Image.LANCZOS)
    img.paste(logo, ((w - logo.width) // 2, (h - logo.height) // 2), logo)
    img.save(out)
    return out


def b64_file(path):
    import base64
    return base64.b64encode(Path(path).read_bytes()).decode()


# ── actions ──────────────────────────────────────────────────────────────────

def action_getgames(cat="ports", filter_str="", installed="false"):
    state = load_state()
    games = []
    for i, port in enumerate(PORTS, start=1):
        if filter_str and filter_str.lower() not in port["title"].lower():
            continue
        st = state["apps"].get(port["shortname"], {})
        if installed.lower() == "true" and not st.get("steamClientID"):
            continue
        games.append({
            "ID": i,
            "Name": port["title"],
            "Images": [port["logo"]],
            "ShortName": port["shortname"],
            "SteamClientID": st.get("steamClientID", ""),
        })
    print(json.dumps({"Type": "GameGrid",
                      "Content": {"Games": games, "NeedsLogin": "false"}}))


def action_getgamedetails(shortname):
    port = APPS[shortname]
    state = load_state()
    st = state["apps"].get(shortname, {})
    desc = desc_for(shortname)
    needs = needs_line(port)
    if needs:
        desc += f"<br><br>{needs}"
        if port["needs"][0] not in ("pick", "free"):
            desc += f"<br>{howto_line(port.get('datadir') or str(port_dir(port)))}"
    desc += (f"<br><br><i>Source: github.com/{port['repo']}"
             + (f" — build {st.get('tag')}" if st.get("tag") else "") + "</i>")
    print(json.dumps({"Type": "GameDetails", "Content": {
        "Name": port["title"],
        "Description": desc,
        "ApplicationPath": "", "ManualPath": "", "RootFolder": "",
        "DatabaseID": shortname, "ConfigurationPath": "",
        "Images": [port["logo"]],
        "ShortName": shortname,
        "SteamClientID": st.get("steamClientID", ""),
        "HasDosConfig": False, "HasBatFiles": False,
        "Editors": [],
    }}))


def action_getgamesize(shortname):
    size = ""
    try:
        state = load_state()
        info = release_info(state, APPS[shortname])
        save_state(state)
        mb = info["size"] / (1 << 20)
        size = f"Download Size: {mb:.1f} MB"
    except Exception:
        pass
    print(json.dumps({"Type": "GameSize", "Content": {"Size": size}}))


def action_getjsonimages(shortname):
    port = APPS[shortname]
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    try:
        content["Grid"] = b64_file(compose(port, 600, 900))
        content["GridH"] = b64_file(compose(port, 920, 430))
        content["Hero"] = b64_file(compose(port, 1920, 620))
        content["Logo"] = b64_file(fetch_logo(port))
    except Exception as e:
        print(f"artwork failed: {e}", file=sys.stderr)
    print(json.dumps({"Type": "Images", "Content": content}))


def action_download(shortname):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    write_progress(shortname, 0, "Starting…")
    subprocess.Popen([PYEXE, os.path.abspath(__file__), "worker", shortname],
                     start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env=os.environ.copy())
    print(json.dumps({"Type": "Progress",
                      "Content": {"Message": "Installing"}}))


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
    port = APPS[shortname]
    state = load_state()
    st = app_state(state, shortname)
    if steam_client_id:
        st["steamClientID"] = str(steam_client_id)
    save_state(state)
    exe = st.get("exe") or (find_exe(port) or "")
    if not exe:
        print(json.dumps({"Type": "Error", "Content": {
            "Message": f"{port['title']} is not installed yet."}}))
        return
    script = write_launch_script(port, exe)
    print(json.dumps({"Type": "LaunchOptions", "Content": {
        "Exe": str(script),
        "Options": "",
        "WorkingDir": str(port_dir(port)),
        "Compatibility": False,           # native Linux builds
        "Name": port["title"],
    }}))


def action_uninstall(shortname):
    port = APPS[shortname]
    state = load_state()
    pdir = port_dir(port)
    if port["kind"] == "flatpak" and port.get("appid"):
        subprocess.run(["flatpak", "uninstall", "--user", "-y", port["appid"]],
                       capture_output=True, timeout=600)
    # safety: only ever delete inside our own ports root. NB: this removes the
    # whole folder, including ROMs the user dropped in it (documented choice).
    if pdir.is_dir() and str(pdir.resolve()).startswith(
            str(PORTS_DIR.resolve()) + os.sep):
        shutil.rmtree(pdir, ignore_errors=True)
    state["apps"].pop(shortname, None)
    save_state(state)
    try:
        (SCRIPTS_DIR / f"{shortname}.sh").unlink()
    except Exception:
        pass
    print(json.dumps({"Type": "Success",
                      "Content": {"Message": "Uninstalled"}}))


def action_autoupdate():
    worker_autoupdate()
    print(json.dumps({"Type": "Success", "Content": {"Message": "done"}}))


def main():
    argv = sys.argv[1:]
    if not argv:
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": "no action"}}))
        return
    action, args = argv[0], argv[1:]
    if action == "getgames":
        action_getgames(args[0] if args else "ports",
                        args[1] if len(args) > 1 else "",
                        args[2] if len(args) > 2 else "false")
    elif action == "getgamedetails":
        action_getgamedetails(args[0])
    elif action == "getgamesize":
        action_getgamesize(args[0])
    elif action == "getjsonimages":
        action_getjsonimages(args[0])
    elif action == "download":
        action_download(args[0])
    elif action == "worker":
        worker_install(args[0])
    elif action == "autoupdate":
        action_autoupdate()
    elif action == "getprogress":
        action_getprogress(args[0])
    elif action == "cancelinstall":
        action_cancelinstall(args[0])
    elif action == "install":
        action_install(args[0], args[1] if len(args) > 1 else "")
    elif action == "uninstall":
        action_uninstall(args[0])
    else:
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": f"unknown action {action}"}}))


if __name__ == "__main__":
    main()
