import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))


class CatalogUniqueTest(unittest.TestCase):
    """The same project must never be listed twice in Classics Reborn."""

    def test_unique_shortnames_and_repos(self):
        import ports
        names = Counter(p["shortname"] for p in ports.PORTS)
        self.assertEqual([n for n, c in names.items() if c > 1], [])
        repos = Counter((p["repo"].lower(), p["asset"]) for p in ports.PORTS)
        self.assertEqual([r for r, c in repos.items() if c > 1], [])

    def test_every_port_has_a_description(self):
        import ports
        import ports_i18n
        missing = [p["shortname"] for p in ports.PORTS if p["shortname"] not in ports_i18n.DESCS]
        self.assertEqual(missing, [])
