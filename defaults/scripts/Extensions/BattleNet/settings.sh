#!/usr/bin/env bash
# Battle.net extension settings. Sourced by store.sh when PLATFORM == BattleNet.
export PYTHONPATH="${DECKY_PLUGIN_DIR}/scripts/":"${DECKY_PLUGIN_DIR}/scripts/shared/":$PYTHONPATH

export LAUNCHER="${DECKY_PLUGIN_DIR}/scripts/Extensions/BattleNet/battlenet-launcher.sh"

# Shared Proton prefix holding the Battle.net client and every game.
if [[ -z "${BATTLENET_PREFIX}" ]]; then
    export BATTLENET_PREFIX="${HOME}/Games/battlenet/prefix"
fi
