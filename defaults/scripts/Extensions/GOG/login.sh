#!/usr/bin/env bash
# These need to be exported because it does not get executed in the context of the plugin.
export DECKY_PLUGIN_RUNTIME_DIR="${HOME}/homebrew/data/SkullKey"
export DECKY_PLUGIN_DIR="${HOME}/homebrew/plugins/SkullKey"
export DECKY_PLUGIN_LOG_DIR="${HOME}/homebrew/logs/SkullKey"
export WORKING_DIR=$DECKY_PLUGIN_DIR
export Extensions="Extensions"
ID=$1
echo $1
shift

source "${DECKY_PLUGIN_DIR}/scripts/Extensions/GOG/settings.sh"

CODE=$(/usr/bin/python3 "${DECKY_PLUGIN_DIR}/scripts/Extensions/GOG/gog-login-gui.py" 2>> "${DECKY_PLUGIN_LOG_DIR}/goglogin.log")
if [[ -n "${CODE}" ]]; then
    $GOGDL auth --code "${CODE}" &>> "${DECKY_PLUGIN_LOG_DIR}/goglogin.log"
else
    echo "GOG login window closed without a code" >> "${DECKY_PLUGIN_LOG_DIR}/goglogin.log"
fi
"${DECKY_PLUGIN_DIR}/scripts/skullkey.sh" GOG loginstatus --flush-cache
