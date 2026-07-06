#!/usr/bin/env python3
"""Unattended daily game updates for every SkullKey store.

Run by main.py (once a day while the plugin is up) with cwd = the directory
that contains ./scripts/skullkey.sh and the DECKY_* env set. Each store is
handled with the lightest reliable mechanism it offers:

- MiHoYo : mihoyo.py autoupdate — compares installed vs live API version and
           respawns the (parallel, resumable) install worker on change.
- Amazon : `nile list-updates` gives the exact list → dispatch the store's own
           Update action only for those games.
- Epic   : legendary's `update <app> -y` is a no-op when current → dispatch
           Update for every installed game (cheap manifest check).
- GOG    : gogdl's update is incremental/no-op when current → same approach.
- Ports  : ports.py autoupdate — re-downloads a port when its GitHub release
           tag (or rolling asset date) changed; user ROMs/saves untouched.

Dispatching through ./scripts/skullkey.sh reuses the exact plumbing the UI
uses (auth env, language, DB refresh, detached progress files) — so a game
being updated even shows the progress bar if the user opens its page.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time

RUNTIME = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR",
                         os.path.expanduser("~/homebrew/data/SkullKey"))
NILE = os.path.expanduser("~/.local/share/skullkey-nile/bin/nile")
STAGGER = 10  # seconds between dispatched store updates (avoid an I/O storm)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def dispatch(store, verb, *args):
    """Fire a store action through the normal dispatcher (detached workers)."""
    cmd = ["bash", "./scripts/skullkey.sh", store, verb, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = (r.stdout or "").strip()
    log(f"{store} {verb} {' '.join(args)} → {out[:200]}")


def mihoyo():
    r = subprocess.run(
        ["python3", "./scripts/Extensions/MiHoYo/mihoyo.py", "autoupdate"],
        capture_output=True, text=True, timeout=600)
    log(f"MiHoYo autoupdate → {(r.stdout or '').strip()[:300]}")


def ports():
    r = subprocess.run(
        ["python3", "./scripts/ports.py", "autoupdate"],
        capture_output=True, text=True, timeout=1200)
    log(f"Ports autoupdate → {(r.stdout or '').strip()[:300]}")


def amazon():
    env = dict(os.environ, NILE_CONFIG_PATH=RUNTIME)
    r = subprocess.run([NILE, "list-updates", "--json"],
                       capture_output=True, text=True, timeout=120, env=env)
    try:
        ids = json.loads(r.stdout or "[]")
    except Exception:
        log(f"Amazon list-updates unparseable: {r.stdout[:120]!r}")
        return
    if not ids:
        log("Amazon: all up to date")
        return
    for gid in ids:
        gid = gid if isinstance(gid, str) else gid.get("id", "")
        if gid:
            dispatch("Amazon", "update", gid)
            time.sleep(STAGGER)


def _installed_from_db(dbfile):
    if not os.path.exists(dbfile):
        return []
    con = sqlite3.connect(dbfile)
    try:
        rows = con.execute(
            "SELECT ShortName FROM Game "
            "WHERE InstallPath IS NOT NULL AND InstallPath != ''").fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def epic():
    ids = _installed_from_db(os.path.join(RUNTIME, "epic.db"))
    log(f"Epic: {len(ids)} installed")
    for gid in ids:
        dispatch("Epic", "update", gid)   # legendary no-ops when current
        time.sleep(STAGGER)


def gog():
    ids = _installed_from_db(os.path.join(RUNTIME, "gog.db"))
    log(f"GOG: {len(ids)} installed")
    for gid in ids:
        dispatch("GOG", "update", gid)    # gogdl is incremental/no-op
        time.sleep(STAGGER)


def main():
    log("=== autoupdate_games run ===")
    for step in (mihoyo, amazon, epic, gog, ports):
        try:
            step()
        except Exception as e:
            log(f"{step.__name__} failed: {e}")
    log("=== done ===")


if __name__ == "__main__":
    main()
