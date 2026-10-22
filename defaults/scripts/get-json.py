#!/usr/bin/env python3
import os
import json
import sys
import os
import json
from collections.abc import MutableMapping

# Build json_fragments by reading content.json files
json_fragments = {}

# Function to merge a dictionary with another dictionary


def update(d, u):
    for k, v in u.items():
        if isinstance(v, MutableMapping):
            d[k] = update(d.get(k, {}), v)
        elif isinstance(v, list):
            if k in d:
                d[k].extend(v)
            else:
                d[k] = v
        else:
            d[k] = v
    return d


queue = ['../../data/SkullKey/scripts/Extensions', './scripts/Extensions']

while queue:
    current_dir = queue.pop(0)
    if not os.path.exists(current_dir):
        continue
    for entry in os.scandir(current_dir):
        if entry.is_dir():
            queue.append(entry.path)
        elif entry.is_file() and entry.name == 'static.json':
            with open(entry.path) as file:
                try:
                    content = json.load(file)
                    json_fragments = update(json_fragments, content)
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON from {entry.path}: {e}")


# Tab order must not depend on the directory listing order (os.scandir is
# arbitrary): stores first, then miHoYo, Minecraft and the Classics last.
TAB_ORDER = ["GetEpicActions", "GetGOGActions", "GetXboxActions", "GetAmazonActions", "GetBattleNetActions",
             "GetUbisoftActions", "GetEAActions",
             "GetMiHoYoActions", "GetMinecraftActions", "GetPortsActions", "GetDisksActions"]
# Platforms the player switched off in SkullKey's settings are left out
# everywhere (store bar and Quick Access menu). SK_ALL_TABS lists them all.
def _disabled_tabs():
    if os.environ.get("SK_ALL_TABS"):
        return set()
    runtime = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR") or os.path.expanduser("~/homebrew/data/SkullKey")
    try:
        with open(os.path.join(runtime, "platforms.json")) as f:
            return set(json.load(f).get("disabled") or [])
    except (OSError, ValueError):
        return set()


DISABLED = _disabled_tabs()
for fragment in json_fragments.values():
    tabs = fragment.get("Content", {}).get("Tabs") if isinstance(fragment, dict) else None
    if isinstance(tabs, list):
        tabs[:] = [tab for tab in tabs if tab.get("ActionId") not in DISABLED]
        tabs.sort(key=lambda tab: TAB_ORDER.index(tab.get("ActionId"))
                  if tab.get("ActionId") in TAB_ORDER else len(TAB_ORDER))

# Check if an argument is provided
if len(sys.argv) < 2:
    error = {
        "Type": "Error",
        "Content": {
            "Title": "Error",
            "Message": "Please provide an argument."
        }
    }
    print(json.dumps(error))
    sys.exit(1)

# Get the argument from the command line
argument = sys.argv[1]

# Look up the JSON fragment based on the argument
if argument in json_fragments:
    json_fragment = json_fragments[argument]
    print(json.dumps(json_fragment))
else:
    error = {
        "Type": "Error",
        "Content": {
            "Title": "Error",
            "Message": "Invalid argument."
        }
    }
    print(json.dumps(error))
    sys.exit(1)
