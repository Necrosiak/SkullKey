#!/usr/bin/env python3
"""Discs & Installers: find what can be installed — inserted optical discs,
disc images, offline installers and folders holding a setup — and guess a
title and a filesystem-safe slug for it. Pure stdlib, no side effects except
`mount_optical`."""

import os
import re
import subprocess
import unicodedata
from pathlib import Path

IMAGE_EXTS = {".iso", ".bin", ".cue", ".mdf", ".mds", ".img", ".nrg"}
DESCRIPTOR_EXTS = (".cue", ".mds")
LONE_MIN_EXTS = {".bin", ".img"}       # without a descriptor, must look disc-sized
LONE_MIN_SIZE = 50 << 20      # describe a data file next to them
INSTALLER_NAME = re.compile(r"^(setup|install)", re.I)
INSTALLER_MARKERS = (b"Inno Setup", b"Nullsoft", b"NullsoftInst", b"InstallShield")
DISC_TAG = re.compile(r"[\s._-]*[\(\[]?\b(?:disc|disk|cd|dvd)[\s._-]*(\d+)\b[\)\]]?", re.I)
GOG_PART = re.compile(r"^(setup_.+)-(\d+)\.bin$", re.I)
NOISE_TOKENS = {"setup", "install", "installer", "pcwin", "win", "win32", "win64",
                "windows", "gog", "dvd", "cd", "iso", "x86", "x64", "multi"}


# ── optical discs ────────────────────────────────────────────────────────────

def _unescape_mount(field):
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), field)


def optical_volumes(media_root="/run/media", mounts="/proc/mounts"):
    """Mounted optical discs (CD/DVD/Blu-ray, internal or USB): /dev/sr*."""
    vols = []
    try:
        lines = Path(mounts).read_text().splitlines()
    except OSError:
        return vols
    for line in lines:
        parts = line.split()
        if len(parts) < 3 or not re.fullmatch(r"/dev/sr\d+", parts[0]):
            continue
        mountpoint = _unescape_mount(parts[1])
        vols.append({"device": parts[0], "mountpoint": mountpoint,
                     "label": os.path.basename(mountpoint.rstrip("/")) or parts[0]})
    return vols


def unmounted_optical_devices(mounts="/proc/mounts"):
    mounted = {v["device"] for v in optical_volumes(mounts=mounts)}
    return sorted(str(p) for p in Path("/dev").glob("sr[0-9]*") if str(p) not in mounted)


def mount_optical(device):
    """Mount a disc without root (udisks). Returns the mountpoint or None."""
    try:
        out = subprocess.run(["udisksctl", "mount", "-b", device, "--no-user-interaction"],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r" at (.+?)\.?\s*$", out.stdout.strip())
    return m.group(1) if out.returncode == 0 and m else None


# ── installers inside a source ───────────────────────────────────────────────

def parse_autorun(text):
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if section == "autorun" and "=" in line:
            key, value = line.split("=", 1)
            if key.strip().lower() in ("open", "shellexecute") and value.strip():
                return value.strip()
    return None


def _find_ci(root, rel):
    """Resolve a Windows-style relative path case-insensitively."""
    cur = Path(root)
    for part in re.split(r"[\\/]+", rel):
        if not part:
            continue
        match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None) \
            if cur.is_dir() else None
        if match is None:
            return None
        cur = match
    return cur if cur.is_file() else None


def find_installers(root):
    """Installers at the root of a source, best first."""
    root = Path(root)
    found = []
    autorun = _find_ci(root, "autorun.inf")
    target = None
    if autorun:
        value = parse_autorun(autorun.read_text(errors="replace"))
        if value:
            target = _find_ci(root, value.split()[0].strip('"'))
    names = {}
    try:
        for child in root.iterdir():
            if child.is_file() and child.suffix.lower() == ".exe":
                names[child.name.lower()] = child
    except OSError:
        return []
    setup = names.get("setup.exe")
    ordered = []
    if target and setup and target != setup and not INSTALLER_NAME.match(target.name):
        ordered += [setup, target]          # autorun is a menu: setup first
    elif target:
        ordered.append(target)
    for name in ("setup.exe", "install.exe"):
        if name in names:
            ordered.append(names[name])
    ordered += sorted((p for n, p in names.items() if n.startswith("setup")), key=lambda p: p.name.lower())
    for p in ordered:
        if p not in found:
            found.append(p)
    return [str(p) for p in found]


# ── folder scan ──────────────────────────────────────────────────────────────

def _is_installer_exe(path):
    if INSTALLER_NAME.match(path.name):
        return True
    try:
        if path.stat().st_size < 1 << 20:
            return False
        with open(path, "rb") as f:
            head = f.read(4 << 20)
    except OSError:
        return False
    return any(m in head for m in INSTALLER_MARKERS)


def _disc_key(path):
    m = DISC_TAG.search(path.stem)
    if not m:
        return None, 0
    return (path.parent, DISC_TAG.sub("", path.stem).strip().lower(), path.suffix.lower()), int(m.group(1))


def scan_folder(root, max_depth=3):
    """List installable things under `root` (depth-limited, links ignored)."""
    root = Path(root)
    entries, files = [], []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        depth = len(here.relative_to(root).parts)
        dirnames[:] = sorted(d for d in dirnames if not (here / d).is_symlink())
        if depth >= 1 and ({f.lower() for f in filenames} & {"autorun.inf", "setup.exe"}):
            entries.append({"kind": "folder", "path": str(here), "parts": [str(here)],
                            "label": here.name})
            dirnames[:] = []
            continue
        if depth + 1 > max_depth:
            dirnames[:] = []
            continue
        if depth + 1 >= max_depth:
            dirnames[:] = []
        files += [here / f for f in sorted(filenames) if not (here / f).is_symlink()]

    used = set()
    # GOG offline installers: setup_x.exe + setup_x-1.bin…
    for f in files:
        if f.suffix.lower() == ".exe" and f.name.lower().startswith("setup_"):
            parts = [f] + sorted((b for b in files if (m := GOG_PART.match(b.name))
                                  and b.parent == f.parent and m.group(1).lower() == f.stem.lower()),
                                 key=lambda b: int(GOG_PART.match(b.name).group(2)))
            used.update(parts)
            entries.append({"kind": "installer", "path": str(f), "parts": [str(p) for p in parts],
                            "label": f.stem})
    # descriptor + data images (.cue/.bin, .mds/.mdf)
    for f in files:
        if f in used or f.suffix.lower() not in DESCRIPTOR_EXTS:
            continue
        group = [f] + [o for o in files if o is not f and o.parent == f.parent
                       and o.stem.lower() == f.stem.lower() and o.suffix.lower() in IMAGE_EXTS]
        used.update(group)
        entries.append({"kind": "image", "path": str(f), "parts": [str(p) for p in group], "label": f.stem})
    # multi-disc images (a lone small .bin/.img is firmware, not a disc)
    groups = {}
    for f in files:
        if f in used or f.suffix.lower() not in IMAGE_EXTS:
            continue
        if f.suffix.lower() in LONE_MIN_EXTS and f.stat().st_size < LONE_MIN_SIZE:
            continue
        key, n = _disc_key(f)
        groups.setdefault(key or f, []).append((n, f))
    for key, members in groups.items():
        members.sort(key=lambda t: t[0])
        paths = [p for _, p in members]
        used.update(paths)
        entries.append({"kind": "image", "path": str(paths[0]), "parts": [str(p) for p in paths],
                        "label": paths[0].stem})
    # other installers (by name, or Inno/NSIS/InstallShield marker)
    for f in files:
        if f not in used and f.suffix.lower() == ".exe" and _is_installer_exe(f):
            entries.append({"kind": "installer", "path": str(f), "parts": [str(f)], "label": f.stem})
    entries.sort(key=lambda e: e["path"].lower())
    return entries


# ── titles ───────────────────────────────────────────────────────────────────

def clean_title(raw):
    name = os.path.basename(raw.rstrip("/\\"))
    stem, ext = os.path.splitext(name)
    if ext.lower() in IMAGE_EXTS | {".exe"}:
        name = stem
    name = DISC_TAG.sub("", name)
    name = re.sub(r"[_.]+", " ", name)
    words = []
    for token in name.split():
        kept = [w for w in token.split("-") if w and w.lower() not in NOISE_TOKENS
                and not re.fullmatch(r"v?\d+([.]\d+)*", w, re.I)]
        if kept:
            words.append("-".join(kept))
    title = " ".join(words).strip() or stem
    if title.isupper() or title.islower():
        title = " ".join(w.capitalize() for w in title.split())
    return title


def make_slug(title, taken):
    ascii_ = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-") or "game"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug
