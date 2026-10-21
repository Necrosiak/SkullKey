import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))

import xbox_keyring as K


class KeyringTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        p = mock.patch.object(K, "KSECRETD", Path(self.tmp.name) / "ksecretd")
        p.start()
        self.addCleanup(p.stop)
        K.KSECRETD.write_text("")

    def tearDown(self):
        self.tmp.cleanup()

    def files(self):
        return [self.home / ".local/bin/ksecretd-gamescope",
                self.home / ".local/share/dbus-1/services/org.kde.secretservicecompat.service",
                self.home / ".local/share/dbus-1/services/org.freedesktop.impl.portal.desktop.kwallet.service"]

    def test_installs_three_files_with_mark(self):
        self.assertEqual(K.install(self.home), "installed")
        for f in self.files():
            self.assertIn(K.MARK, f.read_text())
        wrapper = self.files()[0].read_text()
        self.assertIn("QT_QPA_PLATFORM=xcb", wrapper)
        self.assertIn("STEAM_GAME", wrapper)
        self.assertIn(f"exec {K.KSECRETD}", wrapper)
        self.assertIn(f"Exec={self.files()[0]}", self.files()[1].read_text())

    def test_second_install_reports_present(self):
        K.install(self.home)
        self.assertEqual(K.install(self.home), "present")

    def test_foreign_file_untouched(self):
        f = self.files()[1]
        f.parent.mkdir(parents=True)
        f.write_text("[D-BUS Service]\nName=org.kde.secretservicecompat\nExec=/mine\n")
        self.assertEqual(K.install(self.home), "foreign")
        self.assertIn("/mine", f.read_text())

    def test_reinstall_updates_own_file(self):
        K.install(self.home)
        self.files()[0].write_text("#!/bin/bash\n" + K.MARK + "\nold\n")
        self.assertEqual(K.install(self.home), "installed")
        self.assertIn("QT_QPA_PLATFORM", self.files()[0].read_text())

    def test_skipped_without_ksecretd(self):
        K.KSECRETD.unlink()
        self.assertEqual(K.install(self.home), "present")
        self.assertFalse(self.files()[0].exists())


if __name__ == "__main__":
    unittest.main()
