"""Discs & Installers: disc image extraction through a stub 7z."""
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))
import disks_extract as dx

STUB = r"""#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if args[0] == "l":
    print("Path = x\nSize = %s\n" % os.environ.get("STUB_SIZE", "100"))
    sys.exit(0)
if args[0] == "x":
    out = next(a[2:] for a in args if a.startswith("-o"))
    os.makedirs(out, exist_ok=True)
    print(" 50%")
    open(os.path.join(out, "setup.exe"), "w").write(os.path.basename(args[-1]))
    print("100%")
    sys.exit(int(os.environ.get("STUB_FAIL", "0")))
"""


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.bin = tempfile.TemporaryDirectory()
        stub = Path(self.bin.name) / "7z"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.env = patch.dict(os.environ, {"PATH": self.bin.name + os.pathsep + os.environ["PATH"]})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.bin.cleanup()

    def test_refuses_when_space_short(self):
        with tempfile.TemporaryDirectory() as d, \
                patch.dict(os.environ, {"STUB_SIZE": str(10 << 30), "SK_DISKS_FAKE_FREE": str(1 << 30)}):
            iso = Path(d) / "game.iso"
            iso.write_bytes(b"x")
            dest = Path(d) / "out"
            with self.assertRaises(dx.NotEnoughSpace) as cm:
                dx.extract_images([str(iso)], str(dest))
            self.assertEqual(cm.exception.needed, 10 << 30)
            self.assertFalse(dest.exists())

    def test_multidisc_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            parts = []
            for n in (1, 2):
                p = Path(d) / f"Game (Disc {n}).iso"
                p.write_bytes(b"x")
                parts.append(str(p))
            seen = []
            dirs = dx.extract_images(parts, str(Path(d) / "out"), progress=seen.append)
            self.assertEqual([Path(x).name for x in dirs], ["disc1", "disc2"])
            self.assertEqual((Path(dirs[1]) / "setup.exe").read_text(), "Game (Disc 2).iso")
            self.assertTrue(seen and max(seen) == 100)

    def test_cue_bin_extracts_the_data_file(self):
        with tempfile.TemporaryDirectory() as d:
            cue, data = Path(d) / "Old.cue", Path(d) / "Old.bin"
            cue.write_text('FILE "Old.bin" BINARY\n')
            data.write_bytes(b"x")
            dirs = dx.extract_images([str(cue), str(data)], str(Path(d) / "out"))
            self.assertEqual(len(dirs), 1)
            self.assertEqual((Path(dirs[0]) / "setup.exe").read_text(), "Old.bin")

    def test_missing_7z(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"PATH": "/nonexistent"}):
            iso = Path(d) / "g.iso"
            iso.write_bytes(b"x")
            with self.assertRaises(dx.ExtractError):
                dx.extract_images([str(iso)], str(Path(d) / "out"))

    def test_failure_raises_and_cleans(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"STUB_FAIL": "2"}):
            iso = Path(d) / "g.iso"
            iso.write_bytes(b"x")
            with self.assertRaises(dx.ExtractError):
                dx.extract_images([str(iso)], str(Path(d) / "out"))
            self.assertFalse((Path(d) / "out").exists())

    def test_unicode_dest(self):
        with tempfile.TemporaryDirectory() as d:
            iso = Path(d) / "Jeu été.iso"
            iso.write_bytes(b"x")
            dirs = dx.extract_images([str(iso)], str(Path(d) / "Disques" / "jeu été"))
            self.assertTrue((Path(dirs[0]) / "setup.exe").exists())


if __name__ == "__main__":
    unittest.main()
