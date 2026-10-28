#!/usr/bin/env python3
"""Errors a player can act on, for every store and tool.

- Before a download starts: is there room on the chosen drive?
- Any error a store tool reports (directly or while installing) gets a code
  (no_space, network, auth…) that the panel words in the player's language,
  with the tool's own text kept underneath as details.
- Every error is written to its own log file, credentials masked, and the
  panel tells the player where it is so they can attach it to a report.
"""
import hashlib
import os
import re
import shutil
import time

MARGIN = 1 << 30           # headroom left after an install
MIN_FREE = 2 << 30         # nothing installs below this, size known or not
KEEP_LOGS = 50

# First match wins: the most specific causes come first.
CAUSES = (
    ("disk_full", r"no space left|enospc|errno 28|not enough (?:\w+ )?(?:disk )?space|disk (?:is )?full"
                  r"|insufficient (?:disk )?space|out of disk"),
    ("permission", r"permission denied|read-only file system|eacces|errno 13|errno 30|operation not permitted"),
    ("auth", r"\b401\b|unauthori[sz]ed|token (?:has )?expired|invalid[_ ]grant|not logged in|login (?:required|expired)"
             r"|re-?authenticat|session expired|sign in again|explicit ea authentication required"),
    ("unavailable", r"\b403\b|forbidden|http error 404|\b404 not found|not owned|no entitlement|do(?:es)? not own"
                    r"|not available in your (?:region|country)|ownership"),
    ("corrupt", r"hash mismatch|checksum|corrupt|crc (?:error|mismatch)|verification failed|integrity"),
    ("network", r"timed? ?out|connection (?:reset|refused|aborted|error|closed)|temporary failure in name resolution"
                r"|name or service not known|could not resolve|network is unreachable|max retries exceeded"
                r"|ssl|certificate verify|remote end closed|http error 5\d\d|status(?: code)? 5\d\d|econnreset"
                r"|failed to fetch|download failed|no route to host"),
    ("tool_missing", r"command produced no output|command not found|bad interpreter|modulenotfounderror"
                     r"|no module named"),
)
_CAUSES = [(code, re.compile(rx, re.I)) for code, rx in CAUSES]

_SECRET_LINE = re.compile(r"token|authorization|bearer|cookie|password|passwd|secret|signature|xuid|xbl3\.0"
                          r"|refresh_|access_|client_secret|\bcode=", re.I)
_LONG_OPAQUE = re.compile(r"[A-Za-z0-9_+/=-]{40,}")
_EMAIL = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_HTML = re.compile(r"<br\s*/?>", re.I)


def classify(text):
    """A cause code for an error text, or "unknown"."""
    text = _HTML.sub("\n", str(text or ""))
    return next((code for code, rx in _CAUSES if rx.search(text)), "unknown")


def sanitize(text, limit=20000):
    """Error text safe to keep in a file a player may share."""
    out = []
    for line in _HTML.sub("\n", str(text or "")).splitlines():
        if _SECRET_LINE.search(line):
            out.append("[line hidden: it looked like it carried a credential]")
            continue
        line = _LONG_OPAQUE.sub("[…]", line)
        out.append(_EMAIL.sub("[email]", line))
    return "\n".join(out)[-limit:]


# ── free space ──────────────────────────────────────────────────────────────

def free_bytes(path):
    p = os.path.abspath(os.path.expanduser(path or "~"))
    while p != "/" and not os.path.exists(p):
        p = os.path.dirname(p)
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return None


def needed_bytes(size_content):
    """Bytes a game will take, from a store's GameSize content (0 = unknown)."""
    if not isinstance(size_content, dict):
        return 0
    values = []
    for key in ("DiskBytes", "DownloadBytes"):
        try:
            values.append(int(size_content.get(key) or 0))
        except (TypeError, ValueError):
            pass
    return max(values, default=0)


def space_problem(target, need, extra=0):
    """None when the drive has room, else what the panel needs to say so."""
    free = free_bytes(target)
    if free is None:
        return None
    want = (need + MARGIN if need else MIN_FREE) + extra
    if free >= want:
        return None
    return {"Code": "no_space", "Need": (need + extra) if need else want, "Free": free,
            "Drive": os.path.abspath(os.path.expanduser(target or "~"))}


def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB", "MB") else f"{n:.1f} {unit}"
        n /= 1024


ENGLISH = {
    "no_space": "Not enough free space on {drive}: this game needs about {need} and only {free} is free. "
                "Free up some space or choose another drive.",
    "disk_full": "The drive ran out of space during the download. Free up some space or choose another drive, "
                 "then try again.",
    "permission": "SkullKey cannot write to the install folder (no permission, or the drive is read-only). "
                  "Choose another drive.",
    "auth": "Your sign-in to this store has expired. Log out and log in again from the store's tab, then try again.",
    "unavailable": "The store refused this download: the game is not available for this account or region.",
    "corrupt": "Some downloaded files were damaged. Try again; if it happens again, check the drive.",
    "network": "The download stopped because of a network problem (connection lost, or the store's server "
               "is not answering). Check your connection and try again.",
    "tool_missing": "A tool SkullKey needs for this store did not start. Open About > Dependencies and "
                    "install them again.",
    "unknown": "Something went wrong.",
}


def english(code, need=0, free=0, drive=""):
    return ENGLISH.get(code, ENGLISH["unknown"]).format(need=human(need), free=human(free), drive=drive or "the drive")


# ── error logs ──────────────────────────────────────────────────────────────

_recent = {}


def write_log(log_dir, action_set, action_name, code, message, details="", context=None, dedupe_s=600):
    """One file per error; the same error repeated by progress polling is
    written once. Returns the file path, or "" when nothing was written."""
    key = hashlib.sha1(f"{action_set}|{action_name}|{code}|{message}|{details}".encode(
        "utf-8", "replace")).hexdigest()
    now = time.time()
    for k, t in list(_recent.items()):
        if now - t[0] > dedupe_s:
            _recent.pop(k, None)
    if key in _recent:
        return _recent[key][1]
    folder = os.path.join(log_dir, "errors")
    try:
        os.makedirs(folder, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "-", f"{action_set}-{action_name}")[:60]
        path = os.path.join(folder, time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(now)) + f"_{safe}_{key[:6]}.log")
        lines = [f"SkullKey error — {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))}",
                 f"Store / action: {action_set} / {action_name}",
                 f"Cause: {code}",
                 f"Shown to the player: {sanitize(message)}"]
        for k, v in (context or {}).items():
            lines.append(f"{k}: {sanitize(v)}")
        if details:
            lines += ["", "Details from the tool:", sanitize(details)]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        logs = sorted(os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".log"))
        for old in logs[:-KEEP_LOGS]:
            try:
                os.remove(old)
            except OSError:
                pass
    except OSError:
        return ""
    _recent[key] = (now, path)
    return path
