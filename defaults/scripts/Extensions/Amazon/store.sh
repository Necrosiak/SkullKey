#!/usr/bin/env bash

# Register Amazon as a platform with the skeletonkey.sh script
PLATFORMS+=("Amazon")

# only source the settings if the platform is Amazon - avoids conflicts with other plugins
if [[ "${PLATFORM}" == "Amazon" ]]; then
    source "${DECKY_PLUGIN_DIR}/scripts/${Extensions}/Amazon/settings.sh"
fi

function Amazon_init() {
    $AMAZONCONF --list --dbfile $DBFILE $OFFLINE_MODE &> /dev/null
}

function Amazon_refresh() {
    TEMP=$(Amazon_init)
    echo "{\"Type\": \"RefreshContent\", \"Content\": {\"Message\": \"Refreshed\"}}"
}

function Amazon_getgames(){
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
    TEMP=$($AMAZONCONF --getgameswithimages "${IMAGE_PATH}" "${FILTER}" "${INSTALLED}" "${LIMIT}" "true" --dbfile $DBFILE)
    echo $TEMP >> $DECKY_PLUGIN_LOG_DIR/debug.log
    if echo "$TEMP" | jq -e '.Content.Games | length == 0' &>/dev/null; then
        if [[ $FILTER == "" ]] && [[ $INSTALLED == "false" ]]; then
            TEMP=$(Amazon_init)
            TEMP=$($AMAZONCONF --getgameswithimages "${IMAGE_PATH}" "${FILTER}" "${INSTALLED}" "${LIMIT}" "true" --dbfile $DBFILE)
        fi
    fi
    echo $TEMP
}

function Amazon_saveplatformconfig(){
    cat | $AMAZONCONF --parsejson "${1}" --dbfile $DBFILE --platform Proton --fork "" --version "" --dbfile $DBFILE
}
function Amazon_getplatformconfig(){
    TEMP=$($AMAZONCONF --confjson "${1}" --platform Proton --fork "" --version "" --dbfile $DBFILE)
    echo $TEMP
}

function Amazon_download(){
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    mkdir -p "${INSTALL_DIR}"
    (
        updategamedetailsafteramazoncmd $1 $NILE install $1 --base-path "${INSTALL_DIR}" > "${DECKY_PLUGIN_LOG_DIR}/${1}.output" 2> $PROGRESS_LOG
        echo "===NILE_EXIT:$?===" >> $PROGRESS_LOG
    # Detach the backgrounded subshell's stdio from the caller's pipe. Otherwise
    # it keeps the script's stdout open, the plugin's script runner blocks
    # reading until the whole download finishes, and the "Downloading" reply that
    # starts the frontend progress bar only comes back once it's already done.
    ) </dev/null >/dev/null 2>&1 &
    echo $! > "${DECKY_PLUGIN_LOG_DIR}/${1}.pid"
    echo "{\"Type\": \"Progress\", \"Content\": {\"Message\": \"Downloading\"}}"
}

function Amazon_update(){
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    (
        updategamedetailsafteramazoncmd $1 $NILE update $1 >> "${DECKY_PLUGIN_LOG_DIR}/${1}.log" 2> $PROGRESS_LOG
        echo "===NILE_EXIT:$?===" >> $PROGRESS_LOG
    # Detach the backgrounded subshell's stdio from the caller's pipe. Otherwise
    # it keeps the script's stdout open, the plugin's script runner blocks
    # reading until the whole download finishes, and the "Downloading" reply that
    # starts the frontend progress bar only comes back once it's already done.
    ) </dev/null >/dev/null 2>&1 &
    echo $! > "${DECKY_PLUGIN_LOG_DIR}/${1}.pid"
    echo "{\"Type\": \"Progress\", \"Content\": {\"Message\": \"Updating\"}}"
}

function Amazon_verify(){
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    (
        updategamedetailsafteramazoncmd $1 $NILE verify $1 >> "${DECKY_PLUGIN_LOG_DIR}/${1}.log" 2> $PROGRESS_LOG
        echo "===NILE_EXIT:$?===" >> $PROGRESS_LOG
    # Detach the backgrounded subshell's stdio from the caller's pipe. Otherwise
    # it keeps the script's stdout open, the plugin's script runner blocks
    # reading until the whole download finishes, and the "Downloading" reply that
    # starts the frontend progress bar only comes back once it's already done.
    ) </dev/null >/dev/null 2>&1 &
    echo $! > "${DECKY_PLUGIN_LOG_DIR}/${1}.pid"
    echo "{\"Type\": \"Progress\", \"Content\": {\"Message\": \"Updating\"}}"
}

function Amazon_repair(){
    Amazon_verify "${@}"
}

function Amazon_repair_and_update(){
    Amazon_update "${@}"
}

function Amazon_cancelinstall(){
    PID=$(cat "${DECKY_PLUGIN_LOG_DIR}/${1}.pid")
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    pkill -TERM -P "${PID}" 2>/dev/null
    kill -TERM "${PID}" 2>/dev/null
    pkill -f "nile.*install ${1}" 2>/dev/null
    rm -f "${DECKY_PLUGIN_LOG_DIR}/${1}.pid"
    echo "{\"Type\": \"Success\", \"Content\": {\"Message\": \"${1} installation Cancelled\"}}"
}

function Amazon_install(){
    PROGRESS_LOG="${DECKY_PLUGIN_LOG_DIR}/${1}.progress"
    rm $PROGRESS_LOG &>> ${DECKY_PLUGIN_LOG_DIR}/${1}.log
    RESULT=$($AMAZONCONF --addsteamclientid "${1}" "${2}" --dbfile $DBFILE)
    TEMP=$($AMAZONCONF --update-umu-id "${1}" amazon --dbfile $DBFILE)
    mkdir -p "${INSTALL_DIR}"
    TEMP=$($AMAZONCONF --launchoptions "${1}" "" "" --dbfile $DBFILE $OFFLINE_MODE)
    echo $TEMP
    exit 0
}

function Amazon_getlaunchoptions(){
    TEMP=$($AMAZONCONF --launchoptions "${1}" "" "" --dbfile $DBFILE $OFFLINE_MODE)
    echo $TEMP
    exit 0
}

function Amazon_uninstall(){
    $NILE uninstall "${1}" >> "${DECKY_PLUGIN_LOG_DIR}/${1}.log" 2>&1
    TEMP=$($AMAZONCONF --clear-install-info "${1}" --dbfile $DBFILE)
    echo $TEMP
}

function Amazon_getgamedetails(){
    IMAGE_PATH=""
    TEMP=$($AMAZONCONF --getgamedata "${1}" "${IMAGE_PATH}" --dbfile $DBFILE --forkname "Proton" --version "null" --platform "Windows")
    echo $TEMP
    exit 0
}

function Amazon_getgamesize(){
    TEMP=$($AMAZONCONF --get-game-size "${1}" "${2}" --dbfile $DBFILE)
    echo $TEMP
}

function Amazon_getprogress(){
    TEMP=$($AMAZONCONF --getprogress "${DECKY_PLUGIN_LOG_DIR}/${1}.progress" --dbfile $DBFILE)
    echo $TEMP
}

function Amazon_loginstatus(){
    if [[ -z $1 ]]; then
        FLUSH_CACHE=""
    else
        FLUSH_CACHE="--flush-cache"
    fi
    TEMP=$($AMAZONCONF --getloginstatus --dbfile $DBFILE $OFFLINE_MODE $FLUSH_CACHE)
    echo $TEMP
}

function Amazon_protontricks(){
    get_steam_env
    unset STEAM_RUNTIME_LIBRARY_PATH
    export PROTONTRICKS_GUI=yad
    ARGS="--verbose $2 --gui &> \\\"${DECKY_PLUGIN_LOG_DIR}/${1}.log\\\""
    launchoptions "${PROTON_TRICKS}"  "${ARGS}" "${3}" "Protontricks" false ""
}

function Amazon_run-exe(){
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
    GAME_PATH=$($AMAZONCONF --get-game-dir $GAME_SHORTNAME --dbfile $DBFILE)
    launchoptions "\\\"${GAME_PATH}/${GAME_EXE}\\\""  "${ARGS}  &> ${DECKY_PLUGIN_LOG_DIR}/run-exe.log" "${GAME_PATH}" "Run exe" true "${COMPAT_TOOL}"
}

function Amazon_get-exe-list(){
    get_steam_env
    STEAM_ID="${1}"
    GAME_SHORTNAME="${2}"
    GAME_PATH=$($AMAZONCONF --get-game-dir $GAME_SHORTNAME --dbfile $DBFILE)
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

function Amazon_login(){
    get_steam_env
    launchoptions "${DECKY_PLUGIN_DIR}/scripts/Extensions/Amazon/login.sh" "" "${DECKY_PLUGIN_LOG_DIR}" "Amazon Games Login"
}

function Amazon_login-launch-options(){
    get_steam_env
    loginlaunchoptions "${DECKY_PLUGIN_DIR}/scripts/Extensions/Amazon/login.sh" "" "${DECKY_PLUGIN_LOG_DIR}" "Amazon Games Login"
}

function Amazon_logout(){
    $NILE auth --logout &>> "${DECKY_PLUGIN_LOG_DIR}/amazonlogin.log"
    Amazon_loginstatus --flush-cache
}

function Amazon_getsetting(){
    TEMP=$($AMAZONCONF --getsetting $1 --dbfile $DBFILE)
    echo $TEMP
}
function Amazon_savesetting(){
    $AMAZONCONF --savesetting $1 $2 --dbfile $DBFILE
}
function Amazon_getjsonimages(){
    TEMP=$($AMAZONCONF --get-base64-images "${1}" --dbfile $DBFILE --offline)
    echo $TEMP
}
function Amazon_update-umu-id(){
    TEMP=$($AMAZONCONF --update-umu-id "${1}" amazon --dbfile $DBFILE)
    echo "{\"Type\": \"Success\", \"Content\": {\"Message\": \"Umu Id updated\"}}"
}

function Amazon_gettabconfig(){
    if [[ ! -d "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas" ]]; then
        mkdir -p "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas"
    fi
    if [[ -f "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/amazontabconfig.json" ]]; then
        TEMP=$(cat "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/amazontabconfig.json")
    else
        TEMP=$(cat "${DECKY_PLUGIN_DIR}/conf_schemas/amazontabconfig.json")
    fi
    echo "{\"Type\":\"IniContent\", \"Content\": ${TEMP}}"
}
function Amazon_savetabconfig(){
    cat > "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/amazontabconfig.json"
    echo "{\"Type\": \"Success\", \"Content\": {\"Message\": \"Amazon tab config saved\"}}"
}

function updategamedetailsafteramazoncmd() {
    game=$1
    shift
    "$@"
    local rc=$?
    $AMAZONCONF --update-game-details $game --dbfile $DBFILE &> /dev/null
    return $rc
}
