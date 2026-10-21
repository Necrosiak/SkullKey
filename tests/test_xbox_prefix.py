import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))


class PrefixTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = self.tmp.name
        import importlib
        import xbox_tools
        import xbox_prefix
        importlib.reload(xbox_tools)
        self.p = importlib.reload(xbox_prefix)
        self.rt = Path(self.tmp.name) / "rt" / "runtime-new"
        (self.rt / "files" / "bin").mkdir(parents=True)
        for b in ("wine", "wineserver"):
            (self.rt / "files" / "bin" / b).write_text("#!/bin/sh\n")
        dll = b"MZdll"
        lib = self.rt / "files" / "lib" / "wine" / "x86_64-windows"
        lib.mkdir(parents=True)
        (lib / "windows.web.dll").write_bytes(dll)
        (self.rt / "XODUS_NEXUS_PATCH.json").write_text(json.dumps(
            {"features": ["winrt-json-v1"], "components": {"windows.web.dll": hashlib.sha256(dll).hexdigest()}}))
        mock.patch.object(self.p.xbox_tools, "runtime_root", return_value=self.rt).start()
        self.addCleanup(mock.patch.stopall)
        self.pfx = self.p.prefix_dir("9AAA") / "pfx"
        (self.pfx / "dosdevices").mkdir(parents=True)
        (self.pfx / "drive_c" / "windows" / "system32").mkdir(parents=True)
        os.symlink("/", self.pfx / "dosdevices" / "z:")

    def tearDown(self):
        self.tmp.cleanup()

    def test_home_drive_created_and_z_untouched(self):
        self.p.ensure_home_drive(self.pfx)
        self.assertEqual(os.readlink(self.pfx / "dosdevices" / "y:"), self.p.home_root())
        self.assertEqual(os.readlink(self.pfx / "dosdevices" / "z:"), "/")

    def test_home_drive_idempotent(self):
        self.p.ensure_home_drive(self.pfx)
        self.p.ensure_home_drive(self.pfx)
        self.assertTrue((self.pfx / "dosdevices" / "y:").is_symlink())

    def test_home_drive_does_not_replace_a_user_drive(self):
        os.symlink("/mnt/data", self.pfx / "dosdevices" / "y:")
        self.p.ensure_home_drive(self.pfx)
        self.assertEqual(os.readlink(self.pfx / "dosdevices" / "y:"), "/mnt/data")

    def test_runner_has_prefix_and_no_mei_paths(self):
        with mock.patch.dict(os.environ, {"LD_LIBRARY_PATH": "/tmp/_MEIabc"}):
            runner = self.p.write_runner("9AAA")
        text = runner.read_text()
        import shlex
        self.assertIn("export WINEPREFIX=%s\n" % shlex.quote(str(self.pfx)), text)
        self.assertNotIn("_MEI", text)
        self.assertIn("wineserver -w", text)
        self.assertEqual(runner.stat().st_mode & 0o777, 0o700)

    def test_runtime_components_copied_after_checksum(self):
        self.p.write_runner("9AAA")
        self.assertEqual((self.pfx / "drive_c/windows/system32/windows.web.dll").read_bytes(), b"MZdll")

    def test_bad_component_checksum_refused(self):
        (self.rt / "files/lib/wine/x86_64-windows/windows.web.dll").write_bytes(b"evil")
        with self.assertRaises(self.p.PrefixError):
            self.p.write_runner("9AAA")

    def test_ensure_prefix_env(self):
        seen = {}

        def run(cmd, env, **kw):
            seen.update(env)
            (self.pfx / "drive_c" / "windows" / "system32" / "kernel32.dll").write_text("x")
            (self.pfx / "system.reg").write_text("x")
            return mock.Mock(returncode=0)
        (self.rt / "proton").write_text("")
        with mock.patch.object(self.p.subprocess, "run", side_effect=run):
            self.p.ensure_prefix("9AAA")
        for k, v in {"SteamAppId": "0", "SteamGameId": "0", "UMU_ID": "xodus-nexus", "UMU_USE_STEAM": "0"}.items():
            self.assertEqual(seen[k], v)
        self.assertEqual(seen["STEAM_COMPAT_DATA_PATH"], str(self.p.prefix_dir("9AAA")))
        self.assertTrue((self.pfx / "dosdevices" / "y:").is_symlink())

    def test_stale_runtime_symlinks_rebased(self):
        old = Path(self.tmp.name) / "rt" / "runtime-old" / "files" / "lib" / "wine" / "x.dll"
        target = self.pfx / "drive_c" / "windows" / "system32" / "x.dll"
        os.symlink(old, target)
        self.p.rebase_runtime_links(self.pfx, Path(self.tmp.name) / "rt")
        self.assertEqual(os.readlink(target), str(self.rt / "files" / "lib" / "wine" / "x.dll"))


if __name__ == "__main__":
    unittest.main()
