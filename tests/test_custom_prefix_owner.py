"""The Decky backend is root, while Proton runs as the Steam user."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack


SCRIPT = Path(__file__).resolve().parents[1] / "defaults/scripts/shared/prefixes.py"
spec = importlib.util.spec_from_file_location("skullkey_prefixes_test", SCRIPT)
prefixes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prefixes)


def with_uid(info, uid, gid):
    fields = list(info)
    fields[4], fields[5] = uid, gid
    return os.stat_result(fields)


class CustomPrefixOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "deck"
        self.home.mkdir()
        self.root = self.home / "Prefix" / "Skullkey"
        self.game = self.root / "epic-FallGuys"
        prefixes.RUNTIME = str(Path(self.temp.name) / "runtime")
        prefixes.CFG = str(Path(prefixes.RUNTIME) / "prefixes.json")
        prefixes.STEAM_COMPAT = str(Path(self.temp.name) / "compatdata")
        prefixes.set_root(str(self.root))
        prefixes.assign("Epic", "FallGuys", "123")
        self.real_stat = os.stat
        self.real_lstat = os.lstat

    def as_decky_root(self, existing_root_owned=()):
        home = self.home
        real_stat = self.real_stat
        real_lstat = self.real_lstat
        owned = {str(path) for path in existing_root_owned}

        def stat(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            return with_uid(info, 1000, 1000) if str(path) == str(home) else info

        def lstat(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            return with_uid(info, 0, 0) if str(path) in owned else info

        stack = ExitStack()
        stack.enter_context(patch.dict(os.environ, {"HOME": str(home),
                                                    "DECKY_USER_HOME": str(home)}))
        stack.enter_context(patch.multiple(prefixes.os, geteuid=lambda: 0,
                                           stat=stat, lstat=lstat,
                                           chown=lambda *args: None, create=True))
        return stack

    def test_new_prefix_created_for_steam_user(self):
        owner_calls = []
        with self.as_decky_root(), patch.object(prefixes.os, "chown",
                                                side_effect=lambda path, uid, gid:
                                                owner_calls.append((str(path), uid, gid))):
            option = prefixes.env_for("Epic", "FallGuys")
        self.assertTrue(self.game.is_dir())
        self.assertIn(str(self.root), [call[0] for call in owner_calls])
        self.assertIn((str(self.game), 1000, 1000), owner_calls)
        self.assertIn("STEAM_COMPAT_DATA_PATH=", option)

    def test_repairs_empty_prefix_from_previous_release(self):
        self.game.mkdir(parents=True)
        owner_calls = []
        with self.as_decky_root((self.root, self.game)), \
             patch.object(prefixes.os, "chown",
                          side_effect=lambda path, uid, gid:
                          owner_calls.append((str(path), uid, gid))):
            prefixes.env_for("Epic", "FallGuys")
        self.assertIn((str(self.root), 1000, 1000), owner_calls)
        self.assertIn((str(self.game), 1000, 1000), owner_calls)

    def test_startup_repairs_existing_prefix_without_reinstall(self):
        self.game.mkdir(parents=True)
        unrelated = self.home / "unrelated"
        unrelated.mkdir()
        owner_calls = []
        with self.as_decky_root((self.root, self.game, unrelated)), \
             patch.object(prefixes.os, "chown",
                          side_effect=lambda path, uid, gid:
                          owner_calls.append((str(path), uid, gid))):
            self.assertEqual(prefixes.repair_existing(), 1)
        self.assertIn((str(self.game), 1000, 1000), owner_calls)
        self.assertNotIn(str(unrelated), [call[0] for call in owner_calls])

    def test_tilde_path_uses_steam_users_home_even_under_root(self):
        with self.as_decky_root():
            prefixes.set_root("~/Prefix/Skullkey")
            prefixes.assign("Epic", "NewGame", "456")
            self.assertEqual(prefixes.root(), str(self.root))
            self.assertEqual(prefixes.path_for("Epic", "NewGame"),
                             str(self.root / "epic-NewGame"))


if __name__ == "__main__":
    unittest.main()
