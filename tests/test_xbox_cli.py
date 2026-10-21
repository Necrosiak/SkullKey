import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "defaults" / "scripts"))
FAKE = ROOT / "tests" / "fixtures" / "xbox" / "fake_xodus_cli.py"

import xbox_cli as C

PROGRESS = ('NEXUS_PROGRESS {"schema": 1, "event": "progress", "sequence": 4, "phase": "downloading", '
            '"completedBytes": 512, "totalBytes": 2048, "bytesPerSecond": 1048576, "paused": false, "canPause": true}')


class CliTest(unittest.TestCase):
    def setUp(self):
        FAKE.chmod(FAKE.stat().st_mode | stat.S_IXUSR)
        p = mock.patch.object(C, "_binary", return_value=FAKE)
        p.start()
        self.addCleanup(p.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_profile_strips_gamerpic(self):
        prof = C.profile()
        self.assertNotIn("gamerpicDataUrl", prof)
        self.assertEqual(prof["gamertag"], "Tester")

    def test_account_hides_username(self):
        self.assertEqual(C.account(), {"stored": True})

    def test_library_returns_entitlements(self):
        self.assertEqual(C.library("FR")[0]["productId"], "9AAA")

    def test_cli_error_hides_private_lines(self):
        with self.assertRaises(C.CliError) as ctx:
            C.resolve("9BAD", "FR", strict=True)
        msg = str(ctx.exception)
        for bad in ("SECRET", "@", "http"):
            self.assertNotIn(bad, msg)
        self.assertIn("Package not found", msg)

    def test_resolve_returns_none_on_failure(self):
        self.assertIsNone(C.resolve("9BAD", "FR"))

    def test_parse_progress_fixture_lines(self):
        p = C.parse_progress(PROGRESS)
        self.assertEqual(p["percent"], 25.0)
        self.assertEqual(p["phase"], "downloading")
        self.assertIsNone(C.parse_progress("hello"))
        self.assertIsNone(C.parse_progress('NEXUS_PROGRESS {"schema": 2}'))

    def test_streaming_reports_complete(self):
        proc = C.start_streaming("9AAA", Path(self.tmp.name) / "g", "FR")
        last = None
        for line in proc.stdout:
            last = C.parse_progress(line) or last
        proc.wait()
        self.assertEqual(last["phase"], "complete")

    def test_cancel_kills_after_timeout(self):
        with mock.patch.dict(os.environ, {"FAKE_XODUS_MODE": "ignore-sigint", "FAKE_XODUS_DELAY": "5"}):
            proc = C.start_streaming("9AAA", Path(self.tmp.name) / "g", "FR")
            time.sleep(0.5)
            start = time.time()
            C.cancel(proc, grace=1)
            self.assertIsNotNone(proc.poll())
            self.assertLess(time.time() - start, 4)

    def test_inspect_game_reads_microsoftgame_config(self):
        d = Path(self.tmp.name) / "G"
        d.mkdir()
        (d / "MicrosoftGame.Config").write_text(
            '<Game><Identity Name="Pub.Game" Version="1.0"/><StoreId>9AAA</StoreId>'
            '<ExecutableList><Executable Name="Bin\\Game.exe" Id="Game"/></ExecutableList>'
            '<ShellVisuals DefaultDisplayName="My Game" PublisherDisplayName="Pub"/></Game>')
        info = C.inspect_game(d)
        self.assertEqual((info["title"], info["executable"], info["storeId"]), ("My Game", "Bin\\Game.exe", "9AAA"))


if __name__ == "__main__":
    unittest.main()
