#!/usr/bin/env bash
# Amazon extension dependencies: nile (the Amazon Games client used by Heroic),
# installed in a dedicated venv built with the Homebrew python.
# nile's pyproject lacks a packages config (fails with modern setuptools), so
# we clone, patch and install from the local copy.
VENV="${HOME}/.local/share/skullkey-nile"
NILE_REPO="https://github.com/imLinguin/nile"

# Auto-détection du python pour builder le venv, SELON L'OS (cf GOG) :
# Homebrew sur Bazzite/SteamOS (python système sans headers), sinon python
# système sur Arch/CachyOS/Fedora/Debian (headers dispo).
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
    echo "ERROR: aucun python3 utilisable (headers de dev ou Homebrew requis) pour builder nile"
    return 1
}

function uninstall() {
    echo "Removing nile venv"
    rm -rf "${VENV}"
}

function install() {
    # nile est installé depuis un clone local (pyproject à patcher) → git requis.
    if ! command -v git >/dev/null 2>&1; then
        echo "ERROR: git manquant (requis pour installer nile) — installe-le via ton gestionnaire de paquets (ex: pacman -S git)"
        return 1
    fi
    pick_python || return 1
    if [ ! -x "${VENV}/bin/pip" ]; then
        "${PY}" -m venv "${VENV}"
    fi
    "${VENV}/bin/pip" install --upgrade setuptools wheel requests protobuf pycryptodome zstandard json5 platformdirs
    TMP_SRC=$(mktemp -d)
    git clone --depth 1 "${NILE_REPO}" "${TMP_SRC}/nile"
    grep -q "tool.setuptools.packages" "${TMP_SRC}/nile/pyproject.toml" || \
        printf '\n[tool.setuptools.packages.find]\ninclude = ["nile*"]\n' >> "${TMP_SRC}/nile/pyproject.toml"
    CC=gcc "${VENV}/bin/pip" install --upgrade --no-build-isolation "${TMP_SRC}/nile"
    rm -rf "${TMP_SRC}"
    "${VENV}/bin/nile" --version && echo "nile installed OK"
}

function check() {
    # Cheap, offline presence check used by the boot-time auto-provision.
    # Exit 0 = deps present, non-zero = missing (triggers install).
    [ -x "${VENV}/bin/nile" ]
}

if [ "$1" == "uninstall" ]; then
    echo "Uninstalling dependencies: Amazon extension"
    uninstall
elif [ "$1" == "check" ]; then
    check
else
    echo "Installing dependencies: Amazon extension"
    install
fi
