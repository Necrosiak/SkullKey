#!/usr/bin/env bash
# GOG extension dependencies: gogdl (the GOG download client used by Heroic),
# installed in a dedicated venv built with the Homebrew python (the system
# python on Bazzite/SteamOS images has no headers to compile gogdl's C ext).
VENV="${HOME}/.local/share/skullkey-gogdl"
GOGDL_SRC="git+https://github.com/Heroic-Games-Launcher/heroic-gogdl"

# Auto-détection du python pour builder le venv, SELON L'OS :
#  - Bazzite/SteamOS : le python SYSTÈME n'a pas les headers de dev (image
#    atomique) → on prend celui de Homebrew (préinstallé sur ces images).
#  - Arch/CachyOS/Fedora/Debian : le python système a les headers (paquet
#    -devel/-dev dispo) → on l'utilise directement, pas besoin de Homebrew.
PY=""
pick_python() {
    local brew_py="/home/linuxbrew/.linuxbrew/bin/python3"
    if [ -x "${brew_py}" ]; then PY="${brew_py}"; return 0; fi
    if command -v python3 >/dev/null 2>&1 && python3 -c "import venv" 2>/dev/null; then
        PY="$(command -v python3)"; return 0
    fi
    if [ -x /home/linuxbrew/.linuxbrew/bin/brew ]; then
        /home/linuxbrew/.linuxbrew/bin/brew install python && PY="${brew_py}" && return 0
    fi
    echo "ERROR: aucun python3 utilisable (headers de dev ou Homebrew requis) pour builder gogdl"
    return 1
}

function uninstall() {
    echo "Removing gogdl venv"
    rm -rf "${VENV}"
}

function install() {
    pick_python || return 1
    if [ ! -x "${VENV}/bin/pip" ]; then
        "${PY}" -m venv "${VENV}"
    fi
    CC=gcc "${VENV}/bin/pip" install --upgrade "${GOGDL_SRC}"
    "${VENV}/bin/gogdl" --version && echo "gogdl installed OK"
}

function check() {
    # Cheap, offline presence check used by the boot-time auto-provision.
    # Exit 0 = deps present, non-zero = missing (triggers install).
    [ -x "${VENV}/bin/gogdl" ]
}

if [ "$1" == "uninstall" ]; then
    echo "Uninstalling dependencies: GOG extension"
    uninstall
elif [ "$1" == "check" ]; then
    check
else
    echo "Installing dependencies: GOG extension"
    install
fi
