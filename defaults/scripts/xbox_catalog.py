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


def _merge(name, updates):
    """Add entries to a cache file under an exclusive lock: the grid and the
    background check write the same files at the same time."""
    import fcntl
    p = _cache(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p.with_suffix(".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _load(name)
        data.update(updates)
        _save(name, data)


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


FAILED_TTL = 6 * 3600


def installable(product_id, market, deadline=None):
    """contentId when installable, "" when not, None when the time budget ran
    out (hidden for now, checked again next time)."""
    cache = _load("resolve.json")
    key = f"{market}:{product_id}"
    hit = cache.get(key)
    if hit and time.time() - hit["t"] < (RESOLVE_TTL if hit["content"] is not None else FAILED_TTL):
        return hit["content"]
    if deadline is not None and time.monotonic() > deadline:
        return None
    resolved = xbox_cli.resolve(product_id, market)
    if resolved is None:
        # The engine failed or timed out: unknown, not "unsupported". Remember
        # it briefly so the same failures do not eat every grid's time budget.
        _merge("resolve.json", {key: {"content": None, "t": time.time()}})
        return None
    content = supported_content(resolved) or ""
    _merge("resolve.json", {key: {"content": content, "t": time.time()}})
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


DETAILS_URL = "https://displaycatalog.mp.microsoft.com/v7.0/products"
DETAILS_TTL = 7 * 24 * 3600


def _https(uri):
    return ("https:" + uri) if uri and uri.startswith("//") else uri


def _description(lp):
    """Short description, else the full one (many games only fill that),
    with line breaks kept for the details page."""
    text = (lp.get("ShortDescription") or lp.get("ProductDescription") or "").strip()
    if len(text) > 1500:
        text = text[:1500].rsplit(" ", 1)[0] + "…"
    return "<br>".join(line.strip() for line in text.replace("\r\n", "\n").split("\n"))


def details(ids, market, lang, fetch=http_json):
    """{id: {"title","publisher","description","game": bool,"art": {...}}} for
    library entries (titles and artwork), 7-day cache. Missing ids stay out."""
    cache = _load("details-v2.json")
    out, todo = {}, []
    for pid in ids:
        hit = cache.get(f"{market}:{pid}")
        if hit and time.time() - hit["t"] < DETAILS_TTL:
            out[pid] = hit["d"]
        else:
            todo.append(pid)
    for i in range(0, len(todo), 20):
        q = {"bigIds": ",".join(todo[i:i + 20]), "market": market, "languages": f"{lang},neutral",
             "MS-CV": "DGU1mcuYo0WMMp+F.1"}
        try:
            products = (fetch(DETAILS_URL + "?" + urllib.parse.urlencode(q)) or {}).get("Products") or []
        except Exception:
            continue
        for p in products:
            lp = (p.get("LocalizedProperties") or [{}])[0]
            imgs = {}
            for img in lp.get("Images") or []:
                imgs.setdefault(img.get("ImagePurpose"), _https(img.get("Uri")))
            d = {"title": lp.get("ProductTitle") or p.get("ProductId"), "publisher": lp.get("PublisherName") or "",
                 "description": _description(lp), "game": p.get("ProductKind") == "Game",
                 "art": {"cover": imgs.get("Poster") or imgs.get("BoxArt"),
                         "hero": imgs.get("SuperHeroArt") or imgs.get("TitledHeroArt") or imgs.get("Hero"),
                         "wide": imgs.get("TitledHeroArt") or imgs.get("BoxArt") or imgs.get("SuperHeroArt"),
                         "logo": imgs.get("Logo")}}
            pid = (p.get("ProductId") or "").upper()
            out[pid] = d
            cache[f"{market}:{pid}"] = {"t": time.time(), "d": d}
    if todo:
        _merge("details-v2.json", {k: v for k, v in cache.items() if k.split(":", 1)[-1] in todo})
    return out
