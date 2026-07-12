#!/usr/bin/env python3
"""SkullKey — backup/restore des saves de jeux via ludusavi.

Les jeux hors Steam (Epic/GOG/Amazon) n'ont AUCUN cloud save sur cette machine :
un uninstall, une réinstallation ou un disque mort = progression perdue.
ludusavi (mtkennerly/ludusavi) connaît les emplacements de saves de ~20 000
jeux (manifest PCGamingWiki) et sait fouiller un prefix Proton arbitraire via
--wine-prefix — exactement notre cas (compatdata/<steamClientID>/pfx).

Appel (depuis shared.sh, actions backup-saves / restore-saves) :
    saves.py backup  <dbfile> <shortname> <steamClientID>
    saves.py restore <dbfile> <shortname> <steamClientID>

Sortie : JSON SkullKey sur stdout — {"Type":"Success"|"Error", "Content":…}.
Success → toast natif, Error → modal (executeAction.tsx fait déjà tout ça).

Le binaire ludusavi est auto-provisionné depuis les releases GitHub (idiome
hpatchz de mihoyo.py) dans ~/.local/share/skullkey-ludusavi, avec des XDG
isolés (le user peut avoir SON ludusavi configuré — on n'y touche pas).
Les backups vivent dans ~/.local/share/skullkey-saves (survivent au plugin).
"""
import io
import json
import os
import platform
import shutil
import sqlite3
import ssl
import subprocess
import sys
import tarfile
import urllib.request

HOME = os.path.expanduser("~")
TOOL_DIR = os.path.join(HOME, ".local", "share", "skullkey-ludusavi")
TOOL_BIN = os.path.join(TOOL_DIR, "ludusavi")
XDG_DIR = os.path.join(TOOL_DIR, "xdg")
SAVES_DIR = os.path.join(HOME, ".local", "share", "skullkey-saves")
LATEST_API = "https://api.github.com/repos/mtkennerly/ludusavi/releases/latest"
COMPAT_DATA = os.path.join(HOME, ".local", "share", "Steam", "steamapps",
                           "compatdata")


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


def _download_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SkullKey-Saves"})
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as r:
        return r.read()


def out(kind, message, toast_title=None):
    content = {"Message": message}
    if toast_title:
        content["Title"] = toast_title
    print(json.dumps({"Type": kind, "Content": content}))
    sys.exit(0)


def err(message):
    out("Error", message)


def ensure_ludusavi():
    """Binaire ludusavi : natif du PATH d'abord (idiome stand-alone), sinon
    auto-download de la release GitHub (asset -linux.tar.gz, x86_64 only)."""
    native = shutil.which("ludusavi")
    if native:
        return native
    if os.access(TOOL_BIN, os.X_OK):
        return TOOL_BIN
    if platform.machine() != "x86_64":
        err("ludusavi has no prebuilt binary for this CPU — install the "
            "'ludusavi' package for your distro, then retry.")
    try:
        rel = json.loads(_download_bytes(LATEST_API).decode("utf-8"))
        url = next(a["browser_download_url"] for a in rel["assets"]
                   if a["name"].endswith("-linux.tar.gz"))
        data = _download_bytes(url)
    except Exception as e:
        err(f"Could not download ludusavi (network?): {e}")
    os.makedirs(TOOL_DIR, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        member = next(m for m in tf.getmembers()
                      if os.path.basename(m.name) == "ludusavi")
        with tf.extractfile(member) as src, open(TOOL_BIN, "wb") as dst:
            shutil.copyfileobj(src, dst)
    os.chmod(TOOL_BIN, 0o755)
    return TOOL_BIN


def run_ludusavi(binpath, *args):
    """Run ludusavi avec XDG isolés (config+manifest à nous, pas ceux du user).
    Retourne (rc, parsed_json | None, stderr)."""
    env = dict(os.environ)
    env["XDG_CONFIG_HOME"] = os.path.join(XDG_DIR, "config")
    env["XDG_CACHE_HOME"] = os.path.join(XDG_DIR, "cache")
    os.makedirs(env["XDG_CONFIG_HOME"], exist_ok=True)
    os.makedirs(env["XDG_CACHE_HOME"], exist_ok=True)
    p = subprocess.run([binpath, *args], capture_output=True, text=True,
                       env=env, timeout=600)
    parsed = None
    try:
        parsed = json.loads(p.stdout)
    except Exception:
        pass
    return p.returncode, parsed, p.stderr.strip()


def game_title(dbfile, shortname):
    conn = sqlite3.connect(dbfile)
    try:
        row = conn.execute("SELECT Title FROM Game WHERE ShortName=?",
                           (shortname,)).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        err(f"Game '{shortname}' not found in the database.")
    return row[0]


def canonical_title(binpath, title):
    """Titre exact du manifest ludusavi (find --normalized tolère les
    suffixes d'édition etc.). Score le plus haut si plusieurs candidats."""
    rc, res, stderr = run_ludusavi(binpath, "find", "--api", "--normalized",
                                   "--multiple", title)
    games = (res or {}).get("games") or {}
    if not games:
        err(f"'{title}' is not in the ludusavi save-location manifest — "
            "this game's save paths are unknown, cannot back up.")
    return max(games, key=lambda g: (games[g] or {}).get("score") or 0)


def wine_prefix(app_id):
    if not app_id:
        return None
    pfx = os.path.join(COMPAT_DATA, str(app_id), "pfx")
    return pfx if os.path.isdir(os.path.join(pfx, "drive_c")) else None


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def do_backup(binpath, title, app_id):
    args = ["backup", "--api", "--force", "--path", SAVES_DIR]
    pfx = wine_prefix(app_id)
    if pfx:
        args += ["--wine-prefix", pfx]
    rc, res, stderr = run_ludusavi(binpath, *args, title)
    overall = (res or {}).get("overall") or {}
    if res is None or (rc != 0 and not overall.get("processedGames")):
        err(f"ludusavi backup failed: {stderr or 'unknown error'}")
    if not overall.get("processedGames"):
        out("Success",
            f"No save files found for {title} — nothing to back up "
            "(has the game been played yet?)", "Backup saves")
    game = (res.get("games") or {}).get(title, {})
    nfiles = len(game.get("files") or {})
    size = fmt_size(overall.get("processedBytes") or 0)
    out("Success",
        f"{title}: {nfiles} file(s), {size} backed up to {SAVES_DIR}",
        "Backup saves")


def do_restore(binpath, title, app_id):
    rc, res, stderr = run_ludusavi(binpath, "restore", "--api", "--force",
                                   "--path", SAVES_DIR, title)
    overall = (res or {}).get("overall") or {}
    if res is None or (rc != 0 and not overall.get("processedGames")):
        err(f"ludusavi restore failed: {stderr or 'unknown error'}")
    if not overall.get("processedGames"):
        err(f"No backup found for {title} — back up its saves first.")
    size = fmt_size(overall.get("processedBytes") or 0)
    out("Success", f"{title}: saves restored ({size}).", "Restore saves")


def main():
    if len(sys.argv) != 5 or sys.argv[1] not in ("backup", "restore"):
        err("usage: saves.py backup|restore <dbfile> <shortname> <appid>")
    mode, dbfile, shortname, app_id = sys.argv[1:5]
    title = game_title(dbfile, shortname)
    binpath = ensure_ludusavi()
    title = canonical_title(binpath, title)
    if mode == "backup":
        do_backup(binpath, title, app_id)
    else:
        do_restore(binpath, title, app_id)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": f"saves.py: {e}"}}))
