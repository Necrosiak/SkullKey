"""Discs & Installers: artwork, details, saves check and uninstall."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "defaults" / "scripts"))


class DetailsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"DECKY_PLUGIN_RUNTIME_DIR": str(t / "rt"),
                                           "SK_DISKS_COMPAT_ROOT": str(t / "compat")})
        self.env.start()
        import importlib
        import disks
        self.disks = importlib.reload(disks)
        self.root = t / "Disques" / "foo"
        (self.root / "game").mkdir(parents=True)
        (self.root / "game" / "Foo.exe").write_bytes(b"MZ")
        self.pfx = t / "compat" / "77" / "pfx" / "drive_c"
        state = {"games": {"foo": {"title": "Foo", "slug": "foo", "source_kind": "ready", "source": "/x",
                                   "parts": [], "root": str(self.root), "installer": "",
                                   "exe": str(self.root / "game" / "Foo.exe"), "steamClientID": "77",
                                   "stage": "installed", "snapshot": []}}, "last_scan_dir": ""}
        self.disks.save_state(state)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def call(self, fn, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return json.loads(buf.getvalue().strip().splitlines()[-1])

    def make_save(self, rel, size=100):
        p = self.pfx / "users" / "steamuser" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"s" * size)

    def test_art_fallback_without_network(self):
        with patch.object(self.disks, "steam_appid", side_effect=OSError("offline")), \
                patch.object(self.disks, "text_tile", return_value=None) as tile:
            res = self.call(self.disks.action_getjsonimages, "foo")
        self.assertEqual(res["Type"], "Images")
        self.assertTrue(tile.called)

    def test_art_uses_steam_images(self):
        with patch.object(self.disks, "steam_appid", return_value=42), \
                patch.object(self.disks, "fetch_b64", return_value=("QUJD", "jpg")) as fetch:
            res = self.call(self.disks.action_getjsonimages, "foo")
        self.assertEqual(res["Content"]["Grid"], "QUJD")
        self.assertTrue(any("/42/" in c.args[0] for c in fetch.call_args_list))

    def test_grid_cover_uses_steam_or_tile(self):
        cache = Path(os.environ["DECKY_PLUGIN_RUNTIME_DIR"]) / "disks" / "art.json"
        cache.write_text(json.dumps({"foo": 42}))
        self.assertIn("/42/library_600x900", self.disks.cover_url("foo"))
        cache.write_text(json.dumps({"foo": None}))
        with patch.object(self.disks, "tile_file", return_value=None):
            self.assertEqual(self.disks.cover_url("foo"), "")
        tile = Path(self.tmp.name) / "t.png"
        tile.write_bytes(b"PNG")
        with patch.object(self.disks, "tile_file", return_value=tile):
            self.assertEqual(self.disks.cover_url("foo"), "data:image/png;base64,UE5H")

    def test_savecheck_lists_nonempty_only(self):
        self.make_save("Documents/Foo/save1.dat", 300)
        (self.pfx / "users" / "steamuser" / "Saved Games").mkdir(parents=True)
        res = self.call(self.disks.action_savecheck, "foo")
        dirs = res["Content"]["dirs"]
        self.assertEqual([d["path_label"] for d in dirs], ["Documents/Foo"])
        self.assertEqual(dirs[0]["bytes"], 300)
        self.assertNotIn(self.tmp.name, json.dumps(res))

    def test_uninstall_keep_moves_saves(self):
        self.make_save("Documents/Foo/save1.dat")
        self.call(self.disks.action_uninstall, "foo", "keep")
        kept = self.root.parent / "_sauvegardes" / "foo" / "Documents" / "Foo" / "save1.dat"
        self.assertTrue(kept.exists())
        self.assertFalse(self.root.exists())
        self.assertFalse(self.pfx.exists())
        self.assertNotIn("foo", self.disks.load_state()["games"])

    def test_uninstall_without_keep_deletes_all(self):
        self.make_save("Documents/Foo/save1.dat")
        self.call(self.disks.action_uninstall, "foo")
        self.assertFalse(self.root.exists())
        self.assertFalse((self.root.parent / "_sauvegardes").exists())
        self.assertFalse(self.pfx.exists())

    def test_details_has_no_absolute_user_path(self):
        res = self.call(self.disks.action_getgamedetails, "foo")
        self.assertEqual(res["Type"], "GameDetails")
        self.assertEqual(res["Content"]["Name"], "Foo")
        self.assertIn("Foo.exe", res["Content"]["Description"])
        self.assertNotIn(os.path.expanduser("~"), res["Content"]["Description"])


if __name__ == "__main__":
    unittest.main()
