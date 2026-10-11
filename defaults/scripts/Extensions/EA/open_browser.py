#!/usr/bin/env python3
"""Open EA's HTTPS sign-in in the desktop environment; never log the URL."""
import os
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


def desktop_env():
    result = os.environ.copy()
    for key in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        original = result.pop("SK_EA_BROWSER_" + key, None)
        result.pop(key, None)
        if original is not None:
            result[key] = original
    result.pop("BROWSER", None)  # Avoid recursive invocation by xdg-open.
    result.pop("SK_ACCOUNT_DIR", None)
    return result


def open_login(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "accounts.ea.com"
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443)):
        raise ValueError("Unexpected sign-in destination")
    environment = desktop_env()
    # Steam's xdg-open shim can redirect HTTPS into its overlay browser, which
    # cannot dispatch EA's qrc:// callback. Prefer a real desktop browser.
    firefox = shutil.which("firefox", path=environment.get("PATH"))
    flatpak = shutil.which("flatpak", path=environment.get("PATH"))
    if firefox:
        command = [firefox, "--new-window", url]
    elif flatpak and subprocess.run([flatpak, "info", "org.mozilla.firefox", "--show-ref"],
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10).returncode == 0:
        command = [flatpak, "run", "org.mozilla.firefox", "--new-window", url]
    else:
        # gio resolves the desktop association directly, unlike Steam's shim.
        gio = shutil.which("gio", path=environment.get("PATH"))
        if not gio:
            raise RuntimeError("Desktop browser opener unavailable")
        command = [gio, "open", url]
    # New browser processes may outlive this helper; do not kill them after a
    # short timeout while the user is typing their second-factor code.
    subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("One URL required")
        open_login(sys.argv[1])
    except Exception:
        sys.exit(1)
