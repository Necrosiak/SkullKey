import json
import os
import re
import subprocess
import sys
import sqlite3
import time
from datetime import datetime, timedelta

import GamesDb


class CmdException(Exception):
    pass


class Amazon(GamesDb.GamesDb):
    def __init__(self, db_file, storeName, setNameConfig=None):
        super().__init__(db_file, storeName=storeName, setNameConfig=setNameConfig)
        self.storeURL = "https://gaming.amazon.com/"

    nile_cmd = os.path.expanduser(os.environ.get('NILE', 'nile'))
    install_dir = os.path.expanduser(os.environ.get('INSTALL_DIR', '~/Games/amazon/'))

    # nile config dir (honours NILE_CONFIG_PATH set in settings.sh)
    def config_dir(self):
        base = os.environ.get('NILE_CONFIG_PATH') or os.environ.get(
            'XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
        return os.path.join(base, 'nile')

    def execute_shell(self, cmd, expect_json=True):
        result = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  shell=True).communicate()[0].decode()
        if not expect_json:
            return result
        if result.strip() == "":
            raise CmdException(f"Command produced no output (try installing dependencies from the About menu): {cmd}")
        return json.loads(result)

    def get_list(self, offline):
        if offline:
            return
        self.execute_shell(f"{self.nile_cmd} library sync", expect_json=False)
        games = self.execute_shell(f"{self.nile_cmd} library list --json")
        if not isinstance(games, list):
            raise CmdException("Unexpected nile library output (not logged in?)")
        id_list = []
        game_dict = {}
        for entry in games:
            product = entry.get('product') or {}
            pid = product.get('id')
            if not pid:
                continue
            id_list.append(pid)
            game_dict[pid] = product
        left_overs = self.insert_data(id_list)
        print(f"left_overs: {left_overs}", file=sys.stderr)
        for game in left_overs:
            if game in game_dict:
                self.proccess_leftovers(game_dict[game])

    def proccess_leftovers(self, product):
        print(f"Processing leftover game: {product.get('title')}", file=sys.stderr)
        conn = self.get_connection()
        c = conn.cursor()
        try:
            shortname = product['id']
            c.execute("SELECT * FROM Game WHERE ShortName=?", (shortname,))
            if c.fetchone() is None:
                cols = ["Title", "Notes", "ApplicationPath", "ManualPath", "Publisher",
                        "RootFolder", "Source", "DatabaseID", "Genre", "ConfigurationPath",
                        "Developer", "ReleaseDate", "Size", "InstallPath", "UmuId",
                        "SteamClientID", "ShortName"]
                vals = [product.get('title', shortname), "", "", "", "",
                        "", "Amazon", shortname, "", "",
                        "", "", "", "", "",
                        "", shortname]
                placeholders = ', '.join(['?' for _ in cols])
                c.execute(f"INSERT INTO Game ({', '.join(cols)}) VALUES ({placeholders})", vals)
                game_id = c.lastrowid
                details = (product.get('productDetail') or {}).get('details') or {}
                vertical = details.get('iconUrl') or details.get('logoUrl')
                wide = details.get('backgroundUrl2') or details.get('backgroundUrl1') or vertical
                if vertical:
                    c.execute("INSERT INTO Images (GameID, ImagePath, FileName, SortOrder, Type) VALUES (?, ?, ?, ?, ?)",
                              (game_id, vertical, '', 0, 'vertical_cover'))
                if wide:
                    c.execute("INSERT INTO Images (GameID, ImagePath, FileName, SortOrder, Type) VALUES (?, ?, ?, ?, ?)",
                              (game_id, wide, '', 1, 'horizontal_artwork'))
                conn.commit()
        except Exception as e:
            print(f"Error inserting leftover game: {e}", file=sys.stderr)
        conn.close()

    def get_login_status(self, offline, flush_cache=False):
        cache_key = "amazon-login"
        if flush_cache:
            self.clear_cache(cache_key)
        cache = self.get_cache(cache_key)
        if cache is not None:
            return cache
        try:
            status = self.execute_shell(f"{self.nile_cmd} auth --status")
        except (CmdException, json.JSONDecodeError):
            status = {'Username': '<not logged in>', 'LoggedIn': False}
        username = status.get('Username', '<not logged in>')
        if offline and status.get('LoggedIn'):
            username += " (offline)"
        value = json.dumps({'Type': 'LoginStatus', 'Content': {
            'Username': username, 'LoggedIn': bool(status.get('LoggedIn'))}})
        timeout = datetime.now() + timedelta(hours=1)
        try:
            self.add_cache(cache_key, value, timeout)
        except Exception as e:
            print(f"Error adding cache: {e}", file=sys.stderr)
        return value

    def read_installed(self):
        installed_file = os.path.join(self.config_dir(), 'installed.json')
        if not os.path.isfile(installed_file):
            return []
        try:
            with open(installed_file) as f:
                return json.load(f)
        except Exception:
            return []

    def get_install_path(self, game_id):
        for entry in self.read_installed():
            if entry.get('id') == game_id:
                return entry.get('path')
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT InstallPath FROM Game WHERE ShortName=?", (game_id,))
        result = c.fetchone()
        conn.close()
        if result and result[0]:
            return result[0]
        return None

    def get_game_dir(self, game_id, offline):
        print(self.get_install_path(game_id) or "")

    def get_working_dir(self, game_id, offline):
        task = self.get_primary_task(game_id)
        print(task['working_dir'])

    def get_primary_task(self, game_id):
        game_path = self.get_install_path(game_id)
        if not game_path:
            raise CmdException(f"Game {game_id} is not installed")
        fuel_file = os.path.join(game_path, "fuel.json")
        if not os.path.isfile(fuel_file):
            raise CmdException(f"fuel.json not found in {game_path}")
        # fuel.json sometimes contains control characters — be lenient
        with open(fuel_file, encoding="utf-8-sig", errors="replace") as f:
            fuel = json.loads(f.read(), strict=False)
        main = fuel.get('Main') or {}
        command = (main.get('Command') or "").replace("\\", os.sep)
        if not command:
            raise CmdException(f"No Main.Command in {fuel_file}")
        arguments = main.get('Args') or []
        if isinstance(arguments, list):
            arguments = " ".join(arguments)
        sub = (main.get('WorkingSubdirOverride') or "").replace("\\", os.sep)
        working_dir = os.path.join(game_path, sub) if sub else game_path
        return {'exe': os.path.join(game_path, command), 'working_dir': working_dir,
                'arguments': arguments, 'game_dir': game_path}

    def get_parameters(self, game_id, offline):
        return self.get_primary_task(game_id)['arguments']

    def get_lauch_options(self, game_id, steam_command, name, offline):
        task = self.get_primary_task(game_id)
        launcher = os.environ['LAUNCHER']
        script_path = os.path.expanduser(launcher)
        return json.dumps(
            {
                'Type': 'LaunchOptions',
                'Content':
                {
                    'Exe': f"\"{task['exe']}\"".replace("$", "\\\\\\$"),
                    'Options': f"{script_path} {game_id}%command%",
                    'WorkingDir': task['working_dir'],
                    'Compatibility': True,
                    'Name': name
                }
            })

    def get_game_size(self, game_id, installed):
        if installed == 'true':
            conn = self.get_connection()
            c = conn.cursor()
            c.row_factory = sqlite3.Row
            c.execute("SELECT Size FROM Game WHERE ShortName=?", (game_id,))
            result = c.fetchone()
            conn.close()
            if result and bool(result['Size']):
                size = f"Size on Disk: {result['Size']}"
            else:
                size = ""
        else:
            try:
                info = self.execute_shell(f"{self.nile_cmd} install {game_id} --info --json")
                download = info.get('download_size') or info.get('size')
                disk = info.get('disk_size') or info.get('size')
                disk_str = f"Install Size: {self.convert_bytes(disk)}" if disk else ""
                dl_str = f"Download Size: {self.convert_bytes(download)}" if download else ""
                size = disk_str + (f" ({dl_str})" if dl_str and disk_str else dl_str)
            except Exception as e:
                print(f"nile info failed: {e}", file=sys.stderr)
                size = ""
        return json.dumps({'Type': 'GameSize', 'Content': {'Size': size}})

    def update_game_details(self, game_id):
        path = self.get_install_path(game_id)
        size = None
        if path and os.path.isdir(path):
            total = 0
            for root, dirs, files in os.walk(path):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
            size = self.convert_bytes(total)
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE Game SET Size=?, InstallPath=? WHERE ShortName=?", (size, path, game_id))
        conn.commit()
        conn.close()

    def clear_install_info(self, game_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE Game SET Size=NULL, InstallPath=NULL, SteamClientID='' WHERE ShortName=?", (game_id,))
        conn.commit()
        conn.close()
        print(json.dumps({'Type': 'Success', 'Content': {'Message': 'Install info cleared'}}))

    # nile uses the same "[PROGRESS] INFO: = Progress: ..." log format as gogdl;
    # store.sh appends "===NILE_EXIT:N===" when the wrapped command exits.
    def get_last_progress_update(self, file_path):
        progress_re = re.compile(
            r"= Progress: (\d+\.\d+) (\d+)/(\d+), Running for: (\d+:\d+:\d+), ETA: (\d+:\d+:\d+)")
        exit_re = re.compile(r"===NILE_EXIT:(\d+)===")
        last_progress_update = None
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
            percent = None
            downloaded = None
            total = None
            exit_code = None
            for line in lines:
                if match := progress_re.search(line):
                    percent = float(match.group(1))
                    downloaded = int(match.group(2))
                    total = int(match.group(3))
                elif match := exit_re.search(line):
                    exit_code = int(match.group(1))
            if exit_code is not None:
                if exit_code == 0:
                    last_progress_update = {
                        "Percentage": 100,
                        "Description": "Finished installation process"
                    }
                else:
                    tail = "".join(lines[-15:])
                    last_progress_update = {
                        "Percentage": 0,
                        "Description": "Installation Failed.",
                        "Error": tail.replace("\n", "<br />")
                    }
            elif percent is not None:
                pct = min(int(percent), 99)
                desc = f"Downloaded {round((downloaded or 0) / 1024 / 1024, 1)} MB"
                if total:
                    desc += f"/{round(total / 1024 / 1024, 1)} MB"
                desc += f" ({pct}%)"
                last_progress_update = {
                    "Percentage": pct,
                    "Description": desc
                }
            if last_progress_update is None:
                last_progress_update = {
                    "Percentage": 0,
                    "Description": lines[-1].strip() if lines else "Starting..."
                }
        except Exception as e:
            print("Waiting for progress update", e, file=sys.stderr)
            time.sleep(1)
        return json.dumps({'Type': 'ProgressUpdate', 'Content': last_progress_update})
