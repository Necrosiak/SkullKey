#!/usr/bin/env python3
"""Replays the xodus-cli external sign-in protocol (frame shapes from the
21/10/2026 spike). argv[1]: ok | untrusted | hang. Received stdin lines are
appended to argv[2]."""
import json
import sys
import time

mode, log = sys.argv[1], sys.argv[2]


def frame(obj):
    print("NEXUS_AUTH_V1 " + json.dumps(obj), flush=True)


def read():
    line = sys.stdin.readline()
    with open(log, "a") as f:
        f.write(line)
    return json.loads(line) if line.strip() else None


frame({"type": "ready", "version": 1})
assert read()["type"] == "hello"
url = "https://evil.example/login" if mode == "untrusted" else "https://login.live.com/ppsecure/InlineLogin.srf?x=1"
frame({"type": "open", "session": 1, "url": url, "headers": {"cxh-protocol": "p", "hostapp": "h"}})
if mode == "hang":
    time.sleep(60)
msg = read()
assert msg["type"] == "ipc" and msg["session"] == 1
frame({"type": "context", "session": 1, "context": "ctx"})
while True:
    msg = read()
    if msg and "SERVERDATA" in msg.get("payload", ""):
        break
frame({"type": "close", "session": 1})
sys.exit(0)
