"""Xbox tab: install and update the Xodus engine (xodus-cli, xodus-service),
the Xodus Proton runtime and, for the fallback sign-in only, the Xodus Nexus
AppImage — always from the official domsvoboda/xodus-nexus and
domsvoboda/nexus-runtime releases, checked against their published SHA-512
sums.

Updates happen on use (tab opened, game launched), at most every 6 hours, and
never while an install or a game is running: a running game keeps the files
it started with. A failed download or checksum keeps the version in place."""

import contextlib
import json
import os
import re
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
RUNTIME_DIR = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                                  str(HOME / "homebrew/data/SkullKey")))
XBOX_DIR = RUNTIME_DIR / "xbox"
RELEASES_URL = "https://api.github.com/repos/domsvoboda/xodus-nexus/releases?per_page=100"
# Since Nexus 0.4.0 the runtime has its own repository; the main one stays the
# fallback until the new one has published something, as Nexus itself does.
RUNTIME_RELEASES_URL = "https://api.github.com/repos/domsvoboda/nexus-runtime/releases?per_page=30"
UPDATE_EVERY = 6 * 3600

FAMILIES = {
    "backend": (re.compile(r"^backend-v\d+(\.\d+)*$"),
                re.compile(r"^xodus-nexus-backend-[\d.]+-linux-x86_64\.tar\.xz$")),
    "runtime": (re.compile(r"^runtime-"),
                re.compile(r"^(xodus-)?nexus-runtime-.+-x86_64\.tar\.xz$")),
    "launcher": (re.compile(r"^v\d+(\.\d+)*$"),
                 re.compile(r"^Xodus-Nexus-[\d.]+-x86_64\.AppImage$")),
}


class ToolsError(Exception):
    pass


def _ssl():
    for ca in ("/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(ca):
            return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


def http_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "SkullKey"})
    with urllib.request.urlopen(req, timeout=20, context=_ssl()) as r:
        return json.loads(r.read())


def http_download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "SkullKey"})
    with urllib.request.urlopen(req, timeout=60, context=_ssl()) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)


def _newest_runtime(releases):
    """Newest published runtime that has both its archive and its checksum.
    Runtime tags end in a commit hash, so they are compared by date."""
    best, best_date = None, ""
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        if not FAMILIES["runtime"][0].match(rel.get("tag_name", "")):
            continue
        try:
            pick_assets("runtime", rel.get("assets") or [])
        except ToolsError:
            continue
        date = rel.get("published_at") or ""
        if best is None or date > best_date:
            best, best_date = (rel["tag_name"], rel.get("assets") or []), date
    return best


def latest_releases(fetch=http_json):
    out = {}
    main = fetch(RELEASES_URL)
    for rel in main:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        for kind, (tag_re, _) in FAMILIES.items():
            if kind != "runtime" and kind not in out and tag_re.match(rel.get("tag_name", "")):
                out[kind] = (rel["tag_name"], rel.get("assets") or [])
    try:
        runtime = _newest_runtime(fetch(RUNTIME_RELEASES_URL))
    except Exception:
        runtime = None
    runtime = runtime or _newest_runtime(main)
    if runtime:
        out["runtime"] = runtime
    return out


def _version_tuple(text):
    m = re.search(r"(\d+(?:\.\d+)+)", text or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def engine_version():
    """Version of the engine in use, e.g. (0, 2, 12), or None if unknown."""
    if _own("xodus-cli"):
        try:
            meta = json.loads((XBOX_DIR / OWN_ENGINE / "BUILD-METADATA.json").read_text())
            return _version_tuple(meta.get("source_tag"))
        except (OSError, ValueError):
            return None
    return _version_tuple((current("backend") or {}).get("version"))


def runtime_fits_engine(runtime_dir):
    """A runtime may need a minimum engine (requiresBackendVersion)."""
    try:
        meta = json.loads((Path(runtime_dir) / "XODUS_NEXUS_PATCH.json").read_text())
    except (OSError, ValueError):
        return True
    need = _version_tuple(meta.get("requiresBackendVersion"))
    have = engine_version()
    return not need or (have is not None and have >= need)


def pick_assets(kind, assets):
    """(archive asset, checksum asset) for a release, ignoring -source files."""
    _, name_re = FAMILIES[kind]
    archive = next((a for a in assets if name_re.match(a["name"])), None)
    if not archive:
        raise ToolsError(f"No {kind} download in this release.")
    base = re.sub(r"\.tar\.xz$", "", archive["name"])
    wanted = {base + ".sha512sum", archive["name"] + ".sha512sum"}
    checksum = next((a for a in assets if a["name"] in wanted), None)
    if not checksum:
        raise ToolsError(f"No checksum for the {kind} download.")
    return archive, checksum


def verify_sha512(path, sumfile_text):
    import hashlib
    h = hashlib.sha512()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    for line in sumfile_text.splitlines():
        parts = line.split()
        if parts and parts[0].lower() == h.hexdigest() and (len(parts) == 1 or
                                                            parts[-1].lstrip("*") == Path(path).name):
            return True
    return False


def _pointer(kind):
    return XBOX_DIR / kind / "current.json"


def current(kind):
    try:
        data = json.loads(_pointer(kind).read_text())
        return data if Path(data["path"]).exists() else None
    except Exception:
        return None


def install_component(kind, fetch=http_json, download=http_download):
    rel = latest_releases(fetch).get(kind)
    if not rel:
        raise ToolsError(f"No {kind} release found.")
    tag, assets = rel
    archive, checksum = pick_assets(kind, assets)
    root = XBOX_DIR / kind
    cache = XBOX_DIR / "cache"
    root.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as work:
        dl = Path(work) / archive["name"]
        sums = Path(work) / checksum["name"]
        try:
            download(archive["browser_download_url"], dl)
            download(checksum["browser_download_url"], sums)
        except Exception as e:
            raise ToolsError(f"Download failed ({kind}).") from e
        if not verify_sha512(dl, sums.read_text(errors="ignore")):
            raise ToolsError(f"The {kind} download did not match its checksum.")
        final = root / tag
        staging = Path(tempfile.mkdtemp(dir=root, prefix=".new-"))
        try:
            if kind == "launcher":
                target = staging / "Xodus-Nexus.AppImage"
                shutil.move(str(dl), target)
                target.chmod(0o755)
            else:
                with tarfile.open(dl, "r:xz") as tar:
                    tar.extractall(staging, filter="tar")
                entries = list(staging.iterdir())
                if len(entries) == 1 and entries[0].is_dir():
                    inner = entries[0]
                    for item in inner.iterdir():
                        shutil.move(str(item), staging / item.name)
                    inner.rmdir()
            if kind == "runtime" and not runtime_fits_engine(staging):
                raise ToolsError("This Xbox runtime needs a newer Xbox engine.")
            if final.exists():
                shutil.rmtree(final)
            staging.rename(final)
        except ToolsError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(staging, ignore_errors=True)
            raise ToolsError(f"Could not unpack the {kind} download.") from e
    tmp = _pointer(kind).with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": tag, "path": str(final)}))
    tmp.replace(_pointer(kind))
    for old in root.iterdir():
        if old.is_dir() and old != final and not old.name.startswith(".") and not busy():
            shutil.rmtree(old, ignore_errors=True)
    return final


def _path(kind, *parts):
    cur = current(kind)
    if not cur:
        return None
    p = Path(cur["path"]).joinpath(*parts)
    return p if p.exists() else None


# SkullKey build of the engine, made with the upstream `key-chain-file`
# feature: the Microsoft sign-in is kept in a private file
# (~/.xodus-keyring.ron, like other launchers) instead of KDE Wallet, so no
# wallet prompt ever blocks Game Mode. Preferred over the official build.
OWN_ENGINE = "engine-file-keychain"
# Built from the official backend source with only the upstream
# `key-chain-file` feature switched on (see xodus-engine/BUILD.md), published
# as a SkullKey release asset and pinned here by checksum. A different pinned
# version replaces the installed one when no install or game is running.
OWN_ENGINE_VERSION = (0, 2, 12)
OWN_ENGINE_ASSET = "xodus-engine-skullkey-0.2.12-linux-x86_64.tar.xz"
OWN_ENGINE_URL = "https://github.com/Necrosiak/SkullKey/releases/download/v1.21.1/" + OWN_ENGINE_ASSET
OWN_ENGINE_SHA512 = ("3684d0c780536e26b1f65c855c02e09d4fdc78adaf9be5b7e9a86c3d2cf9333f2788fb5a234c37d3718716654f0511c6"
                     "8a09512420d0f15fd919e3af6556f092")


def install_own_engine(download=None):
    download = download or http_download
    import hashlib
    cache = XBOX_DIR / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as work:
        dl = Path(work) / OWN_ENGINE_ASSET
        try:
            download(OWN_ENGINE_URL, dl)
        except Exception as e:
            raise ToolsError("Download failed (Xbox engine).") from e
        h = hashlib.sha512(dl.read_bytes()).hexdigest()
        if h != OWN_ENGINE_SHA512:
            raise ToolsError("The Xbox engine download did not match its checksum.")
        staging = Path(tempfile.mkdtemp(dir=XBOX_DIR, prefix=".engine-"))
        try:
            with tarfile.open(dl, "r:xz") as tar:
                tar.extractall(staging, filter="tar")
            inner = staging / "xodus-engine-skullkey"
            final = XBOX_DIR / OWN_ENGINE
            if final.exists():
                shutil.rmtree(final)
            inner.rename(final)
            for name in ("xodus-cli", "xodus-service"):
                (final / name).chmod(0o755)
        finally:
            shutil.rmtree(staging, ignore_errors=True)


def _own(name):
    p = XBOX_DIR / OWN_ENGINE / name
    return p if p.exists() else None


def cli_path():
    return _own("xodus-cli") or _path("backend", "xodus-cli")


def service_path():
    return _own("xodus-service") or _path("backend", "xodus-service")


def wine_path():
    return _path("runtime", "files", "bin", "wine")


def proton_path():
    return _path("runtime", "proton")


def runtime_root():
    return _path("runtime")


def launcher_path():
    return _path("launcher", "Xodus-Nexus.AppImage")


# ── activity locks ───────────────────────────────────────────────────────────

def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False


def busy():
    locks = XBOX_DIR / "locks"
    if not locks.is_dir():
        return False
    for f in locks.iterdir():
        try:
            if _alive(f.read_text().strip()):
                return True
        except OSError:
            pass
        f.unlink(missing_ok=True)
    return False


def busy_with(name):
    try:
        return _alive((XBOX_DIR / "locks" / name).read_text().strip())
    except OSError:
        return False


@contextlib.contextmanager
def hold(name, pid=None):
    locks = XBOX_DIR / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    lock = locks / name
    lock.write_text(str(pid or os.getpid()))
    try:
        yield lock
    finally:
        lock.unlink(missing_ok=True)


def present(kind):
    return {"backend": cli_path, "runtime": wine_path, "launcher": launcher_path}[kind]() is not None


def _engine_attempt_due():
    """A new pinned engine is fetched right away; a failed fetch of it is
    retried at most every 6 h, so an offline launch is not held up."""
    mark = XBOX_DIR / "cache" / "engine-attempt"
    pinned = ".".join(map(str, OWN_ENGINE_VERSION))
    try:
        version, when = mark.read_text().split()
        if version == pinned and time.time() - float(when) < UPDATE_EVERY:
            return False
    except (OSError, ValueError):
        pass
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text(f"{pinned} {time.time()}")
    return True


def ensure(update=True, components=("backend", "runtime"), present=present):
    """Install what is missing; refresh the rest at most every 6 h when idle.
    Returns {"installed": [...], "updated": [...], "errors": [...]}."""
    result = {"installed": [], "updated": [], "errors": []}
    if "backend" in components:
        had = _own("xodus-cli") is not None
        stale = had and engine_version() != OWN_ENGINE_VERSION
        if not had or (update and stale and not busy() and _engine_attempt_due()):
            try:
                install_own_engine()
                result["updated" if had else "installed"].append("engine")
            except ToolsError as e:
                result["errors"].append(str(e))
    missing = [k for k in components if not present(k)]
    for kind in missing:
        try:
            install_component(kind)
            result["installed"].append(kind)
        except ToolsError as e:
            result["errors"].append(str(e))
    if not update or busy():
        return result
    stamp = XBOX_DIR / "cache" / "last-check"
    try:
        if time.time() - float(stamp.read_text()) < UPDATE_EVERY:
            return result
    except (OSError, ValueError):
        pass
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(str(time.time()))
    try:
        latest = latest_releases()
    except Exception:
        return result
    for kind in components:
        if kind in missing or kind not in latest:
            continue
        if (current(kind) or {}).get("version") != latest[kind][0]:
            try:
                install_component(kind)
                result["updated"].append(kind)
            except ToolsError as e:
                result["errors"].append(str(e))
    return result
