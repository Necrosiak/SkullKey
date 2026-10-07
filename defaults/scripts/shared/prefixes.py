#!/usr/bin/env python3
"""Emplacement des préfixes Proton des jeux SkullKey (SkullKey #5).

Par défaut, Steam range le préfixe d'un raccourci dans
steamapps/compatdata/<id Steam>. Si l'utilisateur choisit un autre dossier,
les jeux installés ENSUITE y reçoivent leur préfixe : SkullKey met
STEAM_COMPAT_DATA_PATH=<dossier>/<magasin>-<jeu> devant ses options de
lancement (mesuré le 07/10 : Proton le respecte, mais le dossier doit exister
avant — sinon FileNotFoundError sur pfx.lock).

Les jeux déjà installés gardent leur préfixe : leurs sauvegardes y vivent
souvent. Seuls les jeux enregistrés dans prefixes.json changent d'endroit.

Usage shell :
    prefixes.py assign <magasin> <jeu> <id Steam>   # à l'installation
    prefixes.py compatdir <id Steam>                 # dossier compatdata du jeu
    prefixes.py env <id Steam>                       # « STEAM_COMPAT_DATA_PATH=… » ou rien
"""
import json
import os
import re
import shlex
import sys

RUNTIME = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                         os.path.expanduser("~/homebrew/data/SkullKey"))
CFG = os.path.join(RUNTIME, "prefixes.json")
STEAM_COMPAT = os.path.expanduser("~/.local/share/Steam/steamapps/compatdata")


def load():
    try:
        with open(CFG) as f:
            d = json.load(f)
        if isinstance(d, dict):
            d.setdefault("root", "")
            d.setdefault("games", {})
            return d
    except Exception:
        pass
    return {"root": "", "games": {}}


def save(d):
    os.makedirs(RUNTIME, exist_ok=True)
    tmp = CFG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, CFG)


def root():
    r = (load().get("root") or "").strip()
    return os.path.expanduser(r) if r else ""


def set_root(path):
    d = load()
    d["root"] = (path or "").strip()
    save(d)
    return d["root"]


def _safe(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s))[:80]


def assign(store, game_id, steam_id=""):
    """À l'installation : choisit le dossier du préfixe d'un NOUVEAU jeu.
    Renvoie le chemin, ou "" si le jeu reste dans compatdata."""
    d = load()
    key = f"{store}:{game_id}"
    if key in d["games"]:
        if steam_id:
            d["games"][key]["steam_id"] = str(steam_id)
            save(d)
        return d["games"][key]["path"]
    r = root()
    if not r:
        return ""
    # Réinstallation d'un jeu qui a déjà un préfixe Steam : on le garde.
    if steam_id and os.path.isdir(os.path.join(STEAM_COMPAT, str(steam_id), "pfx")):
        return ""
    path = os.path.join(r, f"{_safe(store).lower()}-{_safe(game_id)}")
    d["games"][key] = {"path": path, "steam_id": str(steam_id or "")}
    save(d)
    return path


def path_for(store, game_id):
    e = load()["games"].get(f"{store}:{game_id}")
    return e["path"] if e else ""


def path_for_steam(steam_id):
    for e in load()["games"].values():
        if steam_id and e.get("steam_id") == str(steam_id):
            return e["path"]
    return ""


def compat_dir(steam_id):
    """Dossier compatdata réel d'un jeu (celui qui contient pfx/)."""
    return path_for_steam(steam_id) or os.path.join(STEAM_COMPAT, str(steam_id))


def _env(path):
    if not path:
        return ""
    os.makedirs(path, exist_ok=True)        # Proton exige que le dossier existe
    return f"STEAM_COMPAT_DATA_PATH={shlex.quote(path)} "


def env_for(store, game_id):
    """Préfixe à mettre devant les options de lancement (ou "")."""
    return _env(path_for(store, game_id))


def env_for_steam(steam_id):
    return _env(path_for_steam(steam_id))


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if cmd == "assign" and len(args) >= 2:
        print(assign(args[0], args[1], args[2] if len(args) > 2 else ""))
    elif cmd == "compatdir" and args:
        print(compat_dir(args[0]))
    elif cmd == "env" and args:
        print(env_for_steam(args[0]), end="")
    else:
        sys.exit(2)
