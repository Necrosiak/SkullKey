#!/usr/bin/env bash
PLATFORMS+=("EA")
function EA_init() { :; }
# Python dispatcher, not shell eval. settings.sh exports the current account.
function _ea_py() { python3 "${DECKY_PLUGIN_DIR}/scripts/Extensions/EA/ea.py" "$@"; }
function EA_getgames() { _ea_py getgames "$@"; }
function EA_loginstatus() { _ea_py loginstatus "$@"; }
function EA_login() { _ea_py login "$@"; }
function EA_login-browser() { exec /usr/bin/python3 "${DECKY_PLUGIN_DIR}/scripts/Extensions/EA/browser_login.py"; }
function EA_login-launch-options() { _ea_py login-launch-options "$@"; }
function EA_logout() { _ea_py logout "$@"; }
function EA_getsetting() { _ea_py getsetting "$@"; }
function EA_savesetting() { _ea_py savesetting "$@"; }
function EA_refresh() { _ea_py refresh "$@"; }
function EA_getgamedetails() { _ea_py getgamedetails "$@"; }
function EA_getjsonimages() { _ea_py getjsonimages "$@"; }
function EA_getlaunchoptions() { _ea_py getlaunchoptions "$@"; }
function EA_install() { _ea_py install "$@"; }
function EA_download() { _ea_py download "$@"; }
function EA_getgamesize() { _ea_py getgamesize "$@"; }
function EA_getprogress() { _ea_py getprogress "$@"; }
function EA_cancelinstall() { _ea_py cancelinstall "$@"; }
function EA_uninstall() { _ea_py uninstall "$@"; }
function EA_gettabconfig(){
    mkdir -p "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas"
    if [[ -f "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/eatabconfig.json" ]]; then
        TEMP=$(cat "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/eatabconfig.json")
    else
        TEMP=$(cat "${DECKY_PLUGIN_DIR}/conf_schemas/eatabconfig.json")
    fi
    echo "{\"Type\":\"IniContent\", \"Content\": ${TEMP}}"
}
function EA_savetabconfig(){
    mkdir -p "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas"
    cat > "${DECKY_PLUGIN_RUNTIME_DIR}/conf_schemas/eatabconfig.json"
    echo "{\"Type\": \"Success\", \"Content\": {\"Message\": \"EA tab config saved\"}}"
}
