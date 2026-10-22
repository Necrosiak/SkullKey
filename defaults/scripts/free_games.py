"""Free games to claim: Epic's weekly giveaways (Epic's own store API) and the
other stores' (GOG, Steam, Ubisoft, Battle.net, EA, Amazon Prime Gaming,
itch.io) from GamerPower's public giveaway API.

SkullKey only tells the player and opens the claim page in Steam's browser:
claiming is an order on the store (sometimes with a captcha), so the player
confirms it themselves. Nothing is bought or claimed automatically."""

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", os.path.expanduser("~/homebrew/data/SkullKey")))
STATE = RUNTIME / "free_games.json"
TTL = 6 * 3600
UA = {"User-Agent": "SkullKey"}
EPIC_URL = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
GP_URL = "https://www.gamerpower.com/api/filter"

# store key -> (label, GamerPower platform name or None for Epic's own API)
STORES = {
    "epic": ("Epic Games", None),
    "gog": ("GOG", "gog"),
    "steam": ("Steam", "steam"),
    "ubisoft": ("Ubisoft", "ubisoft"),
    "battlenet": ("Battle.net", "battlenet"),
    "ea": ("EA", "origin"),
    "amazon": ("Prime Gaming", "prime-gaming"),
    "itch": ("itch.io", "itchio"),
}
DEFAULT_ON = {"epic", "gog", "steam", "amazon"}
# GamerPower "platforms" text -> store key
GP_NAMES = {"gog": "gog", "steam": "steam", "ubisoft": "ubisoft", "battle.net": "battlenet",
            "origin": "ea", "ea app": "ea", "prime gaming": "amazon", "amazon": "amazon", "itch.io": "itch"}


def http_json(url, timeout=20):
    import ssl
    ctx = None
    for ca in ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
        if os.path.exists(ca):
            ctx = ssl.create_default_context(cafile=ca)
            break
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout, context=ctx) as r:
        return json.loads(r.read())


def load():
    try:
        st = json.loads(STATE.read_text())
    except (OSError, ValueError):
        st = {}
    st.setdefault("enabled", sorted(DEFAULT_ON))
    st.setdefault("seen", [])
    st.setdefault("offers", [])
    st.setdefault("t", 0)
    return st


def save(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st))
    tmp.replace(STATE)


def _iso(s):
    return (s or "")[:10]


def epic_offers(country="US", locale="en-US", fetch=None):
    fetch = fetch or http_json
    q = urllib.parse.urlencode({"locale": locale, "country": country, "allowCountries": country})
    data = fetch(f"{EPIC_URL}?{q}")
    out = []
    for e in (((data.get("data") or {}).get("Catalog") or {}).get("searchStore") or {}).get("elements") or []:
        promos = e.get("promotions") or {}
        for kind, field in (("now", "promotionalOffers"), ("soon", "upcomingPromotionalOffers")):
            offers = [o for p in promos.get(field) or [] for o in p.get("promotionalOffers") or []
                      if (o.get("discountSetting") or {}).get("discountPercentage") == 0]
            if not offers:
                continue
            slug = next((m.get("pageSlug") for m in (e.get("offerMappings") or []) + ((e.get("catalogNs") or {}).get("mappings") or [])
                         if m.get("pageSlug")), None) or e.get("productSlug")
            img = next((i.get("url") for i in e.get("keyImages") or [] if i.get("type") in ("OfferImageWide", "Thumbnail")), "")
            out.append({"id": f"epic:{e.get('id')}:{_iso(offers[0].get('startDate'))}", "store": "epic",
                        "title": e.get("title", ""), "image": img, "now": kind == "now",
                        "start": _iso(offers[0].get("startDate")), "end": _iso(offers[0].get("endDate")),
                        "url": f"https://store.epicgames.com/p/{slug}" if slug else "https://store.epicgames.com/free-games"})
            break
    return out


def gamerpower_offers(stores, fetch=None):
    fetch = fetch or http_json
    names = [STORES[s][1] for s in stores if STORES.get(s, (0, None))[1]]
    if not names:
        return []
    data = fetch(f"{GP_URL}?" + urllib.parse.urlencode({"platform": ".".join(names), "type": "game"}))
    if not isinstance(data, list):
        return []
    out = []
    for g in data:
        plats = [p.strip().lower() for p in (g.get("platforms") or "").split(",")]
        store = next((GP_NAMES[p] for p in plats if p in GP_NAMES), None)
        if store not in stores or g.get("status", "Active") != "Active":
            continue
        title = (g.get("title") or "").replace(" Giveaway", "")
        for suffix in (" (GOG)", " (Steam)", " (Epic Games)", " (Ubisoft)", " (Battle.net)", " (Origin)",
                       " (Prime Gaming)", " (IndieGala)", " (itch.io)"):
            title = title.replace(suffix, "")
        if title.endswith(" Key"):
            title = title[:-4]
        out.append({"id": f"gp:{g.get('id')}", "store": store, "title": title.strip(), "image": g.get("image") or "",
                    "now": True, "start": _iso(g.get("published_date")),
                    "end": "" if (g.get("end_date") or "N/A") == "N/A" else _iso(g.get("end_date")),
                    "url": g.get("open_giveaway_url") or g.get("gamerpower_url") or ""})
    return out


def refresh(force=False, country="US", locale="en-US"):
    """Current offers for the enabled stores (cached TTL). Returns the state."""
    st = load()
    if not force and time.time() - st["t"] < TTL:
        return st
    enabled = set(st["enabled"])
    offers, ok = [], False
    if "epic" in enabled:
        try:
            offers += epic_offers(country, locale)
            ok = True
        except Exception:
            pass
    try:
        offers += gamerpower_offers(enabled - {"epic"})
        ok = True
    except Exception:
        pass
    if ok or not enabled:
        st["offers"] = offers
        st["t"] = time.time()
        save(st)
    return st


def new_events(country="US", locale="en-US"):
    """Offers available now that were never announced (at most MAX_EVENTS per
    call, the rest come next time). Marks the returned ones as seen."""
    st = refresh(country=country, locale=locale)
    fresh = [o for o in st["offers"] if o["now"] and o["store"] in st["enabled"] and o["id"] not in st["seen"]]
    fresh = fresh[:MAX_EVENTS]
    if fresh:
        st["seen"] = (st["seen"] + [o["id"] for o in fresh])[-500:]
        save(st)
    return fresh


MAX_EVENTS = 3


def set_enabled(store, on):
    st = load()
    en = set(st["enabled"])
    (en.add if on else en.discard)(store)
    st["enabled"] = sorted(s for s in en if s in STORES)
    st["t"] = 0  # fetch again with the new selection
    save(st)
    return st["enabled"]
