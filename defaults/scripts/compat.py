"""Linux compatibility of games with an anti-cheat, for every store's game
page: data from AreWeAntiCheatYet (MIT, github.com/AreWeAntiCheatYet),
refreshed weekly. Matching is by normalised title, so it also works for
games that are not installed."""

import json
import os
import re
import ssl
import time
import unicodedata
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/HEAD/games.json"
TTL = 7 * 24 * 3600
RUNTIME = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", os.path.expanduser("~/homebrew/data/SkullKey")))
CACHE = RUNTIME / "compat" / "awacy.json"
BAD = {"Broken", "Denied"}
_EDITION = re.compile(r"\b(standard|deluxe|ultimate|gold|definitive|complete|anniversary|premium|game of the year|goty|"
                      r"edition|pc|windows|for windows|remastered)\b")


def normalize(title):
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[™®©]", "", t)
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = _EDITION.sub(" ", t)
    return " ".join(t.split())


def _ctx():
    for ca in ("/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(ca):
            return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


def load(fetch=None):
    try:
        if time.time() - CACHE.stat().st_mtime < TTL:
            return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        pass
    try:
        if fetch:
            data = fetch(URL)
        else:
            req = urllib.request.Request(URL, headers={"User-Agent": "SkullKey"})
            with urllib.request.urlopen(req, timeout=20, context=_ctx()) as r:
                data = json.loads(r.read())
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(CACHE)
        return data
    except Exception:
        try:
            return json.loads(CACHE.read_text())  # stale is better than nothing
        except (OSError, ValueError):
            return []


def check(title, fetch=None):
    """{"status": "Broken"|"Denied", "anticheats": [...]} when the game is
    known not to run on Linux, else None."""
    key = normalize(title)
    if not key:
        return None
    for game in load(fetch):
        if normalize(game.get("name")) == key:
            if game.get("status") in BAD:
                return {"status": game["status"], "anticheats": game.get("anticheats") or []}
            return None
    return None
