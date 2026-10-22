import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))


class MoveGameTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = str(self.root / "rt")
        os.environ["HOME"] = str(self.root / "home")
        import importlib
        import move_game
        self.m = importlib.reload(move_game)
        self.game = self.root / "home" / "Games" / "gog" / "Blood"
        self.game.mkdir(parents=True)
        (self.game / "blood.exe").write_text("MZ")
        db = self.root / "rt" / "accounts" / "1" / "gog.db"
        db.parent.mkdir(parents=True)
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE Game (ShortName TEXT, InstallPath TEXT)")
        con.execute("INSERT INTO Game VALUES ('1374469660', ?)", (str(self.game),))
        con.commit()
        self.db = db
        self.drive = self.root / "sd"
        self.drive.mkdir()

    def base(self, store, drive):
        return str(self.drive / "SkullKey" / store) + "/" if drive else ""

    def test_gog_game_moved_and_database_updated(self):
        with mock.patch.object(self.m, "target_base", side_effect=self.base):
            new = self.m.move("GOGActions", "1374469660", str(self.drive), self.root / "home" / "Games" / "gog")
        self.assertEqual(Path(new), self.drive / "SkullKey" / "gog" / "Blood")
        self.assertEqual((Path(new) / "blood.exe").read_text(), "MZ")
        self.assertFalse(self.game.exists())
        row = sqlite3.connect(self.db).execute("SELECT InstallPath FROM Game").fetchone()
        self.assertEqual(row[0], new)

    def test_tool_record_paths_rewritten(self):
        rec = self.root / "installed.json"
        rec.write_text(json.dumps({"g": {"install_path": str(self.game), "exe": str(self.game) + "/blood.exe",
                                         "other": "/elsewhere"}}))
        self.m.rewrite_tool_records(str(self.game), "/new/Blood", files=[rec])
        data = json.loads(rec.read_text())["g"]
        self.assertEqual((data["install_path"], data["exe"], data["other"]), ("/new/Blood", "/new/Blood/blood.exe", "/elsewhere"))

    def test_account_tool_records_are_included(self):
        rec = self.root / "rt" / "accounts" / "1" / "nile" / "installed.json"
        rec.parent.mkdir(parents=True)
        rec.write_text("[]")
        self.assertIn(rec, self.m.tool_records())

    def test_failed_copy_keeps_game_and_records(self):
        with mock.patch.object(self.m, "target_base", side_effect=self.base), \
             mock.patch.object(self.m.shutil, "copytree", side_effect=OSError("full")):
            with self.assertRaises(self.m.MoveError):
                self.m.move("GOGActions", "1374469660", str(self.drive), self.root)
        self.assertTrue((self.game / "blood.exe").exists())
        self.assertEqual(sqlite3.connect(self.db).execute("SELECT InstallPath FROM Game").fetchone()[0], str(self.game))

    def test_existing_target_folder_refused(self):
        (self.drive / "SkullKey" / "gog" / "Blood").mkdir(parents=True)
        with mock.patch.object(self.m, "target_base", side_effect=self.base):
            with self.assertRaises(self.m.MoveError):
                self.m.move("GOGActions", "1374469660", str(self.drive), self.root)
        self.assertTrue(self.game.exists())

    def test_epic_path_from_legendary_record(self):
        rec = self.root / "rt" / "accounts" / "1" / "legendary" / "installed.json"
        rec.parent.mkdir(parents=True)
        game = self.root / "home" / "Games" / "epic" / "FallGuys"
        game.mkdir(parents=True)
        rec.write_text(json.dumps({"abc": {"install_path": str(game)}}))
        self.assertEqual(self.m.current_path("EpicActions", "abc"), str(game))
        with mock.patch.object(self.m, "target_base", side_effect=self.base):
            new = self.m.move("EpicActions", "abc", str(self.drive), self.root)
        self.assertEqual(json.loads(rec.read_text())["abc"]["install_path"], new)
        self.assertFalse(game.exists())

    def test_unsupported_platform_refused(self):
        with self.assertRaises(self.m.MoveError):
            self.m.move("MiHoYoActions", "x", "", self.root)


if __name__ == "__main__":
    unittest.main()
