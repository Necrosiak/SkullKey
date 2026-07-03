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

source "${DECKY_PLUGIN_DIR}/scripts/Extensions/Epic/settings.sh"
$LEGENDARY auth -v &>> "${DECKY_PLUGIN_LOG_DIR}/epiclogin.log"
"${DECKY_PLUGIN_DIR}/scripts/skeletonkey.sh" Epic loginstatus --flush-cache 