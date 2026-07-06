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
$LEGENDARY auth -v &>> "${DECKY_PLUGIN_LOG_DIR}/epiclogin.log"
"${DECKY_PLUGIN_DIR}/scripts/skullkey.sh" Epic loginstatus --flush-cache 