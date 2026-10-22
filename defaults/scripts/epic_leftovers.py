"""Epic uninstall helper: find a game's folder (from legendary's records)
and, after legendary removed the game, delete the folder only when nothing
but SkullKey's own launcher files is left in it."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OURS = {"install_deps.bat", "install.done", "launcher.log"}


def clean(path):
    try:
        entries = os.listdir(path)
    except OSError:
        return "gone"
    if not set(entries) <= OURS or any(os.path.isdir(os.path.join(path, e)) for e in entries):
        return "kept (other files)"
    for e in entries:
        os.remove(os.path.join(path, e))
    os.rmdir(path)
    return "removed"


if __name__ == "__main__":
    if sys.argv[1] == "path":
        import move_game
        print(move_game._legendary_path(sys.argv[2]) or "")
    elif sys.argv[1] == "clean":
        print("leftovers:", clean(sys.argv[2]))
