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


async def _auto_update_check():
    """Silent release-based auto-update, a little after startup so the plugin
    is fully usable first. Module-level (no `self`) because decky's dispatch
    doesn't bind an instance to a task spawned from inside _main."""
    try:
        await asyncio.sleep(20)
        if not updater.is_autoupdate_enabled():
            return
        info = await updater.check()
        if not info.get("update_available"):
            return
        decky_plugin.logger.info(
            f"[updater] {info['latest']} available (have {info['current']}); auto-applying"
        )
        if await updater.apply(info["url"]):
            updater.restart_loader()
    except Exception as e:
        decky_plugin.logger.error(f"[updater] auto-check error: {e}")


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
        decky_plugin.logger.info("[deps] ensure finished")
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
            if Helper.verbose:
                decky_plugin.logger.info(f"init result: {result}")
            await Helper.start_ws_server()
            decky_plugin.logger.info("SkullKey started")
            # Schedule the silent auto-update as a module-level coroutine —
            # decky's method dispatch doesn't bind `self` for a task created
            # from inside _main, so keep it self-free.
            asyncio.create_task(_auto_update_check())
            asyncio.create_task(_ensure_deps())
            asyncio.create_task(_resume_downloads())
            asyncio.create_task(_games_autoupdate())

        except Exception as e:
            decky_plugin.logger.error(f"Error in _main: {e}")

    async def check_update(self):
        return await updater.check()

    async def get_version(self):
        return updater.get_current_version()

    async def apply_update(self, url):
        res = await updater.apply(url)
        if res.get("ok"):
            updater.restart_loader()
        return res

    async def get_autoupdate(self):
        return updater.is_autoupdate_enabled()

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
            if Helper.verbose:
                decky_plugin.logger.info(f"init result: {result}")
        except Exception as e:
            decky_plugin.logger.error(f"Error in _main: {e}")

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

            # Stop WebSocket server
            await Helper.stop_ws_server()

            # Cancel all pending asyncio tasks
            tasks = [task for task in asyncio.all_tasks() if not task.done()]
            if tasks:
                decky_plugin.logger.info(f"Cancelling {len(tasks)} pending tasks...")
                for task in tasks:
                    task.cancel()
                # Wait for all tasks to complete cancellation
                await asyncio.gather(*tasks, return_exceptions=True)

            # Clear the action cache
            Helper.action_cache.clear()

            decky_plugin.logger.info("SkullKey out!")
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
