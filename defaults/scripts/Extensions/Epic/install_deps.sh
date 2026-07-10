#!/usr/bin/env bash
# Epic extension dependencies: legendary (the Epic Games client used by Heroic).
# Stand-alone : legendary est installé dans un venv pip dédié (comme GOG/Amazon)
# → AUCUNE dépendance flatpak obligatoire (CachyOS/Arch/Fedora/Debian OK).
# Un flatpak legendary DÉJÀ installé (installs historiques Bazzite) est gardé
# tel quel et reste prioritaire (cf settings.sh) ; les deux backends partagent
# la même config via le symlink multi-comptes.
VENV="${HOME}/.local/share/skullkey-legendary"
LEGACY_FLATPAK="com.github.derrod.legendary"

# Auto-détection du python pour builder le venv, SELON L'OS (cf GOG/Amazon) :
# Homebrew sur Bazzite/SteamOS (python système sans headers), sinon python
# système sur Arch/CachyOS/Fedora/Debian.
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
    echo "ERROR: no usable python3 to build the legendary venv — run: ${HINT}"
    return 1
}

flatpak_legendary_present() {
    command -v flatpak >/dev/null 2>&1 && flatpak info "${LEGACY_FLATPAK}" &>/dev/null
}

function uninstall() {
    if command -v flatpak >/dev/null 2>&1; then
        echo "Uninstalling flatpaks"
        if flatpak list | grep -q "${LEGACY_FLATPAK}"; then
            echo "legendary flatpak is installed, removing"
            flatpak --user uninstall "${LEGACY_FLATPAK}" -y
        fi
        if flatpak list | grep -q "com.github.Matoking.protontricks"; then
            echo "protontricks flatpak is installed, removing"
            flatpak --user uninstall com.github.Matoking.protontricks -y
        fi
        echo "Removing unused flatpaks"
        flatpak --user uninstall --unused -y
    fi
    echo "Removing legendary venv"
    rm -rf "${VENV}"
}

function install() {
    if flatpak_legendary_present; then
        echo "legendary flatpak déjà installé → gardé (prioritaire), pas de venv"
    else
        pick_python || return 1
        if [ ! -x "${VENV}/bin/pip" ]; then
            "${PY}" -m venv "${VENV}"
        fi
        "${VENV}/bin/pip" install --upgrade legendary-gl
        "${VENV}/bin/legendary" --version && echo "legendary installed OK"
    fi
    # protontricks (optionnel, utilisé par le bouton Protontricks) : natif si
    # présent, sinon flatpak si flatpak dispo, sinon simple note.
    if command -v protontricks >/dev/null 2>&1; then
        echo "protontricks natif présent ✓"
    elif command -v flatpak >/dev/null 2>&1; then
        if ! flatpak info com.github.Matoking.protontricks &>/dev/null; then
            flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
            flatpak --user install flathub com.github.Matoking.protontricks -y
        fi
    else
        echo "NOTE: protontricks absent (optionnel) — installe-le via ton gestionnaire de paquets (ex: pacman -S protontricks)"
    fi
}

function check() {
    # Cheap, offline presence check used by the boot-time auto-provision.
    # Exit 0 = deps present, non-zero = missing (triggers install).
    [ -x "${VENV}/bin/legendary" ] && return 0
    flatpak_legendary_present
}

if [ "$1" == "uninstall" ]; then
    echo "Uninstalling dependencies: Epic extension"
    uninstall
elif [ "$1" == "check" ]; then
    check
else
    echo "Installing dependencies: Epic extension"
    install
fi
