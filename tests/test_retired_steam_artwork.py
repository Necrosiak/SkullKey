"""Retired Steam titles can still have usable official library artwork."""
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "defaults" / "scripts" / "shared"))
from GamesDb import GamesDb


class RetiredSteamArtworkTests(unittest.TestCase):
    def test_fall_guys_uses_verified_retired_appid_without_storesearch(self):
        game_db = object.__new__(GamesDb)
        with patch("GamesDb.urllib.request.urlopen") as urlopen:
            self.assertEqual(game_db.get_steam_appid("Fall Guys"), 1097150)
            urlopen.assert_not_called()

    def test_other_titles_still_use_exact_store_search(self):
        game_db = object.__new__(GamesDb)
        with patch("GamesDb.urllib.request.urlopen",
                   side_effect=lambda *args, **kwargs: io.BytesIO(
                       b'{"items": [{"name": "Example", "id": 123}]}')):
            self.assertEqual(game_db.get_steam_appid("Example"), 123)
            self.assertIsNone(game_db.get_steam_appid("Not Example"))

    def test_fall_guys_gets_a_logo_slot_without_epic_logo_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = str(Path(temporary) / "epic.db")
            connection = sqlite3.connect(database)
            connection.executescript("""
                CREATE TABLE Game (ID INTEGER PRIMARY KEY, ShortName TEXT, Title TEXT);
                CREATE TABLE Images (GameID INTEGER, ImagePath TEXT,
                                     Type TEXT, SortOrder INTEGER);
                INSERT INTO Game VALUES (1, 'fall-guys-id', 'Fall Guys');
                INSERT INTO Images VALUES (1, 'https://example.com/cover.jpg',
                                           'vertical_cover', 0);
            """)
            connection.close()
            game_db = object.__new__(GamesDb)
            game_db.db_file = database
            with patch.object(game_db, "download", side_effect=lambda url: url):
                content = json.loads(game_db.get_base64_images("fall-guys-id"))["Content"]
            self.assertEqual(content["Logo"],
                             "https://cdn.cloudflare.steamstatic.com/steam/apps/1097150/logo.png")


if __name__ == "__main__":
    unittest.main()
