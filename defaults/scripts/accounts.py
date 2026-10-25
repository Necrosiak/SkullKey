#!/usr/bin/env python3
"""Switch store accounts without signing out of the store.

Each store keeps its session in a few files. Switching moves those files (and
the store's library database, which lists that account's games) into a
per-account slot and puts another slot's files in their place. Nothing is
revoked server-side and the files are only copied or moved, never opened: no
credential is parsed, printed or logged. Installed games and their install
records stay where they are.

usage: accounts.py STORE list
       accounts.py STORE switch CURRENT_NAME TARGET_NAME
       accounts.py STORE new CURRENT_NAME
       accounts.py STORE forget NAME
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Per store: session files and library database. Plain paths are relative to
# the Steam account's SkullKey space, "~/" paths to the home directory (the
# Xbox engine keeps its sign-in in ~/.xodus-keyring.ron, not in KWallet).
STORES = {
    "Epic": ["legendary/user.json", "epic.db"],
    "GOG": ["gog_auth.json", "gog.db"],
    "Amazon": ["nile/current_user.json", "nile/*.enc", "nile/library.json", "amazon.db"],
    "EA": ["ea/data/maxima/auth.toml", "ea/state.json"],
    "Xbox": ["~/.xodus-keyring.ron"],
}

# A download or game still using the store's session: never swap under it.
BUSY = {
    "Epic": ["legendary"],
    "GOG": ["gogdl"],
    "Amazon": ["nile"],
    "EA": ["maxima-cli"],
    "Xbox": ["xodus-cli", "xodus-service"],
}


def emit(kind, content):
    print(json.dumps({"Type": kind, "Content": content}))


def space():
    for var in ("SK_ACCOUNT_DIR", "DECKY_PLUGIN_RUNTIME_DIR"):
        path = os.environ.get(var, "")
        if path and Path(path).is_absolute():
            return Path(path)
    raise RuntimeError("SkullKey data directory unavailable")


def home():
    return Path(os.environ.get("HOME") or os.path.expanduser("~"))


def slots_root(store):
    root = space() / "store-accounts" / store
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    return root


def slot_dir(store, name):
    key = hashlib.sha256(name.strip().casefold().encode()).hexdigest()[:16]
    return slots_root(store) / key


def active_files(store):
    """(file, name inside a slot) for every session file present now."""
    found = []
    for pattern in STORES[store]:
        if pattern.startswith("~/"):
            base, rel, prefix = home(), pattern[2:], "home"
        else:
            base, rel, prefix = space(), pattern, "space"
        found += [(p, f"{prefix}/{p.relative_to(base)}") for p in base.glob(rel) if p.is_file()]
    return found


def slot_target(stored):
    prefix, rel = stored.split("/", 1)
    return (home() if prefix == "home" else space()) / rel


def busy(store):
    uid = str(os.getuid())
    for name in BUSY[store]:
        # Exact process name, never the command line: account names and
        # paths such as .../legendary/user.json appear in arguments.
        if subprocess.run(["pgrep", "-u", uid, "-x", name], capture_output=True).returncode == 0:
            return True
    return False


def snapshot(store, name):
    """Copy the active session into NAME's slot, replacing what was there."""
    files = active_files(store)
    if not name.strip() or not files:
        return
    target = slot_dir(store, name)
    staging = target.with_name(target.name + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(mode=0o700)
    for path, stored in files:
        dest = staging / stored
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(path, dest)
        os.chmod(dest, 0o600)
    (staging / "slot.json").write_text(json.dumps({"name": name.strip()}))
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)


def clear_active(store):
    for path, _ in active_files(store):
        path.unlink(missing_ok=True)


def restore(store, name):
    source = slot_dir(store, name)
    clear_active(store)
    for f in source.rglob("*"):
        if not f.is_file() or f.name == "slot.json":
            continue
        dest = slot_target(str(f.relative_to(source)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        os.chmod(dest, 0o600)


def saved(store):
    names = []
    for d in slots_root(store).iterdir():
        meta = d / "slot.json"
        if d.is_dir() and not d.name.endswith(".new") and meta.is_file():
            try:
                names.append(json.loads(meta.read_text())["name"])
            except (ValueError, KeyError, OSError):
                continue
    return sorted(names, key=str.casefold)


def run(argv):
    """Returns (type, content)."""
    if len(argv) < 2 or argv[0] not in STORES:
        return "Error", {"Message": "Account switching is not available for this store."}
    store, action, args = argv[0], argv[1], argv[2:]
    if action == "list":
        return "Accounts", {"Saved": saved(store)}
    if action == "forget" and len(args) == 1:
        shutil.rmtree(slot_dir(store, args[0]), ignore_errors=True)
        return "Accounts", {"Saved": saved(store)}
    if action not in ("switch", "new"):
        return "Error", {"Message": "Unknown account action."}
    if busy(store):
        return "Error", {"Message": "busy"}
    if action == "switch" and len(args) == 2:
        current, target = args
        if current.strip().casefold() == target.strip().casefold():
            return "Accounts", {"Saved": saved(store)}
        if not (slot_dir(store, target) / "slot.json").is_file():
            return "Error", {"Message": "This account is no longer saved."}
        snapshot(store, current)
        restore(store, target)
        return "Accounts", {"Saved": saved(store), "Switched": True}
    if action == "new" and len(args) == 1:
        snapshot(store, args[0])
        clear_active(store)
        return "Accounts", {"Saved": saved(store), "Cleared": True}
    return "Error", {"Message": "Unknown account action."}


def main(argv):
    try:
        kind, content = run(argv)
    except Exception:
        # The current session is only removed after its copy is complete.
        kind, content = "Error", {"Message": "Account switch failed; the current session was kept."}
    emit(kind, content)
    return kind, content


if __name__ == "__main__":
    main(sys.argv[1:])
