import asyncio
import os
import json
import sys
import time

from aiohttp import web
import shlex
import decky_plugin
import zipfile
import shutil
import aiohttp
import os
import concurrent.futures

# Decky registers its OWN `updater` module in sys.modules → a plain
# `import updater` returns Decky's (without is_autoupdate_enabled) instead of
# ours, silently breaking auto-update after a Decky update. Load our file
# explicitly by path, under a unique name, to avoid the collision.
import importlib.util as _ilu
_uspec = _ilu.spec_from_file_location(
    "skullkey_updater", os.path.join(os.path.dirname(os.path.abspath(__file__)), "updater.py")
)
updater = _ilu.module_from_spec(_uspec)
_uspec.loader.exec_module(updater)


# Background tasks started by _main, kept here for two reasons: asyncio only
# holds a weak reference to a running task, so one with no reference left can be
# collected mid-flight, and _unload needs to know which tasks are *ours* rather
# than cancelling everything the loop happens to be running.
_bg_tasks: set = set()


def _spawn(coro):
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return task


# How many release checks, and how long between two. The check runs a few
# seconds after the backend, which is often BEFORE the network is reachable:
# the logs on the test machine show three boots out of four dying on
# "Temporary failure in name resolution". Nothing retried, so the plugin stayed
# on its version until the next boot — which failed the same way.
UPDATE_CHECK_TRIES = 10
UPDATE_CHECK_DELAY_S = 30


async def _recheck(updater):
    """`updater.check()`, retried for as long as it is the network that is missing."""
    from asyncio import sleep as _sleep
    info = await updater.check()
    for _ in range(UPDATE_CHECK_TRIES - 1):
        if not info.get("error"):
            break
        await _sleep(UPDATE_CHECK_DELAY_S)
        info = await updater.check()
    return info


async def _auto_update_check():
    """Silent release-based auto-update, a little after startup so the plugin
    is fully usable first. Module-level (no `self`) because decky's dispatch
    doesn't bind an instance to a task spawned from inside _main."""
    try:
        await asyncio.sleep(20)
        if not updater.is_autoupdate_enabled():
            return
        info = await _recheck(updater)
        if not info.get("update_available"):
            return
        decky_plugin.logger.info(
            f"[updater] {info['latest']} available (have {info['current']}); applying"
        )
        # apply() returns a dict: {"ok": False, "error": …} is always truthy,
        # so a failure used to pass for a success and the loader was restarted
        # anyway — on a loop, since the installed version had not changed.
        # Read the field, not the truthiness of the dict.
        # We apply it OURSELVES. The plugin directory is root-owned, but every
        # file inside it belongs to us (except plugin.json) — measured on
        # 2026-09-13: overwriting an existing file works, creating an entry does
        # not. The updater now sorts that out BEFORE writing anything.
        #
        # ⛔ Do NOT delegate to `utilities/install_plugin`: that is the Decky
        # Store route, and it reports the install to plugins.deckbrew.xyz. Our
        # plugins are not there → 404 → the rest never runs: files written,
        # plugin never reloaded, and a frozen modal across the Steam UI.
        # Measured here on 2026-09-13.
        global _PENDING_UPDATE
        res = await updater.apply(info["url"])
        if res.get("ok"):
            if updater.restart_loader():
                return
            # Refused: plugin_loader is a system unit and this plugin is not
            # root, so polkit asks for an authentication nobody can give here
            # (measured 2026-09-22). The files are in place; the code is not.
            log(f"[updater] {info['latest']} written to disk; loader restart "
                "refused (plugin is not root) — active at next Steam start")
            _PENDING_UPDATE = {"version": info["latest"], "reload": True}
            return
        # Failed: say so, instead of leaving someone on a stale version without
        # knowing it. The frontend does the telling — it is the only side that
        # can raise a notification.
        decky_plugin.logger.error(
            f"[updater] update aborted: {res.get('error', 'unknown reason')}"
        )
        _PENDING_UPDATE = {"version": info["latest"], "error": res.get("error", "")}
    except Exception as e:
        decky_plugin.logger.error(f"[updater] auto-check error: {e}")


# Failure notice parked by _auto_update_check, taken by the frontend that notifies.
_PENDING_UPDATE = None


async def _ensure_deps():
    """Boot-time self-heal: install any MISSING GOG/Amazon store deps (small,
    self-contained venvs) so a fresh machine is ready without the user pressing
    "Install dependencies". Detached from Helper.lock so a first-run install
    never blocks the UI; the presence check is a cheap `test -x`, so on every
    later boot this is a quick no-op. Epic's heavier flatpak deps stay manual."""
    try:
        await asyncio.sleep(30)  # let the plugin finish coming up first
        log_path = os.path.join(decky_plugin.DECKY_PLUGIN_LOG_DIR, "ensure_deps.log")
        with open(log_path, "a") as log:
            proc = await asyncio.create_subprocess_shell(
                "./scripts/install_deps.sh ensure",
                stdout=log,
                stderr=log,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=Helper.working_directory,
                env=Helper.get_environment(),
                start_new_session=True,
            )
            await proc.wait()
        if proc.returncode == 0:
            decky_plugin.logger.info("[deps] ensure finished successfully")
        else:
            decky_plugin.logger.error(
                f"[deps] ensure failed with exit code {proc.returncode}; "
                f"see {log_path}"
            )
    except Exception as e:
        decky_plugin.logger.error(f"[deps] ensure error: {e}")


async def _resume_downloads():
    """Boot-time resume: respawn miHoYo install workers that a reboot/crash
    interrupted mid-download. The worker restarts from the already-finished
    segments and the idempotence guard makes this a no-op for completed
    installs, so it is always safe."""
    try:
        await asyncio.sleep(35)  # let the plugin finish coming up first
        log_path = os.path.join(decky_plugin.DECKY_PLUGIN_LOG_DIR,
                                "resume_downloads.log")
        with open(log_path, "a") as log:
            proc = await asyncio.create_subprocess_shell(
                "python3 ./scripts/Extensions/MiHoYo/mihoyo.py resume-pending",
                stdout=log,
                stderr=log,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=Helper.working_directory,
                env=Helper.get_environment(),
                start_new_session=True,
            )
            await proc.wait()
        decky_plugin.logger.info("[resume] pending-downloads check finished")
    except Exception as e:
        decky_plugin.logger.error(f"[resume] error: {e}")


async def _games_autoupdate():
    """Unattended game updates for every store, at most once a day, without
    the user ever opening the plugin UI. The orchestrator
    (scripts/autoupdate_games.py) does per-store detection and dispatches the
    same Update actions the UI uses."""
    stamp_path = os.path.join(decky_plugin.DECKY_PLUGIN_RUNTIME_DIR,
                              "autoupdate_games.json")
    try:
        await asyncio.sleep(180)  # after boot tasks (deps/resume/update)
        while True:
            last = 0
            try:
                with open(stamp_path) as f:
                    last = json.load(f).get("last", 0)
            except Exception:
                pass
            if time.time() - last >= 86400:
                log_path = os.path.join(decky_plugin.DECKY_PLUGIN_LOG_DIR,
                                        "autoupdate_games.log")
                with open(log_path, "a") as log:
                    proc = await asyncio.create_subprocess_shell(
                        "python3 ./scripts/autoupdate_games.py",
                        stdout=log,
                        stderr=log,
                        stdin=asyncio.subprocess.DEVNULL,
                        cwd=Helper.working_directory,
                        env=Helper.get_environment(),
                        start_new_session=True,
                    )
                    await proc.wait()
                with open(stamp_path, "w") as f:
                    json.dump({"last": time.time()}, f)
                decky_plugin.logger.info("[gamesupd] daily run finished")
            await asyncio.sleep(6 * 3600)  # re-check a few times a day
    except Exception as e:
        decky_plugin.logger.error(f"[gamesupd] error: {e}")


class Helper:
    websocket_port = 8765
    action_cache = {}
    working_directory = decky_plugin.DECKY_PLUGIN_RUNTIME_DIR

    ws_loop = None
    app = None
    site = None
    runner = None
    wsServerIsRunning = False

    verbose = False

    lock = asyncio.Lock()

    @staticmethod
    async def pyexec_subprocess(
        cmd: str,
        input: str = "",
        unprivilege: bool = False,
        env=None,
        websocket=None,
        stream_output: bool = False,
        app_id="",
        game_id="",
    ):
        decky_plugin.logger.info(f"creating lock")
        async with Helper.lock:
            try:
                decky_plugin.logger.info(f"inside lock")
                if unprivilege:
                    cmd = f"sudo -u {decky_plugin.DECKY_USER} {cmd}"
                decky_plugin.logger.info(f"running cmd: {cmd}")
                if env is None:
                    env = Helper.get_environment()
                    env["APP_ID"] = app_id
                    env["SteamOverlayGameId"] = game_id
                    env["SteamGameId"] = game_id
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE,
                    shell=True,
                    env=env,
                    cwd=Helper.working_directory,
                    start_new_session=True,
                )
                if stream_output:

                    async def read_stream(stream, stream_type):
                        while True:
                            line = await stream.readline()
                            if line:
                                line = line.decode()
                                if stream_output:
                                    await websocket.send_str(
                                        json.dumps(
                                            {
                                                "status": "open",
                                                "data": line,
                                                "type": stream_type,
                                            }
                                        )
                                    )
                            else:
                                break

                    await asyncio.gather(
                        read_stream(proc.stdout, "stdout"),
                        read_stream(proc.stderr, "stderr"),
                    )
                    await proc.wait()
                    await websocket.send_str(
                        json.dumps({"status": "closed", "data": ""})
                    )
                    return {"returncode": proc.returncode}
                else:
                    try:
                        stdout, stderr = await proc.communicate(input.encode())
                        stdout = stdout.decode()
                        stderr = stderr.decode()
                        if Helper.verbose:
                            decky_plugin.logger.info(
                                f"Returncode: {proc.returncode}\nSTDOUT: {stdout[:300]}\nSTDERR: {stderr[:300]}"
                            )
                        return {
                            "returncode": proc.returncode,
                            "stdout": stdout,
                            "stderr": stderr,
                        }
                    finally:
                        # Ensure process is terminated and cleaned up
                        if proc.returncode is None:
                            try:
                                proc.terminate()
                                await asyncio.wait_for(proc.wait(), timeout=5.0)
                            except asyncio.TimeoutError:
                                proc.kill()
                                await proc.wait()
                            except Exception:
                                pass

            except Exception as e:
                decky_plugin.logger.error(f"Error in pyexec_subprocess: {e}")
                # Clean up process on error
                try:
                    if "proc" in locals() and proc.returncode is None:
                        proc.terminate()
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                except Exception:
                    if "proc" in locals():
                        try:
                            proc.kill()
                            await proc.wait()
                        except Exception:
                            pass
                return None

    @staticmethod
    def get_environment(platform=""):
        env = {
            "DECKY_HOME": decky_plugin.DECKY_HOME,
            "DECKY_PLUGIN_DIR": decky_plugin.DECKY_PLUGIN_DIR,
            "DECKY_PLUGIN_LOG_DIR": decky_plugin.DECKY_PLUGIN_LOG_DIR,
            "DECKY_PLUGIN_NAME": "skullkey",
            "DECKY_PLUGIN_RUNTIME_DIR": decky_plugin.DECKY_PLUGIN_RUNTIME_DIR,
            "DECKY_PLUGIN_SETTINGS_DIR": decky_plugin.DECKY_PLUGIN_SETTINGS_DIR,
            "WORKING_DIR": Helper.working_directory,
            "CONTENT_SERVER": "http://localhost:1337/plugins",
            "DECKY_USER_HOME": decky_plugin.DECKY_USER_HOME,
            "HOME": os.path.abspath(decky_plugin.DECKY_USER_HOME),
            "PLATFORM": platform,
        }
        return env

    @staticmethod
    async def call_script(cmd: str, *args, input_data="", app_id="", game_id=""):
        try:
            decky_plugin.logger.info(f"call_script: {cmd} {args} {input_data}")
            encoded_args = [shlex.quote(arg) for arg in args]
            decky_plugin.logger.info(f"call_script: {cmd} {' '.join(encoded_args)}")
            decky_plugin.logger.info(f"input_data: {input_data}")
            decky_plugin.logger.info(f"args: {args}")
            cmd = f"{cmd} {' '.join(encoded_args)}"

            res = await Helper.pyexec_subprocess(
                cmd, input_data, app_id=app_id, game_id=game_id
            )
            if Helper.verbose:
                decky_plugin.logger.info(f"call_script result: {res['stdout'][:100]}")
            return res["stdout"]
        except Exception as e:
            decky_plugin.logger.error(f"Error in call_script: {e}")
            return None

    @staticmethod
    def get_action(actionSet, actionName):
        result = None
        if set := Helper.action_cache.get(actionSet):
            for action in set:
                if action["Id"] == actionName:
                    result = action
        if not result:
            file_path = os.path.join(Helper.working_directory, f"{actionSet}.json")
            if not os.path.exists(file_path):
                file_path = os.path.join(
                    decky_plugin.DECKY_PLUGIN_RUNTIME_DIR, ".cache", f"{actionSet}.json"
                )

            if os.path.exists(file_path):
                with open(file_path) as f:
                    data = json.load(f)
                    for action in data:
                        if action["Id"] == actionName:
                            result = action
        return result

    @staticmethod
    async def execute_action(
        actionSet, actionName, *args, input_data="", app_id="", game_id=""
    ):
        try:
            result = ""
            json_result = {}
            action = Helper.get_action(actionSet, actionName)
            cmd = action["Command"]
            if cmd:
                decky_plugin.logger.info(f"execute_action cmd: {cmd}")
                decky_plugin.logger.info(f"execute_action args: {args}")
                decky_plugin.logger.info(f"execute_action app_id: {app_id}")
                decky_plugin.logger.info(f"execute_action game_id: {game_id}")

                decky_plugin.logger.info(f"execute_action input_data: {input_data}")
                result = await Helper.call_script(
                    os.path.expanduser(cmd),
                    *args,
                    input_data=input_data,
                    app_id=app_id,
                    game_id=game_id,
                )
                if Helper.verbose:
                    decky_plugin.logger.info(f"execute_action result: {result}")
                try:
                    json_result = json.loads(result)
                    if json_result["Type"] == "ActionSet":
                        decky_plugin.logger.info(
                            f"Init action set {json_result['Content']['SetName']}"
                        )
                        Helper.write_action_set_to_cache(
                            json_result["Content"]["SetName"],
                            json_result["Content"]["Actions"],
                        )
                except Exception as e:
                    decky_plugin.logger.info("Error parsing json result", e)
                    json_result = {
                        "Type": "Error",
                        "Content": {
                            "Message": f"Error parsing json result {e}",
                            "Data": result,
                            "ActionName": actionName,
                            "ActionSet": actionSet,
                        },
                    }
                return json_result
            return {
                "Type": "Error",
                "Content": {
                    "Message": f"Action not found {actionSet}, {actionName}",
                    "Data": result[:300],
                },
                "ActionName": actionName,
                "ActionSet": actionSet,
            }

        except Exception as e:
            decky_plugin.logger.error(f"Error executing action: {e}")
            return {
                "Type": "Error",
                "Content": {
                    "Message": "Action not found",
                    "Data": str(e),
                    "ActionName": actionName,
                    "ActionSet": actionSet,
                },
            }

    @staticmethod
    def write_action_set_to_cache(setName, actionSet, writeToDisk: bool = False):
        # Prevent cache from growing unbounded - limit to 100 entries
        if len(Helper.action_cache) > 100:
            # Remove oldest entries (FIFO)
            oldest_keys = list(Helper.action_cache.keys())[:50]
            for key in oldest_keys:
                del Helper.action_cache[key]

        Helper.action_cache[setName] = actionSet
        if writeToDisk:
            cache_dir = os.path.join(decky_plugin.DECKY_PLUGIN_RUNTIME_DIR, ".cache")
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            file_path = os.path.join(cache_dir, f"{setName}.json")

            # if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                json.dump(actionSet, f)

    @staticmethod
    async def ws_handler(request):
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)

        try:
            async for message in websocket:
                decky_plugin.logger.info(f"ws_handler message: {message.data}")
                data = json.loads(message.data)
                if data["action"] == "install_dependencies":
                    await Helper.pyexec_subprocess(
                        "./scripts/install_deps.sh",
                        websocket=websocket,
                        stream_output=True,
                    )
                if data["action"] == "uninstall_dependencies":
                    await Helper.pyexec_subprocess(
                        "./scripts/install_deps.sh uninstall",
                        websocket=websocket,
                        stream_output=True,
                    )

        except Exception as e:
            decky_plugin.logger.error(f"Error in ws_handler: {e}")
        finally:
            # Ensure websocket is properly closed
            if not websocket.closed:
                await websocket.close()

        return websocket

    async def start_ws_server():
        Helper.ws_loop = asyncio.get_event_loop()
        # Don't use ThreadPoolExecutor for async tasks - just call directly
        await Helper._start_ws_server_thread()

    @staticmethod
    async def _start_ws_server_thread():
        try:
            Helper.wsServerIsRunning = True
            port = 8765
            while Helper.wsServerIsRunning:
                try:
                    decky_plugin.logger.info(
                        f"Starting WebSocket server on port {port}"
                    )

                    # Helper.runner.setup()
                    Helper.app = web.Application()
                    Helper.app.router.add_get("/ws", Helper.ws_handler)
                    Helper.runner = web.AppRunner(Helper.app)
                    await Helper.runner.setup()
                    Helper.site = web.TCPSite(Helper.runner, "localhost", port)

                    Helper.websocket_port = port
                    await Helper.site.start()
                    break
                except OSError:
                    port += 1

            decky_plugin.logger.info("WebSocket server started")

        except Exception as e:
            decky_plugin.logger.error(f"Error in start_ws_server: {e}")

    async def stop_ws_server():
        try:
            decky_plugin.logger.info("Stopping WebSocket server")

            # Signal the server to stop
            Helper.wsServerIsRunning = False

            # Stop the site
            if Helper.site:
                decky_plugin.logger.info("Stopping site")
                await Helper.site.stop()
                decky_plugin.logger.info("Site stopped")

            # Cleanup the runner
            if Helper.runner:
                await Helper.runner.cleanup()
                decky_plugin.logger.info("Runner cleaned up")

            # Clear references
            Helper.site = None
            Helper.runner = None
            Helper.app = None

        except Exception as e:
            decky_plugin.logger.error(f"Error in stop_ws_server: {e}")
        finally:
            # Stop the event loop if it exists
            if Helper.ws_loop and Helper.ws_loop.is_running():
                Helper.ws_loop.stop()
            Helper.ws_loop = None
            Helper.wsServerIsRunning = False
            decky_plugin.logger.info("WebSocket server stopped")

    @staticmethod
    def get_installed_extensions():
        """
        Get list of installed extension directory names by checking for static.json files
        Searches in both plugin dir and runtime dir (data)
        Returns a list of unique extension names (directory names containing static.json)
        """
        extensions = set()

        # Search paths
        search_paths = [
            os.path.join(decky_plugin.DECKY_PLUGIN_DIR, "scripts", "Extensions"),
            os.path.join(
                decky_plugin.DECKY_PLUGIN_RUNTIME_DIR, "scripts", "Extensions"
            ),
        ]

        for base_path in search_paths:
            if not os.path.exists(base_path):
                continue

            try:
                # Walk through the Extensions directory
                for root, dirs, files in os.walk(base_path):
                    # If this directory contains static.json
                    if "static.json" in files:
                        # Get the directory name relative to Extensions
                        rel_path = os.path.relpath(root, base_path)
                        # If it's directly under Extensions (not the Extensions dir itself)
                        if rel_path != ".":
                            # Get just the top-level directory name
                            ext_name = rel_path.split(os.sep)[0]
                            extensions.add(ext_name)

            except Exception as e:
                decky_plugin.logger.error(
                    f"Error scanning extensions in {base_path}: {e}"
                )

        # Convert to sorted list
        result = sorted(list(extensions))
        decky_plugin.logger.info(f"Found installed extensions: {result}")
        return result


# import requests



# ── Connexion dans le navigateur de Steam (SkullKey #4) ─────────────────────
# Les fenêtres de connexion Epic / GOG / Amazon sont des applis GTK + WebKit2
# lancées comme un jeu. SteamOS d'origine n'a NI PyGObject NI WebKit2 (et son
# système est en lecture seule) → connexion impossible sur un Steam Deck.
# Repli : la page de connexion s'ouvre dans le navigateur intégré de Steam
# (Navigation.NavigateToExternalWeb côté interface) et on lit le code par le
# CDP de Steam (127.0.0.1:8080). Ce navigateur N'APPARAÎT PAS dans /json : seul
# Target.getTargets au niveau navigateur le liste (mesuré 04/10, Chrome 126).
BROWSER_LOGIN = {
    # Epic : legendary.gl renvoie vers la connexion Epic, qui finit sur une page
    # JSON contenant authorizationCode (l'URL ne contient pas le code).
    "Epic": {"match": "epicgames.com/id/api/redirect", "param": None},
    "GOG": {"match": "embed.gog.com/on_login_success", "param": "code"},
    "Amazon": {"match": "openid.oa2.authorization_code",
               "param": "openid.oa2.authorization_code"},
}


class BrowserLogin:
    state = {"status": "idle"}          # idle | waiting | finishing | done | error
    task = None

    @staticmethod
    async def _cdp(ws, method, params=None, session=None, _ids=[0]):
        _ids[0] += 1
        my = _ids[0]
        msg = {"id": my, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        await ws.send_str(json.dumps(msg))
        while True:
            m = await asyncio.wait_for(ws.receive(), timeout=10)
            if m.type != aiohttp.WSMsgType.TEXT:
                raise RuntimeError(f"CDP fermé ({m.type})")
            d = json.loads(m.data)
            if d.get("id") == my:
                if "error" in d:
                    raise RuntimeError(d["error"].get("message"))
                return d.get("result") or {}

    @staticmethod
    async def _find_code(session, platform):
        """Une passe : cherche la page de redirection et en extrait le code."""
        from urllib.parse import urlparse, parse_qs
        rule = BROWSER_LOGIN[platform]
        async with session.get("http://127.0.0.1:8080/json/version") as r:
            ver = await r.json(content_type=None)
        async with session.ws_connect(ver["webSocketDebuggerUrl"], max_msg_size=0) as ws:
            targets = (await BrowserLogin._cdp(ws, "Target.getTargets")).get("targetInfos", [])
            for t in targets:
                url = t.get("url") or ""
                if t.get("type") != "page" or rule["match"] not in url:
                    continue
                if rule["param"]:
                    vals = parse_qs(urlparse(url).query).get(rule["param"])
                    if vals and vals[0]:
                        return vals[0]
                    continue
                # Epic : lire la page JSON.
                att = await BrowserLogin._cdp(ws, "Target.attachToTarget",
                                              {"targetId": t["targetId"], "flatten": True})
                sid = att.get("sessionId")
                try:
                    res = await BrowserLogin._cdp(ws, "Runtime.evaluate",
                                                  {"expression": "document.body ? document.body.innerText : ''",
                                                   "returnByValue": True}, session=sid)
                finally:
                    try:
                        await BrowserLogin._cdp(ws, "Target.detachFromTarget", {"sessionId": sid})
                    except Exception:
                        pass
                text = ((res.get("result") or {}).get("value") or "").strip()
                try:
                    code = json.loads(text).get("authorizationCode")
                except Exception:
                    code = None
                if code:
                    return code
        return None

    @staticmethod
    async def _watch(platform, deadline):
        async with aiohttp.ClientSession() as session:
            while time.time() < deadline and BrowserLogin.state.get("status") == "waiting":
                try:
                    code = await BrowserLogin._find_code(session, platform)
                except Exception as e:
                    decky_plugin.logger.warning(f"[browser-login] {e!r}")
                    code = None
                if code:
                    BrowserLogin.state = {"status": "finishing", "platform": platform}
                    out = await Helper.call_script(
                        "./scripts/skullkey.sh",
                        platform, "login-code", code)
                    ok = '"Error"' not in (out or "")
                    decky_plugin.logger.info(f"[browser-login] {platform} : code reçu, "
                                             f"connexion {'OK' if ok else 'en échec'}")
                    BrowserLogin.state = ({"status": "done", "platform": platform} if ok else
                                          {"status": "error", "platform": platform,
                                           "message": (out or "")[-300:]})
                    return
                await asyncio.sleep(1)
        if BrowserLogin.state.get("status") == "waiting":
            BrowserLogin.state = {"status": "error", "platform": platform, "message": "timeout"}



# ── Gestionnaire de Proton (demande user 07/10) ─────────────────────────────
# Proton communautaires installés dans compatibilitytools.d depuis la DERNIÈRE
# release GitHub de chaque projet, archive vérifiée en SHA-512 avant extraction
# (leçons du script GE de bc250-tweaks : lire le vrai nom d'archive dans l'API,
# ne jamais le deviner ; une archive tronquée casse Steam en silence). Le Proton
# de Valve, lui, s'installe par Steam (assistant d'installation, côté interface).
PROTON_SOURCES = {
    "ge": {"name": "GE-Proton", "repo": "GloriousEggroll/proton-ge-custom",
           "asset": r"-x86_64\.tar\.gz$"},
    "cachyos": {"name": "Proton-CachyOS", "repo": "CachyOS/proton-cachyos",
                "asset": r"-slr-x86_64\.tar\.xz$"},
}


class ProtonManager:
    state = {"status": "idle"}     # idle | downloading | verifying | extracting | done | error
    task = None

    @staticmethod
    def compat_dir():
        return os.path.join(decky_plugin.DECKY_USER_HOME, ".local", "share", "Steam",
                            "compatibilitytools.d")

    @staticmethod
    def _ssl():
        import ssl
        # Le Python de Decky n'a pas de magasin de certificats : on pointe celui
        # du système (chemins Fedora/Bazzite, Debian/SteamOS, Arch).
        for ca in ("/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/certs/ca-certificates.crt",
                   "/etc/ssl/cert.pem"):
            if os.path.exists(ca):
                return ssl.create_default_context(cafile=ca)
        return ssl.create_default_context()

    @staticmethod
    def installed():
        d = ProtonManager.compat_dir()
        try:
            return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)))
        except OSError:
            return []

    @staticmethod
    async def latest(key):
        import re
        src = PROTON_SOURCES[key]
        url = f"https://api.github.com/repos/{src['repo']}/releases/latest"
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ProtonManager._ssl())) as s:
            async with s.get(url, headers={"Accept": "application/vnd.github+json",
                                           "User-Agent": "SkullKey"}, timeout=aiohttp.ClientTimeout(total=20)) as r:
                rel = await r.json(content_type=None)
        assets = rel.get("assets") or []
        arc = next((a for a in assets if re.search(src["asset"], a.get("name", ""))), None)
        if not arc:
            return {"key": key, "name": src["name"], "error": "no x86_64 archive in latest release"}
        base = re.sub(r"\.tar\.(gz|xz)$", "", arc["name"])
        sha = next((a for a in assets if a.get("name") == base + ".sha512sum"), None)
        inst = ProtonManager.installed()
        tag = rel.get("tag_name") or base
        # Dossier extrait : GE = « GE-Proton11-7 » (ou suffixé -x86_64),
        # CachyOS = nom de l'archive sans extension.
        is_inst = any(n == tag or n.startswith(tag + "-") or n == base for n in inst)
        return {"key": key, "name": src["name"], "tag": tag, "url": arc["browser_download_url"],
                "size": arc.get("size", 0), "sha_url": sha["browser_download_url"] if sha else "",
                "installed": is_inst}

    @staticmethod
    async def install(key):
        import hashlib, tarfile, tempfile
        st = ProtonManager.state
        tmp = None
        try:
            info = await ProtonManager.latest(key)
            if info.get("error"):
                raise RuntimeError(info["error"])
            if not info.get("sha_url"):
                raise RuntimeError("no SHA-512 checksum published for this release")
            ProtonManager.state = st = {"status": "downloading", "key": key, "tag": info["tag"],
                                        "done": 0, "total": info["size"]}
            ssl_ctx = ProtonManager._ssl()
            tmp = tempfile.NamedTemporaryFile(prefix="skullkey-proton-", delete=False,
                                              dir=decky_plugin.DECKY_PLUGIN_RUNTIME_DIR)
            h = hashlib.sha512()
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as s:
                async with s.get(info["sha_url"], headers={"User-Agent": "SkullKey"}) as r:
                    expected = (await r.text()).split()[0].strip().lower()
                async with s.get(info["url"], headers={"User-Agent": "SkullKey"},
                                 timeout=aiohttp.ClientTimeout(total=None, sock_read=60)) as r:
                    r.raise_for_status()
                    async for chunk in r.content.iter_chunked(1 << 20):
                        tmp.write(chunk)
                        h.update(chunk)
                        st["done"] += len(chunk)
            tmp.close()
            st["status"] = "verifying"
            if h.hexdigest() != expected:
                raise RuntimeError("checksum mismatch — download corrupted, nothing was installed")
            st["status"] = "extracting"
            dest = ProtonManager.compat_dir()
            os.makedirs(dest, exist_ok=True)

            def _extract():
                with tarfile.open(tmp.name) as tf:
                    for m in tf.getmembers():   # pas de chemin qui sort du dossier
                        if m.name.startswith("/") or ".." in m.name.split("/"):
                            raise RuntimeError(f"unsafe path in archive: {m.name}")
                    tf.extractall(dest)
            await asyncio.get_event_loop().run_in_executor(None, _extract)
            ProtonManager.state = {"status": "done", "key": key, "tag": info["tag"]}
            decky_plugin.logger.info(f"[proton] {info['tag']} installé dans {dest}")
        except Exception as e:
            decky_plugin.logger.error(f"[proton] install {key}: {e!r}")
            ProtonManager.state = {"status": "error", "key": key, "message": str(e)}
        finally:
            if tmp is not None:
                try:
                    tmp.close()
                    os.unlink(tmp.name)
                except Exception:
                    pass


class Plugin:
    async def _main(self):
        decky_plugin.logger.info("SkullKey starting up...")
        try:
            Helper.action_cache = {}
            if os.path.exists(
                os.path.join(decky_plugin.DECKY_PLUGIN_RUNTIME_DIR, "init.json")
            ):
                Helper.working_directory = decky_plugin.DECKY_PLUGIN_RUNTIME_DIR
            else:
                Helper.working_directory = decky_plugin.DECKY_PLUGIN_DIR

            decky_plugin.logger.info(
                f"plugin: {decky_plugin.DECKY_PLUGIN_NAME} dir: {decky_plugin.DECKY_PLUGIN_RUNTIME_DIR}"
            )
            # pass cmd argument to _call_script method
            decky_plugin.logger.info("SkullKey initializing")
            result = await Helper.execute_action("init", "init")
            decky_plugin.logger.info("SkullKey initialized")
            try:
                repaired = self._prefixes_mod().repair_existing()
                if repaired:
                    decky_plugin.logger.info(f"[prefixes] checked {repaired} existing custom prefixes")
            except Exception as e:
                decky_plugin.logger.warning(f"[prefixes] repair: {e!r}")
            if Helper.verbose:
                decky_plugin.logger.info(f"init result: {result}")
            await Helper.start_ws_server()
            decky_plugin.logger.info("SkullKey started")
            # Schedule the silent auto-update as a module-level coroutine —
            # decky's method dispatch doesn't bind `self` for a task created
            # from inside _main, so keep it self-free.
            _spawn(_auto_update_check())
            _spawn(_ensure_deps())
            _spawn(_resume_downloads())
            _spawn(_games_autoupdate())

        except Exception as e:
            decky_plugin.logger.error(f"Error in _main: {e}")

    async def check_update(self):
        return await updater.check()

    async def get_version(self):
        return updater.get_current_version()

    async def apply_update(self, url):
        res = await updater.apply(url)
        # Writing the files is not loading them. The frontend takes it from
        # here: it asks the loader to re-import THIS plugin. We no longer
        # restart plugin_loader from the backend — it is not allowed to (see
        # restart_loader) and it would bounce every plugin for nothing.
        return res

    async def take_pending_update(self):
        """Hand the failed-update notice to the frontend, once.

        Cleared on read: the notification must fire ONCE, not on every QAM open.
        """
        global _PENDING_UPDATE
        pending, _PENDING_UPDATE = _PENDING_UPDATE, None
        return pending or {}

    async def get_autoupdate(self):
        return updater.is_autoupdate_enabled()

    async def take_port_update_events(self):
        """Relay completed automatic game updates once, even with QAM closed."""
        directory = os.path.join(decky_plugin.DECKY_PLUGIN_RUNTIME_DIR, "ports_update_events")
        events = []
        if not os.path.isdir(directory):
            return events
        for name in sorted(os.listdir(directory))[:20]:
            if not name.endswith(".json"):
                continue
            path = os.path.join(directory, name)
            try:
                with open(path) as handle:
                    event = json.load(handle)
                if isinstance(event, dict) and event.get("name"):
                    events.append(event)
                os.unlink(path)
            except Exception as error:
                decky_plugin.logger.warning(f"[portsupd] event read failed: {error}")
        return events

    # ── Emplacement des préfixes (SkullKey #5) ─────────────────────────────
    # La logique vit dans scripts/shared/prefixes.py (partagée avec les scripts
    # des magasins) ; ici, seulement lire / écrire le dossier choisi.
    @staticmethod
    def _prefixes_mod():
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = decky_plugin.DECKY_PLUGIN_RUNTIME_DIR
        os.environ["DECKY_USER_HOME"] = decky_plugin.DECKY_USER_HOME
        d = os.path.join(decky_plugin.DECKY_PLUGIN_DIR, "scripts", "shared")
        if d not in sys.path:
            sys.path.insert(0, d)
        import prefixes
        return prefixes

    async def get_prefix_root(self):
        try:
            return self._prefixes_mod().load().get("root") or ""
        except Exception as e:
            decky_plugin.logger.warning(f"[prefixes] get: {e!r}")
            return ""

    async def set_prefix_root(self, path=""):
        try:
            return {"ok": True, "root": self._prefixes_mod().set_root(path or "")}
        except Exception as e:
            decky_plugin.logger.warning(f"[prefixes] set: {e!r}")
            return {"ok": False, "error": str(e)}

    async def set_autoupdate(self, enabled):
        return updater.set_autoupdate_enabled(enabled)

    async def reload(self):
        try:
            Helper.action_cache = {}
            if os.path.exists(
                os.path.join(decky_plugin.DECKY_PLUGIN_RUNTIME_DIR, "init.json")
            ):
                Helper.working_directory = decky_plugin.DECKY_PLUGIN_RUNTIME_DIR
            else:
                Helper.working_directory = decky_plugin.DECKY_PLUGIN_DIR

            decky_plugin.logger.info(
                f"plugin: {decky_plugin.DECKY_PLUGIN_NAME} dir: {decky_plugin.DECKY_PLUGIN_RUNTIME_DIR}"
            )
            # pass cmd argument to _call_script method
            result = await Helper.execute_action("init", "init")
            try:
                self._prefixes_mod().repair_existing()
            except Exception as e:
                decky_plugin.logger.warning(f"[prefixes] repair: {e!r}")
            if Helper.verbose:
                decky_plugin.logger.info(f"init result: {result}")
        except Exception as e:
            decky_plugin.logger.error(f"Error in _main: {e}")

    async def has_action(self, actionSet, actionName):
        """L'action existe-t-elle pour ce magasin ? Appeler une action absente
        ouvre une fenêtre d'erreur côté interface : les boutons optionnels
        (réglages, supprimer le client) demandent d'abord ici (SkullKey #4)."""
        try:
            return Helper.get_action(actionSet, actionName) is not None
        except Exception:
            return False

    async def browser_login_needed(self):
        """True si la fenêtre de connexion GTK/WebKit ne peut pas s'ouvrir
        (SteamOS d'origine) → l'interface passe par le navigateur de Steam.
        ~/.config/skullkey-force-browser-login force ce chemin (tests, ou si la
        fenêtre GTK pose problème)."""
        if os.path.exists(os.path.join(decky_plugin.DECKY_USER_HOME, ".config",
                                       "skullkey-force-browser-login")):
            return True
        try:
            p = await asyncio.create_subprocess_exec(
                "/usr/bin/env", "python3", "-c",
                'import gi; gi.require_version("Gtk","3.0"); gi.require_version("WebKit2","4.1")',
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            return (await p.wait()) != 0
        except Exception:
            return True

    async def browser_login_start(self, actionSet):
        """Démarre la connexion dans le navigateur de Steam pour le magasin de
        `actionSet` ; renvoie l'URL que l'interface ouvre."""
        try:
            action = Helper.get_action(actionSet, "Login") or {}
            parts = (action.get("Command") or "").split()
            platform = next((x for x in parts if x in BROWSER_LOGIN), None)
            if not platform:
                return {"ok": False, "error": f"unsupported store ({actionSet})"}
            out = await Helper.call_script(
                "./scripts/skullkey.sh",
                platform, "login-url")
            url = (json.loads(out or "{}").get("Content") or {}).get("Url")
            if not url:
                return {"ok": False, "error": (out or "no url")[-300:]}
            if BrowserLogin.task and not BrowserLogin.task.done():
                BrowserLogin.task.cancel()
            BrowserLogin.state = {"status": "waiting", "platform": platform}
            BrowserLogin.task = asyncio.get_event_loop().create_task(
                BrowserLogin._watch(platform, time.time() + 600))
            decky_plugin.logger.info(f"[browser-login] {platform} : page ouverte")
            return {"ok": True, "url": url, "platform": platform}
        except Exception as e:
            decky_plugin.logger.error(f"[browser-login] start: {e!r}")
            return {"ok": False, "error": str(e)}

    async def browser_login_status(self):
        return BrowserLogin.state

    async def browser_login_cancel(self):
        if BrowserLogin.state.get("status") == "waiting":
            BrowserLogin.state = {"status": "idle"}
        return {"ok": True}

    async def proton_list(self):
        out = []
        for key in PROTON_SOURCES:
            try:
                out.append(await ProtonManager.latest(key))
            except Exception as e:
                out.append({"key": key, "name": PROTON_SOURCES[key]["name"], "error": str(e)})
        return {"sources": out, "installed": ProtonManager.installed()}

    async def proton_install(self, key):
        if key not in PROTON_SOURCES:
            return {"ok": False, "error": "unknown source"}
        if ProtonManager.task and not ProtonManager.task.done():
            return {"ok": False, "error": "busy"}
        ProtonManager.state = {"status": "downloading", "key": key, "done": 0, "total": 0}
        ProtonManager.task = asyncio.get_event_loop().create_task(ProtonManager.install(key))
        return {"ok": True}

    async def proton_status(self):
        return ProtonManager.state

    async def get_websocket_port(self):
        return Helper.websocket_port

    # ...

    async def execute_action(
        self, actionSet, actionName, inputData="", gameId="", appId="", *args, **kwargs
    ):
        try:
            decky_plugin.logger.info(f"execute_action: {actionSet} {actionName} ")
            decky_plugin.logger.info(f"execute_action args: {args}")
            if Helper.verbose:
                decky_plugin.logger.info(f"execute_action kwargs: {kwargs}")

            if isinstance(inputData, (dict, list)):
                inputData = json.dumps(inputData)

            result = await Helper.execute_action(
                actionSet,
                actionName,
                *args,
                *kwargs.values(),
                input_data=inputData,
                game_id=gameId,
                app_id=appId,
            )
            if Helper.verbose:
                decky_plugin.logger.info(f"execute_action result: {result}")
            return result
        except Exception as e:
            decky_plugin.logger.error(f"Error in execute_action: {e}")
            return None

    async def download_custom_backend(self, url, backup: bool = False):
        try:
            runtime_dir = decky_plugin.DECKY_PLUGIN_RUNTIME_DIR
            decky_plugin.logger.info(f"Downloading file from {url}")

            # Create a temporary file to save the downloaded zip file
            temp_file = "/tmp/custom_backend.zip"
            # disabling ssl verfication for testing, github doesn't seem to have a valid ssl cert, seems wrong
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                decky_plugin.logger.info(f"Downloading {url}")
                async with session.get(url, allow_redirects=True) as response:
                    decky_plugin.logger.debug(f"Response status: {response}")
                    # assert response.status == 200
                    with open(temp_file, "wb") as f:
                        while True:
                            chunk = await response.content.readany()
                            if not chunk:
                                break
                            f.write(chunk)
            decky_plugin.logger.debug(f"Downloaded {temp_file} from {url}")
            # Extract the contents of the zip file to the runtime directory

            if backup:
                # Find the latest backup folder
                decky_plugin.logger.info("Creating backup")
                backup_dir = os.path.join(runtime_dir, "backup")
                backup_count = 1
                while os.path.exists(f"{backup_dir} {backup_count}"):
                    backup_count += 1
                latest_backup_dir = f"{backup_dir} {backup_count}"
                decky_plugin.logger.info(f"Creating backup at {latest_backup_dir}")

                # Create the latest backup folder
                os.makedirs(latest_backup_dir, exist_ok=True)

                # Move non-backup files to the latest backup folder
                for item in os.listdir(runtime_dir):
                    item_path = os.path.join(runtime_dir, item)
                    if (
                        os.path.isfile(item_path) or os.path.isdir(item_path)
                    ) and not item.startswith("backup"):
                        if item.endswith(".db"):
                            shutil.copy(item_path, latest_backup_dir)
                        else:
                            shutil.move(item_path, latest_backup_dir)
                decky_plugin.logger.info("Backup completed successfully")

            with zipfile.ZipFile(temp_file, "r") as zip_ref:
                zip_ref.extractall(runtime_dir)
                scripts_dir = os.path.join(
                    decky_plugin.DECKY_PLUGIN_RUNTIME_DIR, "scripts"
                )
                for root, dirs, files in os.walk(scripts_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        os.chmod(file_path, 0o755)

            decky_plugin.logger.info("Download and extraction completed successfully")

        except Exception as e:
            decky_plugin.logger.error(f"Error in download_custom_backend: {e}")
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    decky_plugin.logger.info(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    decky_plugin.logger.warning(f"Failed to remove temp file: {e}")

    async def get_logs(self):
        log_dir = decky_plugin.DECKY_PLUGIN_LOG_DIR
        log_files = []
        for file in os.listdir(log_dir):
            if file.endswith(".log"):
                file_path = os.path.join(log_dir, file)
                with open(file_path, "r") as f:
                    content = f.read()
                    log_files.append({"FileName": file, "Content": content})
        log_files.sort(key=lambda x: x["FileName"], reverse=True)
        with open(
            os.path.join(
                decky_plugin.DECKY_USER_HOME, ".local/share/Steam/logs/console_log.txt"
            ),
            "r",
        ) as f:
            content = f.read()
            log_files.append({"FileName": "console_log.txt", "Content": content})

        return log_files

    async def _unload(self):
        try:
            decky_plugin.logger.info("Starting plugin unload...")

            # Cancel our own background tasks — and only those.
            # This used to sweep asyncio.all_tasks(), which has two problems:
            # the unload coroutine is itself a running task, so it cancelled
            # itself and recursed through Task.cancel() until Python gave up
            # with a RecursionError (leaving everything below this line
            # unexecuted), and the rest of the sweep hit tasks belonging to
            # Decky's own machinery rather than to this plugin.
            tasks = [t for t in _bg_tasks if not t.done()]
            if tasks:
                decky_plugin.logger.info(f"Cancelling {len(tasks)} pending tasks...")
                for task in tasks:
                    task.cancel()

            # Nothing below may depend on an await resuming. Decky stops running
            # this loop as soon as _unload suspends, so anything after a real
            # suspension point simply never happens — which is why the old code
            # never reached this point even before the RecursionError: its
            # gather() on the cancelled tasks was never resumed. Cancellation
            # itself is synchronous, so the tasks are told to stop either way.
            Helper.action_cache.clear()
            Helper.wsServerIsRunning = False

            decky_plugin.logger.info("SkullKey out!")

            # LAST, and knowingly so: stopping the aiohttp site waits for its
            # handlers, i.e. a real suspension — which, per the note above, never
            # resumes here. Measured on Steamcord 2026-09-22: the loader then
            # SIGKILLs the plugin exactly 5 s later, every single reload. Sitting
            # at the end, it costs nothing (the process is about to die, so the
            # port goes with it) instead of taking the whole unload down with it.
            await Helper.stop_ws_server()
        except Exception as e:
            decky_plugin.logger.error(f"Error during unload: {e}")

    async def _migration(self):
        plugin_dir = "SkullKey"
        decky_plugin.logger.info("Migrating")
        # Here's a migration example for logs:
        # - `~/.config/decky-template/template.log` will be migrated to `decky_plugin.DECKY_PLUGIN_LOG_DIR/template.log`
        decky_plugin.migrate_logs(
            os.path.join(
                decky_plugin.DECKY_USER_HOME, ".config", plugin_dir, "template.log"
            )
        )
        # Here's a migration example for settings:
        # - `~/homebrew/settings/template.json` is migrated to `decky_plugin.DECKY_PLUGIN_SETTINGS_DIR/template.json`
        # - `~/.config/decky-template/` all files and directories under this root are migrated to `decky_plugin.DECKY_PLUGIN_SETTINGS_DIR/`
        decky_plugin.migrate_settings(
            os.path.join(decky_plugin.DECKY_HOME, "settings", "template.json"),
            os.path.join(decky_plugin.DECKY_USER_HOME, ".config", plugin_dir),
        )
        # Here's a migration example for runtime data:
        # - `~/homebrew/template/` all files and directories under this root are migrated to `decky_plugin.DECKY_PLUGIN_RUNTIME_DIR/`
        # - `~/.local/share/decky-template/` all files and directories under this root are migrated to `decky_plugin.DECKY_PLUGIN_RUNTIME_DIR/`
        decky_plugin.migrate_runtime(
            os.path.join(decky_plugin.DECKY_HOME, plugin_dir),
            os.path.join(decky_plugin.DECKY_USER_HOME, ".local", "share", plugin_dir),
        )
