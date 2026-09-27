#!/usr/bin/env bash
# Steam shortcut launcher for Ubisoft Connect. Invoked as launch options:
#   "<this script> setup %command%"        first use: silent client install,
#                                          then its sign-in window
#   "<this script> client %command%"       show the client
#   "<this script> install:<ID> %command%" open the client's install dialog
#   "<this script> game:<ID> %command%"    play an installed game
# %command% is Steam's Proton command line ending with UbisoftConnect.exe (or
# the installer on first use). Every Ubisoft game shares ONE prefix, where the
# client lives, so the Proton prefix Steam picked for the shortcut is replaced
# by ours.

# Exported because this does not run in the plugin's context.
export DECKY_PLUGIN_RUNTIME_DIR="${HOME}/homebrew/data/SkullKey"
export DECKY_PLUGIN_DIR="${HOME}/homebrew/plugins/SkullKey"
export DECKY_PLUGIN_LOG_DIR="${HOME}/homebrew/logs/SkullKey"

UBI_PY="${DECKY_PLUGIN_DIR}/scripts/Extensions/Ubisoft/ubisoft.py"
MODE=$1
shift

PREFIX=$(python3 "${UBI_PY}" prefix-dir)
# Proton refuses a compat data path that does not exist yet.
mkdir -p "${PREFIX}"
export STEAM_COMPAT_DATA_PATH="${PREFIX}"

LOG="${DECKY_PLUGIN_LOG_DIR}/ubisoft.log"
mkdir -p "${DECKY_PLUGIN_LOG_DIR}"
echo "$(date '+%F %T') ${MODE}: $*" >> "${LOG}"

# The client stays open after a game exits (and pops its full window with
# ads): close everything in the prefix so Steam gets control back.
stop_client() {
    local tool
    IFS=: read -r tool _ <<< "${STEAM_COMPAT_TOOL_PATHS}"
    if [[ -x "${tool}/files/bin/wineserver" ]]; then
        WINEPREFIX="${PREFIX}/pfx" "${tool}/files/bin/wineserver" -k 2>> "${LOG}"
    fi
}

case "${MODE}" in
    setup)
        # Silent install (NSIS /S), then the same Proton command pointed at
        # the freshly installed client to show its sign-in window.
        "$@" /S >> "${LOG}" 2>&1
        UPC=$(python3 "${UBI_PY}" upc-exe)
        if [[ -f "${UPC}" ]]; then
            ARGS=("$@")
            ARGS[-1]="${UPC}"
            "${ARGS[@]}" >> "${LOG}" 2>&1
        else
            echo "client install failed" >> "${LOG}"
        fi
        ;;
    client)
        python3 "${UBI_PY}" stop-client
        "$@" >> "${LOG}" 2>&1
        ;;
    install:*)
        python3 "${UBI_PY}" stop-client
        "$@" "uplay://install/${MODE#install:}" >> "${LOG}" 2>&1
        ;;
    game:*)
        ID="${MODE#game:}"
        # The client only honours the launch URI when Steam starts it with
        # it: a client still running (install window, previous game) must go.
        # stop-client also turns UPC's overlay off: while it is on, the
        # gamepad drives the overlay and never reaches the game.
        python3 "${UBI_PY}" stop-client
        "$@" "uplay://launch/${ID}/0" >> "${LOG}" 2>&1 &
        RUNNER=$!
        # Wait for the game (the client may update it first: up to an hour),
        # then for it to exit, then close the client.
        STARTED=0
        for _ in $(seq 1 1800); do
            kill -0 "${RUNNER}" 2>/dev/null || break
            if python3 "${UBI_PY}" game-running "${ID}"; then
                STARTED=1
                break
            fi
            sleep 2
        done
        if [[ "${STARTED}" == 1 ]]; then
            echo "game ${ID} started" >> "${LOG}"
            while python3 "${UBI_PY}" game-running "${ID}"; do
                # UPC can restart itself mid-game (its browser crashes) and
                # open its full window over the game: send it back down.
                python3 "${UBI_PY}" hide-client-window
                sleep 3
            done
            echo "game ${ID} exited, closing the client" >> "${LOG}"
            stop_client
        else
            echo "game ${ID} never started, leaving the client open" >> "${LOG}"
        fi
        wait "${RUNNER}"
        ;;
    *)
        "$@" >> "${LOG}" 2>&1
        ;;
esac
