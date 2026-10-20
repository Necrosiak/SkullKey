"""Discs & Installers: game exe detection after an install."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))
import disks_exe as de


def touch(root, rel, data=b"MZ"):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


class SnapshotTests(unittest.TestCase):
    def test_snapshot_is_case_insensitive_and_relative(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, "Program Files/Foo/FOO.EXE")
            touch(d, "Program Files/Foo/readme.txt")
            self.assertEqual(de.snapshot_exes(d), {"program files/foo/foo.exe"})


class LnkTests(unittest.TestCase):
    def test_lnk_parse_utf16(self):
        with tempfile.TemporaryDirectory() as c:
            data = b"L\x00\x00\x00junk" + "C:\\Games\\Foo\\Foo.exe".encode("utf-16-le") + b"\x00\x00"
            touch(c, "ProgramData/Microsoft/Windows/Start Menu/Programs/Foo/Foo.lnk", data)
            touch(c, "Games/Foo/Foo.exe")
            self.assertEqual(de.lnk_targets(c), [str(Path(c) / "Games/Foo/Foo.exe")])

    def test_lnk_parse_ansi_desktop(self):
        with tempfile.TemporaryDirectory() as c:
            touch(c, "users/steamuser/Desktop/Bar.lnk", b"L\x00\x00\x00C:\\Program Files\\Bar\\bar.exe\x00")
            touch(c, "Program Files/Bar/Bar.exe")
            self.assertEqual(de.lnk_targets(c), [str(Path(c) / "Program Files/Bar/Bar.exe")])


class RankTests(unittest.TestCase):
    def test_lnk_target_beats_size(self):
        r = de.rank_candidates(["/g/big.exe", "/g/Foo.exe"], ["/g/Foo.exe"], "Something",
                               {"/g/big.exe": 900, "/g/Foo.exe": 10})
        self.assertEqual(r[0]["path"], "/g/Foo.exe")

    def test_title_match_beats_size(self):
        r = de.rank_candidates(["/g/data.exe", "/g/devil.exe"], [], "The Devil Inside",
                               {"/g/data.exe": 900, "/g/devil.exe": 10})
        self.assertEqual(r[0]["path"], "/g/devil.exe")

    def test_excludes_uninstaller_and_redist(self):
        paths = ["/g/unins000.exe", "/g/vcredist_x86.exe", "/g/DXSETUP.exe", "/g/CrashReporter.exe",
                 "/g/AutoUpdate.exe", "/g/setup.exe", "/g/game.exe"]
        r = de.rank_candidates(paths, [], "Game", {})
        self.assertEqual([c["path"] for c in r], ["/g/game.exe"])

    def test_config_never_default(self):
        r = de.rank_candidates(["/g/config.exe"], [], "Game", {})
        self.assertEqual(len(r), 1)
        self.assertFalse(r[0]["default_ok"])

    def test_empty_diff_returns_empty(self):
        self.assertEqual(de.rank_candidates([], [], "Game", {}), [])


if __name__ == "__main__":
    unittest.main()
