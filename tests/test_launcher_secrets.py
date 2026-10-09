"""Keep login-bearing launch arguments out of per-game logs."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LauncherSecretTests(unittest.TestCase):
    def test_store_launchers_do_not_log_raw_arguments(self):
        for store, filename in (("Epic", "epic-launcher.sh"),
                                ("GOG", "gog-launcher.sh"),
                                ("Amazon", "amazon-launcher.sh")):
            with self.subTest(store=store):
                content = (ROOT / "defaults" / "scripts" / "Extensions" /
                           store / filename).read_text()
                self.assertNotIn('echo "ARGS: ${ARGS}"', content)
                self.assertNotIn('echo -e "Running: ${QUOTED_ARGS}"', content)


if __name__ == "__main__":
    unittest.main()
