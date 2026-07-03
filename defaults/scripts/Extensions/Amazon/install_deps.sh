#!/usr/bin/env bash
# Amazon extension dependencies: nile (the Amazon Games client used by Heroic),
# installed in a dedicated venv built with the Homebrew python.
# nile's pyproject lacks a packages config (fails with modern setuptools), so
# we clone, patch and install from the local copy.
VENV="${HOME}/.local/share/skeletonkey-nile"
BREW_PY="/home/linuxbrew/.linuxbrew/bin/python3"
NILE_REPO="https://github.com/imLinguin/nile"

function uninstall() {
    echo "Removing nile venv"
    rm -rf "${VENV}"
}

function install() {
    if [ ! -x "${BREW_PY}" ]; then
        echo "Homebrew python not found, installing via brew..."
        if [ -x /home/linuxbrew/.linuxbrew/bin/brew ]; then
            /home/linuxbrew/.linuxbrew/bin/brew install python
        else
            echo "ERROR: Homebrew not available, cannot install nile"
            return 1
        fi
    fi
    if [ ! -x "${VENV}/bin/pip" ]; then
        "${BREW_PY}" -m venv "${VENV}"
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

if [ "$1" == "uninstall" ]; then
    echo "Uninstalling dependencies: Amazon extension"
    uninstall
else
    echo "Installing dependencies: Amazon extension"
    install
fi
