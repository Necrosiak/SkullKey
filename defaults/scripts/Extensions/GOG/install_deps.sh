#!/usr/bin/env bash
# GOG extension dependencies: gogdl (the GOG download client used by Heroic),
# installed in a dedicated venv built with the Homebrew python (the system
# python on Bazzite/SteamOS images has no headers to compile gogdl's C ext).
VENV="${HOME}/.local/share/skeletonkey-gogdl"
BREW_PY="/home/linuxbrew/.linuxbrew/bin/python3"
GOGDL_SRC="git+https://github.com/Heroic-Games-Launcher/heroic-gogdl"

function uninstall() {
    echo "Removing gogdl venv"
    rm -rf "${VENV}"
}

function install() {
    if [ ! -x "${BREW_PY}" ]; then
        echo "Homebrew python not found, installing via brew..."
        if [ -x /home/linuxbrew/.linuxbrew/bin/brew ]; then
            /home/linuxbrew/.linuxbrew/bin/brew install python
        else
            echo "ERROR: Homebrew not available, cannot install gogdl"
            return 1
        fi
    fi
    if [ ! -x "${VENV}/bin/pip" ]; then
        "${BREW_PY}" -m venv "${VENV}"
    fi
    CC=gcc "${VENV}/bin/pip" install --upgrade "${GOGDL_SRC}"
    "${VENV}/bin/gogdl" --version && echo "gogdl installed OK"
}

if [ "$1" == "uninstall" ]; then
    echo "Uninstalling dependencies: GOG extension"
    uninstall
else
    echo "Installing dependencies: GOG extension"
    install
fi
