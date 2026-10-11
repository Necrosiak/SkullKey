#!/usr/bin/env python3
"""Drives a game can be installed on (asked at every fresh install).

The system drive keeps each store's usual folder (~/Games/<store>, …). Any
other drive gets <mount>/SkullKey/<store>/<game>. Works on SteamOS, Bazzite
and other distros: mounts under /run/media, /media, /mnt, /var/mnt plus every
Steam library folder, deduplicated by device.

Shell usage:  drives.py dir <store>   → install folder for $SK_INSTALL_ROOT
              drives.py list          → JSON list of drives
"""
import json
import os
import pwd
import re
import sys

FILESYSTEMS = {"ext4", "ext3", "btrfs", "xfs", "f2fs", "exfat", "ntfs3", "ntfs", "fuseblk", "vfat"}
MOUNT_ROOTS = ("/run/media/", "/media/", "/mnt/", "/var/mnt/")
MIN_SIZE = 8 * 2 ** 30  # ignore tiny partitions (EFI, boot)


def user_home():
    return os.environ.get("DECKY_USER_HOME") or os.path.expanduser("~")


def _steam_libraries(home):
    vdf = os.path.join(home, ".local/share/Steam/steamapps/libraryfolders.vdf")
    try:
        with open(vdf, errors="replace") as f:
            return re.findall(r'"path"\s+"([^"]+)"', f.read())
    except OSError:
        return []


def _kind(path):
    # "ssd", "hdd" or "sd" from the kernel's rotational flag of the disk
    # holding path (partition → parent disk via sysfs).
    # btrfs reports a virtual st_dev, so use the mount's source device.
    try:
        real, source, best = os.path.realpath(path), "", ""
        with open("/proc/mounts") as f:
            for line in f:
                src, mount = line.split()[:2]
                mount = mount.replace("\\040", " ")
                if src.startswith("/dev/") and (real == mount or real.startswith(mount.rstrip("/") + "/")) \
                        and len(mount) > len(best):
                    source, best = src, mount
        if not source:
            return ""
        block = os.path.realpath("/sys/class/block/" + os.path.basename(os.path.realpath(source)))
        name = os.path.basename(block)
        if name.startswith("mmcblk"):
            return "sd"
        for candidate in (block, os.path.dirname(block)):
            flag = os.path.join(candidate, "queue/rotational")
            if os.path.exists(flag):
                with open(flag) as f:
                    return "hdd" if f.read().strip() == "1" else "ssd"
    except OSError:
        pass
    return ""


def list_drives(home=None):
    home = home or user_home()
    drives, seen = [], set()

    def add(path, label, system=False):
        try:
            st, dev = os.statvfs(path), os.stat(path).st_dev
        except OSError:
            return
        total = st.f_blocks * st.f_frsize
        if dev in seen or (not system and total < MIN_SIZE):
            return
        seen.add(dev)
        drives.append({"path": path, "label": label, "free": st.f_bavail * st.f_frsize,
                       "total": total, "system": system, "kind": _kind(path)})

    add(home, "System", True)
    try:
        with open("/proc/mounts") as f:
            for line in f:
                source, mount, fstype = line.split()[:3]
                mount = mount.replace("\\040", " ")
                if fstype in FILESYSTEMS and source.startswith("/dev/") and mount.startswith(MOUNT_ROOTS):
                    add(mount, os.path.basename(mount.rstrip("/")) or mount)
    except OSError:
        pass
    for library in _steam_libraries(home):
        add(library, os.path.basename(library.rstrip("/")) or library)
    return drives


def install_dir(store, default):
    """Folder for a new install: $SK_INSTALL_ROOT/SkullKey/<store>/ if a
    non-system drive was picked, else the store's usual folder."""
    root = os.environ.get("SK_INSTALL_ROOT", "")
    if not root or root not in [d["path"] for d in list_drives() if not d["system"]]:
        return os.path.expanduser(default)
    path = os.path.join(root, "SkullKey", store)
    os.makedirs(path, exist_ok=True)
    # Decky runs as root; games run as the user.
    try:
        user = pwd.getpwnam(os.path.basename(user_home()))
        for p in (os.path.join(root, "SkullKey"), path):
            if os.stat(p).st_uid == 0:
                os.chown(p, user.pw_uid, user.pw_gid)
    except (KeyError, OSError):
        pass  # exFAT/FAT: ownership comes from mount options
    return path + "/"


# Stores without their own record of where a game lives (Classics, miHoYo)
# remember non-default locations here.
def _paths_file():
    runtime = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR") or os.path.join(user_home(), "homebrew/data/SkullKey")
    return os.path.join(runtime, "install_paths.json")


def _load_paths():
    try:
        with open(_paths_file()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_paths(data):
    path = _paths_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(data, f, indent=1)
    os.replace(path + ".tmp", path)


def game_path(store, game, default):
    """Where an installed game lives: the remembered drive, else default."""
    return _load_paths().get(store, {}).get(game) or str(default)


def assign(store, game, default):
    """Fresh install: pick the folder from the install dialog's drive and
    remember it (or forget any old entry when the system drive is used)."""
    base = install_dir(store, "")
    data = _load_paths()
    entries = data.setdefault(store, {})
    if base:
        entries[game] = os.path.join(base, game)
    else:
        entries.pop(game, None)
    _save_paths(data)
    return entries.get(game) or str(default)


def forget(store, game):
    data = _load_paths()
    if data.get(store, {}).pop(game, None) is not None:
        _save_paths(data)


def owned_folder(store, path, default_root):
    """True if path is one of SkullKey's own install folders for store, i.e.
    safe to delete on uninstall."""
    real = os.path.realpath(path)
    parent = os.path.dirname(real)
    return (parent == os.path.realpath(str(default_root))
            or parent.endswith(os.sep + os.path.join("SkullKey", store)))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        print(json.dumps(list_drives()))
    elif len(sys.argv) >= 4 and sys.argv[1] == "dir":
        print(install_dir(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
