"""A game page opened before its tab: the action set is loaded from static.json."""
import ast
import json
import os
import subprocess
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def helper():
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Helper")
    keep = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ("get_action", "load_static_action_set")]
    mod = ast.Module(body=[ast.ClassDef(name="Helper", bases=[], keywords=[], body=keep, decorator_list=[])], type_ignores=[])
    ns = {"os": os, "json": json, "subprocess": subprocess,
          "decky_plugin": types.SimpleNamespace(DECKY_PLUGIN_RUNTIME_DIR="/nonexistent")}
    exec(compile(ast.fix_missing_locations(mod), "<helper>", "exec"), ns)
    H = ns["Helper"]
    H.action_cache = {}
    H.working_directory = str(ROOT / "defaults")
    return H


class StaticActionFallbackTest(unittest.TestCase):
    def test_xbox_details_found_without_opening_the_tab(self):
        H = helper()
        action = H.get_action("XboxActions", "GetDetails")
        self.assertEqual(action["Command"], "./scripts/xbox.py getgamedetails")
        self.assertIn("XboxActions", H.action_cache)

    def test_main_menu_found_after_reload(self):
        H = helper()
        self.assertIsNotNone(H.get_action("MainMenu", "SkullKeyInit"))

    def test_runs_without_the_decky_library_path(self):
        H = helper()
        with mock.patch.dict(os.environ, {"LD_LIBRARY_PATH": "/tmp/_MEIbroken"}):
            self.assertIsNotNone(H.get_action("MainMenu", "SkullKeyInit"))

    def test_unknown_set_stays_none(self):
        H = helper()
        self.assertIsNone(H.get_action("NopeActions", "GetDetails"))
        self.assertIsNone(H.get_action("../../x", "GetDetails"))


if __name__ == "__main__":
    unittest.main()
