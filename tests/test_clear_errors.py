import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))

import clear_errors as ce


class ClassifyTest(unittest.TestCase):
    def test_causes_from_real_tool_messages(self):
        cases = {
            "OSError: [Errno 28] No space left on device": "disk_full",
            "[cli] ERROR: Not enough available disk space! 12.3 GiB < 40.1 GiB": "disk_full",
            "PermissionError: [Errno 13] Permission denied: '/run/media/x'": "permission",
            "Read-only file system": "permission",
            "[cli] ERROR: Login failed: token has expired": "auth",
            "HTTP Error 401: Unauthorized": "auth",
            "Explicit EA authentication required": "auth",
            "ERROR: You do not own this game": "unavailable",
            "requests.exceptions.ConnectionError: Max retries exceeded with url": "network",
            "urlopen error [Errno -3] Temporary failure in name resolution": "network",
            "The read operation timed out": "network",
            "Hash mismatch for file Game.pak": "corrupt",
            "Command produced no output (try installing dependencies from the About menu): x": "tool_missing",
            "/x/bin/legendary: bad interpreter: No such file or directory": "tool_missing",
            "Something odd": "unknown",
        }
        for text, code in cases.items():
            with self.subTest(text=text):
                self.assertEqual(ce.classify(text), code)

    def test_html_line_breaks_are_read_as_lines(self):
        self.assertEqual(ce.classify("ok<br />No space left on device"), "disk_full")


class SanitizeTest(unittest.TestCase):
    def test_credentials_and_emails_are_hidden(self):
        text = ("line one\nAuthorization: Bearer abc\nrefresh_token=xyz\nuser me@example.com failed\n"
                "id " + "A" * 64)
        out = ce.sanitize(text)
        self.assertNotIn("Bearer", out)
        self.assertNotIn("xyz", out)
        self.assertNotIn("me@example.com", out)
        self.assertNotIn("A" * 64, out)
        self.assertIn("line one", out)


class SpaceTest(unittest.TestCase):
    def test_needed_bytes_takes_the_larger_size(self):
        self.assertEqual(ce.needed_bytes({"DiskBytes": 10, "DownloadBytes": 7}), 10)
        self.assertEqual(ce.needed_bytes({"DownloadBytes": "7"}), 7)
        self.assertEqual(ce.needed_bytes({"Size": "12 GB"}), 0)
        self.assertEqual(ce.needed_bytes(None), 0)

    def test_blocked_when_the_game_does_not_fit(self):
        with mock.patch.object(ce, "free_bytes", return_value=5 << 30):
            problem = ce.space_problem("/mnt/x", 10 << 30)
        self.assertEqual(problem["Code"], "no_space")
        self.assertEqual(problem["Need"], 10 << 30)
        self.assertEqual(problem["Free"], 5 << 30)

    def test_headroom_is_required(self):
        with mock.patch.object(ce, "free_bytes", return_value=(10 << 30) + 1):
            self.assertIsNotNone(ce.space_problem("/mnt/x", 10 << 30))
        with mock.patch.object(ce, "free_bytes", return_value=12 << 30):
            self.assertIsNone(ce.space_problem("/mnt/x", 10 << 30))

    def test_unknown_size_still_needs_a_minimum(self):
        with mock.patch.object(ce, "free_bytes", return_value=1 << 30):
            self.assertIsNotNone(ce.space_problem("/mnt/x", 0))
        with mock.patch.object(ce, "free_bytes", return_value=3 << 30):
            self.assertIsNone(ce.space_problem("/mnt/x", 0))

    def test_extra_space_for_a_first_setup(self):
        with mock.patch.object(ce, "free_bytes", return_value=5 << 30):
            self.assertIsNotNone(ce.space_problem("/mnt/x", 2 << 30, extra=3 << 30))

    def test_unreadable_drive_does_not_block(self):
        with mock.patch.object(ce, "free_bytes", return_value=None):
            self.assertIsNone(ce.space_problem("/nowhere", 1 << 40))

    def test_free_bytes_walks_up_to_an_existing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNotNone(ce.free_bytes(os.path.join(tmp, "not", "yet", "created")))

    def test_english_message_has_the_numbers(self):
        text = ce.english("no_space", 10 << 30, 5 << 30, "/run/media/x/SSD")
        self.assertIn("10.0 GB", text)
        self.assertIn("5.0 GB", text)
        self.assertIn("/run/media/x/SSD", text)


class LogTest(unittest.TestCase):
    def setUp(self):
        ce._recent.clear()

    def test_one_file_per_error_masked_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = ce.write_log(tmp, "EpicActions", "GetProgress", "network", "msg",
                                "Max retries exceeded\naccess_token=secret", {"Game": "fixture"})
            self.assertTrue(os.path.isfile(path))
            text = Path(path).read_text()
            self.assertIn("EpicActions / GetProgress", text)
            self.assertIn("Cause: network", text)
            self.assertIn("Game: fixture", text)
            self.assertNotIn("secret", text)
            again = ce.write_log(tmp, "EpicActions", "GetProgress", "network", "msg",
                                 "Max retries exceeded\naccess_token=secret", {"Game": "fixture"})
            self.assertEqual(again, path)
            self.assertEqual(len(os.listdir(os.path.join(tmp, "errors"))), 1)

    def test_old_logs_are_trimmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "errors")
            os.makedirs(folder)
            for i in range(ce.KEEP_LOGS + 5):
                Path(folder, f"2000-01-01_00-00-{i:02d}_old.log").write_text("x")
            ce.write_log(tmp, "GOGActions", "Download", "disk_full", "msg")
            self.assertEqual(len(os.listdir(folder)), ce.KEEP_LOGS)

    def test_unwritable_folder_returns_empty(self):
        self.assertEqual(ce.write_log("/proc/nope", "X", "Y", "unknown", "msg"), "")


if __name__ == "__main__":
    unittest.main()
