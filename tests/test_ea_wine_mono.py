"""Managed DirectX needs wine-mono in Maxima's prefix (Syndicate, #10)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts" / "Extensions" / "EA"))

import ea


class WineMonoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.wine = self.root / "data/maxima/wine"
        self.windows = self.wine / "prefix/pfx/drive_c/windows"
        self.framework = self.windows / "Microsoft.NET/Framework/v4.0.30319"
        patcher = mock.patch.object(ea, "root", return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def add_package(self, *versions):
        for version in versions:
            msi = self.wine / f"proton/files/share/wine/mono/{version}/support/winemono-support.msi"
            msi.parent.mkdir(parents=True)
            msi.touch()
        umu = self.wine / "umu/umu-run"
        umu.parent.mkdir(parents=True)
        umu.touch()

    def test_new_prefix_is_left_to_proton(self):
        with mock.patch.object(subprocess, "run") as run:
            self.assertEqual(ea.ensure_wine_mono({}), "no-prefix")
        run.assert_not_called()

    def test_present_framework_runs_nothing(self):
        self.framework.mkdir(parents=True)
        self.add_package("wine-mono-11.3.0")
        with mock.patch.object(subprocess, "run") as run:
            self.assertEqual(ea.ensure_wine_mono({}), "present")
        run.assert_not_called()

    def test_missing_package_is_reported(self):
        self.windows.mkdir(parents=True)
        self.assertEqual(ea.ensure_wine_mono({}), "no-package")

    def test_missing_framework_installs_versioned_package_in_maxima_prefix(self):
        self.windows.mkdir(parents=True)
        self.add_package("wine-mono", "wine-mono-11.3.0")

        def install(command, **kwargs):
            self.framework.mkdir(parents=True)
            return subprocess.CompletedProcess(command, 0)

        with mock.patch.object(subprocess, "run", side_effect=install) as run:
            self.assertEqual(ea.ensure_wine_mono({"PATH": "/usr/bin"}), "installed")
        command, kwargs = run.call_args.args[0], run.call_args.kwargs
        self.assertEqual(command[1:3], ["msiexec", "/i"])
        self.assertTrue(command[3].startswith("Z:\\"))
        self.assertIn("wine-mono-11.3.0\\support\\winemono-support.msi", command[3])
        self.assertEqual(command[4], "/qn")
        self.assertEqual(kwargs["env"]["WINEPREFIX"], str(self.wine / "prefix"))
        self.assertEqual(kwargs["env"]["PROTONPATH"], str(self.wine / "proton"))
        self.assertEqual(kwargs["env"]["PATH"], "/usr/bin")

    def test_install_that_leaves_no_framework_is_a_failure(self):
        self.windows.mkdir(parents=True)
        self.add_package("wine-mono-11.3.0")
        with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertEqual(ea.ensure_wine_mono({}), "failed")
        with mock.patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("umu-run", 600)):
            self.assertEqual(ea.ensure_wine_mono({}), "failed")


if __name__ == "__main__":
    unittest.main()
