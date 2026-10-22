"""Xbox tab: one Proton prefix per game and the Wine runner xodus-cli uses.

The runner environment is adapted from Xodus Nexus src/main/proton.ts
(MIT, see third_party/xodus-nexus/LICENSE).

Immutable systems (Bazzite, SteamOS…): Wine maps "/" to Z:, and "/" is a
read-only image reporting 0 bytes free, so games that check free space on
their own drive refuse to patch. A Y: drive pointing at the home volume makes
Wine pick Y:\\… for every path under it. Z: must stay "/" (Wine needs it to
convert Linux paths)."""

import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

import xbox_tools


class PrefixError(Exception):
    pass


def prefix_dir(product_id):
    return xbox_tools.XBOX_DIR / "prefixes" / product_id


def home_root():
    if os.path.isdir("/var/home"):
        return "/var/home"
    return str(Path(os.path.realpath(Path.home())).parent)


def ensure_home_drive(pfx):
    drive = Path(pfx) / "dosdevices" / "y:"
    if drive.is_symlink() or drive.exists():
        return
    drive.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(home_root(), drive)


def steam_root(product_id=None):
    """The real Steam folder, like Xodus Nexus (Proton finds Steam's own
    runtimes there); a private stand-in only when Steam is not installed."""
    real = Path.home() / ".steam" / "root"
    if real.is_dir():
        return real
    return prefix_dir(product_id) / "steam" if product_id else real


def _prefix_ready(pfx):
    return (pfx / "system.reg").exists() and (pfx / "drive_c" / "windows" / "system32" / "kernel32.dll").exists()


def ensure_prefix(product_id):
    root = prefix_dir(product_id)
    pfx = root / "pfx"
    runtime = xbox_tools.runtime_root()
    if not runtime:
        raise PrefixError("The Xbox runtime is not installed.")
    if not _prefix_ready(pfx):
        steam = steam_root(product_id)
        steam.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("LD_LIBRARY_PATH")}
        env.update(STEAM_COMPAT_DATA_PATH=str(root), STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam),
                   SteamAppId="0", SteamGameId="0", UMU_ID="xodus-nexus", UMU_USE_STEAM="0")
        p = subprocess.run(["python3", str(runtime / "proton"), "run", "cmd", "/c", "exit"],
                           env=env, capture_output=True, text=True, timeout=600)
        if not _prefix_ready(pfx):
            raise PrefixError(f"The game prefix could not be prepared (code {p.returncode}).")
    ensure_home_drive(pfx)
    return root


def rebase_runtime_links(pfx, runtimes_dir):
    """After a runtime update, prefix links into the old runtime folder are
    pointed at the same file in the current one."""
    current = xbox_tools.runtime_root()
    if not current:
        return
    runtimes_dir = str(Path(runtimes_dir))
    for dirpath, dirnames, filenames in os.walk(Path(pfx) / "drive_c" / "windows"):
        for name in dirnames + filenames:
            link = Path(dirpath) / name
            if not link.is_symlink():
                continue
            target = os.readlink(link)
            if not target.startswith(runtimes_dir + os.sep) or target.startswith(str(current) + os.sep):
                continue
            rel = Path(target).relative_to(runtimes_dir).parts[1:]
            link.unlink()
            os.symlink(current.joinpath(*rel), link)


def _components(runtime, pfx):
    """Copy the runtime's patched DLLs into system32 after checking their
    SHA-256 against XODUS_NEXUS_PATCH.json. Returns the feature list."""
    try:
        meta = json.loads((runtime / "XODUS_NEXUS_PATCH.json").read_text())
    except (OSError, ValueError):
        return []
    features = meta.get("features") or []
    wanted = {"wine-winhttp-http2-v1": "libnghttp2.dll", "winrt-json-v1": "windows.web.dll",
              "hlsl-state-keywords-v1": "libvkd3d-shader-1.dll", "appstate-registration-v1": "twinapi.appcore.dll"}
    names = [dll for feat, dll in wanted.items() if feat in features]
    dxvk = ["d3d8.dll", "d3d9.dll", "d3d10core.dll", "d3d11.dll", "dxgi.dll"]
    if "dxvk-constant-compare-v1" in features:
        names += dxvk
    verified = []
    for name in names:
        lib = "vkd3d" if name == "libvkd3d-shader-1.dll" else "wine/dxvk" if name in dxvk else "wine"
        data = (runtime / "files" / "lib" / lib / "x86_64-windows" / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != (meta.get("components") or {}).get(name):
            raise PrefixError(f"The Xbox runtime has an invalid {name}.")
        verified.append((name, data))
    sys32 = pfx / "drive_c" / "windows" / "system32"
    for name, data in verified:
        target = sys32 / name
        if target.is_symlink() or not target.exists() or target.read_bytes() != data:
            tmp = target.with_name(name + ".skullkey")
            tmp.write_bytes(data)
            if target.is_symlink():
                target.unlink()
            tmp.replace(target)
    return features


def write_runner(product_id):
    root = prefix_dir(product_id)
    pfx = root / "pfx"
    runtime = xbox_tools.runtime_root()
    if not runtime:
        raise PrefixError("The Xbox runtime is not installed.")
    rebase_runtime_links(pfx, runtime.parent)
    features = _components(runtime, pfx)
    files = runtime / "files"
    host = "wine-host-libraries-v1" in features
    libdirs = [str(files / "lib" / d) for d in ("x86_64-linux-gnu", "aarch64-linux-gnu", "i386-linux-gnu")]
    libs = ":".join((["/usr/lib"] if host else []) + libdirs)
    gst = "/usr/lib/gstreamer-1.0" if host else ":".join(d + "/gstreamer-1.0" for d in libdirs)
    overrides = "dxgi=n;d3d11=n;d3d10core=n;d3d9=n;d3d12=n;d3d12core=n"
    if "wine-winhttp-http2-v1" in features:
        overrides += ";winhttp=b;libnghttp2=n"
    if "dxvk-constant-compare-v1" in features:
        overrides += ";d3d8=n"
    q = shlex.quote
    wine, server = files / "bin" / "wine", files / "bin" / "wineserver"
    lines = [
        "#!/bin/sh",
        f"export WINEPREFIX={q(str(pfx))}",
        "export WINEARCH='win64'",
        f"export WINEDLLPATH={q(str(files / 'lib' / 'vkd3d') + ':' + str(files / 'lib' / 'wine'))}",
        f"export LD_LIBRARY_PATH={q(libs)}",
        f"export ESPEAK_DATA_PATH={q(str(files / 'share'))}",
        f"export GST_PLUGIN_SYSTEM_PATH_1_0={q(gst)}",
        "export GST_PLUGIN_PATH_1_0=''",
        f"export WINE_GST_REGISTRY_DIR={q(str(root / 'gstreamer-1.0'))}",
        f"export MEDIACONV_BLANK_VIDEO_FILE={q(str(files / 'share' / 'media' / 'blank.mkv'))}",
        f"export MEDIACONV_BLANK_AUDIO_FILE={q(str(files / 'share' / 'media' / 'blank.ptna'))}",
        f"export PATH={q(str(files / 'bin'))}:\"$PATH\"",
        f"export WINEDLLOVERRIDES={q(overrides)}",
        "export WINE_LARGE_ADDRESS_AWARE='1'",
        'if [ "${1:-}" = "--skullkey-stop-prefix" ]; then',
        f"  exec {q(str(server))} -k",
        "fi",
        "launch_status=0",
        f"{q(str(wine))} \"$@\" || launch_status=$?",
        "wait_status=0",
        f"{q(str(server))} -w || wait_status=$?",
        'if [ "$launch_status" -ne 0 ]; then exit "$launch_status"; fi',
        'exit "$wait_status"',
        "",
    ]
    runner = root / "skullkey-xbox-wine"
    tmp = runner.with_suffix(".tmp")
    tmp.write_text("\n".join(lines))
    tmp.chmod(0o700)
    tmp.replace(runner)
    return runner
