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
            mock.patch.object(self.x.xbox_tools, "ensure", return_value={"installed": [], "updated": [], "errors": []}),
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

    def test_grid_installs_engine_first(self):
        with mock.patch.object(self.x.xbox_tools, "ensure") as ensure:
            self.grid_names()
        ensure.assert_called_once_with(update=True, components=("backend",))

    def test_imports_games_installed_by_nexus(self):
        home = Path(os.environ["HOME"])
        game = home / "Games" / "Xodus Nexus" / "Aniimo"
        game.mkdir(parents=True)
        (game / "MicrosoftGame.config").write_text(
            "<Game><StoreId>9FREE</StoreId><ExecutableList><Executable Name=\"Aniimo.exe\"/></ExecutableList>"
            "<ShellVisuals DefaultDisplayName=\"Aniimo Legend\"/></Game>")
        (home / "Games" / "Xodus Nexus" / "Empty").mkdir()
        self.x.import_nexus_games()
        g = self.x.load_state()["games"]["9FREE"]
        self.assertEqual((g["root"], g["executable"], g["imported"]), (str(game), "Aniimo.exe", True))
        self.assertEqual(len(self.x.load_state()["games"]), 1)

    def test_imported_game_uninstall_removes_its_folder(self):
        root = Path(os.environ["HOME"]) / "Games" / "Xodus Nexus" / "Aniimo"
        root.mkdir(parents=True)
        with self.x.locked_state() as st:
            st["games"]["9FREE"] = {"title": "A", "root": str(root), "imported": True}
        with mock.patch.object(self.x, "_drives"):
            self.call(self.x.action_uninstall, "9FREE")
        self.assertFalse(root.exists())

    def test_download_of_present_game_skips_download(self):
        self.install_fake("9OWN")
        with mock.patch.object(self.x.subprocess, "Popen") as popen:
            res = self.call(self.x.action_download, "9OWN")
        popen.assert_not_called()
        self.assertEqual(res["Type"], "Progress")
        prog = self.call(self.x.action_getprogress, "9OWN")["Content"]
        self.assertEqual(prog["Percentage"], 100)
        self.assertFalse(prog["Error"])

    def test_progress_steps_are_explicit(self):
        with mock.patch.object(self.x, "_lang", return_value="fr"):
            self.assertEqual(self.x.step_text("engine"), "Étape 1/4 · Préparation du moteur Xbox")
            self.assertEqual(self.x.step_text("metadata"), "Étape 2/4 · Lecture du paquet du jeu")
            text = self.x.step_text("downloading", {"done": 12 * 2**30 + 3 * 2**28, "total": 90 * 2**30,
                                                    "rate": 58 * 2**20})
            self.assertEqual(text, "Étape 3/4 · Téléchargement · 14 % · 12,8 / 90,0 Go · 58 Mo/s · ~23 min")
            self.assertEqual(self.x.step_text("metadata", elapsed=102),
                             "Étape 2/4 · Lecture du paquet du jeu · 1:42")
            self.assertEqual(self.x.step_text("finalizing"), "Étape 4/4 · Finalisation")
        with mock.patch.object(self.x, "_lang", return_value="en"):
            self.assertEqual(self.x.step_text("downloading", {"done": 2**30, "total": 2 * 2**30, "rate": 0}),
                             "Step 3/4 · Downloading · 50 % · 1.0 / 2.0 GB")

    def test_anticheat_detected_in_installed_game(self):
        root = self.install_fake("9OWN")
        (root / "AntiCheatExpert").mkdir()
        self.assertEqual(self.x.anticheat("9OWN"), "AntiCheatExpert (ACE)")

    def test_anticheat_known_before_install(self):
        self.assertEqual(self.x.anticheat("9N1BZS0V3K0C"), "AntiCheatExpert (ACE)")
        self.assertIsNone(self.x.anticheat("9OWN"))

    def test_details_warn_about_anticheat(self):
        root = self.install_fake("9OWN")
        (root / "EasyAntiCheat").mkdir()
        with mock.patch.object(self.x, "_lang", return_value="fr"):
            desc = self.call(self.x.action_getgamedetails, "9OWN")["Content"]["Description"]
        self.assertIn("⚠️ Anti-triche Easy Anti-Cheat", desc)

    def test_run_log_records_exit_code(self):
        self.install_fake("9OWN")
        session = mock.Mock(env={})
        with mock.patch.object(self.x.xbox_service, "start", return_value=session), \
             mock.patch.object(self.x.xbox_prefix, "ensure_prefix"), \
             mock.patch.object(self.x.xbox_prefix, "write_runner", return_value=Path("/r")), \
             mock.patch.object(self.x.xbox_tools, "cli_path", return_value=Path("/cli")), \
             mock.patch.object(self.x.subprocess, "call", return_value=7):
            self.x.action_run("9OWN")
        self.assertIn("SkullKey: the game exited with code 7", (self.x.XBOX_DIR / "logs" / "9OWN.log").read_text())

    def test_details_explain_slower_start(self):
        self.install_fake("9OWN")
        with mock.patch.object(self.x, "_lang", return_value="fr"):
            desc = self.call(self.x.action_getgamedetails, "9OWN")["Content"]["Description"]
        self.assertIn("ℹ️ Démarrage plus long", desc)

    def test_grid_starts_background_check_of_unchecked_games(self):
        with mock.patch.object(self.x.xbox_catalog, "installable", return_value=None), \
             mock.patch.object(self.x, "_start_prefetch") as start:
            self.grid_names()
        start.assert_called_once()
        self.assertTrue({"9OWN", "9GP"} <= set(start.call_args.args[0]))

    def test_prefetch_checks_every_game_without_budget(self):
        seen = []
        with mock.patch.object(self.x.xbox_catalog, "installable",
                               side_effect=lambda pid, m, deadline=None: seen.append((pid, deadline)) or "c"):
            self.x.prefetch(["9A", "9B"])
        self.assertEqual(seen, [("9A", None), ("9B", None)])

    def write_manifest(self, root, langs):
        res = "".join(f'<Resource Language="{l}"/>' for l in langs)
        (root / "MicrosoftGame.config").write_text(
            f'<Game><Resources>{res}</Resources><ExecutableList><Executable Name="g.exe"/></ExecutableList></Game>')

    def test_game_locale_picks_machine_language(self):
        root = self.install_fake("9OWN")
        self.write_manifest(root, ["en-US", "fr-FR", "de-DE"])
        with mock.patch.object(self.x, "_lang", return_value="fr"):
            self.assertEqual(self.x.game_locale(root), "fr-FR")
        self.write_manifest(root, ["en-US", "fr"])
        with mock.patch.object(self.x, "_lang", return_value="fr"):
            self.assertEqual(self.x.game_locale(root), "fr")
        self.write_manifest(root, ["en-US"])
        with mock.patch.object(self.x, "_lang", return_value="fr"):
            self.assertIsNone(self.x.game_locale(root))

    def test_game_locale_follows_steam_language(self):
        root = self.install_fake("9OWN")
        self.write_manifest(root, ["en-US", "fr-FR", "de-DE"])
        reg = Path(os.environ["HOME"]) / ".steam" / "registry.vdf"
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text('"Registry" { "HKCU" { "Software" { "Valve" { "Steam" { "language" "german" } } } } }')
        with mock.patch.object(self.x, "_lang", return_value="fr"):
            self.assertEqual(self.x.game_locale(root), "de-DE")

    def test_locale_environment(self):
        env = self.x.locale_env({}, "fr-FR")
        self.assertEqual((env["XODUS_PACKAGE_LOCALE"], env["WINEUSERLOCALE"], env["LANG"], env["LANGUAGE"]),
                         ("fr-FR", "fr-FR", "fr_FR.UTF-8", "fr_FR:fr"))
        self.assertEqual(self.x.locale_env({"A": "1"}, None), {"A": "1"})

    def test_run_passes_the_game_language(self):
        root = self.install_fake("9OWN")
        self.write_manifest(root, ["en-US", "fr-FR"])
        session = mock.Mock(env={})
        with mock.patch.object(self.x.xbox_service, "start", return_value=session), \
             mock.patch.object(self.x.xbox_prefix, "ensure_prefix"), \
             mock.patch.object(self.x.xbox_prefix, "write_runner", return_value=Path("/r")), \
             mock.patch.object(self.x, "sync_prefix_locale") as sync, \
             mock.patch.object(self.x.xbox_tools, "cli_path", return_value=Path("/cli")), \
             mock.patch.object(self.x, "_lang", return_value="fr"), \
             mock.patch.object(self.x.subprocess, "call", return_value=0) as call:
            self.x.action_run("9OWN")
        self.assertEqual(call.call_args.kwargs["env"]["XODUS_PACKAGE_LOCALE"], "fr-FR")
        sync.assert_called_once()

    def test_install_contents_downloads_licensed_missing_content(self):
        root = self.install_fake("9OWN")
        offer = {"productId": "9CAMP", "contentId": "a49a529d-7ce4-42b3-b5b7-028b96860773", "title": "Campaign", "family": "F"}
        proc = mock.Mock(stdout=['NEXUS_PROGRESS {"schema": 1, "event": "progress", "sequence": 1, "phase": "complete", '
                                 '"completedBytes": 1, "totalBytes": 1, "bytesPerSecond": 0, "paused": false, "canPause": false}'])
        proc.wait.return_value = 0
        with mock.patch.object(self.x.xbox_content, "plan", return_value=[offer]) as plan, \
             mock.patch.object(self.x.xbox_cli, "start_streaming", return_value=proc) as stream:
            got = self.x.install_contents("9OWN")
        self.assertEqual(got, ["Campaign"])
        self.assertEqual(stream.call_args.args[0], offer["contentId"])
        self.assertIn("9OWN", plan.call_args.args[1])  # licensed set comes from the account
        self.assertTrue(self.x.xbox_content.installed("9OWN", "9CAMP"))

    def test_run_passes_content_roots(self):
        self.install_fake("9OWN")
        session = mock.Mock(env={})
        with mock.patch.object(self.x.xbox_service, "start", return_value=session), \
             mock.patch.object(self.x.xbox_prefix, "ensure_prefix"), \
             mock.patch.object(self.x.xbox_prefix, "write_runner", return_value=Path("/r")), \
             mock.patch.object(self.x, "install_contents", return_value=[]) as contents, \
             mock.patch.object(self.x.xbox_content, "roots_env", return_value="Z:\\c\\9CAMP"), \
             mock.patch.object(self.x.xbox_tools, "cli_path", return_value=Path("/cli")), \
             mock.patch.object(self.x.subprocess, "call", return_value=0) as call:
            self.x.action_run("9OWN")
        contents.assert_called_once_with("9OWN")
        self.assertEqual(call.call_args.kwargs["env"]["XODUS_CONTENT_ROOTS"], "Z:\\c\\9CAMP")

    def test_autoupdate_updates_only_games_with_a_newer_version(self):
        self.install_fake("9OWN")
        self.install_fake("9GP")
        session = mock.Mock(env={"XODUS_SOCKET": "/s"})
        answers = {"9OWN": {"available": True, "latest": "2.0.0.0"}, "9GP": {"available": False, "latest": "1.0.0.0"}}
        with mock.patch.object(self.x.xbox_service, "start", return_value=session), \
             mock.patch.object(self.x.xbox_updates, "installed_version", return_value="1.0.0.0"), \
             mock.patch.object(self.x.xbox_updates, "query", side_effect=lambda s, pid, v: answers[pid]), \
             mock.patch.object(self.x, "update_game", return_value=True) as upd:
            res = self.call(self.x.action_autoupdate)
        upd.assert_called_once_with("9OWN")
        self.assertIn("1 updated", res["Content"]["Message"])

    def test_autoupdate_asks_with_the_installed_store_id(self):
        root = self.install_fake("9BUNDLE")
        (root / "MicrosoftGame.config").write_text("<Game><StoreId>9BASE</StoreId><Identity Name=\"A\" Publisher=\"B\" Version=\"1.0.0.0\"/></Game>")
        session = mock.Mock(env={"XODUS_SOCKET": "/s"})
        with mock.patch.object(self.x.xbox_service, "start", return_value=session), \
             mock.patch.object(self.x.xbox_updates, "query", return_value={"available": False}) as q:
            self.call(self.x.action_autoupdate)
        self.assertEqual(q.call_args.args[1], "9BASE")
        session.stop.assert_called_once()

    def test_autoupdate_skips_running_games(self):
        self.install_fake("9OWN")
        session = mock.Mock(env={"XODUS_SOCKET": "/s"})
        with self.x.xbox_tools.hold("run-9OWN"), \
             mock.patch.object(self.x.xbox_service, "start", return_value=session), \
             mock.patch.object(self.x.xbox_updates, "query") as q:
            self.call(self.x.action_autoupdate)
        q.assert_not_called()

    def test_failed_update_keeps_the_installed_game(self):
        root = self.install_fake("9OWN")
        (root / "game.bin").write_text("x")
        proc = mock.Mock(stdout=[])
        proc.wait.return_value = 1
        with mock.patch.object(self.x.xbox_cli, "start_streaming", return_value=proc), \
             mock.patch.object(self.x, "install_contents", return_value=[]):
            self.assertFalse(self.x.update_game("9OWN"))
        self.assertTrue((root / "game.bin").exists())
        self.assertIn("9OWN", self.x.load_state()["games"])

    def test_grid_always_shows_account_bar(self):
        self.assertEqual(self.call(self.x.action_getgames, "", "false")["Content"]["NeedsLogin"], "true")

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

    def test_run_starts_account_service_for_the_game(self):
        self.install_fake("9OWN")
        session = mock.Mock(env={"XODUS_SOCKET": "/s", "XODUS_BRIDGE_PORT": "1", "XODUS_BRIDGE_KEY": "k",
                                 "XODUS_SAVE_SYNC": "auto"})
        with mock.patch.object(self.x.xbox_service, "start", return_value=session),              mock.patch.object(self.x.xbox_prefix, "ensure_prefix"),              mock.patch.object(self.x.xbox_prefix, "write_runner", return_value=Path("/r")),              mock.patch.object(self.x.xbox_tools, "cli_path", return_value=Path("/cli")),              mock.patch.object(self.x.subprocess, "call", return_value=0) as call:
            self.assertEqual(self.x.action_run("9OWN"), 0)
        env = call.call_args.kwargs["env"]
        self.assertEqual((env["XODUS_BRIDGE_KEY"], env["XODUS_SAVE_SYNC"]), ("k", "auto"))
        log = call.call_args.kwargs["stdout"]
        self.assertTrue(log.name.endswith("logs/9OWN.log"))
        self.assertIs(call.call_args.kwargs["stderr"], self.x.subprocess.STDOUT)
        session.stop.assert_called_once()

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

    def test_login_status_shows_gamertag_and_subscription(self):
        with mock.patch.object(self.x, "_lang", return_value="fr"):
            res = self.call(self.x.action_loginstatus)
        self.assertEqual(res["Content"], {"Username": "T · Game Pass : inactif", "LoggedIn": True})
        self.sub = {"status": "active"}
        with self.x.locked_state() as st:
            st.pop("account", None)
        with mock.patch.object(self.x, "_lang", return_value="en"):
            res = self.call(self.x.action_loginstatus)
        self.assertEqual(res["Content"]["Username"], "T · Game Pass: active")

    def test_settings_roundtrip(self):
        self.assertEqual(self.call(self.x.action_getsetting, "LoginSteamClientId")["Content"],
                         {"name": "LoginSteamClientId", "value": ""})
        self.call(self.x.action_savesetting, "LoginSteamClientId", "42")
        self.assertEqual(self.call(self.x.action_getsetting, "LoginSteamClientId")["Content"]["value"], "42")

    def test_static_json_login_has_settings(self):
        d = json.loads((ROOT / "defaults/scripts/Extensions/Xbox/static.json").read_text())
        ids = {a["Id"] for a in d["xbox-login-actions"]["Content"]["Actions"]}
        self.assertTrue({"GetSetting", "SaveSetting"} <= ids)

    def test_tab_order_xbox_right_after_gog(self):
        import ast
        src = (ROOT / "defaults" / "scripts" / "get-json.py").read_text()
        order = ast.literal_eval(src[src.index("[", src.index("TAB_ORDER")):src.index("]", src.index("TAB_ORDER")) + 1])
        self.assertEqual(order.index("GetXboxActions"), order.index("GetGOGActions") + 1)
        self.assertEqual(order[-1], "GetDisksActions")

    def test_static_json_has_download_action(self):
        d = json.loads((ROOT / "defaults/scripts/Extensions/Xbox/static.json").read_text())
        ids = {a["Id"]: a["Command"] for a in d["xbox-actions"]["Content"]["Actions"]}
        self.assertIn("Download", ids)
        login = [a for a in d["xbox-login-actions"]["Content"]["Actions"] if a["Id"] == "Login"][0]
        self.assertIn("Xbox", login["Command"].split())


if __name__ == "__main__":
    unittest.main()
