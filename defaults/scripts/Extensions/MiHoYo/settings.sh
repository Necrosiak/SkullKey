#!/usr/bin/env bash
# MiHoYo extension settings. Sourced by store.sh when PLATFORM == MiHoYo.
MIHOYO_PY="${DECKY_PLUGIN_DIR}/scripts/Extensions/MiHoYo/mihoyo.py"
export PYTHONPATH="${DECKY_PLUGIN_DIR}/scripts/":"${DECKY_PLUGIN_DIR}/scripts/shared/":$PYTHONPATH

export LAUNCHER="${DECKY_PLUGIN_DIR}/scripts/Extensions/MiHoYo/mihoyo-launcher.sh"

if [[ -z "${MIHOYO_INSTALL_DIR}" ]]; then
    export MIHOYO_INSTALL_DIR="${HOME}/Games/mihoyo/"
fi
