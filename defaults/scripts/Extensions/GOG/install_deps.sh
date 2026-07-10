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
    # Debian/Ubuntu : `import venv` passe mais la CRÉATION échoue (ensurepip
    # strippé du paquet de base, il faut python3-venv) → tester ensurepip.
    if command -v python3 >/dev/null 2>&1 && python3 -c "import ensurepip" 2>/dev/null; then
        PY="$(command -v python3)"; return 0
    fi
    if [ -x /home/linuxbrew/.linuxbrew/bin/brew ]; then
        /home/linuxbrew/.linuxbrew/bin/brew install python && PY="${brew_py}" && return 0
    fi
    local HINT="install python3 (with venv/ensurepip)"
    if command -v pacman >/dev/null 2>&1; then HINT="sudo pacman -S python"
    elif command -v rpm-ostree >/dev/null 2>&1; then HINT="rpm-ostree install python3"
    elif command -v dnf >/dev/null 2>&1; then HINT="sudo dnf install python3"
    elif command -v zypper >/dev/null 2>&1; then HINT="sudo zypper install python3"
    elif command -v apt >/dev/null 2>&1; then HINT="sudo apt install python3 python3-venv"
    fi
    echo "ERROR: no usable python3 to build the gogdl venv — run: ${HINT}"
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
