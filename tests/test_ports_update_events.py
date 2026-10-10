"""Exercise the backend event consumer without starting Decky."""
import ast
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


class UpdateEventsTests(unittest.TestCase):
    def test_events_are_consumed_once_and_incomplete_writes_ignored(self):
        tree = ast.parse((Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8"))
        plugin = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Plugin")
        method = next(node for node in plugin.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "take_port_update_events")
        module = ast.Module(body=[method], type_ignores=[])
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "ports_update_events"
            directory.mkdir()
            event = {"name": "P.T.", "version": "v1", "success": True, "appid": "42"}
            (directory / "complete.json").write_text(json.dumps(event))
            (directory / "writing.tmp").write_text("{")
            namespace = {"os": os, "json": json, "decky_plugin": SimpleNamespace(DECKY_PLUGIN_RUNTIME_DIR=temporary)}
            exec(compile(module, "main.py", "exec"), namespace)
            consume = namespace["take_port_update_events"]
            def run():
                # This async method performs no awaits; avoid an OS event loop.
                with self.assertRaises(StopIteration) as completed:
                    consume(None).send(None)
                return completed.exception.value
            self.assertEqual(run(), [event])
            self.assertEqual(run(), [])
            self.assertTrue((directory / "writing.tmp").exists())

