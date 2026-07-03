#!/usr/bin/env bash
GOGCONF="${DECKY_PLUGIN_DIR}/scripts/gog-config.py"
GOGDL_BIN="${HOME}/.local/share/skeletonkey-gogdl/bin/gogdl"
GOG_AUTH_FILE="${DECKY_PLUGIN_RUNTIME_DIR}/gog_auth.json"
export GOGDL="${GOGDL_BIN} --auth-config-path ${GOG_AUTH_FILE}"
PROTON_TRICKS="/bin/flatpak run com.github.Matoking.protontricks"
export PYTHONPATH="${DECKY_PLUGIN_DIR}/scripts/":"${DECKY_PLUGIN_DIR}/scripts/shared/":$PYTHONPATH

export LAUNCHER="${DECKY_PLUGIN_DIR}/scripts/${Extensions}/GOG/gog-launcher.sh"
export ARGS_SCRIPT="${DECKY_PLUGIN_DIR}/scripts/${Extensions}/GOG/get-gog-args.sh"
DBNAME="gog.db"
DBFILE="${DECKY_PLUGIN_RUNTIME_DIR}/gog.db"

if [[ -f "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/gogtabconfig.json" ]]; then
    TEMP="${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/gogtabconfig.json"
else
    TEMP="${DECKY_PLUGIN_DIR}/conf_schemas/gogtabconfig.json"
fi
SETTINGS=$($GOGCONF --generate-env-settings-json $TEMP --dbfile $DBFILE)
eval "${SETTINGS}"

if [[ "${GOG_OFFLINEMODE}" == "true" ]]; then
    OFFLINE_MODE="--offline"
else
    OFFLINE_MODE=""
fi
if [[ "${GOG_INSTALLLOCATION}" == "MicroSD" ]]; then
    NVME=$(lsblk --list | grep nvme0n1\ |awk '{ print $2}' |  awk '{split($0, a,":"); print a[1]}')
    LINK=$(find /run/media -maxdepth 1  -type l )
    LINK_TARGET=$(readlink -f "${LINK}")
    MOUNT_POINT=$(lsblk --list --exclude "${NVME}" | grep part |  sed -n 's/.*part //p')
    if [[ "${MOUNT_POINT}" == "${LINK_TARGET}" ]]; then
        INSTALL_DIR="${LINK}/Games/gog/"
    else
        INSTALL_DIR="/run/media/mmcblk0p1/Games/gog/"
    fi
else
    INSTALL_DIR="${HOME}/Games/gog/"
fi
export INSTALL_DIR

if [ -z "${GOG_LANGUAGE}" ]; then
    GOG_LANGUAGE="en-US"
fi

if [[ -f "${DECKY_PLUGIN_RUNTIME_DIR}/gog_overrides.sh" ]]; then
   source "${DECKY_PLUGIN_RUNTIME_DIR}/gog_overrides.sh"
fi
