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
    if not r:
        return ""
    home = os.environ.get("DECKY_USER_HOME") or os.path.expanduser("~")
    if r == "~":
        return home
    if r.startswith("~/"):
        return os.path.join(home, r[2:].replace("/", os.sep))
    return os.path.expanduser(r)


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
    # Les actions Decky tournent en root, mais Steam/Proton tourne avec le
    # compte du joueur. Un mkdir root ici créait un dossier vide inaccessible
    # à Proton (SkullKey #7). On donne au joueur seulement les dossiers du
    # préfixe que SkullKey vient de créer ; on répare aussi un préfixe déjà
    # créé par cette ancienne version.
    target = os.path.realpath(path)
    missing = []
    cursor = target
    while not os.path.lexists(cursor):
        missing.append(cursor)
        parent = os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    os.makedirs(target, exist_ok=True)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        home = os.path.realpath(os.environ.get("DECKY_USER_HOME")
                                or os.environ.get("HOME") or os.path.expanduser("~"))
        owner = os.stat(home)
        if owner.st_uid != 0:
            for directory in reversed(missing):
                os.chown(directory, owner.st_uid, owner.st_gid)
            # Un ancien essai peut avoir laissé le root configuré et le
            # dossier de ce jeu en root. Ne touche jamais aux ancêtres hors
            # du dossier utilisateur (montage SD, /mnt, etc.).
            selected_root = root()
            configured_root = os.path.realpath(selected_root) if selected_root else ""
            repair = [target]
            if configured_root and os.path.dirname(target) == configured_root:
                repair.insert(0, configured_root)
            for directory in repair:
                # Hors du home, seules les nouvelles entrées créées ici
                # changent de propriétaire : un ancien dossier root d'un
                # montage externe ne doit pas être repris arbitrairement.
                if directory not in missing and os.path.commonpath(
                        (home, directory)) != home:
                    continue
                current = os.lstat(directory)
                if current.st_uid == 0 and os.path.isdir(directory):
                    os.chown(directory, owner.st_uid, owner.st_gid)
    return f"STEAM_COMPAT_DATA_PATH={shlex.quote(path)} "


def repair_existing():
    """Répare les anciens préfixes du home, sans créer ni déplacer de dossier.

    Au chargement du plugin, Steam peut déjà avoir un raccourci dont les
    options de lancement sont correctes : il faut alors corriger les droits
    sans imposer une réinstallation ou une nouvelle génération du raccourci.
    """
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return 0
    home = os.path.realpath(os.environ.get("DECKY_USER_HOME")
                            or os.environ.get("HOME") or os.path.expanduser("~"))
    selected_root = root()
    if not selected_root:
        return 0
    configured_root = os.path.abspath(selected_root)
    if (os.path.realpath(configured_root) != configured_root
            or os.path.commonpath((home, configured_root)) != home):
        return 0
    games = load().get("games", {})
    if not isinstance(games, dict):
        return 0
    count = 0
    for key, entry in games.items():
        if not isinstance(key, str) or ":" not in key or not isinstance(entry, dict):
            continue
        store, game_id = key.split(":", 1)
        expected = os.path.join(configured_root,
                                f"{_safe(store).lower()}-{_safe(game_id)}")
        path = entry.get("path")
        if (not isinstance(path, str) or os.path.abspath(path) != expected
                or os.path.realpath(path) != expected or not os.path.isdir(path)):
            continue
        _env(path)
        count += 1
    return count


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
