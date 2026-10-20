#!/usr/bin/env python3
"""Discs & Installers: install Windows games from the user's own discs, disc
images, offline installers or ready-to-play folders, and turn each into a
Steam shortcut (Proton, shortcut prefix).

⚖️ Légalité — l'onglet installe ce que l'utilisateur possède (son disque, son
image, son installeur hors ligne). Aucune gestion de crack, d'émulateur Steam,
de patch « no-CD » ni de contournement de protection anticopie : ne jamais en
ajouter ici.

CLI actions mirror ports.py: getgames, getgamedetails, getjsonimages,
getgamesize, install, uninstall, getprogress, cancelinstall."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

HOME = Path(os.path.expanduser("~"))
RUNTIME_DIR = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                                  str(HOME / "homebrew/data/SkullKey")))
DATA_DIR = RUNTIME_DIR / "disks"
STATE_FILE = DATA_DIR / "state.json"
PROGRESS_DIR = DATA_DIR / "progress"


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


# ── actions ──────────────────────────────────────────────────────────────────

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


def main():
    argv = sys.argv[1:]
    if not argv:
        return error("no action")
    action, args = argv[0], argv[1:]
    if action == "getgames":
        action_getgames(args[1] if len(args) > 1 else "",
                        args[2] if len(args) > 2 else "false")
    else:
        error(f"unknown action {action}")


if __name__ == "__main__":
    main()
