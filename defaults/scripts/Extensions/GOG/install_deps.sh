#!/usr/bin/env bash
# GOG extension dependency: the official gogdl standalone zipapp published by
# Heroic.  Building gogdl from source is not reliable on rolling distributions:
# its xdelta3 extension currently fails to compile with Python 3.14 (CachyOS).
# The upstream zipapp contains the same code and stable-ABI extension, avoiding
# compiler, Python headers and virtualenv compatibility entirely.
VENV="${HOME}/.local/share/skullkey-gogdl"
GOGDL_VERSION="1.3.0"

function uninstall() {
    echo "Removing gogdl venv"
    rm -rf "${VENV}"
}

function install() {
    local arch asset checksum url tmp actual
    arch="$(uname -m)"
    case "${arch}" in
        x86_64|amd64)
            asset="gogdl_linux_x86_64"
            checksum="cba013d42767c808237c437335ab1d56f58405d07e8f37b3324d264ea5c49655"
            ;;
        aarch64|arm64)
            asset="gogdl_linux_arm64"
            checksum="c49e1519146523ec94f33e2d21eedcc9a167004d7da218621e6d5fb84a7a0f4c"
            ;;
        *)
            echo "ERROR: unsupported architecture for gogdl: ${arch}"
            return 1
            ;;
    esac

    url="https://github.com/Heroic-Games-Launcher/heroic-gogdl/releases/download/v${GOGDL_VERSION}/${asset}"
    mkdir -p "${VENV}/bin"
    tmp="${VENV}/bin/gogdl.download"
    if command -v curl >/dev/null 2>&1; then
        curl --fail --location --silent --show-error "${url}" --output "${tmp}" || return 1
    elif command -v wget >/dev/null 2>&1; then
        wget -q "${url}" -O "${tmp}" || return 1
    else
        echo "ERROR: curl or wget is required to download gogdl"
        return 1
    fi

    actual="$(sha256sum "${tmp}" | awk '{print $1}')"
    if [[ "${actual}" != "${checksum}" ]]; then
        echo "ERROR: gogdl checksum mismatch (expected ${checksum}, got ${actual})"
        rm -f "${tmp}"
        return 1
    fi
    chmod +x "${tmp}"
    if ! "${tmp}" --version; then
        echo "ERROR: downloaded gogdl executable did not start"
        rm -f "${tmp}"
        return 1
    fi
    mv -f "${tmp}" "${VENV}/bin/gogdl"
    echo "gogdl ${GOGDL_VERSION} installed OK (official ${asset})"
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
