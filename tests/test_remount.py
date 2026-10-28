import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))


class RemountTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = self.tmp.name
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = t + "/data"
        os.environ["DECKY_USER_HOME"] = t + "/home"
        import importlib
        import remount
        self.r = importlib.reload(remount)
        self.addCleanup(os.environ.pop, "DECKY_USER_HOME")
        media = t + "/run/media/"
        mock.patch.object(self.r, "DRIVE", re.compile(rf"^({re.escape(media)}[^/]+)/([^/]+)(/.+)$")).start()
        mock.patch.object(self.r, "MOUNT_ROOTS", (media,)).start()
        self.addCleanup(mock.patch.stopall)
        self.old = media + "system/SSD2TO"
        self.new = media + "bazzite/SSD2TO"
        self.game = "/SkullKey/Xbox/9NR1R1XWLCNB"
        os.makedirs(self.new + self.game)
        self.data = Path(t) / "data"
        (self.data / "xbox").mkdir(parents=True)
        self.mounts = mock.patch.object(self.r, "_mounts", return_value=[self.new]).start()

    def write(self, rel, obj):
        p = self.data / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj))
        return p

    def test_moved_drive_rewrites_every_state_file(self):
        st = self.write("xbox/state.json", {"games": {"9NR1": {"root": self.old + self.game}}})
        ip = self.write("install_paths.json", {"a": self.old + self.game, "b": self.old + "/SkullKey/ea/gone"})
        ea = self.write("accounts/1/ea/state.json", {"x": [self.old + self.game + "/bin"]})
        moved = self.r.heal()
        self.assertEqual(moved, {self.old: self.new})
        self.assertEqual(json.loads(st.read_text())["games"]["9NR1"]["root"], self.new + self.game)
        # every path on that drive follows it, even one whose folder is gone
        self.assertEqual(json.loads(ip.read_text())["b"], self.new + "/SkullKey/ea/gone")
        self.assertEqual(json.loads(ea.read_text())["x"], [self.new + self.game + "/bin"])

    def test_game_db_install_path_moved(self):
        db = self.data / "gog.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE Game (ShortName TEXT, InstallPath TEXT)")
        con.execute("INSERT INTO Game VALUES ('a', ?), ('b', '/home/x')", (self.old + self.game,))
        con.commit()
        con.close()
        self.r.heal()
        rows = dict(sqlite3.connect(db).execute("SELECT ShortName, InstallPath FROM Game"))
        self.assertEqual(rows, {"a": self.new + self.game, "b": "/home/x"})

    def test_nothing_moves_without_the_same_folder_on_the_drive(self):
        st = self.write("xbox/state.json", {"root": self.old + "/SkullKey/Xbox/OTHER"})
        self.assertEqual(self.r.heal(), {})
        self.assertEqual(json.loads(st.read_text())["root"], self.old + "/SkullKey/Xbox/OTHER")

    def test_ambiguous_label_is_left_alone(self):
        other = self.tmp.name + "/run/media/deck/SSD2TO"
        os.makedirs(other + self.game)
        self.mounts.return_value = [self.new, other]
        self.write("xbox/state.json", {"root": self.old + self.game})
        self.assertEqual(self.r.heal(), {})

    def test_existing_path_untouched(self):
        st = self.write("xbox/state.json", {"root": self.new + self.game})
        self.assertEqual(self.r.heal(), {})
        self.assertEqual(json.loads(st.read_text())["root"], self.new + self.game)


if __name__ == "__main__":
    unittest.main()
