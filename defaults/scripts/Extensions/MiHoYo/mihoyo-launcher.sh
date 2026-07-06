#!/usr/bin/env bash
# Steam shortcut launcher for miHoYo games installed by SkullKey.
# Invoked as launch options: "<this script> <biz>%command%" (same glued shape
# as the GOG/Epic/Amazon launchers, proven in prod). Runs the game through
# Steam's Proton (the shortcut has Compatibility=true).

# Exported because this does not run in the plugin's context.
export DECKY_PLUGIN_RUNTIME_DIR="${HOME}/homebrew/data/SkullKey"
export DECKY_PLUGIN_DIR="${HOME}/homebrew/plugins/SkullKey"
export DECKY_PLUGIN_LOG_DIR="${HOME}/homebrew/logs/SkullKey"

ID=$1
shift

GAME_PATH=$(python3 "${DECKY_PLUGIN_DIR}/scripts/Extensions/MiHoYo/mihoyo.py" game-dir "$ID")
export STEAM_COMPAT_INSTALL_PATH="${GAME_PATH}"
export PROTON_SET_GAME_DRIVE="gamedrive"

QUOTED_ARGS=""
for arg in "$@"; do
    QUOTED_ARGS+=" \"${arg}\""
done

# HI3/HSR anti-cheat: when jadeite is available for this game, rewrite the
# command so Proton runs `jadeite.exe "<game.exe>" --` instead of the game
# directly (otherwise: "Anti-cheat system works error" popup).
JADEITE=$(python3 "${DECKY_PLUGIN_DIR}/scripts/Extensions/MiHoYo/mihoyo.py" jadeite-path "$ID")
GAME_EXE=$(python3 "${DECKY_PLUGIN_DIR}/scripts/Extensions/MiHoYo/mihoyo.py" game-exe "$ID")
if [[ -n "${JADEITE}" && -n "${GAME_EXE}" ]]; then
    QUOTED_ARGS="${QUOTED_ARGS/\"${GAME_EXE}\"/\"${JADEITE}\" \"${GAME_EXE}\" --}"
fi

mkdir -p "${DECKY_PLUGIN_LOG_DIR}"
echo "game path: ${GAME_PATH}" >> "${DECKY_PLUGIN_LOG_DIR}/${ID}.log"
echo -e "Running: ${QUOTED_ARGS}" >> "${DECKY_PLUGIN_LOG_DIR}/${ID}.log"

eval "$(echo -e "$QUOTED_ARGS")" &>> "${DECKY_PLUGIN_LOG_DIR}/${ID}.log"
