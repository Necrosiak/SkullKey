"""Xbox tab: thin wrapper around xodus-cli (the Xodus engine).

Never logs or returns account e-mails, tokens, URLs or the gamer picture:
error messages keep only harmless lines of the engine's output."""

import json
import os
import re
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import xbox_tools

PROGRESS_PREFIX = "NEXUS_PROGRESS "
PHASES = {"initializing", "metadata", "downloading", "finalizing", "complete", "failed"}
_PRIVATE = re.compile(r"@|token|http|bearer|cookie|password|secret", re.I)


class CliError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _binary():
    path = xbox_tools.cli_path()
    if not path:
        raise CliError(-1, "The Xbox engine is not installed.")
    return path


def _env():
    uid = os.getuid()
    # Decky inherits root's session variables; the stored account lives in
    # the player's Secret Service, on their session bus.
    env = dict(os.environ, XODUS_LOG="off", RUST_LOG="off", XDG_RUNTIME_DIR=f"/run/user/{uid}",
               DBUS_SESSION_BUS_ADDRESS=f"unix:path=/run/user/{uid}/bus")
    # Decky's PyInstaller libraries break system binaries.
    orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    else:
        env.pop("LD_LIBRARY_PATH", None)
    return env


def _safe_tail(text):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip() and not _PRIVATE.search(l)]
    return lines[-1][:200] if lines else "The Xbox engine reported an error."


def run_json(args, timeout=60):
    try:
        p = subprocess.run([str(_binary()), *args, "--json"], capture_output=True, text=True,
                           timeout=timeout, env=_env())
    except subprocess.TimeoutExpired:
        raise CliError(-2, "The Xbox engine did not answer in time.")
    if p.returncode != 0:
        raise CliError(p.returncode, _safe_tail(p.stderr or p.stdout))
    try:
        return json.loads(p.stdout)
    except ValueError:
        raise CliError(-3, "The Xbox engine returned an unreadable answer.")


def account():
    return {"stored": bool(run_json(["account"]).get("stored"))}


def profile():
    data = run_json(["profile"])
    return {k: v for k, v in data.items() if k in ("gamertag", "subscription")}


def library(market):
    return run_json(["library", "--market", market]).get("entitlements") or []


def resolve(product, market, strict=False):
    try:
        return run_json(["resolve-package", product, "--market", market], timeout=30)
    except CliError:
        if strict:
            raise
        return None


def logout():
    subprocess.run([str(_binary()), "logout"], capture_output=True, timeout=30, env=_env())


def start_streaming(product, dest, market, content_id=None):
    args = [str(_binary()), "streaming", product, str(dest), "--market", market, "--progress-json", "--control-stdin"]
    if content_id:
        args += ["--selected-content-id", content_id]
    return subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, env=_env(), start_new_session=True)


def parse_progress(line):
    line = (line or "").strip()
    if not line.startswith(PROGRESS_PREFIX) or len(line) > 4096:
        return None
    try:
        v = json.loads(line[len(PROGRESS_PREFIX):])
    except ValueError:
        return None
    if not isinstance(v, dict) or v.get("schema") != 1 or v.get("event") != "progress" or v.get("phase") not in PHASES:
        return None
    done, total = v.get("completedBytes"), v.get("totalBytes")
    percent = min(99.9, done / total * 100) if isinstance(total, int) and total > 0 and isinstance(done, int) else None
    if v["phase"] == "complete":
        percent = 100.0
    return {"phase": v["phase"], "percent": percent, "done": done, "total": total,
            "rate": v.get("bytesPerSecond") or 0, "paused": bool(v.get("paused"))}


def control(proc, command):
    """command: "pause" or "resume"."""
    proc.stdin.write(json.dumps({"schema": 1, "command": command}) + "\n")
    proc.stdin.flush()


def cancel(proc, grace=5):
    """SIGINT (what Nexus sends), then SIGKILL on the whole group."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGINT)
    except OSError:
        pass
    deadline = time.time() + grace
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.1)
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait(5)


# ── installed package manifest ───────────────────────────────────────────────

def _strip(tag):
    return tag.rsplit("}", 1)[-1]


def _find(root, name):
    for el in root.iter():
        if _strip(el.tag) == name:
            return el
    return None


def inspect_game(directory):
    d = Path(directory)
    entries = {p.name.lower(): p for p in d.iterdir()} if d.is_dir() else {}
    cfg = entries.get("microsoftgame.config")
    appx = entries.get("appxmanifest.xml")
    info = {"title": d.name, "executable": None, "storeId": None, "publisher": None}
    for src, kind in ((cfg, "config"), (appx, "appx")):
        if not src:
            continue
        try:
            root = ET.fromstring(src.read_text(errors="ignore"))
        except ET.ParseError:
            continue
        if kind == "config":
            sv, ex, sid = _find(root, "ShellVisuals"), _find(root, "Executable"), _find(root, "StoreId")
            if sv is not None:
                info["title"] = sv.get("DefaultDisplayName") or info["title"]
                info["publisher"] = sv.get("PublisherDisplayName")
            if ex is not None:
                info["executable"] = ex.get("Name")
            if sid is not None and sid.text:
                info["storeId"] = sid.text.strip()
        elif not info["executable"]:
            app, dn = _find(root, "Application"), _find(root, "DisplayName")
            if app is not None:
                info["executable"] = app.get("Executable")
            if dn is not None and dn.text and info["title"] == d.name:
                info["title"] = dn.text.strip()
    return info
