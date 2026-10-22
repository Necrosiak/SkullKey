"""A game's transparent logo, for the Downloads page banner when the game's
own store has none (Xbox only gives box art):
  1. its Steam store page (exact title match, no key needed);
  2. SteamGridDB, with the player's own API key (Settings > Platforms).
Usage: steam_logo.py "<title>"         -> prints a data: URI, or nothing
       steam_logo.py --set-key <key>    -> checks and stores the key ("ok"/"invalid")
       steam_logo.py --has-key          -> "yes" / "no"
Results (hits and misses) are cached per title."""

import base64
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", os.path.expanduser("~/homebrew/data/SkullKey")))
CACHE = RUNTIME / "steam_logos"
KEY_FILE = RUNTIME / "steamgriddb.key"
UA = {"User-Agent": "SkullKey"}
MISS_TTL = 7 * 86400
SGDB = "https://www.steamgriddb.com/api/v2"


def _ctx():
    for ca in ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
        if os.path.exists(ca):
            return ssl.create_default_context(cafile=ca)
    return None


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"[™®©]", "", s.lower())).strip()


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=15, context=_ctx()) as r:
        return r.read()


def _key():
    try:
        return KEY_FILE.read_text().strip()
    except OSError:
        return ""


def _sgdb(path, key):
    return json.loads(_get(SGDB + path, {"Authorization": f"Bearer {key}"}))


def set_key(key):
    key = key.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", key):
        return False
    try:
        if not _sgdb("/search/autocomplete/halo", key).get("success"):
            return False
    except Exception:
        return False
    RUNTIME.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(key)
    os.chmod(KEY_FILE, 0o600)
    for miss in CACHE.glob("*.miss"):  # titles that found nothing may now have a logo
        miss.unlink(missing_ok=True)
    return True


def _from_steam(title):
    found = json.loads(_get("https://store.steampowered.com/api/storesearch/?" +
                            urllib.parse.urlencode({"term": title, "cc": "US", "l": "english"})))
    app = next((i["id"] for i in found.get("items") or [] if _norm(i.get("name", "")) == _norm(title)), None)
    if not app:
        return None
    raw = _get(f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app}/logo.png")
    return raw if raw[:8] == b"\x89PNG\r\n\x1a\n" else None


def _from_sgdb(title, key):
    games = _sgdb("/search/autocomplete/" + urllib.parse.quote(title), key).get("data") or []
    game = next((g for g in games if _norm(g.get("name", "")) == _norm(title)), games[0] if games else None)
    if not game:
        return None
    logos = _sgdb(f"/logos/game/{game['id']}?types=static&nsfw=false&humor=false", key).get("data") or []
    # official style first, then the most upvoted
    logos.sort(key=lambda l: (l.get("style") != "official", -(l.get("score") or 0)))
    for l in logos:
        if (l.get("mime") or "").endswith("png"):
            return _get(l["url"])
    return None


def logo(title):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^a-z0-9]+", "-", _norm(title))[:80] or "x"
    png, miss = CACHE / f"{key}.png", CACHE / f"{key}.miss"
    if png.exists():
        return png.read_bytes()
    if miss.exists() and time.time() - miss.stat().st_mtime < MISS_TTL:
        return None
    data = None
    for source in (lambda: _from_steam(title), lambda: _from_sgdb(title, _key()) if _key() else None):
        try:
            data = source()
        except Exception:
            data = None
        if data:
            break
    if data:
        png.write_bytes(data)
    else:
        miss.write_text("")
    return data


if __name__ == "__main__":
    if sys.argv[1:2] == ["--set-key"]:
        print("ok" if set_key(sys.stdin.read()) else "invalid")
    elif sys.argv[1:2] == ["--has-key"]:
        print("yes" if _key() else "no")
    else:
        d = logo(sys.argv[1])
        if d:
            print("data:image/png;base64," + base64.b64encode(d).decode())
