"""Xbox tab: which games the grid shows, and whether they can be played.

Pure rules, no I/O. A game is shown when the account owns it, when it comes
with an active Game Pass subscription, or when the Store gives it away for
free. Game Pass games stay listed (but locked) once installed, so they can
still be uninstalled after the subscription ends."""

GAME_PASS_PLANS = frozenset({"CFQ7TTC0KHS0", "CFQ7TTC0KGQ8", "CFQ7TTC0P85B",
                             "CFQ7TTC0K5DJ", "CFQ7TTC0K6L8"})


def subscription_active(profile):
    """Only "active" counts; "none" and "unknown" are treated as inactive."""
    return ((profile or {}).get("subscription") or {}).get("status") == "active"


def _valid(entitlement):
    return bool(entitlement) and entitlement.get("status") == "Active" and not entitlement.get("isTrial")


def _result(access, playable=True, reason=""):
    return {"access": access, "playable": playable, "reason": reason}


def classify(entitlement, store, installed, sub_active):
    if _valid(entitlement):
        if entitlement.get("satisfiedByProductId") in GAME_PASS_PLANS:
            if sub_active:
                return _result("gamepass")
            if installed:
                return _result("gamepass", False, "subscription-required")
            return _result("hidden", False, "subscription-required")
        return _result("owned")
    if store:
        if not store.get("installable"):
            return _result("hidden", False, "not-installable")
        if store.get("price") == "free":
            return _result("free")
    return _result("hidden", False, "not-owned")
