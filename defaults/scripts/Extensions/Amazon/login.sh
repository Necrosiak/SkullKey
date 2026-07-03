#!/usr/bin/env bash
# These need to be exported because it does not get executed in the context of the plugin.
export DECKY_PLUGIN_RUNTIME_DIR="${HOME}/homebrew/data/SkeletonKey"
export DECKY_PLUGIN_DIR="${HOME}/homebrew/plugins/SkeletonKey"
export DECKY_PLUGIN_LOG_DIR="${HOME}/homebrew/logs/SkeletonKey"
export WORKING_DIR=$DECKY_PLUGIN_DIR
export Extensions="Extensions"
ID=$1
echo $1
shift

source "${DECKY_PLUGIN_DIR}/scripts/Extensions/Amazon/settings.sh"

/usr/bin/python3 "${DECKY_PLUGIN_DIR}/scripts/Extensions/Amazon/amazon-login-gui.py" &>> "${DECKY_PLUGIN_LOG_DIR}/amazonlogin.log"
"${DECKY_PLUGIN_DIR}/scripts/skeletonkey.sh" Amazon loginstatus --flush-cache
