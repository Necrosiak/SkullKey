"""Switching a platform off hides its tab from the store and the menu."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tabs(env):
    out = subprocess.run(["python3", "scripts/get-json.py", "skullkey-tabs"], cwd=ROOT / "defaults",
                         capture_output=True, text=True, env=env, timeout=30)
    return [t["ActionId"] for t in json.loads(out.stdout)["Content"]["Tabs"]]


class PlatformToggleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, DECKY_PLUGIN_RUNTIME_DIR=self.tmp.name)

    def test_all_tabs_by_default(self):
        self.assertIn("GetXboxActions", tabs(self.env))

    def test_disabled_tab_hidden_but_listed_for_settings(self):
        Path(self.tmp.name, "platforms.json").write_text(json.dumps({"disabled": ["GetXboxActions"]}))
        self.assertNotIn("GetXboxActions", tabs(self.env))
        self.assertIn("GetXboxActions", tabs(dict(self.env, SK_ALL_TABS="1")))


if __name__ == "__main__":
    unittest.main()
