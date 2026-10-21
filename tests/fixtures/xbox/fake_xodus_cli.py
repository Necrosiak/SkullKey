#!/usr/bin/env python3
"""Stand-in for xodus-cli in tests. Behaviour is driven by FAKE_XODUS_MODE."""
import json
import os
import signal
import sys
import time

args = sys.argv[1:]
mode = os.environ.get("FAKE_XODUS_MODE", "")
cmd = args[0] if args else ""

if cmd == "profile":
    print(json.dumps({"schema": 1, "account": "x", "gamertag": "Tester", "gamerpicDataUrl": "data:image/png;base64,AAAA",
                      "subscription": {"status": "unknown", "productIds": [], "checkedAt": "2026-10-21T00:00:00Z"}}))
elif cmd == "account":
    print(json.dumps({"stored": mode != "signed-out", "username": "someone@example.test"}))
elif cmd == "library":
    print(json.dumps({"schema": 1, "entitlements": [
        {"productId": "9AAA", "status": "Active", "isTrial": False, "satisfiedByProductId": None}]}))
elif cmd == "resolve-package":
    if args[1] == "9BAD":
        sys.stderr.write("token=SECRET123 user@example.test\nhttps://private.test/?a=b\nPackage not found\n")
        sys.exit(3)
    print(json.dumps({"productId": args[1], "packages": [{"contentId": "c-" + args[1]}]}))
elif cmd == "streaming":
    dest = args[2]
    os.makedirs(dest, exist_ok=True)
    if mode == "ignore-sigint":
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    seq = 0
    for done in (0, 50, 100):
        seq += 1
        phase = "complete" if done == 100 else "downloading"
        print("NEXUS_PROGRESS " + json.dumps({"schema": 1, "event": "progress", "sequence": seq, "phase": phase,
                                               "completedBytes": done, "totalBytes": 100, "bytesPerSecond": 10,
                                               "paused": False, "canPause": True}), flush=True)
        time.sleep(float(os.environ.get("FAKE_XODUS_DELAY", "0")))
else:
    sys.exit(2)
