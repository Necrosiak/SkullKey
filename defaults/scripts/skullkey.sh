#!/usr/bin/env bash
source "./scripts/settings.sh"
mkdir "${DECKY_PLUGIN_RUNTIME_DIR}/scripts/Extensions" -p
source "${DECKY_PLUGIN_DIR}/scripts/shared.sh"

# plugins hook into the skullkey.sh script by defining a function with the same name as the plugin prefixed with the platform name
# e.g. for the Epic plugin, the function would be Epic_init

PLATFORMS=()
PLATFORM="${1}"

# List of actions that can be performed by the skullkey.sh script
ACTIONS=("init" "accounts" "getgames" "getactions" "saveconfig" "getconfig" "download" \
"install" "update" "verify" "repair" "import" "getjsonimages" "cancelinstall" \
"uninstall" "protontricks" "enable-eos-overlay" "disable-eos-overlay" \
"getgamedetails" "getbats" "savebats" "getprogress" "login" \
"login-launch-options" "login-url" "login-code" "login-browser" "removeinfo" "removeclient" "logout" "loginstatus" "getsetting" "savesetting" \
"getlaunchoptions" "run-exe" "get-exe-list" "gettabconfig" "savetabconfig" \
"saveplatformconfig" "getplatformconfig" "refresh" "getgamesize" "move" "repair_and_update" \
"getvoices" "setvoices" "voice-en" "voice-jp" "voice-cn" "voice-ko" "voice-auto" \
"backup-saves" "restore-saves")


# Function to source scripts recursively from a directory
source_scripts() {
    local dir=$1
    if [[ -d "${dir}" ]]; then
        local store_script="${dir}/store.sh"
        if [[ -f "$store_script" ]]; then
            source "$store_script"
        fi
        local store_platform_script="${dir}/${PLATFORM}/store.sh"
        if [[ -f "$store_platform_script" ]]; then
            source "$store_platform_script"
        fi
        # for subdir in "$dir"/*; do
        #     if [[ -d "$subdir" ]]; then
        #         source_scripts "$subdir"
        #     fi
        # done
    fi
}
    


# List of directories to search for scripts
directories=("${DECKY_PLUGIN_DIR}/scripts/${Extensions}" \
    "${DECKY_PLUGIN_RUNTIME_DIR}/scripts/${Extensions}")

# Source scripts recursively from each directory
for dir in "${directories[@]}"; do
    source_scripts "$dir"
done

# Check if the PLATFORM is in the list of strings
if [[ " ${PLATFORMS[@]} " =~ " ${1} " ]]; then
    export PLATFORM=$1
    shift  # Remove the first argument from the argument list
else
    export PLATFORM=""
fi



# Switch store account without signing out: the session files are swapped by
# accounts.py, then the login status and the library are read again.
function accounts(){
    local out
    out=$(SK_ACCOUNT_DIR="${SK_ACCOUNT_DIR}" python3 "${DECKY_PLUGIN_DIR}/scripts/accounts.py" "${PLATFORM}" "$@")
    if echo "$out" | grep -q '"Switched": true\|"Cleared": true'; then
        rm -f "${DECKY_PLUGIN_RUNTIME_DIR}/library-refresh-${PLATFORM}.stamp"
        "${PLATFORM}_loginstatus" --flush-cache >/dev/null 2>&1
        if [[ "$(type -t ${PLATFORM}_refresh)" == "function" ]]; then
            ( "${PLATFORM}_refresh" >/dev/null 2>&1 ) </dev/null >/dev/null 2>&1 &
        fi
    fi
    echo "$out"
}

# Check if ACTION is one of the actions in the case statement
ACTION=$1
shift  # Remove the first argument from the argument list
FUNCTION="${PLATFORM}_${ACTION}"

# Libraries stay up to date by themselves: when a store's games list is shown
# and was last read more than 30 minutes ago, it is read again in the
# background (new purchases, claimed free games…). The grid shows at once and
# is told to reload when the refresh is done.
if [[ "$ACTION" == "getgames" && -n "$PLATFORM" && "$(type -t ${PLATFORM}_refresh)" == "function" ]]; then
    STAMP="${DECKY_PLUGIN_RUNTIME_DIR}/library-refresh-${PLATFORM}.stamp"
    if [[ ! -f "$STAMP" ]] || [[ -n "$(find "$STAMP" -mmin +30 2>/dev/null)" ]]; then
        touch "$STAMP"
        ( "${PLATFORM}_refresh" >/dev/null 2>&1; rm -f "${STAMP}.running" ) </dev/null >/dev/null 2>&1 &
        touch "${STAMP}.running"
        OUT=$($FUNCTION "${@}")
        echo "$OUT" | jq -c '.Content.Refreshing = "true"' 2>/dev/null || echo "$OUT"
        exit 0
    fi
fi

if [[ " ${ACTIONS[@]} " =~ " $ACTION " ]]; then
    if [[ "$(type -t $FUNCTION)" == "function" ]]; then
            $FUNCTION "${@}"
        else
            $ACTION "${@}"
        fi
else
        echo "Invalid action: $ACTION"
        exit 1
fi

