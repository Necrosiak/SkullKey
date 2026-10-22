import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))
import epic_leftovers as el  # noqa: E402


class EpicLeftoversTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name) / "Game"
        self.d.mkdir()

    def test_only_our_files_removed_with_folder(self):
        for f in ("install_deps.bat", "install.done", "launcher.log"):
            (self.d / f).write_text("x")
        self.assertEqual(el.clean(str(self.d)), "removed")
        self.assertFalse(self.d.exists())

    def test_crash_report_folder_counts_as_leftover(self):
        (self.d / "launcher.log").write_text("x")
        (self.d / ".sentry-native").mkdir()
        (self.d / ".sentry-native" / "report").write_text("x")
        self.assertEqual(el.clean(str(self.d)), "removed")

    def test_other_files_kept(self):
        (self.d / "launcher.log").write_text("x")
        (self.d / "save.dat").write_text("x")
        self.assertEqual(el.clean(str(self.d)), "kept (other files)")
        self.assertTrue((self.d / "save.dat").exists())

    def test_subfolder_kept(self):
        (self.d / "Saved").mkdir()
        self.assertEqual(el.clean(str(self.d)), "kept (other files)")
