import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "defaults" / "scripts"))
FAKE = ROOT / "tests" / "fixtures" / "xbox" / "fake_login_cli.py"

import xbox_login as L


class FakeCdp:
    """Records commands; simulates the Microsoft page reacting to navigation."""
    instances = []

    def __init__(self):
        self.calls, self.handlers, self.closed = [], [], False
        self.location = "about:blank"
        FakeCdp.instances.append(self)

    async def connect(self):
        pass

    def on(self, h):
        self.handlers.append(h)

    def fire(self, method, params):
        for h in self.handlers:
            h({"method": method, "params": params, "sessionId": "S1"})

    async def cmd(self, method, params=None, session=None):
        self.calls.append((method, params or {}, session))
        if method == "Target.createTarget":
            return {"targetId": "T1"}
        if method == "Target.attachToTarget":
            return {"sessionId": "S1"}
        if method == "Page.navigate":
            loop = asyncio.get_running_loop()
            loop.call_soon(self.fire, "Fetch.requestPaused", {"requestId": "r1", "resourceType": "Document",
                                                              "request": {"url": params["url"], "headers": {}}})
            loop.call_soon(self.fire, "Runtime.bindingCalled", {"name": "__skXboxNotify", "payload": "PAGE-1"})
        if method == "Runtime.evaluate" and "dispatchMessage" in params.get("expression", ""):
            self.location = L.POST_SRF
            asyncio.get_running_loop().call_soon(self.fire, "Page.loadEventFired", {})
        if method == "Runtime.evaluate" and params.get("expression") == "location.origin + location.pathname":
            return {"result": {"value": self.location}}
        if method == "Runtime.evaluate" and "ServerData" in params.get("expression", ""):
            return {"result": {"value": '{"SERVERDATA":1}'}}
        return {}

    async def close(self):
        self.closed = True


class LoginTest(unittest.TestCase):
    def setUp(self):
        FakeCdp.instances.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stdin_log = Path(self.tmp.name) / "stdin.log"
        self.logs = []

    def run_login(self, mode, timeout=20):
        async def go():
            b = L.XboxSteamBrowser(cdp_factory=FakeCdp, timeout=timeout, logger=self.logs.append,
                                   command=[sys.executable, str(FAKE), mode, str(self.stdin_log)])
            first = await b.start()
            if mode == "hang":
                await asyncio.sleep(0.5)
                return b, first
            await asyncio.wait_for(b.monitor, 25)
            return b, first
        return asyncio.run(go())

    def sent(self):
        return [json.loads(l) for l in self.stdin_log.read_text().splitlines() if l.strip()]

    def test_handshake_and_open_navigates(self):
        b, first = self.run_login("ok")
        self.assertTrue(first["ok"])
        cdp = FakeCdp.instances[0]
        nav = [p for m, p, s in cdp.calls if m == "Page.navigate"]
        self.assertTrue(nav[0]["url"].startswith("https://login.live.com/"))
        self.assertEqual(self.sent()[0], {"type": "hello", "version": 1})
        ua = [p for m, p, s in cdp.calls if m == "Network.setUserAgentOverride"][0]
        self.assertIn("MSAppHost", ua["userAgent"])

    def test_notify_binding_forwarded_as_ipc(self):
        self.run_login("ok")
        self.assertIn({"type": "ipc", "session": 1, "payload": "PAGE-1"}, self.sent())

    def test_headers_added_to_microsoft_documents(self):
        self.run_login("ok")
        cont = [p for m, p, s in FakeCdp.instances[0].calls if m == "Fetch.continueRequest"][0]
        names = {h["name"] for h in cont["headers"]}
        self.assertTrue({"cxh-protocol", "hostapp", "User-Agent"} <= names)

    def test_post_srf_sends_serverdata_once_and_signs_in(self):
        b, _ = self.run_login("ok")
        sd = [m for m in self.sent() if "SERVERDATA" in m.get("payload", "")]
        self.assertEqual(len(sd), 1)
        self.assertEqual(b.state["status"], "done")
        self.assertIn(("Target.closeTarget", {"targetId": "T1"}, None), FakeCdp.instances[0].calls)

    def test_untrusted_host_aborts(self):
        b, _ = self.run_login("untrusted")
        self.assertEqual(b.state["status"], "error")
        self.assertNotIn("Page.navigate", [m for m, p, s in FakeCdp.instances[0].calls])

    def test_cancel_kills_cli_and_closes_target(self):
        async def go():
            b = L.XboxSteamBrowser(cdp_factory=FakeCdp, logger=self.logs.append,
                                   command=[sys.executable, str(FAKE), "hang", str(self.stdin_log)])
            await b.start()
            await asyncio.sleep(1)
            await b.close()
            return b
        b = asyncio.run(go())
        self.assertIsNotNone(b.proc.returncode)
        self.assertTrue(FakeCdp.instances[0].closed)
        self.assertEqual(b.state["status"], "idle")

    def test_timeout_cleans_up(self):
        async def go():
            b = L.XboxSteamBrowser(cdp_factory=FakeCdp, timeout=1, logger=self.logs.append,
                                   command=[sys.executable, str(FAKE), "hang", str(self.stdin_log)])
            await b.start()
            await asyncio.wait_for(b.monitor, 10)
            return b
        b = asyncio.run(go())
        self.assertEqual(b.state.get("error"), "xbox-login-timeout")
        self.assertIsNotNone(b.proc.returncode)

    def test_logs_never_contain_payload(self):
        self.run_login("ok")
        text = " ".join(self.logs)
        for secret in ("PAGE-1", "SERVERDATA", "login.live.com", "?x=1"):
            self.assertNotIn(secret, text)

    def test_serverdata_sent_on_every_post_srf_load(self):
        async def go():
            b = L.XboxSteamBrowser(cdp_factory=FakeCdp, logger=self.logs.append)
            b.cdp = FakeCdp()
            b.cdp.location = L.POST_SRF
            b.frame = {"session": 1}
            sent = []
            b._send = sent.append
            await b._loaded()
            await b._loaded()
            return sent
        sent = asyncio.run(go())
        self.assertEqual([m["payload"] for m in sent], ["{\"SERVERDATA\":1}"] * 2)

    def test_trusted(self):
        self.assertTrue(L.trusted("https://login.live.com/a"))
        for bad in ("http://login.live.com/", "https://login.live.com.evil.test/", "https://u:p@login.live.com/",
                    "https://login.live.com:444/"):
            self.assertFalse(L.trusted(bad))


if __name__ == "__main__":
    unittest.main()
