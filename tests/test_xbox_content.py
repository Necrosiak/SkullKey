import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))

BASE = "BethesdaSoftworks.DOOMEternal-PC"
CONFIG = f"""<Game><Identity Name="{BASE}" Publisher="CN=X" Version="1.0.56.0"/><StoreId>9P74BRFBXXC6</StoreId>
<RelatedProducts><RelatedProduct>9PC4V8W0VCWT</RelatedProduct><RelatedProduct>9P2MSCGJPKJC</RelatedProduct></RelatedProducts></Game>"""


def pkg(content, family, main=None):
    p = {"PackageFormat": "MSIXVC", "Architectures": ["x64"], "PlatformDependencies": [{"PlatformName": "Windows.Desktop"}],
         "ContentId": content, "PackageFamilyName": family}
    if main:
        p["MainPackageFamilyNameForDlc"] = main
    return p


def product(pid, kind, title, *pkgs):
    return {"ProductId": pid, "ProductType": kind, "LocalizedProperties": [{"ProductTitle": title}],
            "DisplaySkuAvailabilities": [{"Sku": {"Properties": {"IsTrial": False, "Packages": list(pkgs)}}}]}


CATALOG = {"Products": [
    product("9P74BRFBXXC6", "Game", "DOOM Eternal", pkg("1605dd05-06f3-4181-a3cb-dea5317b1291", BASE + "_3275kfvn8vcwc")),
    product("9PC4V8W0VCWT", "Durable", "Campaign", pkg("a49a529d-7ce4-42b3-b5b7-028b96860773",
                                                        "BethesdaSoftworks.DOOMEternalCampaignPC_3275kfvn8vcwc", BASE + "_3275kfvn8vcwc")),
    product("9P2MSCGJPKJC", "Durable", "DLC1", pkg("6237c41d-dd17-468d-8474-15ad7b198a1e",
                                                   "BethesdaSoftworks.DOOMEternalDLC1PC_3275kfvn8vcwc", BASE + "_3275kfvn8vcwc")),
]}


class ContentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = self.tmp.name + "/rt"
        import importlib
        import xbox_tools
        import xbox_content
        importlib.reload(xbox_tools)
        self.c = importlib.reload(xbox_content)
        self.root = Path(self.tmp.name) / "game"
        self.root.mkdir()
        (self.root / "MicrosoftGame.Config").write_text(CONFIG)

    def test_base_manifest_reads_related_products(self):
        b = self.c.base_manifest(self.root)
        self.assertEqual((b["storeId"], b["name"], b["related"]), ("9P74BRFBXXC6", BASE, ["9PC4V8W0VCWT", "9P2MSCGJPKJC"]))

    def test_only_licensed_content_is_offered(self):
        got = self.c.plan(self.root, {"9PC4V8W0VCWT"}, "FR", "fr-fr", fetch=lambda url: CATALOG)
        self.assertEqual([(o["productId"], o["contentId"]) for o in got],
                         [("9PC4V8W0VCWT", "a49a529d-7ce4-42b3-b5b7-028b96860773")])

    def test_content_for_another_game_is_refused(self):
        other = {"Products": [CATALOG["Products"][0], product("9PC4V8W0VCWT", "Durable", "X",
                 pkg("a49a529d-7ce4-42b3-b5b7-028b96860773", "Other.Pkg_1", "Other.Game_1"))]}
        self.assertEqual(self.c.plan(self.root, {"9PC4V8W0VCWT"}, "FR", "fr-fr", fetch=lambda url: other), [])

    def test_roots_env_lists_installed_content_only(self):
        offer = {"productId": "9PC4V8W0VCWT", "contentId": "a49a529d-7ce4-42b3-b5b7-028b96860773"}
        d = self.c.content_dir("9GAME", "9PC4V8W0VCWT")
        d.mkdir(parents=True)
        self.assertEqual(self.c.roots_env("9GAME"), "")
        self.c.mark_installed("9GAME", offer)
        self.assertEqual(self.c.roots_env("9GAME"), "Z:" + str(d).replace("/", "\\"))

    def test_store_down_means_no_content(self):
        def boom(url):
            raise OSError("offline")
        self.assertEqual(self.c.plan(self.root, {"9PC4V8W0VCWT"}, "FR", "fr-fr", fetch=boom), [])


if __name__ == "__main__":
    unittest.main()
