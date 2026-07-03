import json
import os
import re
import subprocess
import sys
import sqlite3
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

import GamesDb


class CmdException(Exception):
    pass


EMBED = "https://embed.gog.com"
# GOG Galaxy client id — same public credentials used by Heroic/Minigalaxy/gogdl
GALAXY_CLIENT_ID = "46899977096215655"


class Gog(GamesDb.GamesDb):
    def __init__(self, db_file, storeName, setNameConfig=None):
        super().__init__(db_file, storeName=storeName, setNameConfig=setNameConfig)
        self.storeURL = "https://www.gog.com/"

    # includes --auth-config-path, set by settings.sh
    gogdl_cmd = os.path.expanduser(os.environ.get('GOGDL', 'gogdl'))
    install_dir = os.path.expanduser(os.environ.get('INSTALL_DIR', '~/Games/gog/'))

    def execute_shell(self, cmd):
        result = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  shell=True).communicate()[0].decode()
        if result.strip() == "":
            raise CmdException(f"Command produced no output (try installing dependencies from the About menu): {cmd}")
        return json.loads(result)

    def get_token(self):
        # `gogdl auth` refreshes if needed and prints the credentials as json
        try:
            creds = self.execute_shell(f"{self.gogdl_cmd} auth")
        except (CmdException, json.JSONDecodeError):
            return None
        if not creds or creds.get("error"):
            return None
        return creds.get("access_token")

    def api_get(self, url, token):
        req = urllib.request.Request(url, headers={
            'Authorization': f"Bearer {token}",
            'User-Agent': 'Mozilla/5.0'
        })
        response = urllib.request.urlopen(req, timeout=60)
        return json.loads(response.read())

    def get_list(self, offline):
        if offline:
            return
        token = self.get_token()
        if token is None:
            raise CmdException("Not logged in to GOG (login first from the GOG tab)")
        page = 1
        total_pages = 1
        id_list = []
        game_dict = {}
        while page <= total_pages:
            data = self.api_get(
                f"{EMBED}/account/getFilteredProducts?mediaType=1&page={page}", token)
            total_pages = data.get('totalPages', 1)
            for product in data.get('products', []):
                # worksOn is unreliable (often all-false); keep everything that
                # is a game — installability is decided by gogdl at install time
                if product.get('isMovie') or product.get('isGame') is False:
                    continue
                shortname = str(product['id'])
                id_list.append(shortname)
                game_dict[shortname] = product
            page += 1
        left_overs = self.insert_data(id_list)
        print(f"left_overs: {left_overs}", file=sys.stderr)
        for game in left_overs:
            if game in game_dict:
                self.proccess_leftovers(game_dict[game])

    def proccess_leftovers(self, product):
        # gamesdb.gog.com had no metadata — insert a minimal row from the library data
        print(f"Processing leftover game: {product.get('title')}", file=sys.stderr)
        conn = self.get_connection()
        c = conn.cursor()
        try:
            shortname = str(product['id'])
            c.execute("SELECT * FROM Game WHERE ShortName=?", (shortname,))
            if c.fetchone() is None:
                cols = ["Title", "Notes", "ApplicationPath", "ManualPath", "Publisher",
                        "RootFolder", "Source", "DatabaseID", "Genre", "ConfigurationPath",
                        "Developer", "ReleaseDate", "Size", "InstallPath", "UmuId",
                        "SteamClientID", "ShortName"]
                vals = [product.get('title', shortname), "", "", "", "",
                        "", "GOG", shortname, "", "",
                        "", "", "", "", "",
                        "", shortname]
                placeholders = ', '.join(['?' for _ in cols])
                c.execute(f"INSERT INTO Game ({', '.join(cols)}) VALUES ({placeholders})", vals)
                game_id = c.lastrowid
                image = product.get('image')
                if image:
                    url = f"https:{image}.jpg" if image.startswith("//") else image
                    c.execute("INSERT INTO Images (GameID, ImagePath, FileName, SortOrder, Type) VALUES (?, ?, ?, ?, ?)",
                              (game_id, url, '', 0, 'vertical_cover'))
                    c.execute("INSERT INTO Images (GameID, ImagePath, FileName, SortOrder, Type) VALUES (?, ?, ?, ?, ?)",
                              (game_id, url, '', 1, 'horizontal_artwork'))
                conn.commit()
        except Exception as e:
            print(f"Error inserting leftover game: {e}", file=sys.stderr)
        conn.close()

    def get_login_status(self, offline, flush_cache=False):
        cache_key = "gog-login"
        if flush_cache:
            self.clear_cache(cache_key)
        cache = self.get_cache(cache_key)
        if cache is not None:
            return cache
        token = self.get_token()
        if token is None:
            value = json.dumps({'Type': 'LoginStatus', 'Content': {'Username': '<not logged in>', 'LoggedIn': False}})
        else:
            username = "GOG user"
            try:
                user = self.api_get(f"{EMBED}/userData.json", token)
                username = user.get('username', username)
            except Exception as e:
                print(f"userData failed: {e}", file=sys.stderr)
            if offline:
                username += " (offline)"
            value = json.dumps({'Type': 'LoginStatus', 'Content': {'Username': username, 'LoggedIn': True}})
        timeout = datetime.now() + timedelta(hours=1)
        try:
            self.add_cache(cache_key, value, timeout)
        except Exception as e:
            print(f"Error adding cache: {e}", file=sys.stderr)
        return value

    def get_install_path(self, game_id, resolve=True):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("SELECT InstallPath FROM Game WHERE ShortName=?", (game_id,))
        result = c.fetchone()
        conn.close()
        if result and result[0]:
            return result[0]
        if not resolve:
            return None
        # not yet resolved: ask gogdl for the store folder name
        folder = game_id
        try:
            info = self.execute_shell(f"{self.gogdl_cmd} info {game_id} --platform windows")
            folder = info.get('folder_name') or game_id
        except Exception as e:
            print(f"gogdl info failed: {e}", file=sys.stderr)
        path = os.path.join(self.install_dir, folder)
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE Game SET InstallPath=? WHERE ShortName=?", (path, game_id))
        conn.commit()
        conn.close()
        return path

    def get_game_dir(self, game_id, offline):
        print(self.get_install_path(game_id))

    def get_working_dir(self, game_id, offline):
        task = self.get_primary_task(game_id)
        print(task['working_dir'])

    def get_primary_task(self, game_id):
        game_path = self.get_install_path(game_id)
        info_file = os.path.join(game_path, f"goggame-{game_id}.info")
        if not os.path.isfile(info_file):
            raise CmdException(f"goggame info file not found: {info_file} (game not installed?)")
        with open(info_file) as f:
            info = json.load(f)
        primary = None
        for task in info.get('playTasks', []):
            if task.get('isPrimary'):
                primary = task
                break
        if primary is None:
            raise CmdException(f"No primary play task in {info_file}")
        exe = os.path.join(game_path, primary['path'].replace("\\", os.sep))
        working_dir = os.path.join(
            game_path, (primary.get('workingDir') or "").replace("\\", os.sep))
        arguments = primary.get('arguments') or ""
        if isinstance(arguments, list):
            arguments = " ".join(arguments)
        return {'exe': exe, 'working_dir': working_dir, 'arguments': arguments,
                'game_dir': game_path}

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
                info = self.execute_shell(f"{self.gogdl_cmd} info {game_id} --platform windows")
                disk = info.get('disk_size')
                download = info.get('download_size')
                disk_str = f"Install Size: {self.convert_bytes(disk)}" if disk else ""
                dl_str = f"Download Size: {self.convert_bytes(download)}" if download else ""
                size = disk_str + (f" ({dl_str})" if dl_str and disk_str else dl_str)
            except Exception as e:
                print(f"gogdl info failed: {e}", file=sys.stderr)
                size = ""
        return json.dumps({'Type': 'GameSize', 'Content': {'Size': size}})

    def update_game_details(self, game_id):
        path = self.get_install_path(game_id, resolve=False)
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
        c.execute("UPDATE Game SET Size=? WHERE ShortName=?", (size, game_id))
        conn.commit()
        conn.close()

    def clear_install_info(self, game_id):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute("UPDATE Game SET Size=NULL, InstallPath=NULL, SteamClientID='' WHERE ShortName=?", (game_id,))
        conn.commit()
        conn.close()
        print(json.dumps({'Type': 'Success', 'Content': {'Message': 'Install info cleared'}}))

    # gogdl progress log format (logging fmt "[NAME] LEVEL: msg"):
    # [PROGRESS] INFO: = Progress: 12.34 1234/56789, Running for: 00:01:02, ETA: 00:12:34
    # [PROGRESS] INFO: = Downloaded: 316.12 MiB, Written: 361.03 MiB
    # [PROGRESS] INFO:  + Download	- 4.00 MiB/s (raw) / 4.00 MiB/s (decompressed)
    # store.sh appends "===GOGDL_EXIT:N===" when the wrapped command exits.
    def get_last_progress_update(self, file_path):
        progress_re = re.compile(
            r"= Progress: (\d+\.\d+) (\d+)/(\d+), Running for: (\d+:\d+:\d+), ETA: (\d+:\d+:\d+)")
        downloaded_re = re.compile(r"= Downloaded: (\d+\.\d+) MiB, Written: (\d+\.\d+) MiB")
        speed_re = re.compile(r"\+ Download\t- (\d+\.\d+) MiB/s")
        exit_re = re.compile(r"===GOGDL_EXIT:(\d+)===")
        last_progress_update = None
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
            percent = None
            total = None
            downloaded = None
            speed = None
            exit_code = None
            for line in lines:
                if match := progress_re.search(line):
                    percent = float(match.group(1))
                    total = int(match.group(3))
                elif match := downloaded_re.search(line):
                    downloaded = float(match.group(2))
                elif match := speed_re.search(line):
                    speed = float(match.group(1))
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
                total_mb = round(total / 1024 / 1024, 2) if total else None
                desc = f"Downloaded {downloaded} MB" if downloaded is not None else "Downloading"
                if total_mb:
                    desc += f"/{total_mb} MB"
                desc += f" ({pct}%)"
                if speed is not None:
                    desc += f"\nSpeed: {speed} MB/s"
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
