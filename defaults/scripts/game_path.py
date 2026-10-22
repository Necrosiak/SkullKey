"""Folder(s) an installed game occupies, for the "Installed games" page.
Usage: game_path.py <ActionSet> <shortname>  -> one path per line (may be none).
Run with the system Python, like the store scripts."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "shared"))
RUNTIME = Path(os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", os.path.expanduser("~/homebrew/data/SkullKey")))


def paths(set_name, shortname):
    if set_name == "XboxActions":
        g = (json.loads((RUNTIME / "xbox" / "state.json").read_text()).get("games") or {}).get(shortname) or {}
        return [g.get("root")]
    if set_name == "DisksActions":
        g = json.loads((RUNTIME / "disks" / "state.json").read_text())["games"].get(shortname) or {}
        out = [g.get("root")]
        exe = g.get("exe") or ""
        # Installed inside its Wine prefix: count the game's own folder there.
        if "/drive_c/" in exe and not exe.startswith(str(g.get("root") or "\0")):
            rel = exe.split("/drive_c/", 1)[1].split("/")
            out.append(exe.split("/drive_c/", 1)[0] + "/drive_c/" + "/".join(rel[:3 if len(rel) > 3 else len(rel) - 1]))
        return out
    if set_name == "EAActions":
        sys.path.insert(0, str(HERE / "Extensions" / "EA"))
        import ea
        return [str(ea.game_dir(shortname))]
    if set_name == "MiHoYoActions":
        sys.path.insert(0, str(HERE / "Extensions" / "MiHoYo"))
        import mihoyo
        return [str(mihoyo._game_dir(shortname))]
    import move_game
    return [move_game.current_path(set_name, shortname)]


if __name__ == "__main__":
    try:
        for p in paths(sys.argv[1], sys.argv[2]):
            if p and os.path.isdir(p):
                print(p)
    except Exception as e:  # noqa: BLE001
        print(f"game_path: {type(e).__name__}: {e}", file=sys.stderr)
