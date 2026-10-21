"""Xbox tab: Microsoft sign-in inside Steam's own browser, in Game Mode.

xodus-cli runs its external sign-in protocol on private stdio
(`--external-webview-stdio login`, frames prefixed "NEXUS_AUTH_V1 "). This
module plays the part of Xodus Nexus' sign-in window with a Steam browser page
driven over the local CDP endpoint (127.0.0.1:8080):

  ready   → reply {"type":"hello","version":1}
  open    → load the Microsoft URL with its cxh-* headers and the MSAppHost UA
  context → answer CloudExperienceHost.getContext inside the page
  close   → the session step ended
  page external.notify(payload) and login.live.com/ppsecure/post.srf
  ServerData → {"type":"ipc","session":N,"payload":…} on stdin

The user types everything; nothing from the page (payloads, cookies, tokens,
URLs with queries, e-mail) is ever logged."""

import asyncio
import json
import os
import signal
from urllib.parse import urlsplit

import xbox_tools

PREFIX = "NEXUS_AUTH_V1 "
HOSTS = ("login.live.com", "account.live.com", "login.microsoftonline.com",
         "login.microsoft.com", "account.microsoft.com", "sisu.xboxlive.com")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; MSAppHost/3.0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.26100")
POST_SRF = "https://login.live.com/ppsecure/post.srf"
INJECT = """(() => { try {
  Object.defineProperty(globalThis.external, 'notify', {configurable: true,
    value: p => { if (typeof p === 'string' && p.length <= 65536) globalThis.__skXboxNotify(p); }});
} catch (e) {} })();"""
TIMEOUT = 600


def trusted(url):
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.hostname in HOSTS and not u.username
                and not u.password and u.port is None)
    except ValueError:
        return False


def context_message(context):
    return json.dumps({"type": "callback", "value": {"name": "CloudExperienceHost.getContext", "args": [
        "CloudExperienceHost", "TokenBroker", "TokenBroker",
        '{"PrivatePropertyBag":1,"PasswordlessConnect":1,"PreferAssociate":1,"ChromelessUI":0}'],
        "context": context}})


def user_env():
    uid = os.getuid()
    env = {k: v for k, v in os.environ.items() if not k.startswith("LD_LIBRARY_PATH")}
    orig = os.environ.get("LD_LIBRARY_PATH_ORIG")
    if orig:
        env["LD_LIBRARY_PATH"] = orig
    env.update(XDG_RUNTIME_DIR=f"/run/user/{uid}", DBUS_SESSION_BUS_ADDRESS=f"unix:path=/run/user/{uid}/bus",
               XODUS_LOG="off", RUST_LOG="off")
    return env


class Cdp:
    """Minimal CDP client on Steam's local endpoint (aiohttp)."""

    def __init__(self):
        self.next, self.pending, self.handlers = 0, {}, []

    async def connect(self):
        import aiohttp
        self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        async with self.http.get("http://127.0.0.1:8080/json/version", allow_redirects=False) as r:
            version = await r.json(content_type=None)
        ws = urlsplit(version["webSocketDebuggerUrl"])
        if ws.scheme != "ws" or ws.hostname not in ("127.0.0.1", "localhost") or ws.port != 8080:
            raise ValueError("Invalid local CDP endpoint")
        self.ws = await self.http.ws_connect(version["webSocketDebuggerUrl"], max_msg_size=4 << 20)
        self.reader = asyncio.ensure_future(self._read())

    async def _read(self):
        async for m in self.ws:
            d = json.loads(m.data)
            if "id" in d:
                f = self.pending.pop(d["id"], None)
                if f and not f.done():
                    if "error" in d:
                        f.set_exception(RuntimeError("CDP command failed"))
                    else:
                        f.set_result(d.get("result") or {})
            else:
                for h in self.handlers:
                    h(d)

    async def cmd(self, method, params=None, session=None):
        self.next += 1
        fut = asyncio.get_running_loop().create_future()
        self.pending[self.next] = fut
        msg = {"id": self.next, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        await self.ws.send_str(json.dumps(msg))
        return await asyncio.wait_for(fut, 20)

    def on(self, handler):
        self.handlers.append(handler)

    async def close(self):
        try:
            self.reader.cancel()
            await self.ws.close()
            await self.http.close()
        except Exception:
            pass


class XboxSteamBrowser:
    def __init__(self, cdp_factory=Cdp, command=None, timeout=TIMEOUT, logger=None):
        self.cdp_factory = cdp_factory
        self.command = command
        self.timeout = timeout
        self.log = logger or (lambda msg: None)
        self.state = {"status": "idle", "platform": "Xbox"}
        self.proc = self.cdp = self.session = self.target = self.frame = None
        self.latest = 0
        self.serverdata_sent = False
        self.closed = False
        self.tasks = set()

    # ── backend side ──
    def _send(self, obj):
        if self.proc and self.proc.stdin and not self.proc.stdin.is_closing():
            self.proc.stdin.write((json.dumps(obj) + "\n").encode())

    async def start(self):
        try:
            cli = self.command or [str(xbox_tools.cli_path() or ""), "--external-webview-stdio", "login"]
            if not cli[0]:
                return self._fail("engine-missing")
            self.cdp = self.cdp_factory()
            await self.cdp.connect()
            self.cdp.on(self._event)
            self.proc = await asyncio.create_subprocess_exec(
                *cli, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, env=user_env(), start_new_session=True)
            self.state = {"status": "waiting", "platform": "Xbox"}
            self.monitor = asyncio.ensure_future(self._run())
            return {"ok": True, "platform": "Xbox", "inline": True}
        except Exception:
            await self.close()
            return self._fail("xbox-browser-start")

    def _fail(self, code):
        self.state = {"status": "error", "platform": "Xbox", "error": code}
        self.log(f"[xbox-login] {code}")
        return {"ok": False, "error": code}

    async def _run(self):
        try:
            await asyncio.wait_for(self._frames(), self.timeout)
            code = await self.proc.wait()
            if self.closed:
                return  # cancelled: close() leaves the state idle
            if self.state["status"] == "waiting":
                if code == 0:
                    self.state = {"status": "done", "platform": "Xbox"}
                    self.log("[xbox-login] signed in")
                else:
                    self._fail("xbox-login-failed")
        except asyncio.TimeoutError:
            self._fail("xbox-login-timeout")
        except Exception:
            if not self.closed:
                self._fail("xbox-login-protocol")
        except asyncio.CancelledError:
            raise
        finally:
            await self.close()

    async def _frames(self):
        ready = False
        while line := await self.proc.stdout.readline():
            line = line.decode(errors="ignore").rstrip("\r\n")
            if not line.startswith(PREFIX):
                continue
            frame = json.loads(line[len(PREFIX):])
            kind = frame.get("type")
            if kind == "ready":
                ready = True
                self._send({"type": "hello", "version": 1})
                await self.proc.stdin.drain()
                continue
            if not ready:
                raise ValueError("no handshake")
            session = frame.get("session")
            if kind == "open":
                if not isinstance(session, int) or session <= self.latest or session > 32 or not trusted(frame.get("url", "")):
                    self._fail("xbox-login-untrusted")
                    raise ValueError("bad open")
                self.latest = session
                self.frame = frame
                await self._open(frame)
            elif kind == "context" and self.frame and session == self.frame["session"]:
                await self.cdp.cmd("Runtime.evaluate", {"expression":
                    'globalThis["CloudExperienceHost.Bridge.dispatchMessage"](%s)'
                    % json.dumps(context_message(frame.get("context", "")))}, self.session)
            elif kind == "close" and self.frame and session == self.frame["session"]:
                self.frame = None

    # ── browser side ──
    async def _open(self, frame):
        if not self.session:
            t = await self.cdp.cmd("Target.createTarget", {"url": "about:blank"})
            self.target = t["targetId"]
            a = await self.cdp.cmd("Target.attachToTarget", {"targetId": self.target, "flatten": True})
            s = self.session = a["sessionId"]
            for method, params in (("Page.enable", {}), ("Runtime.enable", {}),
                                   ("Runtime.addBinding", {"name": "__skXboxNotify"}),
                                   ("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT}),
                                   ("Network.enable", {}),
                                   ("Network.setUserAgentOverride", {"userAgent": UA}),
                                   ("Fetch.enable", {"patterns": [{"urlPattern": f"https://{h}/*",
                                                                   "requestStage": "Request"} for h in HOSTS]})):
                await self.cdp.cmd(method, params, s)
        await self.cdp.cmd("Page.navigate", {"url": frame["url"]}, self.session)

    def _spawn(self, coro):
        task = asyncio.ensure_future(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def _event(self, data):
        if data.get("sessionId") != self.session or self.closed:
            return
        method, params = data.get("method"), data.get("params") or {}
        if method == "Runtime.bindingCalled" and params.get("name") == "__skXboxNotify" and self.frame:
            payload = params.get("payload")
            if isinstance(payload, str) and len(payload) <= 65536:
                self._send({"type": "ipc", "session": self.frame["session"], "payload": payload})
        elif method == "Fetch.requestPaused":
            self._spawn(self._paused(params))
        elif method == "Page.loadEventFired":
            self._spawn(self._loaded())

    async def _paused(self, params):
        try:
            req = params.get("request") or {}
            headers = dict(req.get("headers") or {})
            if self.frame and params.get("resourceType") == "Document" and trusted(req.get("url", "")):
                headers.update(self.frame.get("headers") or {})
                headers["User-Agent"] = UA
            await self.cdp.cmd("Fetch.continueRequest", {"requestId": params["requestId"],
                               "headers": [{"name": k, "value": v} for k, v in headers.items()]}, self.session)
        except Exception:
            pass  # A request that already went away needs nothing.

    async def _loaded(self):
        try:
            r = await self.cdp.cmd("Runtime.evaluate", {"expression": "location.origin + location.pathname",
                                                         "returnByValue": True}, self.session)
            # post.srf loads more than once (password step, then final
            # step): every load carries its own ServerData for the engine.
            if (r.get("result") or {}).get("value") != POST_SRF or not self.frame:
                return
            r = await self.cdp.cmd("Runtime.evaluate", {"expression": "JSON.stringify(globalThis.ServerData ?? null)",
                                                         "returnByValue": True}, self.session)
            payload = (r.get("result") or {}).get("value")
            if isinstance(payload, str) and payload != "null" and len(payload) <= 65536:
                self.serverdata_sent = True
                self._send({"type": "ipc", "session": self.frame["session"], "payload": payload})
        except Exception:
            pass

    async def close(self):
        if self.closed:
            return
        self.closed = True
        if self.proc and self.proc.returncode is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(self.proc.wait(), 1.5)
                except asyncio.TimeoutError:
                    os.killpg(self.proc.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        if self.cdp:
            if self.target:
                try:
                    await self.cdp.cmd("Target.closeTarget", {"targetId": self.target})
                except Exception:
                    pass
            await self.cdp.close()
        if self.state.get("status") == "waiting":
            self.state = {"status": "idle", "platform": "Xbox"}
