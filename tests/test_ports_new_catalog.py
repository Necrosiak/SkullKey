"""Smoke checks for newly curated ports and their release assets."""
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import unittest
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "defaults" / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("ports", SCRIPTS / "ports.py")
ports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ports)
import ports_i18n


class NewPortsTests(unittest.TestCase):
    def test_file_copy_hint_is_portable_for_all_ports(self):
        for home in ("/home/deck", "/home/bazzite", "/home/alex", "/var/home/alex"):
            with self.subTest(home=home), patch.object(ports_i18n.os.path, "expanduser", return_value=home), patch.object(ports_i18n.os, "sep", "/"):
                for lang in ports_i18n.LANGS:
                    with patch.object(ports_i18n, "machine_lang_code", return_value=lang):
                        text = ports_i18n.howto_line(home + "/Games/ports/example/rom")
                        self.assertIn("~/Games/ports/example/rom", text)
                        self.assertNotIn(home, text)
                self.assertIn("<b>~</b>", ports_i18n.howto_line(home))
                self.assertIn(home + "-other/Games", ports_i18n.howto_line(home + "-other/Games"))

    def test_new_ports_have_complete_steam_artwork(self):
        artwork = ports._art_map()
        for name in ("acgc-pc-port", "pt-pc"):
            with self.subTest(name=name):
                self.assertEqual(set(artwork[name]), {"grid", "gridh", "hero", "logo", "icon"})
                for url in artwork[name].values():
                    self.assertTrue(url.startswith("https://cdn2.steamgriddb.com/"))
                self.assertEqual(ports._cover_url(ports.APPS[name]), artwork[name]["grid"])

    def test_official_release_assets_match_catalog(self):
        cases = (
            ("acgc-pc-port", "ACGC-PC-Port0.9.3.zip", "winarchive", "AnimalCrossing.exe"),
            ("pt-pc", "P.T.PC.Port.Setup-linux", "ptsetup", "pt"),
        )
        for name, asset, kind, exe in cases:
            with self.subTest(name=name):
                port = ports.APPS[name]
                self.assertTrue(re.search(port["asset"], asset, re.IGNORECASE))
                self.assertEqual(port["kind"], kind)
                self.assertEqual(port["exe"], exe)

    def test_release_lookup_including_playtest_fallback(self):
        acgc = ports.APPS["acgc-pc-port"]
        releases = [{"tag_name": "v0.9.3-playtest", "assets": [{
            "name": "ACGC-PC-Port0.9.3.zip", "updated_at": "2026-08-02T00:55:54Z",
            "browser_download_url": "https://github.com/flyngmt/ACGC-PC-Port/releases/download/v0.9.3-playtest/ACGC-PC-Port0.9.3.zip",
            "size": 4880000,
        }]}]
        with patch.object(ports, "http_json", side_effect=[urllib.error.HTTPError("https://example.com", 404, "no stable release", {}, None), releases]):
            info = ports.release_info({"releases": {}}, acgc)
        self.assertEqual(info["name"], "ACGC-PC-Port0.9.3.zip")
        self.assertEqual(info["tag"], "v0.9.3-playtest@2026-08-02T00:55:54Z")

    def test_each_language_has_description_and_file_instructions(self):
        for lang in ports_i18n.LANGS:
            with patch.dict(os.environ, {"LC_ALL": f"{lang}_XX.UTF-8"}):
                for name in ("acgc-pc-port", "pt-pc"):
                    with self.subTest(lang=lang, name=name):
                        self.assertTrue(ports_i18n.desc_for(name))
                        self.assertTrue(ports_i18n.needs_line(ports.APPS[name]))

    def test_pt_setup_uses_own_package_and_checks_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "pt-pc-source.pkg"
            source.write_bytes(b"example package")
            port = {**ports.APPS["pt-pc"], "pkg_source": str(source)}
            info = {"url": "https://example.com/setup", "name": "P.T.PC.Port.Setup-linux",
                    "tag": "v1.0.2"}
            pdir = root / "pt-pc"
            pdir.mkdir()

            def fake_download(url, dest, *args):
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b"setup")

            def fake_run(command, **kwargs):
                self.assertEqual(command[2], str(source))
                self.assertEqual(command[3], str(pdir))
                Path(command[4]).write_text("PASS installed\n")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(ports, "RUNTIME_DIR", root), \
                 patch.object(ports, "download_file", side_effect=fake_download), \
                 patch.object(ports, "write_progress"), \
                 patch.object(ports.subprocess, "run", side_effect=fake_run):
                ports._install_pt_setup(port, info, pdir, "pt-pc")

    def test_pt_setup_needs_package_or_existing_game_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            port = {**ports.APPS["pt-pc"], "pkg_source": str(root / "missing.pkg")}
            with self.assertRaisesRegex(RuntimeError, "fake PKG"):
                ports._install_pt_setup(port, {}, root / "pt-pc", "pt-pc")


if __name__ == "__main__":
    unittest.main()
