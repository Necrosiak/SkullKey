import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))


class DownloadsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rt = Path(self.tmp.name)
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = str(self.rt)
        os.environ["DECKY_PLUGIN_LOG_DIR"] = str(self.rt / "logs")
        import importlib
        import downloads
        self.d = importlib.reload(downloads)

    def write(self, rel, data, age=0):
        f = self.rt / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data))
        if age:
            t = time.time() - age
            os.utime(f, (t, t))

    def test_running_xbox_and_port_listed(self):
        self.write("xbox/state.json", {"games": {}, "pending": {"9AB": {"title": "Halo"}}})
        self.write("xbox/progress/9AB.json", {"Percentage": 42, "Description": "Step 2/4"})
        self.write("ports_progress/zelda64.json", {"Percentage": 10, "Description": "Downloading"})
        got = {(x["store"], x["id"], x["pct"]) for x in self.d.active()}
        self.assertIn(("xbox", "9AB", 42.0), got)
        self.assertIn(("ports", "zelda64", 10.0), got)
        self.assertEqual(next(x["title"] for x in self.d.active() if x["id"] == "9AB"), "Halo")

    def test_finished_failed_and_stale_hidden(self):
        self.write("xbox/progress/done.json", {"Percentage": 100, "Description": "Installed"})
        self.write("xbox/progress/err.json", {"Percentage": 5, "Error": "boom"})
        self.write("xbox/progress/old.json", {"Percentage": 30, "Description": "x"}, age=3600)
        self.assertEqual(self.d.active(), [])

    def test_old_file_kept_while_worker_alive(self):
        self.write("xbox/progress/slow.json", {"Percentage": 30, "pid": os.getpid()}, age=3600)
        self.assertEqual([x["id"] for x in self.d.active()], ["slow"])


if __name__ == "__main__":
    unittest.main()
