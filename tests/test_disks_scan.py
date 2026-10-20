"""Discs & Installers: source detection (scan, optical, autorun, titles)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))
import disks_scan as ds


def touch(root, rel, size=10):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)
    return p


class ScanTests(unittest.TestCase):
    def test_scan_groups_gog_parts(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("setup_game_1.0.exe", "setup_game_1.0-1.bin", "setup_game_1.0-2.bin"):
                touch(d, n)
            entries = ds.scan_folder(d)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["kind"], "installer")
            self.assertEqual(len(entries[0]["parts"]), 3)
            self.assertTrue(entries[0]["path"].endswith("setup_game_1.0.exe"))

    def test_scan_groups_multidisc(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, "Game (Disc 2).iso")
            touch(d, "Game (Disc 1).iso")
            entries = ds.scan_folder(d)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["kind"], "image")
            self.assertEqual([Path(p).name for p in entries[0]["parts"]],
                             ["Game (Disc 1).iso", "Game (Disc 2).iso"])

    def test_scan_cue_bin_is_one_image(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, "Old Game.cue")
            touch(d, "Old Game.bin")
            entries = ds.scan_folder(d)
            self.assertEqual([e["kind"] for e in entries], ["image"])
            self.assertTrue(entries[0]["path"].endswith(".cue"))

    def test_scan_folder_with_setup(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, "MyGame/setup.exe")
            touch(d, "MyGame/data/file.cab")
            entries = ds.scan_folder(d)
            self.assertEqual([(e["kind"], Path(e["path"]).name) for e in entries], [("folder", "MyGame")])

    def test_scan_depth_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as other:
            touch(d, "a/b/c/deep.iso")          # depth 4 from root: ignored
            touch(d, "a/b/ok.iso")
            touch(other, "linked.iso")
            os.symlink(other, Path(d) / "link")
            names = sorted(Path(e["path"]).name for e in ds.scan_folder(d))
            self.assertEqual(names, ["ok.iso"])

    def test_scan_unicode_paths(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, "Téléchargements/My Games/Jeu été.iso")
            entries = ds.scan_folder(str(Path(d) / "Téléchargements"))
            self.assertEqual(len(entries), 1)
            self.assertIn("Jeu été.iso", entries[0]["path"])


class AutorunTests(unittest.TestCase):
    def test_parse_autorun(self):
        self.assertEqual(ds.parse_autorun("[AutoRun]\r\nOPEN=Autorun.exe\r\nicon=a.ico"), "Autorun.exe")
        self.assertEqual(ds.parse_autorun("[autorun]\nshellexecute=Setup.exe /x"), "Setup.exe /x")
        self.assertIsNone(ds.parse_autorun("[Other]\nopen=x.exe"))

    def test_find_installers_prefers_setup_over_menu(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "autorun.inf").write_text("[autorun]\nopen=Autorun.exe\n")
            touch(d, "Autorun.exe")
            touch(d, "Setup.exe")
            found = [Path(p).name for p in ds.find_installers(d)]
            self.assertEqual(found[:2], ["Setup.exe", "Autorun.exe"])

    def test_find_installers_autorun_target_first_when_not_menu(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "autorun.inf").write_text("[autorun]\nopen=Install\\Inst.exe\n")
            touch(d, "Install/Inst.exe")
            touch(d, "install.exe")
            self.assertEqual(Path(ds.find_installers(d)[0]).name, "Inst.exe")

    def test_find_installers_none(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, "Game.exe")
            self.assertEqual(ds.find_installers(d), [])


class OpticalTests(unittest.TestCase):
    def test_optical_volumes(self):
        with tempfile.TemporaryDirectory() as d:
            mounts = Path(d) / "mounts"
            mounts.write_text("/dev/sr0 /run/media/u/GAME_DVD udf ro 0 0\n"
                              "/dev/sda1 /run/media/u/USB vfat rw 0 0\n"
                              "/dev/sr1 /run/media/u/My\\040Disc iso9660 ro 0 0\n")
            vols = ds.optical_volumes(mounts=str(mounts))
            self.assertEqual([(v["device"], v["label"]) for v in vols],
                             [("/dev/sr0", "GAME_DVD"), ("/dev/sr1", "My Disc")])
            self.assertEqual(vols[1]["mountpoint"], "/run/media/u/My Disc")


class TitleTests(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(ds.clean_title("GAME_DVD"), "Game")
        self.assertEqual(ds.clean_title("STAR_RACER"), "Star Racer")
        self.assertEqual(ds.clean_title("setup_the_witcher_2.1.0.exe"), "The Witcher")
        self.assertEqual(ds.clean_title("Half-Life (Disc 1).iso"), "Half-Life")
        self.assertEqual(ds.clean_title("Old Game.cue"), "Old Game")

    def test_make_slug(self):
        self.assertEqual(ds.make_slug("AC/DC: Live.", set()), "ac-dc-live")
        self.assertEqual(ds.make_slug("Game", {"game"}), "game-2")
        self.assertEqual(ds.make_slug("Game", {"game", "game-2"}), "game-3")
        self.assertEqual(ds.make_slug("🎮", set()), "game")
        self.assertEqual(ds.make_slug("Jeu été", set()), "jeu-ete")


if __name__ == "__main__":
    unittest.main()
