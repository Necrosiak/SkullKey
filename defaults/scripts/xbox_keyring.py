"""Xbox tab: make the KDE Wallet password prompt visible in Game Mode.

The Xodus engine stores the Microsoft sign-in through the Secret Service
(KWallet on KDE systems). In gamescope the wallet prompt tries Wayland, lands
on the wrong X display and is never shown. A small wrapper, started by D-Bus
instead of ksecretd, puts it on the games' XWayland and tags it with the
focused app id so gamescope displays it. Desktop Mode is unchanged.

Only user files are written; a file SkullKey did not write is never replaced."""

import os
from pathlib import Path

MARK = "# SkullKey xbox keyring v1"
KSECRETD = Path("/usr/bin/ksecretd")
SERVICES = ("org.kde.secretservicecompat", "org.freedesktop.impl.portal.desktop.kwallet")


def _wrapper():
    return f"""#!/bin/bash
{MARK}
# In Game Mode, show the KWallet prompt on the XWayland where games run and
# tag it with the focused app id, so gamescope displays it above that app.
if pgrep -u "$UID" -f gamescope-session >/dev/null; then
  pid=$(pgrep -u "$UID" -n -f "reaper SteamLaunch")
  [ -n "$pid" ] || pid=$(pgrep -u "$UID" -x steam | head -1)
  d=$(tr "\\0" "\\n" < /proc/$pid/environ 2>/dev/null | sed -n "s/^DISPLAY=//p")
  export DISPLAY="${{d:-:1}}" QT_QPA_PLATFORM=xcb XDG_SESSION_TYPE=x11
  unset WAYLAND_DISPLAY
  self=$$
  (
    while kill -0 "$self" 2>/dev/null; do
      # The game being launched (no window yet), else the focused app.
      app=$(pgrep -u "$UID" -n -a -f "reaper SteamLaunch" | grep -o "AppId=[0-9]*" | cut -d= -f2)
      [ -n "$app" ] || app=$(DISPLAY=:0 xprop -root GAMESCOPE_FOCUSED_APP 2>/dev/null | grep -o "[0-9]*$")
      for w in $(xdotool search --pid "$self" 2>/dev/null); do
        [ -n "$app" ] && [ "$app" != 769 ] && xprop -id "$w" -f STEAM_GAME 32c -set STEAM_GAME "$app" 2>/dev/null
      done
      sleep 1
    done
  ) </dev/null >/dev/null 2>&1 &
fi
exec {KSECRETD} "$@"
"""


def _service(name, wrapper):
    return f"[D-BUS Service]\n{MARK}\nName={name}\nExec={wrapper}\n"


def _owner(home):
    try:
        st = home.stat()
        return st.st_uid, st.st_gid
    except OSError:
        return None


def install(home):
    """"installed" (written or refreshed), "present" (nothing to do) or
    "foreign" (a user file is in the way; left alone)."""
    home = Path(home)
    if not KSECRETD.exists():
        return "present"
    wrapper = home / ".local/bin/ksecretd-gamescope"
    plan = {wrapper: _wrapper()}
    for name in SERVICES:
        plan[home / ".local/share/dbus-1/services" / f"{name}.service"] = _service(name, wrapper)
    for path in plan:
        if path.exists() and MARK not in path.read_text(errors="ignore"):
            return "foreign"
    if all(p.exists() and p.read_text(errors="ignore") == text for p, text in plan.items()):
        return "present"
    ids = _owner(home)
    for path, text in plan.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if path == wrapper:
            path.chmod(0o755)
        if ids and os.geteuid() == 0:
            for p in (path, path.parent):
                try:
                    os.chown(p, *ids)
                except OSError:
                    pass
    return "installed"
