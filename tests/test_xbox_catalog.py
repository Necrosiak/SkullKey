import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))


def item(pid, title, price=0, display="Gratuit", game=True):
    return {"productId": pid, "title": title, "price": price, "displayPrice": display, "isGame": game,
            "publisherName": "Pub", "posterArtUrl": "https://img/" + pid + "/poster",
            "boxArtUrl": "https://img/" + pid + "/box", "iconUrl": "https://img/" + pid + "/icon",
            "images": [{"imageType": "SuperHeroArt", "url": "https://img/" + pid + "/hero"}]}


GAMEPASS_ONLY = dict(item("9gp", "Included"), displayPrice="Inclus",
                     priceInfo={"price": 29.99, "displayPrice": "29,99 €"})
LIST = {"productsList": [item("9pk8phlcqdf6", "Aniimo"), item("9wzdncrfhwd2", "Solitaire"),
                         item("9paid", "Paid", 19.99, "19,99 €"),
                         item("9preorder", "Soon", 0, "Disponible sur 22/10/2026"), GAMEPASS_ONLY]}


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = self.tmp.name
        import importlib
        import xbox_tools
        import xbox_catalog
        importlib.reload(xbox_tools)
        self.c = importlib.reload(xbox_catalog)
        self.resolved = []

        def resolve(pid, market):
            self.resolved.append(pid)
            if pid.upper() == "9WZDNCRFHWD2":
                return {"status": "unavailable", "choices": [{"supported": False, "contentId": "u"}]}
            return {"status": "ready", "choices": [{"supported": False, "contentId": "x"},
                                                   {"supported": True, "contentId": "c-" + pid}]}
        p = mock.patch.object(self.c.xbox_cli, "resolve", side_effect=resolve)
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_free_list_filters_paid_and_preorders(self):
        games = self.c.free_games("FR", "fr-fr", fetch=lambda url: LIST)
        self.assertEqual([g["id"] for g in games], ["9PK8PHLCQDF6"])
        self.assertEqual(games[0]["price"], "free")

    def test_uwp_apps_hidden_when_not_installable(self):
        games = self.c.free_games("FR", "fr-fr", fetch=lambda url: LIST)
        self.assertNotIn("9WZDNCRFHWD2", [g["id"] for g in games])

    def test_resolve_cache_24h(self):
        self.c.free_games("FR", "fr-fr", fetch=lambda url: LIST)
        n = len(self.resolved)
        self.c.free_games("FR", "fr-fr", fetch=lambda url: LIST)
        self.assertEqual(len(self.resolved), n)

    def test_engine_error_is_unknown_not_unsupported(self):
        with mock.patch.object(self.c.xbox_cli, "resolve", return_value=None):
            self.assertIsNone(self.c.installable("9FAIL", "FR"))
        # Remembered as unknown for a while, then asked again.
        self.assertIsNone(self.c.installable("9FAIL", "FR"))
        later = self.c.time.time() + self.c.FAILED_TTL + 1
        with mock.patch.object(self.c.time, "time", return_value=later):
            self.assertEqual(self.c.installable("9FAIL", "FR"), "c-9FAIL")

    def test_download_size_of_the_pc_package(self):
        prod = {"Products": [{"DisplaySkuAvailabilities": [{"Sku": {"Properties": {"Packages": [
            {"PackageFormat": "XVC", "ContentId": "x", "MaxDownloadSizeInBytes": 9},
            {"PackageFormat": "MSIXVC", "ContentId": "C-1", "MaxDownloadSizeInBytes": 1161228288}]}}}]}]}
        self.assertEqual(self.c.download_size("9AB", "c-1", "FR", fetch=lambda url: prod), 1161228288)
        self.assertEqual(self.c.download_size("9AB", "c-1", "FR", fetch=lambda url: {}), 1161228288)  # cached
        self.assertEqual(self.c.download_size("9CD", None, "FR", fetch=lambda url: {}), 0)

    def test_store_down_returns_empty_not_raise(self):
        def boom(url):
            raise OSError("offline")
        self.assertEqual(self.c.free_games("FR", "fr-fr", fetch=boom), [])
        self.assertEqual(self.c.search("x", "FR", "fr-fr", fetch=boom), [])

    def test_resolve_budget_15s(self):
        clock = iter([0, 0, 16, 16, 16, 16, 16, 16])
        with mock.patch.object(self.c.time, "monotonic", side_effect=lambda: next(clock, 99)):
            games = self.c.free_games("FR", "fr-fr", fetch=lambda url: {"productsList": [item("9a", "A"), item("9b", "B")]})
        self.assertEqual(len(games), 1)

    def test_search_keeps_owned_paid_games(self):
        res = self.c.search("x", "FR", "fr-fr", owned={"9PAID"}, fetch=lambda url: LIST)
        ids = [g["id"] for g in res]
        self.assertIn("9PAID", ids)
        self.assertIn("9PK8PHLCQDF6", ids)
        self.assertEqual(next(g for g in res if g["id"] == "9PAID")["price"], "paid")

    def test_included_with_game_pass_is_not_free(self):
        games = self.c.free_games("FR", "fr-fr", fetch=lambda url: LIST)
        self.assertNotIn("9GP", [g["id"] for g in games])

    def test_supported_content_id_kept(self):
        g = self.c.free_games("FR", "fr-fr", fetch=lambda url: LIST)[0]
        self.assertEqual(g["contentId"], "c-9PK8PHLCQDF6")

    def test_artwork_from_list_entry(self):
        g = self.c.free_games("FR", "fr-fr", fetch=lambda url: LIST)[0]
        self.assertEqual(g["art"]["hero"], "https://img/9pk8phlcqdf6/hero")
        self.assertEqual(g["art"]["cover"], "https://img/9pk8phlcqdf6/poster")

    def test_details_titles_and_images(self):
        payload = {"Products": [{"ProductId": "9MSWWJWRF4WC", "ProductKind": "Game", "LocalizedProperties": [{
            "ProductTitle": "Fable Fortune", "PublisherName": "Mediatonic", "ShortDescription": "Cards",
            "Images": [{"ImagePurpose": "Poster", "Uri": "//img/poster"}, {"ImagePurpose": "SuperHeroArt", "Uri": "//img/hero"},
                       {"ImagePurpose": "Logo", "Uri": "//img/logo"}, {"ImagePurpose": "BoxArt", "Uri": "//img/box"}]}]},
            {"ProductId": "9DLC", "ProductKind": "Durable", "LocalizedProperties": [{"ProductTitle": "DLC", "Images": []}]}]}
        d = self.c.details(["9MSWWJWRF4WC", "9DLC"], "FR", "fr-fr", fetch=lambda url: payload)
        self.assertEqual(d["9MSWWJWRF4WC"]["title"], "Fable Fortune")
        self.assertEqual(d["9MSWWJWRF4WC"]["art"]["cover"], "https://img/poster")
        self.assertEqual(d["9MSWWJWRF4WC"]["art"]["logo"], "https://img/logo")
        self.assertFalse(d["9DLC"]["game"])

    def test_details_fall_back_to_full_description(self):
        payload = {"Products": [{"ProductId": "9A", "ProductKind": "Game", "LocalizedProperties": [{
            "ProductTitle": "A", "ShortDescription": "", "ProductDescription": "Long text\r\nline two", "Images": []}]}]}
        d = self.c.details(["9A"], "FR", "fr-fr", fetch=lambda url: payload)
        self.assertEqual(d["9A"]["description"], "Long text<br>line two")

    def test_concurrent_writers_keep_every_result(self):
        import subprocess, sys, textwrap
        code = textwrap.dedent('''
            import os, sys
            sys.path.insert(0, sys.argv[1])
            import xbox_catalog
            for i in range(40):
                xbox_catalog._merge("resolve.json", {f"FR:{sys.argv[2]}{i}": {"content": "c", "t": 1}})
        ''')
        scripts = str(Path(__file__).resolve().parents[1] / "defaults" / "scripts")
        procs = [subprocess.Popen([sys.executable, "-c", code, scripts, tag]) for tag in ("A", "B", "C")]
        for p in procs:
            p.wait(timeout=60)
        data = self.c._load("resolve.json")
        self.assertEqual(len(data), 120)

    def test_details_cached(self):
        calls = []
        payload = {"Products": [{"ProductId": "9X", "ProductKind": "Game", "LocalizedProperties": [{"ProductTitle": "X", "Images": []}]}]}
        self.c.details(["9X"], "FR", "fr-fr", fetch=lambda url: calls.append(url) or payload)
        self.c.details(["9X"], "FR", "fr-fr", fetch=lambda url: calls.append(url) or payload)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
