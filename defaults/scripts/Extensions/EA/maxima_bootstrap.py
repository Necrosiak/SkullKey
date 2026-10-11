#!/usr/bin/env python3
"""Linux stand-in for maxima-bootstrap (Maxima v0.14.3, GPL-3.0).

maxima-cli launches games through a `maxima-bootstrap` binary placed next to
it, but the official release only ships maxima-cli. On Unix the upstream
bootstrap only decodes its arguments and runs the game through umu/Proton
(maxima-bootstrap/src/main.rs `platform_launch` → maxima-lib
src/unix/wine.rs `run_wine_command`, CommandType::WaitForExitAndRun). This
script does exactly that, with the same environment, and nothing else.

Usage (called by maxima-cli): maxima-bootstrap launch <base64 JSON {path, args}>
"""
import base64
import json
import os
import sys


def case_insensitive(path):
    # Windows paths ignore case; resolve each component like upstream's
    # unix::fs::case_insensitive_path does for the touchup step.
    if os.path.exists(path):
        return path
    current = "/"
    for part in path.strip("/").split("/"):
        candidate = os.path.join(current, part)
        if not os.path.exists(candidate) and os.path.isdir(current):
            candidate = next((os.path.join(current, n) for n in os.listdir(current)
                              if n.lower() == part.lower()), candidate)
        current = candidate
    return current


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "launch":
        print("usage: maxima-bootstrap launch <base64>", file=sys.stderr)
        return 2
    launch = json.loads(base64.b64decode(sys.argv[2]))
    # maxima_dir() = $XDG_DATA_HOME/maxima (isolated per account by SkullKey).
    maxima = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "maxima")
    env = dict(os.environ,
               WINEPREFIX=os.path.join(maxima, "wine/prefix"),
               GAMEID="umu-0",
               PROTON_VERB="waitforexitandrun",
               PROTONPATH=os.path.join(maxima, "wine/proton"),
               STORE="ea",
               PROTON_EAC_RUNTIME=os.path.join(maxima, "wine/eac_runtime"),
               UMU_ZENITY="1",
               WINEDEBUG="fixme-all",
               LD_PRELOAD="")
    # Maxima always passes EAGameLocale=en_US; use the language chosen in
    # SkullKey's EA settings instead (games read it at startup).
    if os.environ.get("SK_EA_LOCALE"):
        env["EAGameLocale"] = os.environ["SK_EA_LOCALE"]
        # Many games (Unreal titles such as Jedi: Fallen Order) follow the
        # Windows language instead, which Wine takes from LC_ALL/LANG. The
        # inherited LC_ALL=C forced en-US (LCID 1033) whatever LANG said.
        env["LC_ALL"] = env["LANG"] = os.environ["SK_EA_LOCALE"] + ".UTF-8"
    umu = os.path.join(maxima, "wine/umu/umu-run")
    path, args = case_insensitive(launch["path"]), launch.get("args", [])
    # Old EA DOS classics (Theme Hospital, …) start through EALaunchHelper.exe,
    # which goes through the legacy EA Activation module (Qt4 ActivationUI)
    # and exits silently under Proton. The game itself is the bundled DOSBox
    # with its own dosbox.conf: run that directly, same folder, same config.
    folder = os.path.dirname(path)
    dosbox = case_insensitive(os.path.join(folder, "DOSBox.exe"))
    config = case_insensitive(os.path.join(folder, "dosbox.conf"))
    if os.path.basename(path).lower() == "ealaunchhelper.exe" and os.path.isfile(dosbox) and os.path.isfile(config):
        os.chdir(folder)
        path, args = dosbox, ["-conf", os.path.basename(config), "-noconsole"]
    os.execve(umu, [umu, path, *args], env)


if __name__ == "__main__":
    sys.exit(main())
