#!/usr/bin/env python3
"""SkullKey Minecraft extension backend.

One tab, three kinds of entries — everything is installed through the
official, legitimate launchers (owning the game is required, both launchers
enforce their own account login):

  - "java"    : Minecraft Java Edition via Prism Launcher (official GitHub
                AppImage). Prism is pre-configured headlessly (language from
                the machine locale, automatic Java download, no setup wizard
                pages besides the Microsoft login) and a "Vanilla" instance
                is created by hand (instance.cfg + mmc-pack.json — Prism
                resolves and downloads Minecraft itself on first launch).
  - "prism"   : the Prism Launcher UI itself (instance/mod/account
                management), same payload as "java".
  - "bedrock" : Minecraft Bedrock Edition via the maintained mcpelauncher
                Flatpak from Flathub (io.mrarm.mcpelauncher) — the launcher
                downloads the game with the user's Google account. Native
                controller support in game.
  - "mp-<slug>": Modrinth modpacks (live catalog: top downloads by default,
                the store filter string becomes a live Modrinth search).
                Install parses the .mrpack index and builds a Prism instance
                directly (mmc-pack.json + parallel mod downloads with sha1
                verification + overrides), so packs launch straight from
                their Steam shortcut with `PrismLauncher -l <instance>`.

Modeled on ports.py: standalone JSON state, detached install worker +
progress file, Pillow-composed Steam artwork, daily silent auto-update
(Prism AppImage tag, flatpak update for Bedrock, Modrinth version id and
Mojang latest release for packs/vanilla; instance saves are never touched —
only mods/ and overrides are refreshed on update)."""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Lock

try:
    from minecraft_i18n import desc_for, pack_desc, uninstall_note, \
        version_texts, restore_texts
except ImportError:
    desc_for = lambda s: ""                       # noqa: E731
    pack_desc = lambda mc, loader: ""             # noqa: E731
    uninstall_note = lambda: ""                   # noqa: E731
    version_texts = lambda: {"title": "Version", "desc": "",
                             "latest": "Latest (auto-update)"}  # noqa: E731
    restore_texts = lambda: {"none": "No worlds backup found.",
                             "not_installed": "Not installed.",
                             "done": "{n} world(s) restored "
                                     "(backup: {label})."}  # noqa: E731

os.environ["PATH"] = os.pathsep.join(
    dict.fromkeys(
        (os.environ.get("PATH", "").split(os.pathsep))
        + ["/usr/bin", "/bin", "/usr/local/bin",
           os.path.expanduser("~/.local/bin")]
    ).keys()
).strip(os.pathsep)

PYEXE = sys.executable or shutil.which("python3") or "/usr/bin/python3"

HOME = Path(os.path.expanduser("~"))
RUNTIME_DIR = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                                  str(HOME / "homebrew/data/SkullKey")))
STATE_FILE = RUNTIME_DIR / "minecraft_state.json"
ART_DIR = RUNTIME_DIR / "minecraft_art"
PROGRESS_DIR = RUNTIME_DIR / "minecraft_progress"
SCRIPTS_DIR = RUNTIME_DIR / "minecraft_scripts"
MC_DIR = HOME / "Games" / "minecraft"
PRISM_DIR = MC_DIR / "prism"
PRISM_APPIMAGE = PRISM_DIR / "PrismLauncher.AppImage"
PRISM_DATA = MC_DIR / "prism-data"
INSTANCES_DIR = PRISM_DATA / "instances"

# same roof as the ludusavi store-saves backups; OUTSIDE MC_DIR on purpose so
# world backups survive a full uninstall of the Minecraft entries
SAVES_BACKUPS = HOME / ".local/share/skullkey-saves/minecraft"
KEEP_BACKUPS = 3

UA = {"User-Agent": "Necrosiak/SkullKey (Minecraft extension)"}
MODRINTH = "https://api.modrinth.com/v2"
MOJANG_MANIFEST = ("https://launchermeta.mojang.com/mc/game/"
                   "version_manifest_v2.json")
PRISM_REPO = "PrismLauncher/PrismLauncher"
PRISM_ASSET = r"^PrismLauncher-Linux-x86_64\.AppImage$"
BEDROCK_APPID = "io.mrarm.mcpelauncher"
CATALOG_SIZE = 36
PARALLEL = 4

# mrpack dependency keys → Prism component uids
LOADER_UIDS = {
    "fabric-loader": "net.fabricmc.fabric-loader",
    "forge": "net.minecraftforge",
    "neoforge": "net.neoforged",
    "quilt-loader": "org.quiltmc.quilt-loader",
}

FIXED = {
    "java": dict(title="Minecraft: Java Edition", color="#3fa53f",
                 logo="https://raw.githubusercontent.com/PrismLauncher/"
                      "PrismLauncher/HEAD/program_info/"
                      "org.prismlauncher.PrismLauncher_256.png"),
    "bedrock": dict(title="Minecraft: Bedrock Edition", color="#4f8f5f",
                    logo="https://dl.flathub.org/repo/appstream/x86_64/icons/"
                         "128x128/io.mrarm.mcpelauncher.png"),
    # no logo: the grid falls back to the title tile — keeps the utility
    # entry visually distinct from the Java Edition one
    "prism": dict(title="Prism Launcher (manage Java/mods)", color="#7a4fd0",
                  logo=""),
}


# ── state ────────────────────────────────────────────────────────────────────

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"apps": {}, "packs": {}, "catalog": {}, "cache": {},
                "last_check": 0}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1))


def app_state(state, shortname):
    return state["apps"].setdefault(
        shortname, {"steamClientID": "", "installed": False, "tag": "",
                    "pin": ""})


def http_json(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


# ── Modrinth catalog ─────────────────────────────────────────────────────────

def _hit_snapshot(h):
    color = h.get("color")
    return {"slug": h["slug"], "title": h["title"],
            "description": h.get("description", ""),
            "icon_url": h.get("icon_url") or "",
            "color": f"#{color:06x}" if isinstance(color, int) else "#3fa53f",
            "downloads": h.get("downloads", 0)}


def modrinth_search(query="", limit=CATALOG_SIZE):
    params = {"facets": '[["project_type:modpack"]]',
              "index": "downloads" if not query else "relevance",
              "limit": str(limit)}
    if query:
        params["query"] = query
    url = f"{MODRINTH}/search?{urllib.parse.urlencode(params)}"
    return [_hit_snapshot(h) for h in http_json(url).get("hits", [])]


def catalog(state, max_age=6 * 3600):
    cat = state.get("catalog") or {}
    if not cat.get("hits") or time.time() - cat.get("ts", 0) > max_age:
        try:
            cat = {"ts": int(time.time()), "hits": modrinth_search()}
            state["catalog"] = cat
        except Exception:
            cat = state.get("catalog") or {"hits": []}
    return cat.get("hits", [])


def remember_packs(state, hits):
    for h in hits:
        state["packs"][h["slug"]] = h


def pack_info(state, slug):
    """Snapshot of a pack previously listed; refetched if state was wiped."""
    info = state["packs"].get(slug)
    if not info:
        p = http_json(f"{MODRINTH}/project/{slug}")
        info = {"slug": slug, "title": p.get("title", slug),
                "description": p.get("description", ""),
                "icon_url": p.get("icon_url") or "",
                "color": f"#{p['color']:06x}"
                         if isinstance(p.get("color"), int) else "#3fa53f",
                "downloads": p.get("downloads", 0)}
        state["packs"][slug] = info
    return info


def pack_versions(slug):
    versions = http_json(f"{MODRINTH}/project/{slug}/version")
    if not versions:
        raise RuntimeError("no version published on Modrinth")
    return versions


def pack_version(slug, pin=""):
    """Modrinth version of a modpack with its primary .mrpack file: the
    pinned version id when set, else latest stable (else newest)."""
    versions = pack_versions(slug)
    if pin:
        v = next((x for x in versions if x["id"] == pin), None)
        if not v:
            raise RuntimeError(f"pinned version {pin} no longer exists "
                               "on Modrinth")
    else:
        v = next((x for x in versions if x.get("version_type") == "release"),
                 versions[0])
    files = v.get("files") or []
    f = next((x for x in files if x.get("primary")), files[0] if files else None)
    if not f:
        raise RuntimeError("version has no downloadable file")
    return {"id": v["id"], "name": v.get("name", v["id"]),
            "url": f["url"], "size": int(f.get("size", 0)),
            "mc": (v.get("game_versions") or [""])[-1],
            "loaders": v.get("loaders") or []}


# ── GitHub release (Prism AppImage) ──────────────────────────────────────────

def prism_release(state, max_age=6 * 3600):
    cache = state.setdefault("cache", {}).get("prism")
    if cache and time.time() - cache.get("ts", 0) < max_age:
        return cache
    rel = http_json(f"https://api.github.com/repos/{PRISM_REPO}"
                    "/releases/latest")
    rx = re.compile(PRISM_ASSET)
    for a in rel.get("assets", []):
        if rx.search(a.get("name", "")):
            info = {"tag": rel.get("tag_name", ""),
                    "url": a.get("browser_download_url", ""),
                    "size": int(a.get("size", 0)), "ts": int(time.time())}
            state["cache"]["prism"] = info
            return info
    raise RuntimeError("no Linux x86_64 AppImage in latest Prism release")


# ── progress / downloads ─────────────────────────────────────────────────────

def write_progress(shortname, pct, desc, error=None, pid=None):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"Percentage": pct, "Description": desc, "Error": error}
    if pid:
        data["pid"] = pid
    (PROGRESS_DIR / f"{shortname}.json").write_text(json.dumps(data))


def download_file(url, dest, shortname, lo, hi, desc):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        tmp = Path(str(dest) + ".part")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    write_progress(shortname, lo + (hi - lo) * done / total,
                                   desc, pid=os.getpid())
        tmp.rename(dest)


def _sha1(path):
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_rel(path):
    """mrpack paths land inside .minecraft — refuse traversal/absolute."""
    p = Path(path)
    if p.is_absolute() or ".." in p.parts:
        raise RuntimeError(f"unsafe path in modpack index: {path}")
    return p


# ── Prism payload (shared by java / prism / modpacks) ────────────────────────

def prism_lang():
    try:
        from minecraft_i18n import machine_lang_code
        code = machine_lang_code()
    except ImportError:
        code = "en"
    return {"en": "en_US", "pt": "pt_PT"}.get(code, code)


def seed_prism_config():
    """Pre-answer Prism's setup wizard: locale language, automatic Java
    download/switch (Mojang runtimes, no page shown), default themes. The
    only first-launch step left is the Microsoft account login."""
    PRISM_DATA.mkdir(parents=True, exist_ok=True)
    cfg = PRISM_DATA / "prismlauncher.cfg"
    if cfg.exists():
        return
    cfg.write_text("[General]\n"
                   "ConfigVersion=1.3\n"
                   f"Language={prism_lang()}\n"
                   "ApplicationTheme=system\n"
                   "IconTheme=pe_colored\n"
                   "AutomaticJavaSwitch=true\n"
                   "AutomaticJavaDownload=true\n"
                   "UserAskedAboutAutomaticJavaDownload=true\n"
                   "IgnoreJavaWizard=true\n")


def latest_minecraft():
    return http_json(MOJANG_MANIFEST)["latest"]["release"]


def minecraft_releases():
    return [v["id"] for v in http_json(MOJANG_MANIFEST)["versions"]
            if v.get("type") == "release"]


def backup_saves(inst_id, label):
    """Snapshot an instance's worlds to SAVES_BACKUPS/<inst>/<ts>_<label>.
    Called before every version change and before uninstall — a Minecraft
    downgrade can refuse (or corrupt) worlds created on a newer version.
    Keeps the newest KEEP_BACKUPS snapshots. Returns the backup dir or None
    when there is nothing to save."""
    saves = INSTANCES_DIR / inst_id / ".minecraft" / "saves"
    try:
        if not saves.is_dir() or not any(saves.iterdir()):
            return None
    except OSError:
        return None
    label = re.sub(r"[^\w.-]+", "-", str(label) or "unknown").strip("-")
    dest = SAVES_BACKUPS / inst_id / \
        f"{time.strftime('%Y%m%d-%H%M%S')}_{label}"
    shutil.copytree(saves, dest / "saves", dirs_exist_ok=True)
    backups = sorted(p for p in (SAVES_BACKUPS / inst_id).iterdir()
                     if p.is_dir())
    for old in backups[:-KEEP_BACKUPS]:
        shutil.rmtree(old, ignore_errors=True)
    return dest


def instance_mc_version(inst_id):
    try:
        pack = json.loads(
            (INSTANCES_DIR / inst_id / "mmc-pack.json").read_text())
        return next((c.get("version", "") for c in pack.get("components", [])
                     if c.get("uid") == "net.minecraft"), "")
    except Exception:
        return ""


def set_vanilla_version(version):
    """Point the Vanilla instance at a Minecraft version. Only the
    net.minecraft component is touched (mods/loaders the user added through
    the Prism UI survive); Prism re-resolves dependencies on next launch."""
    mmc = INSTANCES_DIR / "Vanilla" / "mmc-pack.json"
    if not mmc.exists():
        return False
    pack = json.loads(mmc.read_text())
    changed = False
    for c in pack.get("components", []):
        if c.get("uid") == "net.minecraft" and c.get("version") != version:
            backup_saves("Vanilla", c.get("version", ""))
            c["version"] = version
            c.pop("cachedVersion", None)
            c.pop("cachedRequires", None)
            changed = True
    if changed:
        mmc.write_text(json.dumps(pack, indent=1))
    return changed


def write_instance(inst_id, name, components, icon_key="default"):
    """Bare Prism instance: Prism resolves/downloads Minecraft, the mod
    loader and a Java runtime itself on first launch."""
    inst = INSTANCES_DIR / inst_id
    inst.mkdir(parents=True, exist_ok=True)
    (inst / ".minecraft").mkdir(exist_ok=True)
    (inst / "instance.cfg").write_text(
        "[General]\nInstanceType=OneSix\n"
        f"name={name}\niconKey={icon_key}\n")
    (inst / "mmc-pack.json").write_text(json.dumps(
        {"formatVersion": 1, "components": components}, indent=1))
    return inst


def ensure_vanilla(pin=""):
    if not (INSTANCES_DIR / "Vanilla" / "mmc-pack.json").exists():
        write_instance("Vanilla", "Minecraft",
                       [{"uid": "net.minecraft",
                         "version": pin or latest_minecraft()}])
    elif pin:
        set_vanilla_version(pin)


def install_prism(state, shortname, lo, hi):
    """Download/refresh the Prism AppImage + seed config. Idempotent."""
    info = prism_release(state)
    seed_prism_config()
    if not PRISM_APPIMAGE.exists() or \
            state.get("cache", {}).get("prism_tag") != info["tag"]:
        download_file(info["url"], PRISM_APPIMAGE, shortname, lo, hi,
                      f"Downloading Prism Launcher {info['tag']}…")
        os.chmod(PRISM_APPIMAGE, 0o755)
        state["cache"]["prism_tag"] = info["tag"]
    return info


def write_launch_script(shortname, instance=None):
    """Steam shortcut launcher. With an instance: launch it directly when a
    Microsoft account is already set up, else open Prism (wizard = login
    page). Without: always open the Prism UI. Bedrock: flatpak run."""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / f"{shortname}.sh"
    if shortname == "bedrock":
        path.write_text("#!/usr/bin/env bash\n"
                        f'exec flatpak run {BEDROCK_APPID} "$@"\n')
    elif instance:
        path.write_text(
            "#!/usr/bin/env bash\n"
            f'PRISM="{PRISM_APPIMAGE}"\nDATA="{PRISM_DATA}"\n'
            'if grep -q \'"type"\' "$DATA/accounts.json" 2>/dev/null; then\n'
            f'  exec "$PRISM" -d "$DATA" -l "{instance}" "$@"\n'
            "fi\n"
            'exec "$PRISM" -d "$DATA" "$@"\n')
    else:
        path.write_text("#!/usr/bin/env bash\n"
                        f'exec "{PRISM_APPIMAGE}" -d "{PRISM_DATA}" "$@"\n')
    os.chmod(path, 0o755)
    return path


# ── install workers ──────────────────────────────────────────────────────────

def worker_java(state, shortname):
    info = install_prism(state, shortname, 5, 85)
    if shortname == "java":
        write_progress(shortname, 90, "Creating the Vanilla instance…",
                       pid=os.getpid())
        pin = state["apps"].get("java", {}).get("pin", "")
        ensure_vanilla(pin)
        write_launch_script("java", instance="Vanilla")
        return pin or latest_minecraft()
    write_launch_script("prism")
    return info["tag"]


def worker_bedrock(shortname):
    if not shutil.which("flatpak"):
        raise RuntimeError("flatpak is not available on this system")
    write_progress(shortname, 10, "Adding the Flathub repository…",
                   pid=os.getpid())
    subprocess.run(
        ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
         "https://dl.flathub.org/repo/flathub.flatpakrepo"],
        capture_output=True, timeout=120)
    write_progress(shortname, 25,
                   "Installing Minecraft Bedrock Launcher from Flathub "
                   "(a few hundred MB — no fine progress, hang tight)…",
                   pid=os.getpid())
    r = subprocess.run(
        ["flatpak", "install", "--user", "--noninteractive", "--or-update",
         "-y", "flathub", BEDROCK_APPID],
        capture_output=True, text=True, timeout=7200)
    if r.returncode:
        tail = ((r.stderr or r.stdout or "").strip().splitlines() or ["?"])[-1]
        raise RuntimeError(f"flatpak install failed: {tail}")
    write_launch_script("bedrock")
    out = subprocess.run(
        ["flatpak", "info", "--user", BEDROCK_APPID],
        capture_output=True, text=True, timeout=60).stdout or ""
    m = re.search(r"Version:\s*(\S+)", out)
    return m.group(1) if m else "installed"


def pack_icon_key(state, slug):
    """Copy the pack icon into Prism's icons dir so the instance shows it in
    the Prism UI too (best effort)."""
    try:
        info = pack_info(state, slug)
        if not info.get("icon_url"):
            return "default"
        from PIL import Image
        icons = PRISM_DATA / "icons"
        icons.mkdir(parents=True, exist_ok=True)
        img = Image.open(BytesIO(urlopen_retry(info["icon_url"])))
        img.convert("RGBA").resize((128, 128)).save(icons / f"{slug}.png")
        return slug
    except Exception:
        return "default"


def worker_modpack(state, shortname):
    slug = shortname[3:]
    info = pack_info(state, slug)
    write_progress(shortname, 2, "Checking the modpack on Modrinth…",
                   pid=os.getpid())
    ver = pack_version(slug, state["apps"].get(shortname, {}).get("pin", ""))

    if not PRISM_APPIMAGE.exists():
        install_prism(state, shortname, 4, 30)
    write_progress(shortname, 30, "Reading the modpack index…",
                   pid=os.getpid())
    mrpack = MC_DIR / f"_dl_{slug}.mrpack"
    MC_DIR.mkdir(parents=True, exist_ok=True)
    download_file(ver["url"], mrpack, shortname, 30, 34,
                  f"Downloading {info['title']} {ver['name']}…")
    with zipfile.ZipFile(mrpack) as z:
        idx = json.loads(z.read("modrinth.index.json"))
        deps = idx.get("dependencies", {})
        mc = deps.get("minecraft")
        if not mc:
            raise RuntimeError("modpack index has no minecraft version")
        components = [{"uid": "net.minecraft", "version": mc}]
        for key, uid in LOADER_UIDS.items():
            if deps.get(key):
                components.append({"uid": uid, "version": deps[key]})
        if len(components) == 1 and any(k not in ("minecraft",)
                                        for k in deps):
            raise RuntimeError(f"unsupported mod loader: {list(deps)}")

        files = [f for f in idx.get("files", [])
                 if (f.get("env") or {}).get("client") != "unsupported"]
        for f in files:
            _safe_rel(f["path"])
        total = sum(int(f.get("fileSize", 0)) for f in files) or 1

        # version change on an existing instance: snapshot the worlds first
        # (downgrades can refuse/corrupt worlds from a newer Minecraft)
        old_tag = state["apps"].get(shortname, {}).get("tag", "")
        if old_tag and old_tag != ver["id"]:
            write_progress(shortname, 34, "Backing up your worlds…",
                           pid=os.getpid())
            backup_saves(slug, instance_mc_version(slug) or old_tag)

        inst = write_instance(slug, info["title"], components,
                              icon_key=pack_icon_key(state, slug))
        gamedir = inst / ".minecraft"
        # update path: mods are fully re-synced, everything else (saves,
        # options, screenshots) is left alone
        shutil.rmtree(gamedir / "mods", ignore_errors=True)

        done = [0]
        lock = Lock()

        def fetch(f):
            dest = gamedir / _safe_rel(f["path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            url = (f.get("downloads") or [None])[0]
            if not url:
                raise RuntimeError(f"no download URL for {f['path']}")
            req = urllib.request.Request(url, headers=UA)
            tmp = Path(str(dest) + ".part")
            with urllib.request.urlopen(req, timeout=60) as r, \
                    open(tmp, "wb") as out:
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    out.write(chunk)
                    with lock:
                        done[0] += len(chunk)
                        write_progress(
                            shortname, 35 + 58 * done[0] / total,
                            f"Downloading mods… "
                            f"({done[0] // (1 << 20)} / {total // (1 << 20)} MB)",
                            pid=os.getpid())
            want = (f.get("hashes") or {}).get("sha1")
            if want and _sha1(tmp) != want:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(f"checksum mismatch for {f['path']}")
            tmp.rename(dest)

        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            for fut in [pool.submit(fetch, f) for f in files]:
                fut.result()

        write_progress(shortname, 95, "Applying modpack overrides…",
                       pid=os.getpid())
        for prefix in ("overrides/", "client-overrides/"):
            for zi in z.infolist():
                if not zi.filename.startswith(prefix) or zi.is_dir():
                    continue
                rel = _safe_rel(zi.filename[len(prefix):])
                dest = gamedir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(zi) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
    mrpack.unlink(missing_ok=True)
    write_launch_script(shortname, instance=slug)
    return ver["id"]


def worker_install(shortname):
    state = load_state()
    try:
        if shortname in ("java", "prism"):
            tag = worker_java(state, shortname)
        elif shortname == "bedrock":
            tag = worker_bedrock(shortname)
        elif shortname.startswith("mp-"):
            tag = worker_modpack(state, shortname)
        else:
            raise RuntimeError(f"unknown item {shortname}")
        st = app_state(state, shortname)
        st["installed"] = True
        st["tag"] = tag
        save_state(state)
        write_progress(shortname, 100, "Done")
    except Exception as e:
        save_state(state)
        write_progress(shortname, 0, "Installation failed", error=str(e))


# ── auto-update ──────────────────────────────────────────────────────────────

def worker_autoupdate():
    state = load_state()
    apps = state.get("apps", {})

    prism_users = [s for s in apps
                   if apps[s].get("installed") and s != "bedrock"]
    if prism_users:
        try:
            info = prism_release(state, max_age=0)
            if state.get("cache", {}).get("prism_tag") != info["tag"]:
                install_prism(state, prism_users[0], 0, 0)
                print(f"minecraft autoupdate: Prism → {info['tag']}",
                      file=sys.stderr)
        except Exception as e:
            print(f"minecraft autoupdate prism: {e}", file=sys.stderr)

    if apps.get("java", {}).get("installed") and \
            not apps["java"].get("pin"):
        try:
            latest = latest_minecraft()
            if set_vanilla_version(latest):
                apps["java"]["tag"] = latest
                print(f"minecraft autoupdate: vanilla → {latest}",
                      file=sys.stderr)
        except Exception as e:
            print(f"minecraft autoupdate vanilla: {e}", file=sys.stderr)

    if apps.get("bedrock", {}).get("installed"):
        try:
            subprocess.run(
                ["flatpak", "update", "--user", "--noninteractive", "-y",
                 BEDROCK_APPID],
                capture_output=True, timeout=7200)
        except Exception as e:
            print(f"minecraft autoupdate bedrock: {e}", file=sys.stderr)

    for shortname, st in list(apps.items()):
        if not shortname.startswith("mp-") or not st.get("installed") \
                or st.get("pin"):
            continue
        try:
            ver = pack_version(shortname[3:])
            if ver["id"] != st.get("tag"):
                worker_install(shortname)
                state = load_state()
                apps = state.get("apps", {})
        except Exception as e:
            print(f"minecraft autoupdate {shortname}: {e}", file=sys.stderr)

    state["last_check"] = int(time.time())
    save_state(state)


# ── artwork (Pillow, ports.py pattern) ───────────────────────────────────────

def urlopen_retry(url, timeout=20, tries=4):
    delay = 1.5
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            if attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise last


def _text_logo(title):
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for path in ("/usr/share/fonts/open-sans/OpenSans-Bold.ttf",
                 "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(path, 56)
            break
        except OSError:
            continue
    img = Image.new("RGBA", (640, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((320, 100), title.split(" (")[0].split(":")[0],
           fill=(255, 255, 255, 255), anchor="mm",
           font=font or ImageFont.load_default())
    return img


def item_meta(state, shortname):
    """(title, logo url, color) for fixed entries and modpacks alike."""
    if shortname in FIXED:
        f = FIXED[shortname]
        return f["title"], f["logo"], f["color"]
    info = pack_info(state, shortname[3:])
    return info["title"], info["icon_url"], info["color"]


def fetch_logo(state, shortname):
    ART_DIR.mkdir(parents=True, exist_ok=True)
    cache = ART_DIR / f"{shortname}_logo.png"
    if not cache.exists():
        from PIL import Image
        title, logo, _ = item_meta(state, shortname)
        try:
            if not logo:
                raise RuntimeError("no icon")
            raw = urlopen_retry(logo, timeout=20)
            img = Image.open(BytesIO(raw)).convert("RGBA")
        except Exception as e:
            print(f"logo fetch failed for {shortname}: {e}", file=sys.stderr)
            img = _text_logo(title)
        img.save(cache)
    return cache


def compose(state, shortname, w, h):
    from PIL import Image
    ART_DIR.mkdir(parents=True, exist_ok=True)
    out = ART_DIR / f"{shortname}_{w}x{h}.png"
    if out.exists():
        return out
    _, _, color = item_meta(state, shortname)
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    top = (int(r * 0.50), int(g * 0.50), int(b * 0.50))
    bottom = (10, 12, 16)
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        row = (int(top[0] + (bottom[0] - top[0]) * t),
               int(top[1] + (bottom[1] - top[1]) * t),
               int(top[2] + (bottom[2] - top[2]) * t))
        for x in range(w):
            px[x, y] = row
    logo = Image.open(fetch_logo(state, shortname)).convert("RGBA")
    max_w, max_h = int(w * 0.68), int(h * 0.42)
    scale = min(max_w / logo.width, max_h / logo.height)
    logo = logo.resize((max(1, int(logo.width * scale)),
                        max(1, int(logo.height * scale))), Image.LANCZOS)
    img.paste(logo, ((w - logo.width) // 2, (h - logo.height) // 2), logo)
    img.save(out)
    return out


def b64_file(path):
    import base64
    return base64.b64encode(Path(path).read_bytes()).decode()


# ── actions ──────────────────────────────────────────────────────────────────

def action_getgames(cat="minecraft", filter_str="", installed="false"):
    state = load_state()
    entries = []
    for shortname, f in FIXED.items():
        if filter_str and filter_str.lower() not in f["title"].lower() \
                and filter_str.lower() not in "minecraft":
            continue
        entries.append((shortname, f["title"], f["logo"]))
    try:
        hits = (modrinth_search(filter_str, 24) if filter_str
                else catalog(state))
        remember_packs(state, hits)
    except Exception:
        hits = []
    for h in hits:
        entries.append((f"mp-{h['slug']}", h["title"], h["icon_url"]))
    # installed packs that fell out of the top list / search still must show
    listed = {sn for sn, _, _ in entries}
    for shortname, st in state["apps"].items():
        if shortname.startswith("mp-") and st.get("installed") \
                and shortname not in listed and not filter_str:
            try:
                info = pack_info(state, shortname[3:])
                entries.append((shortname, info["title"], info["icon_url"]))
            except Exception:
                pass
    save_state(state)
    games = []
    for i, (shortname, title, logo) in enumerate(entries, start=1):
        st = state["apps"].get(shortname, {})
        if installed.lower() == "true" and not st.get("steamClientID"):
            continue
        games.append({
            "ID": i,
            "Name": title,
            "Images": [logo] if logo else [],
            "ShortName": shortname,
            "SteamClientID": st.get("steamClientID", ""),
        })
    print(json.dumps({"Type": "GameGrid",
                      "Content": {"Games": games, "NeedsLogin": "false"}}))


def action_getgamedetails(shortname):
    state = load_state()
    st = state["apps"].get(shortname, {})
    title, logo, _ = item_meta(state, shortname)
    if shortname in FIXED:
        desc = desc_for(shortname)
        if shortname == "java":
            desc += f"<br><br><i>Prism Launcher — github.com/{PRISM_REPO}"
            desc += (f" — build {st.get('tag')}" if st.get("tag") else "") \
                + "</i>"
        elif shortname == "bedrock":
            desc += ("<br><br><i>mcpelauncher — flathub.org/apps/"
                     f"{BEDROCK_APPID}</i>")
        else:
            desc += f"<br><br><i>github.com/{PRISM_REPO}</i>"
    else:
        slug = shortname[3:]
        info = pack_info(state, slug)
        mc = loader = ""
        try:
            cached = state.get("cache", {}).get(f"ver_{slug}") or {}
            mc, loader = cached.get("mc", ""), \
                ", ".join(cached.get("loaders", []))
        except Exception:
            pass
        desc = info["description"]
        desc += "<br><br>" + pack_desc(mc, loader)
        desc += "<br>" + uninstall_note()
        desc += (f"<br><br><i>modrinth.com/modpack/{slug} — "
                 f"{info['downloads']:,} downloads"
                 + (f" — version {st.get('tag')}" if st.get("tag") else "")
                 + "</i>")
    editors = []
    if shortname == "java" or shortname.startswith("mp-"):
        vt = version_texts()
        editors.append({"Type": "IniEditor",
                        "InitActionId": "GetVersionConfigActions",
                        "Description": vt["desc"],
                        "Title": vt["title"],
                        "ContentId": shortname})
    save_state(state)
    print(json.dumps({"Type": "GameDetails", "Content": {
        "Name": title,
        "Description": desc,
        "ApplicationPath": "", "ManualPath": "", "RootFolder": "",
        "DatabaseID": shortname, "ConfigurationPath": "",
        "Images": [logo] if logo else [],
        "ShortName": shortname,
        "SteamClientID": st.get("steamClientID", ""),
        "HasDosConfig": False, "HasBatFiles": False,
        "Editors": editors,
    }}))


def action_getgamesize(shortname):
    size = ""
    state = load_state()
    try:
        if shortname in ("java", "prism"):
            info = prism_release(state)
            size = (f"Launcher download: {info['size'] / (1 << 20):.0f} MB "
                    "(Minecraft + Java are fetched on first launch)")
        elif shortname == "bedrock":
            size = ("Launcher install: ~500 MB (the game itself is "
                    "downloaded inside, with your Google account)")
        else:
            slug = shortname[3:]
            cached = state.setdefault("cache", {}).get(f"size_{slug}")
            if cached is None:
                ver = pack_version(slug)
                state["cache"][f"ver_{slug}"] = {"mc": ver["mc"],
                                                 "loaders": ver["loaders"]}
                req = urllib.request.Request(ver["url"], headers=UA)
                with urllib.request.urlopen(req, timeout=30) as r:
                    idx = json.loads(zipfile.ZipFile(BytesIO(r.read()))
                                     .read("modrinth.index.json"))
                cached = sum(int(f.get("fileSize", 0))
                             for f in idx.get("files", [])
                             if (f.get("env") or {}).get("client")
                             != "unsupported")
                state["cache"][f"size_{slug}"] = cached
            size = (f"Mods download: {cached / (1 << 20):.0f} MB "
                    "(plus Minecraft itself on first launch)")
        save_state(state)
    except Exception:
        pass
    print(json.dumps({"Type": "GameSize", "Content": {"Size": size}}))


def action_getjsonimages(shortname):
    state = load_state()
    content = {"Grid": None, "GridH": None, "Hero": None, "Logo": None}
    try:
        content["Grid"] = b64_file(compose(state, shortname, 600, 900))
        content["GridH"] = b64_file(compose(state, shortname, 920, 430))
        content["Hero"] = b64_file(compose(state, shortname, 1920, 620))
        content["Logo"] = b64_file(fetch_logo(state, shortname))
        save_state(state)
    except Exception as e:
        print(f"artwork failed: {e}", file=sys.stderr)
    print(json.dumps({"Type": "Images", "Content": content}))


def action_download(shortname):
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    write_progress(shortname, 0, "Starting…")
    subprocess.Popen([PYEXE, os.path.abspath(__file__), "worker", shortname],
                     start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env=os.environ.copy())
    print(json.dumps({"Type": "Progress",
                      "Content": {"Message": "Installing"}}))


def action_getprogress(shortname):
    try:
        data = json.loads((PROGRESS_DIR / f"{shortname}.json").read_text())
    except Exception:
        data = {"Percentage": 0, "Description": "Waiting…", "Error": None}
    data.pop("pid", None)
    print(json.dumps({"Type": "ProgressUpdate", "Content": data}))


def action_cancelinstall(shortname):
    try:
        data = json.loads((PROGRESS_DIR / f"{shortname}.json").read_text())
        pid = data.get("pid")
        if pid:
            os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass
    try:
        (PROGRESS_DIR / f"{shortname}.json").unlink()
    except Exception:
        pass
    print(json.dumps({"Type": "Success", "Content": {"Message": "Cancelled"}}))


def action_install(shortname, steam_client_id=""):
    state = load_state()
    st = app_state(state, shortname)
    if steam_client_id:
        st["steamClientID"] = str(steam_client_id)
    save_state(state)
    if not st.get("installed"):
        title, _, _ = item_meta(state, shortname)
        print(json.dumps({"Type": "Error", "Content": {
            "Message": f"{title} is not installed yet."}}))
        return
    script = SCRIPTS_DIR / f"{shortname}.sh"
    title, _, _ = item_meta(state, shortname)
    print(json.dumps({"Type": "LaunchOptions", "Content": {
        "Exe": str(script),
        "Options": "",
        "WorkingDir": str(MC_DIR),
        "Compatibility": False,           # native Linux launchers
        "Name": title,
    }}))


def _prism_still_needed(apps):
    return any(s != "bedrock" and st.get("installed")
               for s, st in apps.items())


def action_uninstall(shortname):
    state = load_state()
    apps = state.get("apps", {})
    if shortname == "bedrock":
        # flatpak data (worlds) stays in ~/.var/app — deliberate
        subprocess.run(["flatpak", "uninstall", "--user", "-y",
                        BEDROCK_APPID], capture_output=True, timeout=600)
    elif shortname == "java":
        backup_saves("Vanilla", "uninstall")
        _rm_instance("Vanilla")
    elif shortname.startswith("mp-"):
        backup_saves(shortname[3:], "uninstall")
        _rm_instance(shortname[3:])
    apps.pop(shortname, None)
    if not _prism_still_needed(apps) and MC_DIR.is_dir():
        shutil.rmtree(MC_DIR, ignore_errors=True)
    save_state(state)
    try:
        (SCRIPTS_DIR / f"{shortname}.sh").unlink()
    except Exception:
        pass
    print(json.dumps({"Type": "Success",
                      "Content": {"Message": "Uninstalled"}}))


def _rm_instance(inst_id):
    inst = (INSTANCES_DIR / inst_id).resolve()
    if inst.is_dir() and str(inst).startswith(
            str(INSTANCES_DIR.resolve()) + os.sep):
        shutil.rmtree(inst, ignore_errors=True)


def action_restore_saves(shortname):
    """Game-menu action: bring back the newest worlds snapshot (made on
    version changes and uninstalls). The current worlds are snapshotted
    first, so a restore never loses anything — and the pre-restore snapshot
    being the newest one, the restore target (second newest) always survives
    the keep-{KEEP_BACKUPS} pruning."""
    rt = restore_texts()
    if shortname != "java" and not shortname.startswith("mp-"):
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": rt["none"]}}))
        return
    inst_id = "Vanilla" if shortname == "java" else shortname[3:]
    root = SAVES_BACKUPS / inst_id
    backups = sorted(p for p in root.iterdir() if p.is_dir()) \
        if root.is_dir() else []
    if not backups:
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": rt["none"]}}))
        return
    target = backups[-1]
    saves = INSTANCES_DIR / inst_id / ".minecraft" / "saves"
    if not (INSTANCES_DIR / inst_id).is_dir():
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": rt["not_installed"]}}))
        return
    backup_saves(inst_id, "pre-restore")
    saves.mkdir(parents=True, exist_ok=True)
    restored = 0
    for world in sorted((target / "saves").iterdir()):
        if not world.is_dir():
            continue
        shutil.rmtree(saves / world.name, ignore_errors=True)
        shutil.copytree(world, saves / world.name)
        restored += 1
    print(json.dumps({"Type": "Success", "Content": {
        "Message": rt["done"].format(n=restored,
                                     label=target.name.split("_", 1)[-1])}}))


def action_getversionconfig(shortname):
    """Version picker (ConfEditor modal): 'latest' keeps the daily
    auto-update, anything else pins that exact version."""
    state = load_state()
    vt = version_texts()
    pin = state["apps"].get(shortname, {}).get("pin", "")
    values = [{"Key": "latest", "Label": vt["latest"], "Description": ""}]
    try:
        if shortname == "java":
            values += [{"Key": v, "Label": v, "Description": ""}
                       for v in minecraft_releases()]
        else:
            for v in pack_versions(shortname[3:])[:40]:
                mc = (v.get("game_versions") or [""])[-1]
                kind = v.get("version_type", "release")
                label = v.get("name", v["id"])
                extra = f" — MC {mc}" if mc else ""
                if kind != "release":
                    extra += f" ({kind})"
                values.append({"Key": v["id"], "Label": label + extra,
                               "Description": ""})
    except Exception as e:
        print(json.dumps({"Type": "Error", "Content": {"Message": str(e)}}))
        return
    print(json.dumps({"Type": "IniContent", "Content": {
        "Sections": [{
            "Name": vt["title"],
            "Description": vt["desc"],
            "ModeLevel": 0,
            "Options": [{
                "Key": "version",
                "Label": vt["title"],
                "Value": pin or "latest",
                "DefaultValue": "latest",
                "Description": vt["desc"],
                "Type": "Enum",
                "Min": 0, "Max": 0, "ModeLevel": 0,
                "Parents": [],
                "EnumValues": values,
            }],
        }],
        "Autoexec": "", "AutoexecEnabled": False,
    }}))


def action_saveversionconfig(shortname):
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        data = {}
    picked = "latest"
    for section in data.get("Sections", []):
        for opt in section.get("Options", []):
            if opt.get("Key") == "version":
                picked = opt.get("Value") or "latest"
    state = load_state()
    st = app_state(state, shortname)
    st["pin"] = "" if picked == "latest" else picked
    save_state(state)
    if st.get("installed"):
        if shortname == "java":
            try:
                target = st["pin"] or latest_minecraft()
                set_vanilla_version(target)
                st["tag"] = target
                save_state(state)
            except Exception as e:
                print(json.dumps({"Type": "Error",
                                  "Content": {"Message": str(e)}}))
                return
        else:
            # re-sync the pack now (detached worker, same as Update) —
            # only when the resolved version actually changes
            try:
                ver = pack_version(shortname[3:], st["pin"])
                if ver["id"] != st.get("tag"):
                    action_download(shortname)
                    return
            except Exception as e:
                print(json.dumps({"Type": "Error",
                                  "Content": {"Message": str(e)}}))
                return
    print(json.dumps({"Type": "Success",
                      "Content": {"Message": "Version saved"}}))


def action_autoupdate():
    worker_autoupdate()
    print(json.dumps({"Type": "Success", "Content": {"Message": "done"}}))


def main():
    argv = sys.argv[1:]
    if not argv:
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": "no action"}}))
        return
    action, args = argv[0], argv[1:]
    if action == "getgames":
        action_getgames(args[0] if args else "minecraft",
                        args[1] if len(args) > 1 else "",
                        args[2] if len(args) > 2 else "false")
    elif action == "getgamedetails":
        action_getgamedetails(args[0])
    elif action == "getgamesize":
        action_getgamesize(args[0])
    elif action == "getjsonimages":
        action_getjsonimages(args[0])
    elif action == "download":
        action_download(args[0])
    elif action == "worker":
        worker_install(args[0])
    elif action == "autoupdate":
        action_autoupdate()
    elif action == "getprogress":
        action_getprogress(args[0])
    elif action == "cancelinstall":
        action_cancelinstall(args[0])
    elif action == "install":
        action_install(args[0], args[1] if len(args) > 1 else "")
    elif action == "uninstall":
        action_uninstall(args[0])
    elif action == "getversionconfig":
        action_getversionconfig(args[0])
    elif action == "saveversionconfig":
        action_saveversionconfig(args[0])
    elif action == "restore-saves":
        action_restore_saves(args[0])
    else:
        print(json.dumps({"Type": "Error",
                          "Content": {"Message": f"unknown action {action}"}}))


if __name__ == "__main__":
    main()
