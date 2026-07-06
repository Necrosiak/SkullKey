#!/usr/bin/env bash
EPICCONF="${DECKY_PLUGIN_DIR}/scripts/epic-config.py"
export LEGENDARY="/bin/flatpak run com.github.derrod.legendary"

# multi-comptes : legendary est un flatpak → il force ses chemins XDG vers
# ~/.var/app/… (--env inopérant, même piège que Vesktop dans Steamcord). Le
# login Epic du compte Steam actif est donc sélectionné en retargetant le
# symlink config/legendary vers l'espace du compte. Le VRAI dossier existant
# (session du propriétaire) est adopté par le premier compte vu ; un dossier
# réel recréé par un run manuel est parqué, jamais supprimé.
SK_ACCOUNT_DIR="${SK_ACCOUNT_DIR:-${DECKY_PLUGIN_RUNTIME_DIR}}"
_LEG_BASE="${HOME}/.var/app/com.github.derrod.legendary/config"
_LEG_TARGET="${SK_ACCOUNT_DIR}/legendary"
if [[ -d "${_LEG_BASE}" ]]; then
    if [[ -d "${_LEG_BASE}/legendary" && ! -L "${_LEG_BASE}/legendary" ]]; then
        if [[ ! -e "${_LEG_TARGET}" ]]; then
            mv "${_LEG_BASE}/legendary" "${_LEG_TARGET}"
        else
            mv "${_LEG_BASE}/legendary" "${_LEG_BASE}/legendary.parked-$$"
        fi
    fi
    mkdir -p "${_LEG_TARGET}"
    if [[ "$(readlink "${_LEG_BASE}/legendary" 2>/dev/null)" != "${_LEG_TARGET}" ]]; then
        ln -sfn "${_LEG_TARGET}" "${_LEG_BASE}/legendary"
    fi
fi
PROTON_TRICKS="/bin/flatpak run com.github.Matoking.protontricks"
# the launcher script to use in steam
export PYTHONPATH="${DECKY_PLUGIN_DIR}/scripts/":"${DECKY_PLUGIN_DIR}/scripts/shared/":$PYTHONPATH

export LAUNCHER="${DECKY_PLUGIN_DIR}/scripts/${Extensions}/Epic/epic-launcher.sh"
export ARGS_SCRIPT="${DECKY_PLUGIN_DIR}/scripts/${Extensions}/Epic/get-epic-args.sh"
DBNAME="epic.db"
# database to use for configs and metadata (per Steam account)
DBFILE="${SK_ACCOUNT_DIR}/epic.db"

if [[ -f "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/epictabconfig.json" ]]; then
    TEMP="${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/epictabconfig.json"
else
    TEMP="${DECKY_PLUGIN_DIR}/conf_schemas/epictabconfig.json"
fi
SETTINGS=$($EPICCONF --generate-env-settings-json $TEMP --dbfile $DBFILE)
eval "${SETTINGS}"


if [[ "${EPIC_OFFLINEMODE}" == "true" ]]; then
    OFFLINE_MODE="--offline"
else
    OFFLINE_MODE=""
fi
if [[ "${EPIC_INSTALLLOCATION}" == "SSD" ]]; then
    INSTALL_DIR="${HOME}/Games/epic/"
elif [[ "${EPIC_INSTALLLOCATION}" == "MicroSD" ]]; then
    NVME=$(lsblk --list | grep nvme0n1\ |awk '{ print $2}' |  awk '{split($0, a,":"); print a[1]}')
    LINK=$(find /run/media -maxdepth 1  -type l )
    LINK_TARGET=$(readlink -f "${LINK}")
    MOUNT_POINT=$(lsblk --list --exclude "${NVME}" | grep part |  sed -n 's/.*part //p')
    if [[ "${MOUNT_POINT}" == "${LINK_TARGET}" ]]; then
        INSTALL_DIR="${LINK}/Games/epic/"
    else    
        INSTALL_DIR="/run/media/mmcblk0p1/Games/epic/"
    fi
else
    INSTALL_DIR="${HOME}/Games/"
fi


if [[ -f "${DECKY_PLUGIN_RUNTIME_DIR}/epic_overrides.sh" ]]; then
   source "${DECKY_PLUGIN_RUNTIME_DIR}/epic_overrides.sh"
fi





