"""Xbox tab: free games from the Microsoft Store (popular lists + search).

Only titles the Xodus engine can actually install are kept (resolve-package
succeeds): classic Store apps (UWP), pre-orders and "available on <date>"
entries are dropped. Every network failure returns an empty list so the grid
still shows the account library."""

import json
import re
import time
import urllib.parse
import urllib.request

import xbox_cli
import xbox_tools

LIST_URL = "https://apps.microsoft.com/api/Reco/GetComputedProductsList"
SEARCH_URL = "https://apps.microsoft.com/api/products/search"
RESOLVE_TTL = 24 * 3600
LIST_TTL = 6 * 3600
RESOLVE_BUDGET = 15
_DATE = re.compile(r"\d{1,4}[/.-]\d{1,2}")


def http_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "SkullKey"})
    with urllib.request.urlopen(req, timeout=15, context=xbox_tools._ssl()) as r:
        return json.loads(r.read())


def _cache(name):
    return xbox_tools.XBOX_DIR / "cache" / name


def _load(name):
    try:
        return json.loads(_cache(name).read_text())
    except Exception:
        return {}


def _save(name, data):
    p = _cache(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(p)


def _art(entry):
    hero = next((i.get("url") for i in entry.get("images") or []
                 if i.get("imageType") in ("SuperHeroArt", "TitledHeroArt", "Hero")), None)
    return {"cover": entry.get("posterArtUrl") or entry.get("boxArtUrl") or entry.get("iconUrl"),
            "hero": hero or entry.get("boxArtUrl"), "icon": entry.get("iconUrl")}


def _normalize(entry):
    # "price" is 0 for games included with Game Pass ("Inclus"); the real
    # retail price is in priceInfo.
    price = (entry.get("priceInfo") or {}).get("price", entry.get("price"))
    display = entry.get("displayPrice") or ""
    free = price == 0 and not _DATE.search(display)
    return {"id": (entry.get("productId") or "").upper(), "title": entry.get("title") or "",
            "publisher": entry.get("publisherName") or "", "price": "free" if free else "paid",
            "art": _art(entry)}


def supported_content(resolved):
    """contentId of the PC package the engine supports, or None (classic Store
    apps, console-only packages)."""
    if not resolved or resolved.get("status") != "ready":
        return None
    return next((c.get("contentId") for c in resolved.get("choices") or [] if c.get("supported")), None)


def installable(product_id, market, deadline=None):
    """contentId when installable, "" when not, None when the time budget ran
    out (hidden for now, checked again next time)."""
    cache = _load("resolve.json")
    key = f"{market}:{product_id}"
    hit = cache.get(key)
    if hit and time.time() - hit["t"] < RESOLVE_TTL:
        return hit["content"]
    if deadline is not None and time.monotonic() > deadline:
        return None
    content = supported_content(xbox_cli.resolve(product_id, market)) or ""
    cache[key] = {"content": content, "t": time.time()}
    _save("resolve.json", cache)
    return content


def _filter(entries, market, keep):
    deadline = time.monotonic() + RESOLVE_BUDGET
    out, seen = [], set()
    for raw in entries:
        g = _normalize(raw)
        if not g["id"] or g["id"] in seen or not keep(g):
            continue
        seen.add(g["id"])
        content = installable(g["id"], market, deadline)
        if content:
            g["installable"] = True
            g["contentId"] = content
            out.append(g)
    return out


def _list(name, market, lang, fetch):
    q = {"listName": name, "pgNo": "1", "noItems": "48", "filteredCategories": "AllProducts",
         "mediaType": "Games", "gl": market, "hl": lang, "exp": "0"}
    return (fetch(LIST_URL + "?" + urllib.parse.urlencode(q)) or {}).get("productsList") or []


def free_games(market, lang, fetch=http_json):
    key = f"{market}:{lang}"
    cached = _load("free.json").get(key)
    if cached and time.time() - cached["t"] < LIST_TTL and fetch is http_json:
        return cached["games"]
    entries = []
    for name in ("TopFreeGames", "TopFree"):
        try:
            entries += _list(name, market, lang, fetch)
        except Exception:
            pass
    games = _filter(entries, market, lambda g: g["price"] == "free")
    if games and fetch is http_json:
        all_cached = _load("free.json")
        all_cached[key] = {"t": time.time(), "games": games}
        _save("free.json", all_cached)
    return games


def search(query, market, lang, owned=frozenset(), fetch=http_json):
    q = {"query": query, "mediaType": "games", "age": "all", "price": "all", "category": "all",
         "subscription": "all", "gl": market, "hl": lang}
    try:
        entries = (fetch(SEARCH_URL + "?" + urllib.parse.urlencode(q)) or {}).get("productsList") or []
    except Exception:
        return []
    return _filter(entries, market, lambda g: g["price"] == "free" or g["id"] in owned)
