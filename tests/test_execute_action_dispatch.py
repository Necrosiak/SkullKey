"""Decky calls Plugin methods with the class itself as `self` (issue #10, PR #13)."""
import ast
import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "defaults" / "scripts"))

import clear_errors

KEEP = ("execute_action", "_space_check", "_clarify", "_shortname")


def plugin(helper, log_dir):
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Plugin")
    keep = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in KEEP]
    mod = ast.Module(body=[ast.ClassDef(name="Plugin", bases=[], keywords=[], body=keep, decorator_list=[])],
                     type_ignores=[])
    logger = types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None)
    ns = {"os": os, "json": json, "asyncio": asyncio, "Helper": helper,
          "decky_plugin": types.SimpleNamespace(logger=logger, DECKY_USER_HOME=log_dir,
                                                DECKY_PLUGIN_LOG_DIR=log_dir,
                                                DECKY_PLUGIN_RUNTIME_DIR=log_dir)}
    exec(compile(ast.fix_missing_locations(mod), "<plugin>", "exec"), ns)
    return ns["Plugin"]


class FakeHelper:
    verbose = False
    pending_install_root = ""
    active_install_root = ""
    results = {}

    @classmethod
    async def execute_action(cls, actionSet, actionName, *args, **kwargs):
        return cls.results.get(actionName, {"Type": "Empty", "Content": {}})


class DispatchTest(unittest.TestCase):
    def setUp(self):
        clear_errors._recent.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        FakeHelper.results = {}
        self.P = plugin(FakeHelper, self.tmp.name)

    def call(self, actionSet, actionName, **kwargs):
        # Same shape as Decky: the class is passed as `self`.
        return asyncio.run(self.P.execute_action(self.P, actionSet, actionName, **kwargs))

    def test_main_menu_runs(self):
        FakeHelper.results = {"SkullKeyInit": {"Type": "MainMenu", "Content": {"Items": []}}}
        self.assertEqual(self.call("MainMenu", "SkullKeyInit"), FakeHelper.results["SkullKeyInit"])

    def test_tool_error_is_clarified(self):
        FakeHelper.results = {"GetContent": {"Type": "Error", "Content": {
            "Message": "OSError: [Errno 28] No space left on device", "Data": ""}}}
        result = self.call("EpicActions", "GetContent")
        self.assertEqual(result["Content"]["Code"], "disk_full")

    def test_download_runs_the_space_check(self):
        FakeHelper.results = {"GetGameSize": {"Type": "GameSize", "Content": {"DiskBytes": 1 << 50}},
                              "Download": {"Type": "Success", "Content": {}}}
        result = self.call("GOGActions", "Download", shortname="fixture")
        self.assertEqual(result["Type"], "Error")
        self.assertEqual(result["Content"]["Code"], "no_space")

    def test_download_that_fits_starts(self):
        FakeHelper.results = {"GetGameSize": {"Type": "GameSize", "Content": {"DiskBytes": 1}},
                              "Download": {"Type": "Success", "Content": {}}}
        with mock.patch.object(clear_errors, "free_bytes", return_value=100 << 30):
            result = self.call("GOGActions", "Download", shortname="fixture")
        self.assertEqual(result["Type"], "Success")


if __name__ == "__main__":
    unittest.main()
