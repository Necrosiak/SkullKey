#!/usr/bin/env bash
EPICCONF="${DECKY_PLUGIN_DIR}/scripts/epic-config.py"

# stand-alone : legendary = flatpak si déjà installé (installs historiques
# Bazzite/SteamOS), sinon venv pip ~/.local/share/skullkey-legendary construit
# par install_deps.sh (CachyOS/Arch/Fedora/Debian n'ont pas forcément flatpak).
# Les deux backends lisent la MÊME config : le vrai dossier vit dans l'espace
# du compte Steam (multi-comptes) et le chemin candidat est symlinké dessus.
_LEG_VENV="${HOME}/.local/share/skullkey-legendary/bin/legendary"
if command -v flatpak >/dev/null 2>&1 && flatpak info com.github.derrod.legendary &>/dev/null; then
    export LEGENDARY="$(command -v flatpak) run com.github.derrod.legendary"
    # flatpak force ses chemins XDG vers ~/.var/app/… (--env inopérant, même
    # piège que Vesktop dans Steamcord) → retarget dans l'app dir du flatpak.
    _LEG_BASE="${HOME}/.var/app/com.github.derrod.legendary/config"
else
    export LEGENDARY="${_LEG_VENV}"
    # le legendary venv lit ~/.config/legendary → même retargeting, autre base.
    _LEG_BASE="${HOME}/.config"
    mkdir -p "${_LEG_BASE}"
fi

# multi-comptes : le login Epic du compte Steam actif est sélectionné en
# retargetant le symlink <base>/legendary vers l'espace du compte. Le VRAI
# dossier existant (session du propriétaire) est adopté par le premier compte
# vu ; un dossier réel recréé par un run manuel est parqué, jamais supprimé.
SK_ACCOUNT_DIR="${SK_ACCOUNT_DIR:-${DECKY_PLUGIN_RUNTIME_DIR}}"
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
# stand-alone : protontricks natif d'abord (pacman/dnf/apt), flatpak en secours
if command -v protontricks >/dev/null 2>&1; then
    PROTON_TRICKS="$(command -v protontricks)"
elif command -v flatpak >/dev/null 2>&1; then
    PROTON_TRICKS="$(command -v flatpak) run com.github.Matoking.protontricks"
else
    # ni natif ni flatpak → vide ; le bouton Protontricks affiche une erreur
    PROTON_TRICKS=""
fi
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





