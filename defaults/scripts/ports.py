#!/usr/bin/env python3
"""SkullKey Ports extension backend.

Curated catalog of open-source NATIVE PC ports of console classics
(decompilations / recompilations / fan remasters), downloaded from each
project's official GitHub releases — never the game assets themselves: every
port needs files from a game copy YOU own (ROM, disc image, MPQ…), and the
game details explain exactly which file goes where (Desktop Mode required to
copy it).

Install kinds:
  - "appimage": single AppImage asset, dropped into the port's folder
  - "archive":  zip / tar.* asset, extracted into the port's folder
  - "flatpak":  .flatpak bundle (possibly zipped), installed per-user with
                `flatpak install --user`; the port folder only keeps a marker
                and the Steam shortcut runs `flatpak run <appid>`. Ports may
                set "datadir" when the game files live outside the port folder
                (e.g. GeneralsX reads ~/GeneralsX/Generals) and "args" for
                extra fixed launch arguments.
  - "winarchive": Windows-only build (zip), extracted like "archive"; the
                Steam shortcut points at the .exe with Proton enabled
                ("winargs" = launch arguments, {dir} = the port folder).
                Recomps that need a disc image may set "iso_import": the user
                drops the .iso into <port>/<subdir>/ and SkullKey extracts the
                listed root entries from it (scripts/xiso_extract.py).
  - "ptsetup": official Linux setup executable, which imports the player's
               own P.T. fake PKG and installs the game in the port folder.

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
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

try:
    from ports_i18n import update_line, desc_for, needs_line, howto_line, iso_status
except ImportError:
    iso_status = lambda k: k                      # noqa: E731
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
# ⚖️ Légalité — règle du catalogue. Chaque entrée télécharge UNIQUEMENT le
# moteur publié par le projet (sa release GitHub officielle). Aucun contenu de
# jeu n'est fourni ni téléchargé : l'utilisateur doit utiliser une copie qu'il
# possède et qu'il a dumpée lui-même (ROM de sa cartouche, image de SON disque,
# fichiers de SA version achetée). Ne jamais ajouter ici de lien, de miroir ou
# d'aide vers une source de jeux : SkullKey n'encourage pas le téléchargement
# illégal, et les projets recensés l'interdisent eux-mêmes.
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
    dict(shortname="fs2open", title="Freespace 2 (FSO)",
         repo="scp-fs2open/fs2open.github.com", kind="archive",
         asset=r"builds-Linux-x86_64\.tar\.gz$",
         exe="fs2_open_*_x64_sse2.appimage",
         logo="https://github.com/scp-fs2open.png?size=256",
         color="#2f4f8f",
         needs=("files", "Freespace 2",
                "root_fs2.vp + *.vp — GOG/Steam")),
    dict(shortname="oldunreal-ut", title="Unreal Tournament (OldUnreal)",
         repo="OldUnreal/UnrealTournamentPatches", kind="archive",
         asset=r"Linux-amd64\.tar\.bz2$", exe="ut-bin",
         logo="https://github.com/OldUnreal.png?size=256",
         color="#b03030",
         needs=("files", "Unreal Tournament (1999)",
                "Maps/ + Music/ + Sounds/ + Textures/ — GOG/Steam")),
    dict(shortname="isle", title="LEGO Island (isle-portable)",
         repo="isledecomp/isle-portable", kind="appimage",
         asset=r"x86_64\.AppImage$", exe="",
         logo="https://github.com/isledecomp.png?size=256",
         color="#c4281c",
         needs=("files", "LEGO Island (1997)",
                "LEGO/ — CD-ROM/installation")),
    dict(shortname="librelancer", title="Librelancer (Freelancer)",
         repo="Librelancer/Librelancer", kind="archive",
         asset=r"^librelancer-[0-9][^ ]*-ubuntu-amd64\.tar\.gz$",
         exe="lancer",
         logo="https://github.com/Librelancer.png?size=256",
         color="#c08030",
         needs=("files", "Freelancer",
                "DATA/ + EXE/ — installation/CD")),
    dict(shortname="openenroth", title="OpenEnroth (Might & Magic VI–VIII)",
         repo="OpenEnroth/OpenEnroth", kind="flatpak",
         appid="io.github.openenroth.openenroth",
         asset=r"^OpenEnroth_nightly_Linux_x86_64_RelWithDebInfo\.flatpak$",
         exe="", datadir=str(HOME / ".var/app/io.github.openenroth.openenroth/data/mm7/data"),
         logo="https://github.com/OpenEnroth.png?size=256",
         color="#8f6f2f",
         needs=("files", "Might and Magic VI–VIII",
                "ANIMS/ + DATA/ + SOUNDS/ — GOG")),
    # ── wave 4 (2026-10-07) : recomps récents ───────────────────────────────
    dict(shortname="banjorecomp", title="Banjo-Kazooie: Recompiled",
         repo="BanjoRecomp/BanjoRecomp", kind="archive",
         asset=r"Linux-X64\.tar\.gz$", exe="BanjoRecompiled",
         logo=RAW.format(repo="BanjoRecomp/BanjoRecomp", path="icons/app.png"),
         color="#c8901e",
         needs=("pick", "Banjo-Kazooie", "N64 US 1.0 — .z64")),
    dict(shortname="goemon64recomp", title="Goemon 64: Recompiled",
         repo="klorfmorf/Goemon64Recomp", kind="archive",
         asset=r"Linux-X64-Release\.zip$", exe="Goemon64Recompiled",
         logo=RAW.format(repo="klorfmorf/Goemon64Recomp", path="icons/512.png"),
         color="#3a78c8",
         needs=("pick", "Mystical Ninja Starring Goemon", "N64 US — .z64")),
    dict(shortname="harvestmoon64recomp", title="Harvest Moon 64: Recompiled",
         repo="HarvestMoon64Recomp/HarvestMoon64Recomp", kind="archive",
         asset=r"Linux-X64\.zip$", exe="HarvestMoon64Recompiled",
         logo=RAW.format(repo="HarvestMoon64Recomp/HarvestMoon64Recomp", path="icons/app.png"),
         color="#5aa040",
         needs=("pick", "Harvest Moon 64", "N64 US — .z64")),
    dict(shortname="lostodysseyrecomp", title="Lost Odyssey Recomp",
         repo="freefrank/LostOdysseyRecomp", kind="appimage",
         asset=r"linux-x64-v[\d.]+\.AppImage$", exe="",
         logo=RAW.format(repo="freefrank/LostOdysseyRecomp", path="assets/lost-odyssey-recomp.png"),
         color="#4a5a8a",
         needs=("pick", "Lost Odyssey", "Xbox 360 — your own discs")),
    dict(shortname="simpsonsgamerecomp", title="The Simpsons Game Recompiled",
         repo="YesterMester/TheSimpsonsGameRecomp", kind="archive",
         asset=r"Linux-x64\.tar\.gz$", exe="Play.sh",
         logo="",  # pas d icône projet : tuile titre (_text_logo),
         color="#f0c020",
         needs=("pick", "The Simpsons Game", "Xbox 360 USA — .iso")),
    dict(shortname="gen1recomp", title="Gen1Recomp (Pokémon Red/Blue/Yellow)",
         repo="bryanthaboi/gen1recomp", kind="appimage",
         asset=r"linux-x86_64\.AppImage$", exe="",
         logo=RAW.format(repo="bryanthaboi/gen1recomp", path="assets/logo/gen1recomp_cover.png"),
         color="#d03030",
         needs=("pick", "Pokémon Red / Blue / Yellow", "Game Boy — .gb")),
    # Recomps uniquement Windows, lancés sous Proton (testé 07/10 : Fable 2
    # tourne sous Proton Experimental, rendu D3D12 via vkd3d-proton).
    dict(shortname="fable2recomp", title="Fable II Recompiled",
         repo="himdo/Fable-2-Recomp", kind="winarchive",
         asset=r"windows\.zip$", exe="fable_2.exe",
         winargs="--game_data_root Z:{dir}/game",
         iso_import=dict(subdir="game", files=("default.xex", "data")),
         logo=RAW.format(repo="himdo/Fable-2-Recomp", path="assets/app-icon.png"),
         color="#8a5a2a",
         needs=("iso", "Fable II — Game of the Year", "Xbox 360 USA/Europe or German GOTY — .iso")),
    dict(shortname="ng2recomp", title="Ninja's Dawn (Ninja Gaiden II)",
         repo="TheSaltTrader/Ninja-s-Dawn---A-Ninja-Gaiden-2-Recompilation-Project",
         kind="winarchive", asset=r"win-amd64\.zip$", exe="ng2.exe",
         logo=RAW.format(repo="TheSaltTrader/Ninja-s-Dawn---A-Ninja-Gaiden-2-Recompilation-Project", path="resources/ng2_256.png"),
         color="#a02020",
         needs=("pick", "Ninja Gaiden II", "Xbox 360 — .iso or extracted folder")),
    dict(shortname="dk64recomp", title="Donkey Kong 64: Recompiled",
         repo="Rainchus/Donkey-Kong-64-Recompiled", kind="archive",
         asset=r"Linux-X64-Release-[\d-]+\.zip$", exe="DK64Recompiled",
         logo="", color="#c8a018",
         needs=("pick", "Donkey Kong 64", "N64 US — .z64")),
    # Build Linux en 32 bits (bibliothèques système 32 bits SDL3/OpenGL/PipeWire,
    # absentes de SteamOS hors runtime Steam) → build Windows sous Proton, qui
    # embarque sa SDL3.dll. Le jeu demande l'image disque au premier lancement.
    dict(shortname="halo-ce", title="Halo: Combat Evolved (OpenCE)",
         repo="OpenCommunityEdition/OpenCE", kind="winarchive",
         asset=r"^halo-windows-release\.zip$", exe="halo.exe",
         logo="", color="#3a6a3a",
         needs=("pick", "Halo: Combat Evolved", "original Xbox — .iso / .xiso")),
    # Le zip Linux contient lui-même un .tar.gz : la double extraction de
    # _extract s'en charge.
    dict(shortname="bm64recomp", title="Bomberman 64: Recompiled",
         repo="RevoSucks/BM64Recomp", kind="archive",
         asset=r"Linux-X64-Release\.zip$", exe="BM64Recompiled",
         logo="", color="#3060c0",
         needs=("pick", "Bomberman 64", "N64 US — .z64")),
    dict(shortname="edgeoftimerecomp", title="Spider-Man: Edge of Time Recompiled",
         repo="goliathret/EdgeOfTimeRecomp", kind="appimage",
         asset=r"x86_64\.AppImage$", exe="",
         logo="", color="#b02020",
         needs=("pick", "Spider-Man: Edge of Time", "Xbox 360 US + title update — your own dump")),
    dict(shortname="splosionmanrecomp", title="'Splosion Man Recomp",
         repo="thefixinhixon/SplosionManRecomp", kind="appimage",
         asset=r"x86_64-v[\d.]+\.AppImage$", exe="",
         logo="", color="#e07020",
         needs=("pick", "'Splosion Man", "Xbox 360 XBLA package — your own")),
    dict(shortname="pacificrimrecomp", title="Pacific Rim Recomp",
         repo="thefixinhixon/PacificRimRecomp", kind="appimage",
         asset=r"x86_64-v[\d.]+\.AppImage$", exe="",
         logo="", color="#2a5a8a",
         needs=("pick", "Pacific Rim", "Xbox 360 XBLA package — your own")),
    dict(shortname="realsteelrecomp", title="Real Steel Recomp",
         repo="thefixinhixon/RealSteelRecomp", kind="appimage",
         asset=r"x86_64-v[\d.]+\.AppImage$", exe="",
         logo="", color="#707880",
         needs=("pick", "Real Steel", "Xbox 360 XBLA package — your own")),
    dict(shortname="themawrecomp", title="The Maw Recomp",
         repo="thefixinhixon/TheMawRecomp", kind="appimage",
         asset=r"x86_64-v[\d.]+\.AppImage$", exe="",
         logo="", color="#6a9a3a",
         needs=("pick", "The Maw", "Xbox 360 XBLA package — your own")),
    # Upstream currently publishes a Windows-only, 32-bit playtest. Run it
    # through Proton until its planned native Linux build is available.
    dict(shortname="acgc-pc-port", title="Animal Crossing (GameCube) PC Port",
         repo="flyngmt/ACGC-PC-Port", kind="winarchive",
         asset=r"^ACGC-PC-Port[\d.]+\.zip$", exe="AnimalCrossing.exe",
         datadir=str(PORTS_DIR / "acgc-pc-port" / "rom"),
         logo="", color="#51a8ba",
         needs=("folder", "Animal Crossing", "GameCube USA GAFE01 Rev 0 — .iso/.gcm/.ciso")),
    dict(shortname="pt-pc", title="P.T. PC Port",
         repo="LoreanXavier/pt-pc", kind="ptsetup",
         asset=r"^P\.T\.PC\.Port\.Setup-linux$", exe="pt",
         pkg_source=str(PORTS_DIR / "pt-pc-source.pkg"),
         datadir=str(PORTS_DIR),
         logo="", color="#776b69",
         needs=("package", "P.T.", "PS4 fake PKG from your own dump, preferably CUSA01127", "pt-pc-source.pkg")),
    # ── Grande vague 12/10/2026 : recomps, portages et moteurs ──
    dict(shortname='rocketr', title='Rocket: Robot on Wheels (Rocket-R)',
         repo='ThatGuyMcd/Rocket-R', kind='archive',
         asset='Linux-x86_64-SteamDeck\\.tar\\.gz$', exe="start-*.sh",
         logo="", color='#3a7bd5',
         needs=('pick', 'Rocket: Robot on Wheels', 'N64 US — .z64')),
    dict(shortname='glover', title='Glover (Glover-R)',
         repo='ThatGuyMcd/Glover-R', kind='archive',
         asset='Linux-x86_64-SteamDeck\\.tar\\.gz$', exe="start-*.sh",
         logo="", color='#d43b3b',
         needs=('pick', 'Glover', 'N64 US rev 0 — .z64')),
    dict(shortname='cv64recomp', title='Castlevania 64: Recompiled',
         repo='RevoSucks/CV64Recomp', kind='archive',
         asset='^CV64Recompiled-Linux-X64-Release\\.zip$', exe="",
         logo="", color='#5a1e1e',
         needs=('pick', 'Castlevania (N64)', 'N64 US — .z64')),
    dict(shortname='megaman64recomp', title='Mega Man 64: Recompiled',
         repo='MegaMan64Recomp/MegaMan64Recompiled', kind='archive',
         asset='Linux-X64\\.zip$', exe="",
         logo="", color='#2f6fd6',
         needs=('pick', 'Mega Man 64', 'N64 US — .z64')),
    dict(shortname='dnzhrecomp', title='Duke Nukem: Zero Hour Recompiled',
         repo='sonicdcer/DNZHRecomp', kind='archive',
         asset='Linux-X64-Release\\.zip$', exe="",
         logo="", color='#c8a018',
         needs=('pick', 'Duke Nukem: Zero Hour', 'N64 US — .z64')),
    dict(shortname='snap64recomp', title='Pokémon Snap (Snap64Recomp)',
         repo='JackandBeans/Snap64Recomp', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#e8c42a',
         needs=('pick', 'Pokémon Snap', 'N64 US — .z64')),
    dict(shortname='goldeneyepc', title='GoldenEye 007 (PC port)',
         repo='jkdansereau/goldeneye-pc-port', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#6b6b6b',
         needs=('named', 'GoldenEye 007', 'N64 US', 'ge007.ntsc-final.z64')),
    dict(shortname='waverace64recomp', title='Wave Race 64 Recompiled',
         repo='danielgomesvieira2000/wave-race-64-recomp', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#1e90c8',
         needs=('pick', 'Wave Race 64', 'N64 USA Rev A — .z64')),
    dict(shortname='sssvrecomp', title='Space Station Silicon Valley Recompiled',
         repo='Cellenseres/SSSV_Recomp', kind='archive',
         asset='_Linux\\.tar\\.gz$', exe="",
         logo="", color='#3aa05a',
         needs=('pick', 'Space Station Silicon Valley', 'N64 US — .z64')),
    dict(shortname='ogrebattle64', title='Ogre Battle 64 Recompiled',
         repo='lfarroco/ogre-battle-64-recomp', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#7a4a1e',
         needs=('pick', 'Ogre Battle 64', 'N64 USA Rev A — .z64')),
    dict(shortname='srw64', title='Super Robot Wars 64 (Marchwind64)',
         repo='dyzz/srw64-recomp', kind='archive',
         asset='linux-x64\\.tar\\.gz$', exe="",
         logo="", color='#2a4a8a',
         needs=('pick', 'Super Robot Taisen 64', 'N64 JP — .z64')),
    dict(shortname='aerogauge', title='AeroGauge Recompiled',
         repo='alondero/aerogauge-recomp', kind='archive',
         asset='linux-x64\\.zip$', exe="",
         logo="", color='#c83a3a',
         needs=('pick', 'AeroGauge', 'N64 US — .z64')),
    dict(shortname='blocksphere', title='Tetrisphere (Blocksphere)',
         repo='djultra64/Blocksphere', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#3a3ad0',
         needs=('pick', 'Tetrisphere', 'N64 US — .z64')),
    dict(shortname='powerdozer', title='Blast Corps (Power Dozer)',
         repo='djultra64/Power-Dozer', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#e0a020',
         needs=('pick', 'Blast Corps', 'N64 US — .z64')),
    dict(shortname='roadrash64', title='Road Rash 64 Recompiled',
         repo='linkssy2/RoadRash64Recompiled', kind='archive',
         asset='Linux.*\\.zip$', exe="",
         logo="", color='#a02a2a',
         needs=('pick', 'Road Rash 64', 'N64 US — .z64')),
    dict(shortname='ghostship', title='Super Mario 64 (Ghostship)',
         repo='HarbourMasters/Ghostship', kind='archive',
         asset='Linux\\.zip$', exe="",
         logo="", color='#d42a2a',
         needs=('pick', 'Super Mario 64', 'N64 US or JP — .z64')),
    dict(shortname='bodyharvest', title='Body Harvest Recompiled',
         repo='danielgomesvieira2000/body-harvest-recomp', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#5a7a3a',
         needs=('pick', 'Body Harvest', 'N64 US — .z64')),
    dict(shortname='snowboardkids', title='Snowboard Kids Recompiled',
         repo='HikariLucy/SnowboardKids-Recomp', kind='archive',
         asset='Linux-x86_64\\.zip$', exe="",
         logo="", color='#e05aa0',
         needs=('pick', 'Snowboard Kids', 'N64 US — .z64')),
    dict(shortname='snowboardkids2', title='Snowboard Kids 2 Recompiled',
         repo='cdlewis/snowboardkids2-recomp', kind='archive',
         asset='Linux-X64-Release\\.tar\\.gz$', exe="",
         logo="", color='#e07a3a',
         needs=('pick', 'Snowboard Kids 2', 'N64 US — .z64')),
    dict(shortname='beetleadventure', title='Beetle Adventure Racing Recompiled',
         repo='danielgomesvieira2000/beetle-adventure-racing-recomp', kind='winarchive',
         asset='windows-x64\\.zip$', exe="",
         logo="", color='#3ac0e0',
         needs=('pick', 'Beetle Adventure Racing!', 'N64 US — .z64')),
    dict(shortname='drmario64', title='Dr. Mario 64 Recompiled',
         repo='theboy181/drmario64_recomp_plus', kind='winarchive',
         asset='Windows\\.zip$', exe="",
         logo="", color='#e03a3a',
         needs=('pick', 'Dr. Mario 64', 'N64 US — .z64')),
    dict(shortname='pokemonstadium', title='Pokémon Stadium Recompiled',
         repo='mstan/PokemonStadiumRecomp', kind='winarchive',
         asset='win64\\.zip$', exe="",
         logo="", color='#c8a018',
         needs=('pick', 'Pokémon Stadium', 'N64 US — .z64')),
    dict(shortname='vpw64', title='Virtual Pro Wrestling 64 Recompiled',
         repo='jessetbh/VPW64Recomp', kind='winarchive',
         asset='Windows\\.zip$', exe="",
         logo="", color='#7a2a2a',
         needs=('pick', 'Virtual Pro Wrestling 64', 'N64 JP — .z64')),
    dict(shortname='wcwrevenge', title='WCW/nWo Revenge Recompiled',
         repo='jessetbh/WCWnWoRevengeRecomp', kind='winarchive',
         asset='Windows\\.zip$', exe="",
         logo="", color='#2a2a2a',
         needs=('pick', 'WCW/nWo Revenge', 'N64 US — .z64')),
    dict(shortname='wcwworldtour', title='WCW vs. nWo: World Tour Recompiled',
         repo='jessetbh/WCWvsNWOWorldTourRecomp', kind='winarchive',
         asset='Windows\\.zip$', exe="",
         logo="", color='#3a3a3a',
         needs=('pick', 'WCW vs. nWo: World Tour', 'N64 US — .z64')),
    dict(shortname='wwfnomercy', title='WWF No Mercy Recompiled',
         repo='jessetbh/WWFNoMercyRecomp', kind='winarchive',
         asset='Windows\\.zip$', exe="",
         logo="", color='#8a1e1e',
         needs=('pick', 'WWF No Mercy', 'N64 US — .z64')),
    dict(shortname='wm2000', title='WWF WrestleMania 2000 Recompiled',
         repo='jessetbh/WWFWrestleMania2000Recomp', kind='winarchive',
         asset='Windows\\.zip$', exe="",
         logo="", color='#1e1e8a',
         needs=('pick', 'WWF WrestleMania 2000', 'N64 US — .z64')),
    dict(shortname='metroidprimeport', title='Metroid Prime (PC port)',
         repo='Odrannnn/MetroidPrimePort', kind='appimage',
         asset='^MetroidPrime-x86_64\\.AppImage$', exe="",
         logo="", color='#d06a1e',
         needs=('pick', 'Metroid Prime', 'GameCube GM8E01 (USA rev 0/1/2) — .iso')),
    dict(shortname='smspcport', title='Super Mario Sunshine (PC port)',
         repo='TekRantGaming/sms-pc-port', kind='appimage',
         asset='linux-x86_64\\.AppImage$', exe="",
         logo="", color='#1e8ad0',
         needs=('pick', 'Super Mario Sunshine', 'GameCube GMSE01 rev 0 — .iso')),
    dict(shortname='opennectar', title='Pikmin (Open Nectar)',
         repo='SSunnKing/Open-Nectar---Pikmin-Native-PC-Mobile-Port', kind='appimage',
         asset='x86_64\\.AppImage$', exe="",
         logo="", color='#e03a3a',
         needs=('pick', 'Pikmin', 'GameCube USA rev 1 or PAL — .iso')),
    dict(shortname='strikers', title='Super Mario Strikers (PC port)',
         repo='new-coke/strikers', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#3aa03a',
         needs=('pick', 'Super Mario Strikers', 'GameCube — .iso')),
    dict(shortname='mscharged', title='Mario Strikers Charged (PC port)',
         repo='yannicksuter/mscharged-port', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#2a8a2a',
         needs=('pick', 'Mario Strikers Charged', 'Wii R4QE01 rev 1 — .iso/.rvz')),
    dict(shortname='ringout', title='Soulcalibur II (RingOut)',
         repo='jackpoison-prog/RingOut', kind='archive',
         asset='steamdeck-x86_64\\.zip$', exe="",
         logo="", color='#c8a018',
         needs=('pick', 'Soulcalibur II', 'GameCube — .iso/.gcm/.rvz/.nkit')),
    dict(shortname='kirbywii', title="Kirby's Return to Dream Land Recompiled",
         repo='ExpansionPak/ModernGekko', kind='archive',
         asset='Linux-x86_64\\.zip$', exe="",
         logo="", color='#e87ab0',
         needs=('pick', "Kirby's Return to Dream Land", 'Wii — .iso/.rvz')),
    dict(shortname='meleeunlocked', title='Super Smash Bros. Melee (Melee Unlocked)',
         repo='Hero88go/melee-unlocked', kind='winarchive',
         asset='win64\\.zip$', exe="",
         logo="", color='#c83a3a',
         needs=('pick', 'Super Smash Bros. Melee', 'GameCube NTSC 1.02 — .iso')),
    dict(shortname='smwrecomp', title='Super Mario World Recompiled',
         repo='mstan/SuperMarioWorldRecomp', kind='appimage',
         asset='linux-.*x86_64\\.AppImage$', exe="",
         logo="", color='#e8c42a',
         needs=('pick', 'Super Mario World', 'SNES US — .sfc')),
    dict(shortname='mmxrecomp', title='Mega Man X Recompiled',
         repo='mstan/MegaManXSNESRecomp', kind='appimage',
         asset='linux-.*x86_64\\.AppImage$', exe="",
         logo="", color='#2a6ad6',
         needs=('pick', 'Mega Man X', 'SNES USA Rev 1 — .sfc')),
    dict(shortname='supermetroidrecomp', title='Super Metroid Recompiled',
         repo='mstan/SuperMetroidRecomp', kind='winarchive',
         asset='windows-x64.*\\.zip$', exe="",
         logo="", color='#d06a1e',
         needs=('pick', 'Super Metroid', 'SNES US — .sfc')),
    dict(shortname='dkc1recomp', title='Donkey Kong Country Recompiled',
         repo='elliotttate/DKC1Recomp', kind='winarchive',
         asset='Windows-x64\\.zip$', exe="",
         logo="", color='#c8a018',
         needs=('pick', 'Donkey Kong Country', 'SNES US — .sfc')),
    dict(shortname='earthbound', title='EarthBound (Phase Distorter)',
         repo='TheRunaway5/Phase-Distorter', kind='archive',
         asset='linux-x86_64\\.zip$', exe="",
         logo="", color='#e05a5a',
         needs=('pick', 'EarthBound', 'SNES US — .sfc')),
    dict(shortname='mksupercircuit', title='Mario Kart: Super Circuit Recompiled',
         repo='mstan/MarioKartSuperCircuitRecomp', kind='appimage',
         asset='linux-x86_64.*\\.AppImage$', exe="",
         logo="", color='#d43b3b',
         needs=('pick', 'Mario Kart: Super Circuit', 'GBA US — .gba')),
    dict(shortname='emeraldrecomp', title='Pokémon Emerald Recompiled',
         repo='mstan/EmeraldRecomp', kind='appimage',
         asset='linux-x86_64.*\\.AppImage$', exe="",
         logo="", color='#2aa05a',
         needs=('pick', 'Pokémon Emerald', 'GBA US — .gba')),
    dict(shortname='mphrecomp', title='Metroid Prime Hunters Recompiled',
         repo='mstan/MetroidPrimeHuntersRecomp', kind='appimage',
         asset='linux-.*x86_64\\.AppImage$', exe="",
         logo="", color='#d06a1e',
         needs=('pick', 'Metroid Prime Hunters', 'DS USA rev 0 — .nds')),
    dict(shortname='gen2recomped', title='Gen2Recomped (Pokémon Gold/Silver/Crystal)',
         repo='UNDERdecoded/Gen2Recomped', kind='archive',
         asset='linux\\.zip$', exe="",
         logo="", color='#c8a018',
         needs=('pick', 'Pokémon Gold / Silver / Crystal', 'GBC — .gbc')),
    dict(shortname='epochequinox', title='Zelda: Oracle of Ages / Seasons (epoch-equinox)',
         repo='ZakyPew/epoch-equinox', kind='archive',
         asset='linux-x64\\.tar\\.gz$', exe="",
         logo="", color='#3aa03a',
         needs=('pick', 'Zelda: Oracle of Ages / Seasons', 'GBC — .gbc')),
    dict(shortname='vandalhearts', title='Vandal Hearts (PC port)',
         repo='HalmyLyseas/VandalHearts-PcPort', kind='appimage',
         asset='linux-x86_64\\.AppImage$', exe="",
         logo="", color='#7a4a1e',
         needs=('files', 'Vandal Hearts', 'PS1 SLUS-00447 / SCPS-45183 / SLPM-86007 — .bin into game/')),
    dict(shortname='bloodyroar2', title='Bloody Roar II Recompiled',
         repo='novapowers0/BloodyRoar2Recomp', kind='archive',
         asset='linux-x64.*\\.zip$', exe="",
         logo="", color='#a01e1e',
         needs=('pick', 'Bloody Roar II', 'PS1 SLES-01722 / SCUS-94424 — .bin/.cue')),
    dict(shortname='ctrnative', title='Crash Team Racing (CTR Native)',
         repo='CTR-tools/ctr-native', kind='archive',
         asset='linux-x86\\.tar\\.gz$', exe="",
         logo="", color='#e07a1e',
         needs=('named', 'Crash Team Racing', 'PS1 NTSC-U, raw MODE2/2352 single-track .bin', 'assets/ctr-u.bin')),
    dict(shortname='severedchains', title='The Legend of Dragoon (Severed Chains)',
         repo='Legend-of-Dragoon-Modding/Severed-Chains', kind='archive',
         asset='^Severed_Chains_Linux\\.tar\\.gz$', exe="",
         logo="", color='#8a1e1e',
         needs=('pick', 'The Legend of Dragoon', 'PS1 — your disc images')),
    dict(shortname='ygofm', title='Yu-Gi-Oh! Forbidden Memories Recompiled',
         repo='Unchiga/YuGiOhForbiddenMemoriesRecomp', kind='archive',
         asset='linux-x64\\.zip$', exe="",
         logo="", color='#7a5a1e',
         needs=('pick', 'Yu-Gi-Oh! Forbidden Memories', 'PS1 — .bin/.cue')),
    dict(shortname='silenthillpc', title='Silent Hill (PC port)',
         repo='SlickAmogus/silent-hill-decomp', kind='archive',
         asset='^SHPC-linux-x64_.*\\.tar\\.gz$', exe="",
         logo="", color='#5a5a5a',
         needs=('pick', 'Silent Hill', 'PS1 USA — .bin/.cue')),
    dict(shortname='einhander', title='Einhänder Recompiled',
         repo='strider973/Einhander-Recompiled', kind='archive',
         asset='linux-x64\\.zip$', exe="",
         logo="", color='#3a5a8a',
         needs=('pick', 'Einhänder', 'PS1 US — .bin/.cue')),
    dict(shortname='ragieracer', title='Rage Racer (PC port)',
         repo='khasinski/rage-racer-pc', kind='archive',
         asset='linux-x86_64\\.zip$', exe="",
         logo="", color='#d02a2a',
         needs=('pick', 'Rage Racer', 'PS1 — .bin/.cue')),
    dict(shortname='lainpsx', title='Serial Experiments Lain (PC port)',
         repo='Y0oshi/lain-psx-decompiled', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#4a3a6a',
         needs=('pick', 'Serial Experiments Lain', 'PS1 JP — your discs')),
    dict(shortname='syphonfilter', title='Syphon Filter (PC port)',
         repo='Madxbio97/SF-pc-port', kind='winarchive',
         asset='win64\\.zip$', exe="",
         logo="", color='#2a4a2a',
         needs=('pick', 'Syphon Filter', 'PS1 USA v1.1 SCUS-94240 — .bin/.cue')),
    dict(shortname='projectcane', title='Sly Cooper (ProjectCane)',
         repo='theclub654/ProjectCane', kind='archive',
         asset='Linux.*\\.rar$', exe="",
         logo="", color='#2a5a8a',
         needs=('pick', 'Sly Cooper and the Thievius Raccoonus', 'PS2 NTSC — .iso')),
    dict(shortname='icopc', title='ICO (PC port)',
         repo='nathanialf/ico-pc', kind='archive',
         asset='linux-portable\\.tar\\.gz$', exe="",
         logo="", color='#8a7a5a',
         needs=('pick', 'ICO', 'PS2 — .iso')),
    dict(shortname='dr2casezero', title='Dead Rising 2: Case Zero Recomp',
         repo='wivi514/Dead_Rising_2_Case_Zero_Xenon_Recomp', kind='archive',
         asset='steamdeck-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#a01e1e',
         needs=('pick', 'Dead Rising 2: Case Zero', 'XBLA package 58410A8D')),
    dict(shortname='dr2casewest', title='Dead Rising 2: Case West Recomp',
         repo='wivi514/Dead_Rising_2_Case_West_Xenon_Recomp', kind='archive',
         asset='steamdeck-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#7a1e1e',
         needs=('pick', 'Dead Rising 2: Case West', 'XBLA package')),
    dict(shortname='hardcorps', title='Contra: Hard Corps Uprising Recompiled',
         repo='saulob/hard-corps-uprising-recompiled', kind='appimage',
         asset='linux-x86_64\\.AppImage$', exe="",
         logo="", color='#c83a1e',
         needs=('pick', 'Hard Corps: Uprising', 'XBLA package')),
    dict(shortname='geowars2', title='Geometry Wars: Retro Evolved 2 Recompiled',
         repo='saulob/geometry-wars-retro-evolved-2-recompiled', kind='appimage',
         asset='linux-x86_64\\.AppImage$', exe="",
         logo="", color='#3ad0e0',
         needs=('pick', 'Geometry Wars: Retro Evolved 2', 'XBLA 584108FF v0.0.1.2')),
    dict(shortname='armyoftwo', title='Army of Two Recomp',
         repo='nikolaygorb/ArmyOfTwoRecomp', kind='archive',
         asset='lin64\\.zip$', exe="",
         logo="", color='#5a5a3a',
         needs=('pick', 'Army of Two', 'Xbox 360 disc — your own dump')),
    dict(shortname='thedarkness', title='The Darkness Recomp',
         repo='nikolaygorb/TheDarknessRecomp', kind='archive',
         asset='lin64\\.zip$', exe="",
         logo="", color='#2a2a2a',
         needs=('pick', 'The Darkness', 'Xbox 360 disc — your own dump')),
    dict(shortname='thp8', title="Tony Hawk's Project 8 Recomp",
         repo='theokyr/Project8Recomp', kind='archive',
         asset='linux-x86_64\\.zip$', exe="",
         logo="", color='#e0a020',
         needs=('pick', "Tony Hawk's Project 8", 'Xbox 360 disc — your own dump')),
    dict(shortname='pinyonshift', title='Forza Horizon (Pinyon Shift)',
         repo='arcanite24/pinyon-shift', kind='archive',
         asset='Launcher-linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#e05a1e',
         needs=('pick', 'Forza Horizon', 'Xbox 360 disc — your own dump')),
    dict(shortname='speedbreaker', title='Need for Speed: Most Wanted (SpeedBreaker)',
         repo='SpeedBreakerProject/speedbreaker', kind='archive',
         asset='steamos-x86_64\\.tar\\.xz$', exe="",
         logo="", color='#c8a018',
         needs=('pick', 'Need for Speed: Most Wanted (2005)', 'Xbox 360 disc — your own dump')),
    dict(shortname='ncaa14', title='NCAA Football 14 Recomp',
         repo='LegendaryDoors/NCAAFootball14Recomp', kind='appimage',
         asset='x86_64\\.AppImage$', exe="",
         logo="", color='#1e3a8a',
         needs=('pick', 'NCAA Football 14', 'Xbox 360 disc — your own dump')),
    dict(shortname='freeriders', title='Sonic Free Riders Recompiled',
         repo='YuutaTsubasa/Free-Riders-Recompiled', kind='archive',
         asset='linux-x64\\.tar\\.gz$', exe="",
         logo="", color='#1e5ad0',
         needs=('pick', 'Sonic Free Riders', 'Xbox 360 disc — your own dump')),
    dict(shortname='nocturnerecomp', title='Castlevania: SotN XBLA (NocturneRecomp)',
         repo='birabittoh/NocturneRecomp', kind='archive',
         asset='^nocturnerecomp-v[\\d.]+-linux-x64\\.tar\\.gz$', exe="",
         logo="", color='#4a1e5a',
         needs=('pick', 'Castlevania: Symphony of the Night (XBLA)', 'XBLA package')),
    dict(shortname='dbzburstlimit', title='Dragon Ball Z: Burst Limit Recompiled',
         repo='iExplosiveRage/DBZ-Burst-Limit-Recompiled', kind='archive',
         asset='linux\\.zip$', exe="",
         logo="", color='#e07a1e',
         needs=('pick', 'Dragon Ball Z: Burst Limit', 'Xbox 360 disc — your own dump')),
    dict(shortname='deadlypremonition', title='Deadly Premonition Recomp',
         repo='LittleBitUA/DPRecomp', kind='winarchive',
         asset='win64\\.zip$', exe="",
         logo="", color='#5a1e1e',
         needs=('pick', 'Deadly Premonition', 'Xbox 360 disc — your own dump')),
    dict(shortname='kingkong', title="Peter Jackson's King Kong Recompiled",
         repo='TekRantGaming/king-kong-recompiled', kind='winarchive',
         asset='windows-x64\\.zip$', exe="",
         logo="", color='#3a2a1e',
         needs=('pick', 'King Kong', 'Xbox 360 disc — your own dump')),
    dict(shortname='openloco', title="OpenLoco (Chris Sawyer's Locomotion)",
         repo='OpenLoco/OpenLoco', kind='appimage',
         asset='linux-x64\\.AppImage$', exe="",
         logo="", color='#3a7a3a',
         needs=('files', "Chris Sawyer's Locomotion", 'Steam / GOG game folder')),
    dict(shortname='uzdoom', title='UZDoom (Doom engine)',
         repo='UZDoom/UZDoom', kind='appimage',
         asset='^Linux-UZDoom-Release-x86_64\\.AppImage$', exe="",
         logo="", color='#a01e1e',
         needs=('files', 'Doom / Doom II / Heretic / Hexen', 'your IWAD (.wad) from Steam/GOG')),
    dict(shortname='dsdadoom', title='dsda-doom',
         repo='kraflab/dsda-doom', kind='appimage',
         asset='linux-x86_64\\.appimage$', exe="",
         logo="", color='#7a1e1e',
         needs=('files', 'Doom / Doom II', 'your IWAD (.wad) from Steam/GOG')),
    dict(shortname='julius', title='Julius (Caesar III)',
         repo='bvschaik/julius', kind='appimage',
         asset='linux\\.AppImage$', exe="",
         logo="", color='#c8a018',
         needs=('files', 'Caesar III', 'Steam / GOG game folder')),
    dict(shortname='opentyrian', title='OpenTyrian (Tyrian 2000)',
         repo='opentyrian/opentyrian', kind='archive',
         asset='linux-x86_64\\.tar\\.gz$', exe="",
         logo="", color='#1e5ad0',
         needs=('files', 'Tyrian 2.1 / 2000', 'data files (Tyrian 2.1 is freeware)')),
    dict(shortname='freesynd', title='FreeSynd (Syndicate)',
         repo='bni/freesynd', kind='winarchive',
         asset='win64\\.zip$', exe="",
         logo="", color='#2a2a5a',
         needs=('files', 'Syndicate', 'GOG / original game data')),
    dict(shortname='vkquake2', title='vkQuake2 (Quake II)',
         repo='kondrak/vkQuake2', kind='winarchive',
         asset='win64\\.zip$', exe="",
         logo="", color='#7a5a2a',
         needs=('files', 'Quake II', 'baseq2 from Steam/GOG')),
    dict(shortname='raze', title='Raze (Duke3D, Blood, Shadow Warrior…)',
         repo='ZDoom/Raze', kind='winarchive',
         asset='windows\\.zip$', exe="",
         logo="", color='#c83a1e',
         needs=('files', 'Duke Nukem 3D / Blood / Shadow Warrior / Exhumed', 'Steam/GOG game files')),
    dict(shortname='nblood', title='NBlood (Blood)',
         repo='nukeykt/NBlood', kind='winarchive',
         asset='^nblood_win64_.*\\.7z$', exe="",
         logo="", color='#8a1e1e',
         needs=('files', 'Blood', 'Steam/GOG game files')),
    dict(shortname='rbdoom3bfg', title='RBDOOM-3-BFG (Doom 3 BFG)',
         repo='RobertBeckebans/RBDOOM-3-BFG', kind='winarchive',
         asset='full-win64.*\\.7z$', exe="",
         logo="", color='#5a1e1e',
         needs=('files', 'Doom 3: BFG Edition', 'Steam/GOG game files')),
    # PS4: the game's own x86-64 code runs natively; its launcher asks for the
    # folder of the player's own dump (the one holding eboot.bin).
    dict(shortname='bloodborne', title='Bloodborne (bbport)',
         repo='ayozetr/bloodborne_linux', kind='appimage',
         asset=r'x86_64\.AppImage$', exe="",
         logo=RAW.format(repo='ayozetr/bloodborne_linux', path='launcher/bloodborne.png'),
         color='#5a4a3a',
         needs=('pick', 'Bloodborne', 'PS4 CUSA03173 v1.09 — your own dump')),
    # Xbox 360 recomp by LittleBitUA: its launcher extracts the player's own
    # .iso on first run and fetches the title update.
    dict(shortname='downpourrecomp', title='Silent Hill: Downpour (DownpourRecomp)',
         repo='LittleBitUA/DownpourRecomp', kind='winarchive',
         asset=r'DownpourRecomp-v[\d.]+\.zip$', exe='PlayDownpour.exe',
         logo="", color='#3a4a52',
         needs=('pick', 'Silent Hill: Downpour', 'Xbox 360 — your own .iso')),
    # Batch of 22/10/2026 — each engine from its project's own GitHub release.
    dict(shortname='crackdownrecomp', title='Crackdown Recompiled',
         repo='saulob/crackdown-xbox360-recompiled', kind='appimage',
         asset='CrackdownRecompiled-v[\\d.]+-x86_64\\.AppImage$', exe='',
         logo='', color='#2a6a3a',
         needs=('pick', 'Crackdown', 'Xbox 360 — your own disc')),
    dict(shortname='mk64recomp', title='Mario Kart 64: Recompiled',
         repo='sonicdcer/MarioKart64Recomp', kind='archive',
         asset='Linux-X64-Release\\.zip$', exe='MarioKart64Recompiled',
         logo='', color='#d02a2a',
         needs=('pick', 'Mario Kart 64', 'N64 USA — .z64')),
    dict(shortname='vf2recomp', title='Virtua Fighter 2 Recomp',
         repo='mr-finster/vf2-recomp', kind='archive',
         asset='deck\\.tar\\.gz$', exe='VirtuaFighter2.sh',
         logo='', color='#3a5ad0',
         needs=('pick', 'Virtua Fighter 2', 'Sega Model 2 — vf2.zip from your own board')),
    dict(shortname='pgr4recomp', title='Project Gotham Racing 4 Recomp',
         repo='beatrixzy/PGR4-Recomp', kind='winarchive',
         asset='PGR4-Recomp-v[\\d.]+\\.zip$', exe='pgr4_recompiled.exe',
         logo='', color='#4a4a4a',
         needs=('pick', 'Project Gotham Racing 4', 'Xbox 360 — your own disc')),
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


def _drives():
    shared = str(Path(__file__).resolve().parent / "shared")
    if shared not in sys.path:
        sys.path.insert(0, shared)
    import drives
    return drives


def port_dir(port):
    # Drive picked in the install dialog, remembered per Classic.
    return Path(_drives().game_path("ports", port["shortname"], PORTS_DIR / port["shortname"]))


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
    rels = []
    try:
        rels = [http_json(
            f"https://api.github.com/repos/{port['repo']}/releases/latest")]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    rx = re.compile(port["asset"], re.IGNORECASE)
    if not any(rx.search(a.get("name", "")) for rel in rels
               for a in rel.get("assets", [])):
        # repos that only publish pre-releases (e.g. OpenGothic) 404 on
        # /latest — fall back to the newest entries of the release list
        rels = http_json(
            f"https://api.github.com/repos/{port['repo']}/releases?per_page=20")
    info = None
    for rel, a in ((rel, a) for rel in rels if not rel.get("draft")
                   for a in rel.get("assets", [])):
        if rx.search(a.get("name", "")):
            info = {"tag": f"{rel.get('tag_name', '')}"
                           f"@{a.get('updated_at') or ''}",
                    "url": a.get("browser_download_url", ""),
                    "size": int(a.get("size", 0)),
                    "name": a.get("name", ""),
                    "ts": int(time.time())}
            break
    if not info:
        raise RuntimeError(f"no compatible asset in {port['repo']} releases")
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
    low = str(archive).lower()
    if low.endswith((".7z", ".rar")):
        _extract_external(archive, dest)
    elif zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="data")
    # Archive dans l'archive (Harvest Moon 64, Goemon : un .zip qui ne
    # contient qu'un .tar.gz) : on la déplie aussi, puis on la supprime.
    inner = [p for p in Path(dest).iterdir()
             if p.is_file() and p.name != Path(archive).name
             and re.search(r"\.(zip|7z|rar|tar\.(gz|xz|bz2|zst)|tgz)$", p.name, re.I)]
    others = [p for p in Path(dest).iterdir()
              if p.name != Path(archive).name and p not in inner]
    if len(inner) == 1 and not others:
        _extract(inner[0], dest, shortname, name)
        inner[0].unlink(missing_ok=True)


def _extract_external(archive, dest):
    """7z / rar releases: Python has no reader, use the system tools
    (SteamOS and Bazzite ship 7z; unrar/unar/bsdtar as fallbacks)."""
    tries = [
        ["7z", "x", "-y", f"-o{dest}", str(archive)],
        ["7za", "x", "-y", f"-o{dest}", str(archive)],
        ["unrar", "x", "-o+", str(archive), str(dest) + "/"],
        ["unar", "-f", "-D", "-o", str(dest), str(archive)],
        ["bsdtar", "-xf", str(archive), "-C", str(dest)],
    ]
    for cmd in tries:
        if not shutil.which(cmd[0]):
            continue
        r = subprocess.run(cmd, capture_output=True, timeout=1800)
        if r.returncode == 0:
            return
    raise RuntimeError("No tool could extract " + Path(archive).name
                       + " (install 7z or unrar)")


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


def _install_archive(archive, pdir, shortname, title, updating=False):
    """Stage release files and preserve user ROMs, saves, mods and settings."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    protected = {"save", "saves", "rom", "roms", "mods", "texture_pack", "game"}
    with tempfile.TemporaryDirectory(prefix="port-stage-", dir=RUNTIME_DIR) as staging:
        _extract(archive, staging, shortname, title)
        for source in Path(staging).rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(staging)
            destination = pdir / relative
            if updating and destination.exists() and (
                    any(part.lower() in protected for part in relative.parts[:-1])
                    or source.suffix.lower() in {".ini", ".cfg"}):
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def find_exe(port):
    """Locate the port's main executable inside its folder: exact hint first,
    then the biggest AppImage, then the biggest ELF (excluding .so)."""
    root = port_dir(port)
    hint = (port.get("exe") or "").lower()
    appimages, elfs = [], []
    from fnmatch import fnmatch
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        low = p.name.lower()
        # exact d'abord ; glob accepté (binaires au nom versionné, ex. FS2)
        if hint and (low == hint or ("*" in hint and fnmatch(low, hint))):
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
    if port.get("kind") == "winarchive":
        # Pas d indice : le plus gros .exe qui n est pas un utilitaire.
        skip = re.compile(r"unins|redist|vc_?redist|crash|setup|dxsetup|"
                          r"updater|launcherhelper|7z", re.I)
        exes = [p for p in Path(root).rglob("*.exe")
                if p.is_file() and not skip.search(p.name)]
        if exes:
            return max(exes, key=lambda p: p.stat().st_size)
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


def _install_pt_setup(port, info, pdir, shortname):
    """Use upstream's integrity-checked setup to import a user's fake PKG."""
    source = Path(port["pkg_source"])
    game_data = pdir / "CUSA01127"
    already_imported = all((game_data / name).is_file() for name in
                           ("chunk1.psarc", "texture.qar"))
    if not source.is_file() and not already_imported:
        raise RuntimeError(f"Copy your own P.T. fake PKG to {source} before installing")
    setup = RUNTIME_DIR / "port_setups" / info["name"]
    download_file(info["url"], setup, shortname, 5, 70,
                  f"Downloading {port['title']} {info['tag']}…")
    setup.chmod(setup.stat().st_mode | 0o111)
    result = RUNTIME_DIR / "port_setups" / "pt-pc-result.txt"
    result.unlink(missing_ok=True)
    write_progress(shortname, 80, "Importing P.T. game files…", pid=os.getpid())
    # Empty source means an existing installation can be updated while the
    # validated archives are preserved by upstream's installer.
    r = subprocess.run([str(setup), "--install",
                        str(source) if source.is_file() else "",
                        str(pdir), str(result)],
                       capture_output=True, text=True, timeout=7200)
    report = result.read_text(errors="replace").strip() if result.exists() else ""
    if r.returncode or not report.startswith("PASS "):
        tail = (report or r.stderr or r.stdout or "P.T. setup failed").strip()
        raise RuntimeError(tail[-500:])


def worker_install(shortname, release=None):
    port = APPS[shortname]
    state = load_state()
    try:
        write_progress(shortname, 2, f"Checking {port['title']} release…",
                       pid=os.getpid())
        info = release or release_info(state, port, max_age=0)
        state.setdefault("releases", {})[shortname] = info
        pdir = port_dir(port)
        pdir.mkdir(parents=True, exist_ok=True)
        if port["kind"] == "ptsetup":
            _install_pt_setup(port, info, pdir, shortname)
        elif port["kind"] == "appimage":
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
            _install_archive(archive, pdir, shortname, port["title"],
                             updating=bool(state.get("apps", {}).get(shortname, {}).get("installed")))
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
        return True
    except Exception as e:
        write_progress(shortname, 0, "Installation failed", error=str(e))
        return False


def iso_import(port):
    """Recomp qui lit un disque extrait (Fable 2) : si l'utilisateur a déposé
    son .iso dans <port>/<subdir>/ et que les fichiers n'y sont pas encore,
    lance l'extraction en arrière-plan. Renvoie une ligne d'état (ou "")."""
    imp = port["iso_import"]
    d = port_dir(port) / imp["subdir"]
    d.mkdir(parents=True, exist_ok=True)
    if all((d / f).exists() for f in imp["files"]):
        return iso_status("ready")
    lock = d / ".extracting"
    if lock.exists():
        try:                                   # extraction en cours ?
            os.kill(int(lock.read_text().strip()), 0)
            return iso_status("busy")
        except Exception:
            # Extraction terminée mais fichiers absents : elle a échoué
            # (mauvaise image, disque plein…) ; le détail est dans .extract.log.
            lock.unlink(missing_ok=True)
            return iso_status("failed")
    isos = sorted(d.glob("*.iso")) + sorted(d.glob("*.ISO"))
    if not isos:
        return iso_status("drop").format(dir=str(d))
    tool = Path(__file__).resolve().parent / "xiso_extract.py"
    with open(d / ".extract.log", "w") as log:
        p = subprocess.Popen([sys.executable, str(tool), str(isos[0]), str(d), *imp["files"]],
                             stdout=log, stderr=subprocess.STDOUT,
                             start_new_session=True)
    lock.write_text(str(p.pid))
    return iso_status("busy")


def _update_event(port, info, installed, success):
    events = RUNTIME_DIR / "ports_update_events"
    events.mkdir(parents=True, exist_ok=True)
    event = {"name": port["title"], "version": info["tag"].split("@")[0],
             "appid": installed.get("steamClientID", ""), "success": success}
    destination = events / f"{time.time_ns()}-{port['shortname']}.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(event))
    temporary.replace(destination)


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
            legacy = st.get("tag", "")
            if legacy == info["tag"].split("T")[0]:
                # Upgrade old date-only stamps without reinstalling every port.
                st["tag"] = info["tag"]
                save_state(state)
            if info["tag"] and info["tag"] != st.get("tag"):
                # Pass the freshly checked release, not the stale on-disk cache.
                success = worker_install(shortname, release=info)
                _update_event(port, info, st, success)
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
        try:
            from PIL import Image
        except ImportError:
            # Pas de Pillow (SteamOS d'origine, cf. SkullKey #4) : le logo
            # brut du projet sert d'illustration plutôt qu'aucune.
            if not port.get("logo"):
                return None
            cache.write_bytes(urlopen_retry(port["logo"], timeout=20))
            return cache
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
    try:
        from PIL import Image
    except ImportError:
        return fetch_logo(port)                 # repli sans Pillow
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

def _cover_url(port):
    """Image de la grille SkullKey : la jaquette SteamGridDB (portrait, comme
    les autres magasins), sinon le logo du projet."""
    return _art_map().get(port["shortname"], {}).get("grid") or port.get("logo") or ""


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
            "Images": [_cover_url(port)],
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
    if port.get("iso_import"):
        status = iso_import(port)
        if status:
            desc += f"<br><br><b>{status}</b>"
    needs = needs_line(port)
    if needs:
        desc += f"<br><br>{needs}"
        if port["needs"][0] not in ("pick", "free"):
            desc += f"<br>{howto_line(port.get('datadir') or str(port_dir(port)))}"
    update_tag = ""
    if st.get("installed") and st.get("tag"):
        try:
            latest = release_info(state, port).get("tag", "")
            if latest and latest != st["tag"]:
                update_tag = latest.split("@")[0]
                desc += ("<br><br><b>⬆ " + update_line(
                    latest.split("@")[0], st["tag"].split("@")[0]) + "</b>")
        except Exception:
            pass  # hors ligne / quota GitHub : on n'affiche rien
    desc += (f"<br><br><i>Source: github.com/{port['repo']}"
             + (f" — build {st["tag"].split("@")[0]}" if st.get("tag") else "") + "</i>")
    print(json.dumps({"Type": "GameDetails", "Content": {
        "Name": port["title"],
        "Description": desc,
        "ApplicationPath": "", "ManualPath": "", "RootFolder": "",
        "DatabaseID": shortname, "ConfigurationPath": "",
        "Images": [_cover_url(port)],
        "ShortName": shortname,
        "UpdateAvailable": update_tag,
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


# Jeu d'images Steam de chaque Classique (jaquette, bannière, héros, logo,
# icône), choisi une fois sur SteamGridDB et figé dans ports_art.json : rien à
# configurer pour l'utilisateur. Ce qui manque retombe sur la tuile composée.
def _art_map():
    try:
        return json.loads((Path(__file__).resolve().parent / "ports_art.json").read_text())
    except Exception:
        return {}


def _art_file(port, slot):
    url = _art_map().get(port["shortname"], {}).get(slot)
    if not url:
        return None
    ext = os.path.splitext(url.split("?")[0])[1].lower() or ".png"
    path = ART_DIR / f"{port['shortname']}_sgdb_{slot}{ext}"
    if not path.exists():
        ART_DIR.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(urlopen_retry(url, timeout=30))
        except Exception as e:
            print(f"art {slot} failed: {e}", file=sys.stderr)
            return None
    return path


def _img_type(path):
    ext = Path(path).suffix.lower().lstrip(".")
    return {"jpeg": "jpg"}.get(ext, ext or "png")


def action_getjsonimages(shortname):
    port = APPS[shortname]
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    fallback = {"Grid": lambda: compose(port, 600, 900), "GridH": lambda: compose(port, 920, 430),
                "Hero": lambda: compose(port, 1920, 620), "Logo": lambda: fetch_logo(port)}
    for key, slot in (("Grid", "grid"), ("GridH", "gridh"), ("Hero", "hero"), ("Logo", "logo")):
        try:
            path = _art_file(port, slot) or fallback[key]()
            if path:
                content[key] = b64_file(path)
                content[key + "Type"] = _img_type(path)
        except Exception as e:
            print(f"artwork {key} failed: {e}", file=sys.stderr)
    icon = _art_file(port, "icon")
    if icon:
        content["IconPath"] = str(icon)
    print(json.dumps({"Type": "Images", "Content": content}))


def action_download(shortname):
    if shortname not in load_state().get("apps", {}):
        _drives().assign("ports", shortname, PORTS_DIR / shortname)
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
    if port["kind"] == "winarchive":
        # Recomp uniquement Windows : Steam lance le .exe sous Proton. Pas de
        # %command% dans les options : Steam y ajoute simplement les
        # arguments (mesuré 07/10 sur Fable 2 : avec « %command% … » Steam
        # passait une commande vide au shell).
        args = (port.get("winargs") or "").replace("{dir}", str(port_dir(port)))
        print(json.dumps({"Type": "LaunchOptions", "Content": {
            "Exe": f'"{exe}"',
            "Options": args,
            "WorkingDir": str(Path(exe).parent),
            "Compatibility": True,
            "Name": port["title"],
        }}))
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
    if pdir.is_dir() and (str(pdir.resolve()).startswith(str(PORTS_DIR.resolve()) + os.sep)
                          or _drives().owned_folder("ports", str(pdir), PORTS_DIR)):
        shutil.rmtree(pdir, ignore_errors=True)
    _drives().forget("ports", shortname)
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
