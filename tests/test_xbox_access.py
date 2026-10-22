import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))

import xbox_access as A

OWNED = {"productId": "9AAA", "status": "Active", "isTrial": False, "satisfiedByProductId": None}
GP = {"productId": "9BBB", "status": "Active", "isTrial": False, "satisfiedByProductId": "CFQ7TTC0KGQ8"}
FREE = {"price": "free", "installable": True}


class AccessTest(unittest.TestCase):
    def test_owned_entitlement_visible_without_sub(self):
        r = A.classify(OWNED, None, False, False)
        self.assertEqual((r["access"], r["playable"], r["reason"]), ("owned", True, ""))

    def test_gamepass_hidden_when_sub_unknown(self):
        self.assertEqual(A.classify(GP, None, False, False)["access"], "hidden")

    def test_gamepass_installed_stays_listed_but_locked(self):
        r = A.classify(GP, None, True, False)
        self.assertEqual((r["access"], r["playable"], r["reason"]),
                         ("gamepass", False, "subscription-required"))

    def test_gamepass_visible_when_active(self):
        r = A.classify(GP, None, False, True)
        self.assertEqual((r["access"], r["playable"]), ("gamepass", True))

    def test_free_store_game_visible(self):
        r = A.classify(None, FREE, False, False)
        self.assertEqual((r["access"], r["playable"]), ("free", True))

    def test_not_installable_hidden(self):
        r = A.classify(None, {"price": "free", "installable": False}, False, False)
        self.assertEqual((r["access"], r["reason"]), ("hidden", "not-installable"))

    def test_paid_store_game_not_owned_hidden(self):
        r = A.classify(None, {"price": "paid", "installable": True}, False, False)
        self.assertEqual((r["access"], r["reason"]), ("hidden", "not-owned"))

    def test_inactive_or_trial_entitlement_ignored(self):
        for bad in ({**OWNED, "status": "Expired"}, {**OWNED, "isTrial": True}):
            self.assertEqual(A.classify(bad, None, False, True)["access"], "hidden")

    def test_owned_but_unsupported_format_hidden(self):
        r = A.classify(OWNED, {"price": "paid", "installable": False}, False, False)
        self.assertEqual((r["access"], r["reason"]), ("hidden", "not-installable"))

    def test_owned_installed_stays_even_if_store_says_unsupported(self):
        r = A.classify(OWNED, {"price": "paid", "installable": False}, True, False)
        self.assertEqual(r["access"], "owned")

    def test_owned_wins_over_free(self):
        self.assertEqual(A.classify(OWNED, FREE, False, False)["access"], "owned")

    def test_subscription_active_only_for_active(self):
        self.assertTrue(A.subscription_active({"subscription": {"status": "active"}}))
        for s in ({"subscription": {"status": "none"}}, {"subscription": {"status": "unknown"}}, {}):
            self.assertFalse(A.subscription_active(s))


if __name__ == "__main__":
    unittest.main()
