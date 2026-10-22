import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))

EPIC = {"data": {"Catalog": {"searchStore": {"elements": [
    {"title": "Free Now", "id": "a1", "offerMappings": [{"pageSlug": "free-now-12"}], "keyImages": [],
     "promotions": {"promotionalOffers": [{"promotionalOffers": [
         {"startDate": "2026-10-22T15:00:00.000Z", "endDate": "2026-10-29T15:00:00.000Z",
          "discountSetting": {"discountPercentage": 0}}]}], "upcomingPromotionalOffers": []}},
    {"title": "Half Price", "id": "a2", "keyImages": [],
     "promotions": {"promotionalOffers": [{"promotionalOffers": [
         {"startDate": "2026-10-22T15:00:00.000Z", "endDate": "2026-10-29T15:00:00.000Z",
          "discountSetting": {"discountPercentage": 50}}]}]}},
    {"title": "Next Week", "id": "a3", "keyImages": [], "productSlug": "next-week",
     "promotions": {"promotionalOffers": [], "upcomingPromotionalOffers": [{"promotionalOffers": [
         {"startDate": "2026-10-29T15:00:00.000Z", "endDate": "2026-11-05T15:00:00.000Z",
          "discountSetting": {"discountPercentage": 0}}]}]}},
]}}}}
GP = [{"id": 7, "title": "Blood (GOG) Giveaway", "platforms": "PC, GOG, DRM-Free", "status": "Active",
       "end_date": "N/A", "published_date": "2026-10-20 10:00:00", "open_giveaway_url": "https://gp/open/blood"},
      {"id": 8, "title": "Some Itch Game", "platforms": "PC, Itch.io", "status": "Active",
       "end_date": "2026-11-01 23:59:59", "published_date": "2026-10-20", "open_giveaway_url": "https://gp/open/x"}]


class FreeGamesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = self.tmp.name
        import importlib
        import free_games
        self.f = importlib.reload(free_games)

    def fetch(self, url):
        return EPIC if "epicgames" in url else GP

    def test_epic_only_free_offers_now_and_upcoming(self):
        offers = self.f.epic_offers(fetch=self.fetch)
        self.assertEqual([(o["title"], o["now"]) for o in offers], [("Free Now", True), ("Next Week", False)])
        self.assertEqual(offers[0]["url"], "https://store.epicgames.com/p/free-now-12")
        self.assertEqual(offers[0]["end"], "2026-10-29")

    def test_gamerpower_maps_store_and_cleans_title(self):
        offers = self.f.gamerpower_offers({"gog"}, fetch=self.fetch)
        self.assertEqual([(o["store"], o["title"], o["end"]) for o in offers], [("gog", "Blood", "")])

    def test_events_once_then_silent(self):
        with mock.patch.object(self.f, "http_json", side_effect=self.fetch):
            first = self.f.new_events()
            again = self.f.new_events()
        self.assertEqual({o["title"] for o in first}, {"Free Now", "Blood"})
        self.assertEqual(again, [])

    def test_disabled_store_not_announced(self):
        self.f.set_enabled("gog", False)
        with mock.patch.object(self.f, "http_json", side_effect=self.fetch):
            titles = {o["title"] for o in self.f.new_events()}
        self.assertNotIn("Blood", titles)

    def test_network_down_keeps_previous_offers(self):
        with mock.patch.object(self.f, "http_json", side_effect=self.fetch):
            self.f.refresh(force=True)
        with mock.patch.object(self.f, "http_json", side_effect=OSError("offline")):
            st = self.f.refresh(force=True)
        self.assertTrue(st["offers"])


if __name__ == "__main__":
    unittest.main()
