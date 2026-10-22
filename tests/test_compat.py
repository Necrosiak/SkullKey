import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))

DATA = [{"name": "Mecha BREAK", "status": "Broken", "anticheats": ["Anti-Cheat Expert"]},
        {"name": "Fortnite", "status": "Denied", "anticheats": ["Easy Anti-Cheat"]},
        {"name": "Halo Infinite", "status": "Supported", "anticheats": ["Easy Anti-Cheat"]},
        {"name": "Call of Duty: Black Ops 6", "status": "Denied", "anticheats": ["Ricochet"]}]


class CompatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = self.tmp.name
        import importlib
        import compat
        self.c = importlib.reload(compat)

    def test_known_broken_games_warn(self):
        self.assertEqual(self.c.check("Mecha BREAK", fetch=lambda u: DATA)["anticheats"], ["Anti-Cheat Expert"])
        self.assertEqual(self.c.check("Fortnite", fetch=lambda u: DATA)["status"], "Denied")

    def test_editions_and_symbols_still_match(self):
        self.assertIsNotNone(self.c.check("Call of Duty®: Black Ops 6 (PC) – Édition Standard", fetch=lambda u: DATA))

    def test_supported_and_unknown_games_do_not_warn(self):
        self.assertIsNone(self.c.check("Halo Infinite", fetch=lambda u: DATA))
        self.assertIsNone(self.c.check("Aniimo", fetch=lambda u: DATA))

    def test_offline_without_cache_never_warns(self):
        def boom(url):
            raise OSError("offline")
        self.assertIsNone(self.c.check("Fortnite", fetch=boom))

    def test_cached_for_a_week(self):
        calls = []
        self.c.check("Fortnite", fetch=lambda u: calls.append(u) or DATA)
        self.c.check("Fortnite", fetch=lambda u: calls.append(u) or DATA)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
