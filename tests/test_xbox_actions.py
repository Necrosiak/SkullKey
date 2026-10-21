import contextlib
import importlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "defaults" / "scripts"))
sys.path.insert(0, str(ROOT / "defaults" / "scripts" / "shared"))

OWNED = {"productId": "9OWN", "status": "Active", "isTrial": False, "satisfiedByProductId": None}
GP = {"productId": "9GP", "status": "Active", "isTrial": False, "satisfiedByProductId": "CFQ7TTC0KGQ8"}
FREE = {"id": "9FREE", "title": "Free Game", "publisher": "P", "price": "free", "installable": True,
        "contentId": "c-free", "art": {"cover": "https://img/free"}}


def details(ids, market, lang, fetch=None):
    names = {"9OWN": "Owned Game", "9GP": "Pass Game", "9FREE": "Free Game"}
    return {i: {"title": names.get(i, i), "publisher": "", "description": "", "game": True,
                "art": {"cover": f"https://img/{i}"}} for i in ids}


class ActionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = self.tmp.name + "/rt"
        os.environ["HOME"] = self.tmp.name + "/home"
        Path(os.environ["HOME"]).mkdir()
        import xbox_tools
        importlib.reload(xbox_tools)
        import xbox_prefix
        importlib.reload(xbox_prefix)
        import xbox
        self.x = importlib.reload(xbox)
        self.sub = {"status": "unknown"}
        patches = [
            mock.patch.object(self.x.xbox_cli, "account", return_value={"stored": True}),
            mock.patch.object(self.x.xbox_cli, "profile", side_effect=lambda: {"gamertag": "T", "subscription": self.sub}),
            mock.patch.object(self.x.xbox_cli, "library", return_value=[OWNED, GP]),
            mock.patch.object(self.x.xbox_catalog, "details", side_effect=details),
            mock.patch.object(self.x.xbox_catalog, "free_games", return_value=[FREE]),
            mock.patch.object(self.x.xbox_catalog, "search", return_value=[FREE]),
            mock.patch.object(self.x.xbox_catalog, "installable", return_value="c-x"),
            mock.patch.object(self.x, "market", return_value=("FR", "fr-fr")),
        ]
        for p in patches:
            p.start()
        self.addCleanup(mock.patch.stopall)

    def call(self, fn, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            fn(*args)
        return [json.loads(l) for l in out.getvalue().splitlines() if l.startswith("{")][-1]

    def grid_names(self):
        return [g["Name"] for g in self.call(self.x.action_getgames, "", "false")["Content"]["Games"]]

    def install_fake(self, pid):
        root = Path(self.tmp.name) / "games" / pid
        root.mkdir(parents=True)
        with self.x.locked_state() as st:
            st["games"][pid] = {"title": pid, "root": str(root), "executable": "g.exe", "steamClientID": ""}
        return root

    def test_grid_without_sub_shows_owned_and_free_only(self):
        self.assertEqual(sorted(self.grid_names()), ["Free Game", "Owned Game"])

    def test_grid_with_active_sub_adds_game_pass(self):
        self.sub = {"status": "active"}
        self.assertIn("Pass Game", self.grid_names())

    def test_installed_gamepass_listed_locked(self):
        self.install_fake("9GP")
        self.assertIn("Pass Game", self.grid_names())
        info, access = self.x._entry("9GP")
        self.assertFalse(access["playable"])

    def test_run_refused_without_subscription(self):
        self.install_fake("9GP")
        with mock.patch.object(self.x.subprocess, "call") as call:
            self.assertEqual(self.x.action_run("9GP"), 3)
            call.assert_not_called()

    def test_download_refused_without_subscription(self):
        res = self.call(self.x.action_download, "9GP")
        self.assertEqual(res["Type"], "Error")

    def test_download_uses_drive_assign(self):
        with mock.patch.object(self.x.subprocess, "Popen") as popen, \
             mock.patch.object(self.x, "_drives") as drives:
            drives.return_value.assign.return_value = str(Path(self.tmp.name) / "d" / "9FREE")
            res = self.call(self.x.action_download, "9FREE")
        self.assertEqual(res["Type"], "Progress")
        drives.return_value.assign.assert_called_once()
        self.assertEqual(self.x.load_state()["pending"]["9FREE"]["contentId"], "c-free")
        self.assertIn("worker", popen.call_args.args[0])

    def test_cancel_mid_download_cleans_partial(self):
        root = Path(self.tmp.name) / "d" / "9FREE"
        root.mkdir(parents=True)
        (root / "part.bin").write_text("x")
        with self.x.locked_state() as st:
            st["pending"] = {"9FREE": {"root": str(root)}}
        with mock.patch.object(self.x, "_drives"):
            self.x._cleanup_partial("9FREE", root)
        self.assertFalse(root.exists())
        self.assertNotIn("9FREE", self.x.load_state().get("pending", {}))

    def test_worker_failure_reports_error_and_cleans(self):
        root = Path(self.tmp.name) / "d" / "9FREE"
        with self.x.locked_state() as st:
            st["pending"] = {"9FREE": {"root": str(root), "title": "Free Game", "art": {}, "contentId": "c"}}
        with mock.patch.object(self.x.xbox_tools, "ensure", return_value={"errors": ["offline"]}), \
             mock.patch.object(self.x, "_drives"):
            self.x.worker("9FREE")
        prog = json.loads((self.x.PROGRESS_DIR / "9FREE.json").read_text())
        self.assertTrue(prog["Error"])
        self.assertNotIn("9FREE", self.x.load_state()["games"])

    def test_uninstall_refused_while_running(self):
        self.install_fake("9OWN")
        with self.x.xbox_tools.hold("run-9OWN"):
            res = self.call(self.x.action_uninstall, "9OWN")
        self.assertEqual(res["Type"], "Error")

    def test_uninstall_removes_game(self):
        root = self.install_fake("9OWN")
        with mock.patch.object(self.x, "_drives"):
            res = self.call(self.x.action_uninstall, "9OWN")
        self.assertEqual(res["Type"], "Success")
        self.assertFalse(root.exists())

    def test_install_gives_native_launch_script(self):
        self.install_fake("9OWN")
        res = self.call(self.x.action_install, "9OWN", "123")
        self.assertEqual(res["Type"], "LaunchOptions")
        self.assertFalse(res["Content"]["Compatibility"])
        self.assertIn("run 9OWN", Path(res["Content"]["Exe"]).read_text())
        self.assertEqual(self.x.load_state()["games"]["9OWN"]["steamClientID"], "123")

    def test_login_status_shows_gamertag(self):
        res = self.call(self.x.action_loginstatus)
        self.assertEqual(res["Content"], {"Username": "T", "LoggedIn": True})

    def test_tab_order_xbox_before_disks(self):
        src = (ROOT / "defaults" / "scripts" / "get-json.py").read_text()
        order = src[src.index("TAB_ORDER"):src.index("]", src.index("TAB_ORDER"))]
        self.assertLess(order.index("GetXboxActions"), order.index("GetDisksActions"))
        self.assertGreater(order.index("GetXboxActions"), order.index("GetPortsActions"))

    def test_static_json_has_download_action(self):
        d = json.loads((ROOT / "defaults/scripts/Extensions/Xbox/static.json").read_text())
        ids = {a["Id"]: a["Command"] for a in d["xbox-actions"]["Content"]["Actions"]}
        self.assertIn("Download", ids)
        login = [a for a in d["xbox-login-actions"]["Content"]["Actions"] if a["Id"] == "Login"][0]
        self.assertIn("Xbox", login["Command"].split())


if __name__ == "__main__":
    unittest.main()
