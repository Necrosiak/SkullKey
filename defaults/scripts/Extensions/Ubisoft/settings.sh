#!/usr/bin/env bash
# Ubisoft extension settings. Sourced by store.sh when PLATFORM == Ubisoft.
export PYTHONPATH="${DECKY_PLUGIN_DIR}/scripts/":"${DECKY_PLUGIN_DIR}/scripts/shared/":$PYTHONPATH

export LAUNCHER="${DECKY_PLUGIN_DIR}/scripts/Extensions/Ubisoft/ubisoft-launcher.sh"

# Shared Proton prefix holding Ubisoft Connect and every game.
if [[ -z "${UBISOFT_PREFIX}" ]]; then
    export UBISOFT_PREFIX="${HOME}/Games/ubisoft/prefix"
fi
