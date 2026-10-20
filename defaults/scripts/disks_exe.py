#!/usr/bin/env python3
"""Discs & Installers: find the game's executable after an install — new
.exe files in the prefix, shortcuts the installer created, title match."""

import os
import re
from fnmatch import fnmatch
from pathlib import Path

EXCLUDE = ("unins*", "*setup*", "*install*", "vcredist*", "vc_redist*", "dxsetup*",
           "directx*", "dotnet*", "*crash*", "*report*", "*update*")
NOT_DEFAULT = ("*config*",)
LNK_DIRS = ("ProgramData/Microsoft/Windows/Start Menu",
            "users/*/Desktop",
            "users/*/AppData/Roaming/Microsoft/Windows/Start Menu")
WIN_EXE = re.compile(r"[A-Za-z]:\\[^\x00-\x1f\"*?<>|]*?\.exe", re.I)


def snapshot_exes(root):
    root = Path(root)
    found = set()
    for dirpath, _dirs, files in os.walk(root, followlinks=False):
        for f in files:
            if f.lower().endswith(".exe"):
                found.add(str((Path(dirpath) / f).relative_to(root)).lower())
    return found


def _resolve_ci(drive_c, win_path):
    cur = Path(drive_c)
    for part in win_path.split("\\")[1:]:
        if not part:
            continue
        try:
            match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None)
        except OSError:
            return None
        if match is None:
            return None
        cur = match
    return cur if cur.is_file() else None


def lnk_targets(drive_c):
    drive_c = Path(drive_c)
    targets = []
    for pattern in LNK_DIRS:
        for base in drive_c.glob(pattern):
            for lnk in base.rglob("*.lnk"):
                try:
                    data = lnk.read_bytes()
                except OSError:
                    continue
                texts = [data.decode("utf-16-le", "ignore"), data.decode("latin-1", "ignore")]
                for text in texts:
                    m = WIN_EXE.search(text)
                    if m:
                        path = _resolve_ci(drive_c, m.group(0))
                        if path and str(path) not in targets:
                            targets.append(str(path))
                        break
    return targets


def _tokens(text):
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2}


def rank_candidates(new_exes, lnk, title, sizes):
    title_tokens = _tokens(title)
    lnk_set = set(lnk)
    biggest = max([sizes.get(p, 0) for p in new_exes] + [1])
    ranked = []
    for path in new_exes:
        name = os.path.basename(path).lower()
        if any(fnmatch(name, g) for g in EXCLUDE):
            continue
        score = 100.0 if path in lnk_set else 0.0
        names = _tokens(name) | _tokens(os.path.basename(os.path.dirname(path)))
        if title_tokens:
            score += 30.0 * len(title_tokens & names) / len(title_tokens)
        score += 10.0 * sizes.get(path, 0) / biggest
        ranked.append({"path": path, "score": round(score, 2),
                       "default_ok": not any(fnmatch(name, g) for g in NOT_DEFAULT)})
    ranked.sort(key=lambda c: (not c["default_ok"], -c["score"]))
    return ranked
