#!/usr/bin/env bash

# Register Ubisoft as a platform with skullkey.sh
PLATFORMS+=("Ubisoft")

# only source the settings when this platform is the active one
if [[ "${PLATFORM}" == "Ubisoft" ]]; then
    source "${DECKY_PLUGIN_DIR}/scripts/Extensions/Ubisoft/settings.sh"
fi

UBISOFT_PY="${DECKY_PLUGIN_DIR}/scripts/Extensions/Ubisoft/ubisoft.py"

# Thin wrapper: every action is handled by ubisoft.py so nothing falls
# through to the generic (Epic) functions in shared.sh.
function _ubisoft_py() {
    python3 "${UBISOFT_PY}" "${@}"
}

function Ubisoft_init() { :; }

function Ubisoft_refresh() {
    echo "{\"Type\": \"RefreshContent\", \"Content\": {\"Message\": \"Refreshed\"}}"
}

function Ubisoft_getgames()             { _ubisoft_py getgames "${@}"; }
function Ubisoft_getgamedetails()       { _ubisoft_py getgamedetails "${@}"; }
function Ubisoft_getgamesize()          { _ubisoft_py getgamesize "${@}"; }
function Ubisoft_getjsonimages()        { _ubisoft_py getjsonimages "${@}"; }
function Ubisoft_getprogress()          { _ubisoft_py getprogress "${@}"; }
function Ubisoft_loginstatus()          { _ubisoft_py loginstatus "${@}"; }
function Ubisoft_login()                { _ubisoft_py login "${@}"; }
function Ubisoft_login-launch-options() { _ubisoft_py login-launch-options "${@}"; }
function Ubisoft_logout()               { _ubisoft_py logout "${@}"; }
function Ubisoft_removeinfo()           { _ubisoft_py removeinfo "${@}"; }
function Ubisoft_removeclient()         { _ubisoft_py removeclient "${@}"; }
function Ubisoft_download()             { _ubisoft_py download "${@}"; }
function Ubisoft_install()              { _ubisoft_py install "${@}"; }
function Ubisoft_update()               { _ubisoft_py update "${@}"; }
function Ubisoft_repair()               { _ubisoft_py repair "${@}"; }
function Ubisoft_repair_and_update()    { _ubisoft_py repair_and_update "${@}"; }
function Ubisoft_verify()               { _ubisoft_py verify "${@}"; }
function Ubisoft_uninstall()            { _ubisoft_py uninstall "${@}"; }
function Ubisoft_cancelinstall()        { _ubisoft_py cancelinstall "${@}"; }
function Ubisoft_getlaunchoptions()     { _ubisoft_py getlaunchoptions "${@}"; }
function Ubisoft_getsetting()         { _ubisoft_py getsetting "${@}"; }
function Ubisoft_savesetting()        { _ubisoft_py savesetting "${@}"; }
