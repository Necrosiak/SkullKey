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

source "${DECKY_PLUGIN_DIR}/scripts/Extensions/Epic/settings.sh"

# Steam launches this helper without an interactive stdin.  Calling plain
# `legendary auth` therefore ends in EOFError as soon as it asks the user to
# paste Epic's authorizationCode.  Reuse SkullKey's GTK/WebKit OAuth window,
# capture the code automatically, then use Legendary's non-interactive option.
CODE=$(/usr/bin/python3 "${DECKY_PLUGIN_DIR}/scripts/Extensions/GOG/gog-login-gui.py" --epic 2>> "${DECKY_PLUGIN_LOG_DIR}/epiclogin.log")
if [[ -n "${CODE}" ]]; then
    $LEGENDARY auth --code "${CODE}" -v &>> "${DECKY_PLUGIN_LOG_DIR}/epiclogin.log"
else
    echo "Epic login window closed without an authorization code" >> "${DECKY_PLUGIN_LOG_DIR}/epiclogin.log"
fi
"${DECKY_PLUGIN_DIR}/scripts/skullkey.sh" Epic loginstatus --flush-cache
