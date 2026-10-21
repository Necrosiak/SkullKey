"""Discs & Installers tab: skeleton, actions and tab order."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "defaults" / "scripts"


def run_disks(runtime, *args):
    env = {**os.environ, "DECKY_PLUGIN_RUNTIME_DIR": runtime}
    out = subprocess.run([sys.executable, str(SCRIPTS / "disks.py"), *args],
                         capture_output=True, text=True, env=env, timeout=60)
    return json.loads(out.stdout.strip().splitlines()[-1])


class DisksSkeletonTests(unittest.TestCase):
    def test_getgames_empty(self):
        with tempfile.TemporaryDirectory() as runtime:
            self.assertEqual(run_disks(runtime, "getgames"),
                             {"Type": "GameGrid", "Content": {"Games": [], "NeedsLogin": "false"}})

    def test_static_json_actions(self):
        data = json.loads((SCRIPTS / "Extensions" / "Disks" / "static.json").read_text(encoding="utf-8"))
        init = [a["Id"] for a in data["skullkey-actions"]["Content"]["Actions"]]
        self.assertIn("GetDisksActions", init)
        tabs = data["skullkey-tabs"]["Content"]["Tabs"]
        self.assertEqual(tabs[0]["ActionId"], "GetDisksActions")
        actions = data["disks-actions"]["Content"]
        self.assertEqual(actions["SetName"], "DisksActions")
        ids = {a["Id"] for a in actions["Actions"]}
        for needed in ("GetContent", "GetDetails", "GetJsonImages", "GetGameSize", "Install",
                       "Uninstall", "GetProgress", "CancelInstall", "GetGameScriptActions",
                       "GetScriptActions"):
            self.assertIn(needed, ids)

    def test_tab_order(self):
        text = (SCRIPTS / "get-json.py").read_text(encoding="utf-8")
        start = text.index("TAB_ORDER = [")
        order = eval(text[start + len("TAB_ORDER = "):text.index("]", start) + 1])
        self.assertEqual(order[-4:], ["GetMinecraftActions", "GetPortsActions", "GetXboxActions", "GetDisksActions"])

    def test_tab_title_localized(self):
        sys.path.insert(0, str(SCRIPTS))
        import disks_i18n
        for lang in disks_i18n.LANGS:
            self.assertTrue(disks_i18n.TEXT["tab_title"].get(lang), lang)
        self.assertEqual(disks_i18n.TEXT["tab_title"]["fr"], "Disques & installeurs")
        self.assertEqual(disks_i18n.TEXT["tab_title"]["en"], "Discs & Installers")


if __name__ == "__main__":
    unittest.main()
