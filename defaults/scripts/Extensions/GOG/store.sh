#!/usr/bin/env bash

# Register GOG as a platform with the skullkey.sh script
PLATFORMS+=("GOG")

# only source the settings if the platform is GOG - avoids conflicts with other plugins
if [[ "${PLATFORM}" == "GOG" ]]; then
    source "${DECKY_PLUGIN_DIR}/scripts/${Extensions}/GOG/settings.sh"
fi

function GOG_init() {
    $GOGCONF --list --dbfile $DBFILE $OFFLINE_MODE &> /dev/null
}

function GOG_refresh() {
    TEMP=$(GOG_init)
    echo "{\"Type\": \"RefreshContent\", \"Content\": {\"Message\": \"Refreshed\"}}"
}

function GOG_getgames(){
    if [ -z "${1}" ]; then
        FILTER=""
    else
        FILTER="${1}"
    fi
    if [ -z "${2}" ]; then
        INSTALLED="false"
    else
        INSTALLED="${2}"
    fi
    if [ -z "${3}" ]; then
        LIMIT="false"
    else
        LIMIT="${3}"
    fi
    IMAGE_PATH=""
    TEMP=$($GOGCONF --getgameswithimages "${IMAGE_PATH}" "${FILTER}" "${INSTALLED}" "${LIMIT}" "true" --dbfile $DBFILE)
    echo $TEMP >> $DECKY_PLUGIN_LOG_DIR/debug.log
    if echo "$TEMP" | jq -e '.Content.Games | length == 0' &>/dev/null; then
        if [[ $FILTER == "" ]] && [[ $INSTALLED == "false" ]]; then
            TEMP=$(GOG_init)
            TEMP=$($GOGCONF --getgameswithimages "${IMAGE_PATH}" "${FILTER}" "${INSTALLED}" "${LIMIT}" "true" --dbfile $DBFILE)
        fi
    fi
    echo $TEMP
}

function GOG_saveplatformconfig(){
    cat | $GOGCONF --parsejson "${1}" --dbfile $DBFILE --platform Proton --fork "" --version "" --dbfile $DBFILE
}
function GOG_getplatformconfig(){
    TEMP=$($GOGCONF --confjson "${1}" --platform Proton --fork "" --version "" --dbfile $DBFILE)
    echo $TEMP
}

function GOG_download(){
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    GAME_DIR=$($GOGCONF --get-game-dir "${1}" --dbfile $DBFILE)
    # gogdl always creates its own <folder_name> subdir inside --path. GAME_DIR
    # already ends in that folder name, so pass the parent to avoid a doubly
    # nested "<folder>/<folder>/" install that get_primary_task can't find.
    DEST_DIR=$(dirname "${GAME_DIR}")
    mkdir -p "${DEST_DIR}"
    (
        updategamedetailsaftergogcmd $1 $GOGDL download $1 --platform windows --path "${DEST_DIR}" --skip-dlcs --lang "${GOG_LANGUAGE}" > "${DECKY_PLUGIN_LOG_DIR}/${1}.output" 2> $PROGRESS_LOG
        echo "===GOGDL_EXIT:$?===" >> $PROGRESS_LOG
    # Detach the backgrounded subshell's stdio from the caller's pipe. Otherwise
    # it keeps the script's stdout open, the plugin's script runner blocks
    # reading until the whole download finishes, and the "Downloading" reply that
    # starts the frontend progress bar only comes back once it's already done.
    ) </dev/null >/dev/null 2>&1 &
    echo $! > "${DECKY_PLUGIN_LOG_DIR}/${1}.pid"
    echo "{\"Type\": \"Progress\", \"Content\": {\"Message\": \"Downloading\"}}"
}

function GOG_update(){
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    GAME_DIR=$($GOGCONF --get-game-dir "${1}" --dbfile $DBFILE)
    DEST_DIR=$(dirname "${GAME_DIR}")
    (
        updategamedetailsaftergogcmd $1 $GOGDL update $1 --platform windows --path "${DEST_DIR}" --skip-dlcs --lang "${GOG_LANGUAGE}" >> "${DECKY_PLUGIN_LOG_DIR}/${1}.log" 2> $PROGRESS_LOG
        echo "===GOGDL_EXIT:$?===" >> $PROGRESS_LOG
    # Detach the backgrounded subshell's stdio from the caller's pipe. Otherwise
    # it keeps the script's stdout open, the plugin's script runner blocks
    # reading until the whole download finishes, and the "Downloading" reply that
    # starts the frontend progress bar only comes back once it's already done.
    ) </dev/null >/dev/null 2>&1 &
    echo $! > "${DECKY_PLUGIN_LOG_DIR}/${1}.pid"
    echo "{\"Type\": \"Progress\", \"Content\": {\"Message\": \"Updating\"}}"
}

function GOG_verify(){
    GOG_repair "${@}"
}

function GOG_repair(){
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    GAME_DIR=$($GOGCONF --get-game-dir "${1}" --dbfile $DBFILE)
    DEST_DIR=$(dirname "${GAME_DIR}")
    (
        updategamedetailsaftergogcmd $1 $GOGDL repair $1 --platform windows --path "${DEST_DIR}" --skip-dlcs --lang "${GOG_LANGUAGE}" >> "${DECKY_PLUGIN_LOG_DIR}/${1}.log" 2> $PROGRESS_LOG
        echo "===GOGDL_EXIT:$?===" >> $PROGRESS_LOG
    # Detach the backgrounded subshell's stdio from the caller's pipe. Otherwise
    # it keeps the script's stdout open, the plugin's script runner blocks
    # reading until the whole download finishes, and the "Downloading" reply that
    # starts the frontend progress bar only comes back once it's already done.
    ) </dev/null >/dev/null 2>&1 &
    echo $! > "${DECKY_PLUGIN_LOG_DIR}/${1}.pid"
    echo "{\"Type\": \"Progress\", \"Content\": {\"Message\": \"Updating\"}}"
}

function GOG_repair_and_update(){
    GOG_repair "${@}"
}

function GOG_cancelinstall(){
    PID=$(cat "${DECKY_PLUGIN_LOG_DIR}/${1}.pid")
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    pkill -TERM -P "${PID}" 2>/dev/null
    kill -TERM "${PID}" 2>/dev/null
    pkill -f "gogdl.*download ${1}" 2>/dev/null
    rm -f "${DECKY_PLUGIN_LOG_DIR}/${1}.pid"
    echo "{\"Type\": \"Success\", \"Content\": {\"Message\": \"${1} installation Cancelled\"}}"
}

function GOG_install(){
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    rm $PROGRESS_LOG &>> ${DECKY_PLUGIN_LOG_DIR}/${1}.log
    RESULT=$($GOGCONF --addsteamclientid "${1}" "${2}" --dbfile $DBFILE)
    TEMP=$($GOGCONF --update-umu-id "${1}" gog --dbfile $DBFILE)
    mkdir -p "${INSTALL_DIR}"
    TEMP=$($GOGCONF --launchoptions "${1}" "" "" --dbfile $DBFILE $OFFLINE_MODE)
    echo $TEMP
    exit 0
}

function GOG_getlaunchoptions(){
    TEMP=$($GOGCONF --launchoptions "${1}" "" "" --dbfile $DBFILE $OFFLINE_MODE)
    echo $TEMP
    exit 0
}

function GOG_uninstall(){
    GAME_DIR=$($GOGCONF --get-game-dir "${1}" --dbfile $DBFILE)
    # safety: only delete a directory that really is this game's install
    if [[ -n "${GAME_DIR}" && -f "${GAME_DIR}/goggame-${1}.info" ]]; then
        rm -rf "${GAME_DIR}"
    fi
    TEMP=$($GOGCONF --clear-install-info "${1}" --dbfile $DBFILE)
    echo $TEMP
}

function GOG_getgamedetails(){
    IMAGE_PATH=""
    TEMP=$($GOGCONF --getgamedata "${1}" "${IMAGE_PATH}" --dbfile $DBFILE --forkname "Proton" --version "null" --platform "Windows")
    echo $TEMP
    exit 0
}

function GOG_getgamesize(){
    TEMP=$($GOGCONF --get-game-size "${1}" "${2}" --dbfile $DBFILE)
    echo $TEMP
}

function GOG_getprogress(){
    TEMP=$($GOGCONF --getprogress "${DECKY_PLUGIN_LOG_DIR}/${1}.progress" --dbfile $DBFILE)
    echo $TEMP
}

function GOG_loginstatus(){
    if [[ -z $1 ]]; then
        FLUSH_CACHE=""
    else
        FLUSH_CACHE="--flush-cache"
    fi
    TEMP=$($GOGCONF --getloginstatus --dbfile $DBFILE $OFFLINE_MODE $FLUSH_CACHE)
    echo $TEMP
}

function GOG_protontricks(){
    get_steam_env
    unset STEAM_RUNTIME_LIBRARY_PATH
    export PROTONTRICKS_GUI=yad
    ARGS="--verbose $2 --gui &> \\\"${DECKY_PLUGIN_LOG_DIR}/${1}.log\\\""
    launchoptions "${PROTON_TRICKS}"  "${ARGS}" "${3}" "Protontricks" false ""
}

function GOG_run-exe(){
    get_steam_env
    STEAM_ID="${1}"
    GAME_SHORTNAME="${2}"
    GAME_EXE="${3}"
    ARGS="${4}"
    if [[ $4 == true ]]; then
        ARGS="some value"
    else
        ARGS=""
    fi
    COMPAT_TOOL="${5}"
    GAME_PATH=$($GOGCONF --get-game-dir $GAME_SHORTNAME --dbfile $DBFILE)
    launchoptions "\\\"${GAME_PATH}/${GAME_EXE}\\\""  "${ARGS}  &> ${DECKY_PLUGIN_LOG_DIR}/run-exe.log" "${GAME_PATH}" "Run exe" true "${COMPAT_TOOL}"
}

function GOG_get-exe-list(){
    get_steam_env
    STEAM_ID="${1}"
    GAME_SHORTNAME="${2}"
    GAME_PATH=$($GOGCONF --get-game-dir $GAME_SHORTNAME --dbfile $DBFILE)
    export STEAM_COMPAT_DATA_PATH="${HOME}/.local/share/Steam/steamapps/compatdata/${STEAM_ID}"
    export STEAM_COMPAT_CLIENT_INSTALL_PATH="${GAME_PATH}"
    cd "${STEAM_COMPAT_CLIENT_INSTALL_PATH}"
    JSON="{\"Type\": \"FileContent\", \"Content\": {\"PathRoot\": \"${GAME_PATH}\", \"Files\": ["
    SEP=""
    while IFS= read -r -d '' FILE; do
        JSON="${JSON}${SEP}{\"Path\": \"${FILE}\"}"
        SEP=","
    done < <(find . \( -name "*.exe" -o -iname "*.bat" -o -iname "*.msi" \) -print0)
    JSON="${JSON}]}}"
    echo "$JSON"
}

function GOG_login(){
    get_steam_env
    launchoptions "${DECKY_PLUGIN_DIR}/scripts/Extensions/GOG/login.sh" "" "${DECKY_PLUGIN_LOG_DIR}" "GOG Login"
}

function loginlaunchoptions () {
    Exe=$1
    Options=$2
    WorkingDir=$3
    Name=$4
    Compatibility=$5
    CompatTooName=$6
    JSON="{\"Type\": \"LaunchOptions\", \"Content\": {
        \"Exe\": \"${Exe}\",
        \"Options\": \"${Options}\",
        \"WorkingDir\": \"${WorkingDir}\",
        \"Name\": \"${Name}\",
        \"Compatibility\": \"${Compatibility}\",
        \"CompatToolName\": \"${CompatTooName}\"
    }}"
    echo $JSON
}

function GOG_login-launch-options(){
    get_steam_env
    loginlaunchoptions "${DECKY_PLUGIN_DIR}/scripts/Extensions/GOG/login.sh" "" "${DECKY_PLUGIN_LOG_DIR}" "GOG Login"
}

function GOG_logout(){
    rm -f "${GOG_AUTH_FILE}"
    GOG_loginstatus --flush-cache
}

function GOG_getsetting(){
    TEMP=$($GOGCONF --getsetting $1 --dbfile $DBFILE)
    echo $TEMP
}
function GOG_savesetting(){
    $GOGCONF --savesetting $1 $2 --dbfile $DBFILE
}
function GOG_getjsonimages(){
    TEMP=$($GOGCONF --get-base64-images "${1}" --dbfile $DBFILE --offline)
    echo $TEMP
}
function GOG_update-umu-id(){
    TEMP=$($GOGCONF --update-umu-id "${1}" gog --dbfile $DBFILE)
    echo "{\"Type\": \"Success\", \"Content\": {\"Message\": \"Umu Id updated\"}}"
}

function GOG_gettabconfig(){
    if [[ ! -d "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas" ]]; then
        mkdir -p "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas"
    fi
    if [[ -f "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/gogtabconfig.json" ]]; then
        TEMP=$(cat "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/gogtabconfig.json")
    else
        TEMP=$(cat "${DECKY_PLUGIN_DIR}/conf_schemas/gogtabconfig.json")
    fi
    echo "{\"Type\":\"IniContent\", \"Content\": ${TEMP}}"
}
function GOG_savetabconfig(){
    cat > "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/gogtabconfig.json"
    echo "{\"Type\": \"Success\", \"Content\": {\"Message\": \"GOG tab config saved\"}}"
}

function updategamedetailsaftergogcmd() {
    game=$1
    shift
    "$@"
    local rc=$?
    $GOGCONF --update-game-details $game --dbfile $DBFILE &> /dev/null
    return $rc
}
