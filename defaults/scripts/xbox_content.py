"""Xbox tab: additional content (DLC, and campaigns sold as content, like
DOOM Eternal's) for an installed game.

The base game declares its related products in MicrosoftGame.config. For each
one the account is licensed for, the Store lists one PC MSIXVC package whose
main package is the base game; xodus-cli downloads it by content id into a
folder of its own, and the game finds it through XODUS_CONTENT_ROOTS.
Adapted from Xodus Nexus src/main/game-content.ts (MIT, see
third_party/xodus-nexus/LICENSE)."""

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import xbox_catalog
import xbox_tools

PRODUCT_ID = re.compile(r"^[0-9A-Z]{12}$")
CONTENT_ID = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
MARKER = ".skullkey-content.json"


def _tag(el):
    return el.tag.rsplit("}", 1)[-1]


def base_manifest(root):
    """{"storeId", "name", "related": [...]} from MicrosoftGame.config, or None."""
    root = Path(root)
    cfg = next((p for p in root.iterdir() if p.name.lower() == "microsoftgame.config"), None) if root.is_dir() else None
    if not cfg:
        return None
    try:
        tree = ET.fromstring(cfg.read_text(errors="ignore"))
    except ET.ParseError:
        return None
    store = next((el.text.strip() for el in tree.iter() if _tag(el) == "StoreId" and el.text), "")
    ident = next((el for el in tree.iter() if _tag(el) == "Identity"), None)
    related = []
    for el in tree.iter():
        if _tag(el) == "RelatedProduct" and el.text and PRODUCT_ID.match(el.text.strip()):
            if el.text.strip() not in related:
                related.append(el.text.strip())
    if not store or ident is None:
        return None
    return {"storeId": store, "name": ident.get("Name", ""), "related": related}


def _packages(product):
    out = []
    for sku in product.get("DisplaySkuAvailabilities") or []:
        props = (sku.get("Sku") or {}).get("Properties") or {}
        if props.get("IsTrial") is not False:
            continue
        for pkg in props.get("Packages") or []:
            if (pkg.get("PackageFormat") == "MSIXVC" and "x64" in (pkg.get("Architectures") or [])
                    and any(d.get("PlatformName") == "Windows.Desktop" for d in pkg.get("PlatformDependencies") or [])):
                out.append(pkg)
    return out


def offers(base, catalog, licensed):
    """Packages to install: one per related product the account holds a
    licence for, whose package depends on this base game."""
    products = {p.get("ProductId"): p for p in (catalog or {}).get("Products") or []}
    base_product = products.get(base["storeId"])
    families = {p.get("PackageFamilyName") for p in _packages(base_product or {})
                if str(p.get("PackageFamilyName", "")).startswith(base["name"] + "_")}
    picked = []
    for pid in base["related"]:
        product = products.get(pid)
        if pid == base["storeId"] or pid not in licensed or not product or product.get("ProductType") != "Durable":
            continue
        cands = [p for p in _packages(product) if p.get("MainPackageFamilyNameForDlc") in families
                 and CONTENT_ID.match(str(p.get("ContentId", ""))) and re.match(r"^[A-Za-z0-9._-]+$", str(p.get("PackageFamilyName", "")))]
        ids = {p["ContentId"].lower() for p in cands}
        if len(ids) != 1 or len({p["PackageFamilyName"] for p in cands}) != 1:
            continue
        title = next((lp.get("ProductTitle") for lp in product.get("LocalizedProperties") or [] if lp.get("ProductTitle")), pid)
        picked.append({"productId": pid, "contentId": ids.pop(), "family": cands[0]["PackageFamilyName"], "title": title})
    return picked


def plan(root, licensed, market, lang, fetch=xbox_catalog.http_json):
    base = base_manifest(root)
    if not base or not base["related"]:
        return []
    ids = [base["storeId"]] + base["related"]
    catalog = {"Products": []}
    for i in range(0, len(ids), 20):
        q = {"bigIds": ",".join(ids[i:i + 20]), "market": market, "languages": f"{lang},neutral", "MS-CV": "DGU1mcuYo0WMMp+F.1"}
        try:
            catalog["Products"] += (fetch(xbox_catalog.DETAILS_URL + "?" + urllib.parse.urlencode(q)) or {}).get("Products") or []
        except Exception:
            return []
    return offers(base, catalog, licensed)


def content_dir(pid, related):
    return xbox_tools.XBOX_DIR / "content" / pid / related


def installed(pid, related):
    try:
        marker = json.loads((content_dir(pid, related) / MARKER).read_text())
        return marker.get("productId") == related
    except (OSError, ValueError):
        return False


def mark_installed(pid, offer):
    (content_dir(pid, offer["productId"]) / MARKER).write_text(json.dumps(
        {"schema": 1, "productId": offer["productId"], "contentId": offer["contentId"], "parent": pid}))


def roots(pid):
    base = xbox_tools.XBOX_DIR / "content" / pid
    if not base.is_dir():
        return []
    return sorted(str(d) for d in base.iterdir() if d.is_dir() and installed(pid, d.name))


def roots_env(pid):
    """XODUS_CONTENT_ROOTS value (Windows paths through Z:), or ""."""
    paths = ["Z:" + r.replace("/", "\\") for r in roots(pid)]
    return ";".join(p for p in paths if len(p) < 258 and ";" not in p[2:])
