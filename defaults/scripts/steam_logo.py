"""A game's transparent logo from its Steam store page, for the Downloads page
banner when the game's own store has none (Xbox only gives box art).
Usage: steam_logo.py "<title>"  -> prints a data: URI, or nothing.
Only an exact title match is used; results (hits and misses) are cached."""

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
UA = {"User-Agent": "SkullKey"}
MISS_TTL = 7 * 86400


def _ctx():
    for ca in ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
        if os.path.exists(ca):
            return ssl.create_default_context(cafile=ca)
    return None


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"[™®©]", "", s.lower())).strip()


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15, context=_ctx()) as r:
        return r.read()


def logo(title):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^a-z0-9]+", "-", _norm(title))[:80] or "x"
    png, miss = CACHE / f"{key}.png", CACHE / f"{key}.miss"
    if png.exists():
        return png.read_bytes()
    if miss.exists() and time.time() - miss.stat().st_mtime < MISS_TTL:
        return None
    data = None
    try:
        found = json.loads(_get("https://store.steampowered.com/api/storesearch/?" +
                                urllib.parse.urlencode({"term": title, "cc": "US", "l": "english"})))
        app = next((i["id"] for i in found.get("items") or [] if _norm(i.get("name", "")) == _norm(title)), None)
        if app:
            raw = _get(f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app}/logo.png")
            if raw[:8] == b"\x89PNG\r\n\x1a\n":
                data = raw
    except Exception:
        data = None
    if data:
        png.write_bytes(data)
    else:
        miss.write_text("")
    return data


if __name__ == "__main__":
    d = logo(sys.argv[1])
    if d:
        print("data:image/png;base64," + base64.b64encode(d).decode())
