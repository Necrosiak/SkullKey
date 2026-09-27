#!/usr/bin/env bash
# Steam shortcut launcher for Battle.net. Invoked as launch options:
#   "<this script> client %command%"        show the client (or its installer)
#   "<this script> client:<CODE> %command%" same, opened on a game's page
#   "<this script> game:<CODE> %command%"   play an installed game
# %command% is Steam's Proton command line ending with Battle.net Launcher.exe
# (or Battle.net-Setup.exe on first use). Every Battle.net game shares ONE
# prefix, where the client lives, so the Proton prefix Steam picked for the
# shortcut is replaced by ours.

# Exported because this does not run in the plugin's context.
export DECKY_PLUGIN_RUNTIME_DIR="${HOME}/homebrew/data/SkullKey"
export DECKY_PLUGIN_DIR="${HOME}/homebrew/plugins/SkullKey"
export DECKY_PLUGIN_LOG_DIR="${HOME}/homebrew/logs/SkullKey"

BNET_PY="${DECKY_PLUGIN_DIR}/scripts/Extensions/BattleNet/battlenet.py"
MODE=$1
shift

PREFIX=$(python3 "${BNET_PY}" prefix-dir)
mkdir -p "${PREFIX}"
export STEAM_COMPAT_DATA_PATH="${PREFIX}"
# Without it the client's sign-in window ignores all input under Wine.
export WINE_SIMULATE_WRITECOPY=1
# Proton's Xalia (gamepad UI helper) crashes the client right after sign-in.
# The switch is PROTON_USE_XALIA=0: PROTON_DISABLE_XALIA does not exist.
export PROTON_USE_XALIA=0

LOG="${DECKY_PLUGIN_LOG_DIR}/battlenet.log"
mkdir -p "${DECKY_PLUGIN_LOG_DIR}"
echo "$(date '+%F %T') ${MODE}: $*" >> "${LOG}"

# wineserver of the Proton Steam is running us with, to stop the client.
stop_client() {
    local tool
    IFS=: read -r tool _ <<< "${STEAM_COMPAT_TOOL_PATHS}"
    if [[ -x "${tool}/files/bin/wineserver" ]]; then
        WINEPREFIX="${PREFIX}/pfx" "${tool}/files/bin/wineserver" -k 2>> "${LOG}"
    fi
}

case "${MODE}" in
    client)
        "$@" >> "${LOG}" 2>&1
        ;;
    client:*)
        CODE="${MODE#client:}"
        if [[ "$*" == *"Battle.net-Setup.exe"* ]]; then
            "$@" >> "${LOG}" 2>&1
        else
            "$@" "--exec=launch ${CODE}" >> "${LOG}" 2>&1
        fi
        ;;
    game:*)
        CODE="${MODE#game:}"
        # A client already running (e.g. the Battle.net shortcut) belongs to
        # another Steam app: the game would open under it. Start fresh.
        if python3 "${BNET_PY}" client-running; then
            echo "stopping the running client first" >> "${LOG}"
            stop_client
            sleep 2
        fi
        # Start the client hidden: with --autostarted (what Windows passes at
        # session start) and AutoStartMinimized it goes straight to the tray.
        # A client started with --exec=launch only opens the game's page; the
        # same verb sent to a client that is signed in and ready starts the
        # game itself. So keep sending it until the game shows up. A client
        # that has an update to apply first (auto-updates are on by default)
        # launches the game once it is done: wait up to an hour for it.
        python3 "${BNET_PY}" hide-client
        "$@" --autostarted >> "${LOG}" 2>&1 &
        RUNNER=$!
        STARTED=0
        for i in $(seq 1 1800); do
            kill -0 "${RUNNER}" 2>/dev/null || break
            if python3 "${BNET_PY}" game-running "${CODE}"; then
                STARTED=1
                break
            fi
            if (( i % 5 == 0 )); then
                python3 "${BNET_PY}" send-launch "${CODE}"
            fi
            sleep 2
        done
        if [[ "${STARTED}" == 1 ]]; then
            echo "game ${CODE} started" >> "${LOG}"
            while python3 "${BNET_PY}" game-running "${CODE}"; do
                sleep 3
            done
            echo "game ${CODE} exited, closing the client" >> "${LOG}"
            stop_client
        else
            echo "game ${CODE} never started, leaving the client open" >> "${LOG}"
        fi
        wait "${RUNNER}"
        ;;
    *)
        "$@" >> "${LOG}" 2>&1
        ;;
esac
