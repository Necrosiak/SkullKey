"""EA adapter contracts, tested without Maxima, OAuth or an EA account."""
import importlib.util
import contextlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import socket
import types
import unittest
from unittest.mock import patch

DIRECTORY = Path(__file__).resolve().parents[1] / "defaults/scripts/Extensions/EA"


def module(name):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"fcntl": types.SimpleNamespace()} if os.name == "nt" else {}):
        spec.loader.exec_module(result)
    return result


ea = module("ea")
callback = module("qrc_callback")
browser = module("open_browser")
webview = module("open_webview")


class EATests(unittest.TestCase):
    def test_integrated_login_requires_saved_auth_and_validated_library(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SK_ACCOUNT_DIR": tmp}), \
                patch.object(ea.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as launch:
            self.assertEqual(ea.dispatch("_desktop-login", [])["Type"], "Error")
            self.assertTrue(launch.call_args.args[0][1].endswith("login_gui.py"))
            state = ea.state(); state["validated"] = True; ea.save(state)
            self.assertEqual(ea.dispatch("_desktop-login", [])["Type"], "Error")
            auth = ea.root() / "data/maxima/auth.toml"
            auth.parent.mkdir(parents=True); auth.write_text("fake fixture")
            self.assertEqual(ea.dispatch("_desktop-login", [])["Type"], "RefreshContent")

    @unittest.skipIf(os.name == "nt", "Unix socket ownership validation")
    def test_webview_url_transport_is_private_and_in_memory(self):
        # Short Unix socket path; avoid the long Windows workspace on Linux.
        with tempfile.TemporaryDirectory(prefix="ea-ipc-") as tmp:
            os.chmod(tmp, 0o700)
            path = Path(tmp) / "browser.sock"
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(path)); os.chmod(path, 0o600); server.listen(1)
                url = "https://accounts.ea.com/connect/auth?nonce=fake-fixture"
                with patch.dict(os.environ, {"SK_EA_LOGIN_SOCKET": str(path)}):
                    webview.deliver(url)
                    with server.accept()[0] as connection:
                        self.assertEqual(connection.recv(32768).decode(), url)
                    os.chmod(path, 0o666)
                    with self.assertRaises(ValueError):
                        webview.deliver(url)

    def test_webview_rejects_non_ea_url_before_connecting(self):
        for url in ("http://accounts.ea.com/", "https://accounts.ea.com.evil/", "file:///tmp/a"):
            with self.assertRaises(ValueError):
                webview.deliver(url)

    def test_maxima_keeps_callback_and_browser_outside_isolated_storage(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,
                {"SK_ACCOUNT_DIR": tmp, "XDG_DATA_HOME": "/desktop/custom-data",
                 "SK_EA_BROWSER_XDG_CONFIG_HOME": "stale"}, clear=True):
            original = dict(os.environ)
            private = ea.env()
            self.assertEqual(private["MAXIMA_DISABLE_QRC"], "1")
            self.assertTrue(private["BROWSER"].endswith("open_browser.py"))
            self.assertNotIn("SK_EA_BROWSER_XDG_CONFIG_HOME", private)
            self.assertEqual(dict(os.environ), original)
            with patch.dict(os.environ, private, clear=True):
                desktop = browser.desktop_env()
            self.assertEqual(desktop["XDG_DATA_HOME"], "/desktop/custom-data")
            self.assertNotIn("XDG_CONFIG_HOME", desktop)
            self.assertNotIn("BROWSER", desktop)
            self.assertNotIn("SK_ACCOUNT_DIR", desktop)

    def test_browser_only_opens_official_https_login_and_never_logs_url(self):
        url = "https://accounts.ea.com/connect/auth?code=secret-fixture"
        with patch.object(browser.shutil, "which", side_effect=lambda n, **kw: "/usr/bin/firefox" if n == "firefox" else None), \
                patch.object(browser.subprocess, "Popen") as run:
            browser.open_login(url)
            self.assertEqual(run.call_args.args[0], ["/usr/bin/firefox", "--new-window", url])
            self.assertEqual(run.call_args.kwargs["stdout"], browser.subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs["stderr"], browser.subprocess.DEVNULL)
        for url in ("file:///tmp/test", "http://accounts.ea.com/", "https://accounts.ea.com.evil/",
                    "https://other.example/", "https://user:pass@accounts.ea.com/", "https://accounts.ea.com:8000/"):
            with self.subTest(url=url), patch.object(browser.subprocess, "Popen") as run:
                with self.assertRaises(ValueError):
                    browser.open_login(url)
                run.assert_not_called()

    def test_flatpak_firefox_avoids_steam_browser_and_short_timeout(self):
        url = "https://accounts.ea.com/connect/auth?code=fixture"
        with patch.object(browser.shutil, "which", side_effect=lambda n, **kw: "/usr/bin/flatpak" if n == "flatpak" else None), \
                patch.object(browser.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as probe, \
                patch.object(browser.subprocess, "Popen") as launch:
            browser.open_login(url)
            self.assertEqual(probe.call_args.args[0], ["/usr/bin/flatpak", "info", "org.mozilla.firefox", "--show-ref"])
            self.assertEqual(launch.call_args.args[0], ["/usr/bin/flatpak", "run", "org.mozilla.firefox", "--new-window", url])
            self.assertNotIn("timeout", launch.call_args.kwargs)

    def test_desktop_opener_fallback_never_uses_steam_xdg_shim(self):
        with patch.object(browser.shutil, "which", side_effect=lambda n, **kw: "/usr/bin/gio" if n == "gio" else None), \
                patch.object(browser.subprocess, "Popen") as launch:
            browser.open_login("https://accounts.ea.com/connect/auth")
            self.assertEqual(launch.call_args.args[0][0:2], ["/usr/bin/gio", "open"])

    def test_desktop_failure_preserves_exit_code_and_elapsed_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SK_ACCOUNT_DIR": tmp}):
            result = types.SimpleNamespace(returncode=7, stdout="secret-token", stderr="secret-code")
            with patch.object(ea, "session_lock", return_value=contextlib.nullcontext()), \
                    patch.object(ea, "setup_callback"), patch.object(ea.shutil, "which", return_value=None), \
                    patch.object(ea, "client", return_value=Path(tmp) / "fake-client"), \
                    patch.object(ea.subprocess, "run", return_value=result):
                response = ea.dispatch("_desktop-login", [])
            self.assertEqual(response["Type"], "Error")
            diagnostic = json.loads((ea.root() / "login-diagnostic.json").read_text())
            self.assertEqual(diagnostic["exit_code"], 7)
            self.assertIn("elapsed_seconds", diagnostic)
            self.assertNotIn("secret", json.dumps(diagnostic))

    def test_login_diagnostic_never_contains_raw_output(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SK_ACCOUNT_DIR": tmp}):
            result = types.SimpleNamespace(returncode=1, stdout="secret-token", stderr="secret-code")
            with patch.object(ea, "client", return_value=Path(tmp) / "fake-client"), patch.object(ea.subprocess, "run", return_value=result):
                with self.assertRaises(RuntimeError):
                    ea.refresh()
            data = (ea.root() / "login-diagnostic.json").read_text()
            self.assertNotIn("secret", data)
            self.assertEqual(json.loads(data)["exit_code"], 1)

    def test_embedded_python_falls_back_to_system_python(self):
        with patch.object(ea.sys, "executable", ""), patch.object(ea.shutil, "which", return_value=__file__):
            self.assertEqual(ea.python_command(), __file__)
        with patch.object(ea.sys, "executable", ""), patch.object(ea.shutil, "which", return_value=None):
            with self.assertRaises(RuntimeError):
                ea.python_command()

    def test_plugin_login_uses_visible_desktop_flow(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SK_ACCOUNT_DIR": tmp}):
            result = ea.dispatch("login", [])
            self.assertTrue(result["Content"]["Exe"].endswith("login-desktop.sh"))
            self.assertIn("_desktop-login", Path(result["Content"]["Exe"]).read_text())

    def test_prepare_is_non_authenticating_and_preserves_user_shortcut(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SK_ACCOUNT_DIR": str(Path(tmp) / "account")}):
            desktop = Path(tmp) / "Desktop"
            def run(command, **kwargs):
                if command[-1] == "--help":
                    return types.SimpleNamespace(returncode=0, stdout="list-games install launch")
                self.assertEqual(command, ["xdg-user-dir", "DESKTOP"])
                return types.SimpleNamespace(stdout=str(desktop))
            with patch.object(ea, "session_lock", return_value=contextlib.nullcontext()), patch.object(ea, "client", return_value=Path(tmp) / "fake-client"), patch.object(ea, "setup_callback") as setup, patch.object(ea.subprocess, "run", side_effect=run):
                result = ea.dispatch("_prepare", [])
                self.assertFalse(result["Content"]["Authenticated"])
                setup.assert_called_once()
                shortcut = desktop / "SkullKey-EA.desktop"
                self.assertIn("login-desktop.sh", shortcut.read_text())
                self.assertFalse((ea.root() / "data/maxima/auth.toml").exists())
                shortcut.write_text("User-owned shortcut")
                with self.assertRaises(RuntimeError):
                    ea.dispatch("_prepare", [])
                self.assertEqual(shortcut.read_text(), "User-owned shortcut")

    def test_callback_accepts_upstream_close_but_not_connection_failure(self):
        with patch.object(callback.urllib.request, "urlopen", side_effect=http.client.RemoteDisconnected()):
            callback.forward("qrc:///login?code=fixture")
        with patch.object(callback.urllib.request, "urlopen", side_effect=ConnectionRefusedError()):
            with self.assertRaises(ConnectionRefusedError):
                callback.forward("qrc:///login?code=fixture")

    @unittest.skipIf(os.name == "nt", "Linux flock qualification")
    def test_accounts_share_session_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"SK_ACCOUNT_DIR": str(Path(tmp) / "alice")}):
                with ea.session_lock():
                    with patch.dict(os.environ, {"SK_ACCOUNT_DIR": str(Path(tmp) / "bob")}):
                        with self.assertRaises(BlockingIOError), ea.session_lock():
                            self.fail("Concurrent EA sessions must not start")

    def test_dead_worker_can_be_retried_without_pid_kill(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SK_ACCOUNT_DIR": tmp}):
            s = ea.state(); s["games"] = [{"slug": "owned", "name": "Owned", "installed": False}]; ea.save(s)
            ea.write_job("owned", {"token": "old", "worker_pid": 999999999, "worker_start": "old", "active": True,
                                 "Percentage": 50, "Description": "Downloading", "Error": None})
            job = ea.read_job("owned")
            self.assertFalse(job["active"])
            self.assertEqual(job["Percentage"], 0)

    def test_install_verification_rejects_false_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            record = json.dumps({"slug": "owned", "installed": True})
            self.assertFalse(ea.installation_verified("owned", directory, record))
            (directory / "game.exe").write_bytes(b"game")
            self.assertTrue(ea.installation_verified("owned", directory, record))
            for output in (record + "\nERROR failed", '{"slug":"other","installed":true}', '{"slug":"owned","installed":false}', "Download Complete"):
                self.assertFalse(ea.installation_verified("owned", directory, output))

    def test_slugs_cannot_escape_account(self):
        for slug in ("..", "../other", "/tmp/game", "a/b", "a;touch x"):
            with self.assertRaises(RuntimeError):
                ea.game(slug)

    @unittest.skipIf(os.name == "nt", "Linux process/session qualification")
    def test_worker_success_failure_and_cancel_without_account(self):
        for mode in ("success", "zero-error", "cancel"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SK_ACCOUNT_DIR": tmp}):
                directory = ea.root()
                auth = directory / "data/maxima/auth.toml"; auth.parent.mkdir(parents=True); auth.write_text("fake fixture, no account")
                s = ea.state(); s.update(validated=True, games=[{"slug": "owned", "name": "Owned", "installed": False}]); ea.save(s)
                cli = directory / "fake-cli"
                cli.write_text('#!/usr/bin/env python3\nimport sys,pathlib\nif sys.argv[1] == "install":\n p=pathlib.Path(sys.argv[-1]); (p/"game.exe").write_bytes(b"fixture")\n print("Progress: 50.25")\n print("ERROR secret-must-not-persist" if ' + repr(mode) + ' == "zero-error" else "Download Complete")\nelse: print(\'{"slug":"owned","installed":true}\')\n')
                cli.chmod(0o700)
                ea.write_job("owned", {"token": "fixture", "active": True, "Percentage": 0, "Description": "Starting", "Error": None})
                if mode == "cancel":
                    (directory / "cancel-owned").write_text("fixture")
                def refresh():
                    s = ea.state(); s["games"][0]["installed"] = True; ea.save(s)
                with patch.object(ea, "client", return_value=cli), patch.object(ea, "refresh", side_effect=refresh):
                    ea.install_worker("owned", "fixture")
                job = ea.read_job("owned")
                self.assertFalse(job["active"])
                self.assertEqual(job["Percentage"], 100 if mode == "success" else 0)
                self.assertNotIn("secret-must-not-persist", ea.job_path("owned").read_text())

    def test_library_dashes_and_installed(self):
        text = "INFO - [maxima_cli] - Owned games:\n" + "\x1b[32mINFO\x1b[37m - [maxima_cli] - " + f"{'my-game':<35} - {'Game - Deluxe':<35} - {'offer':<25} - Installed: true"
        self.assertEqual(ea.parse_library(text), [{"slug": "my-game", "name": "Game - Deluxe", "offer": "offer", "installed": True}])

    def test_library_long_slug_and_title_without_padding(self):
        # maxima-cli widths are minimums: 35+ chars leave a single space before " - ".
        slug, name = "a-very-long-game-slug-that-exceeds-35", "A Very Long Title - Deluxe Edition Plus More"
        rows = [f"INFO - [maxima_cli] - {slug:<35} - {name:<35} - {'Origin.OFR.50.0001234':<25} - Installed: false",
                f"INFO - [maxima_cli] - {'short':<35} - {name:<35} - {'offer':<25} - Installed: true",
                f"INFO - [maxima_cli] -   {'Some DLC':<55} - {'Origin.OFR.50.0009999':<25}"]
        text = "INFO - [maxima_cli] - Owned games:\n" + "\n".join(rows)
        self.assertEqual(ea.parse_library(text), [{"slug": slug, "name": name, "offer": "Origin.OFR.50.0001234", "installed": False},
                                                  {"slug": "short", "name": name, "offer": "offer", "installed": True}])

    def test_exit_zero_error_and_missing_header_fail(self):
        for text in ("ERROR OAuth failed\nOwned games:", "Logging in...", "Owned games:\nbad - Installed: true"):
            with self.assertRaises(RuntimeError):
                ea.parse_library(text)

    def test_callback_fixed_loopback_and_encoding(self):
        self.assertEqual(callback.callback_url("qrc:///login?code=a%26b"), "http://127.0.0.1:31033/auth?code=a%26b")
        for uri in ("https://evil/auth?code=x", "qrc:/?code=a&code=b", "qrc:/?code=", "qrc:/"):
            with self.assertRaises(ValueError):
                callback.callback_url(uri)

    def test_account_required_and_separate(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            ea.root()
        with tempfile.TemporaryDirectory() as tmp:
            for account in ("alice", "bob"):
                with patch.dict(os.environ, {"SK_ACCOUNT_DIR": str(Path(tmp) / account)}):
                    self.assertIn(account, ea.env()["XDG_DATA_HOME"])

    def test_native_launcher_quotes_paths_and_never_proton_on_proton(self):
        with tempfile.TemporaryDirectory(prefix="ea spaces ") as tmp:
            with patch.dict(os.environ, {"SK_ACCOUNT_DIR": tmp}):
                s = ea.state(); s["games"] = [{"slug": "test", "name": "Title", "installed": True}]; ea.save(s)
                options = ea.launch_options("_launch", "test")
                self.assertFalse(options["Compatibility"])
                self.assertNotIn("%command%", options["Options"])
                self.assertIn("export SK_ACCOUNT_DIR=", Path(options["Exe"]).read_text())

    def test_existing_qrc_handler_is_not_replaced(self):
        with patch.object(ea.subprocess, "run", return_value=types.SimpleNamespace(stdout="existing.desktop\n")) as run:
            ea.setup_callback()
            self.assertEqual(run.call_count, 1)

    def test_static_actions_never_call_secret_diagnostics(self):
        content = (DIRECTORY / "static.json").read_text()
        json.loads(content)
        for forbidden in ("account-info", "auth-env", "--login", "shell=True"):
            self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
