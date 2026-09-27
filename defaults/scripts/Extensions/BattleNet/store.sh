#!/usr/bin/env bash

# Register BattleNet as a platform with skullkey.sh
PLATFORMS+=("BattleNet")

# only source the settings when this platform is the active one
if [[ "${PLATFORM}" == "BattleNet" ]]; then
    source "${DECKY_PLUGIN_DIR}/scripts/Extensions/BattleNet/settings.sh"
fi

BATTLENET_PY="${DECKY_PLUGIN_DIR}/scripts/Extensions/BattleNet/battlenet.py"

# Thin wrapper: every action is handled by battlenet.py so nothing falls
# through to the generic (Epic) functions in shared.sh.
function _battlenet_py() {
    python3 "${BATTLENET_PY}" "${@}"
}

function BattleNet_init() { :; }

function BattleNet_refresh() {
    echo "{\"Type\": \"RefreshContent\", \"Content\": {\"Message\": \"Refreshed\"}}"
}

function BattleNet_getgames()             { _battlenet_py getgames "${@}"; }
function BattleNet_getgamedetails()       { _battlenet_py getgamedetails "${@}"; }
function BattleNet_getgamesize()          { _battlenet_py getgamesize "${@}"; }
function BattleNet_getjsonimages()        { _battlenet_py getjsonimages "${@}"; }
function BattleNet_getprogress()          { _battlenet_py getprogress "${@}"; }
function BattleNet_loginstatus()          { _battlenet_py loginstatus "${@}"; }
function BattleNet_login()                { _battlenet_py login "${@}"; }
function BattleNet_login-launch-options() { _battlenet_py login-launch-options "${@}"; }
function BattleNet_logout()               { _battlenet_py logout "${@}"; }
function BattleNet_download()             { _battlenet_py download "${@}"; }
function BattleNet_install()              { _battlenet_py install "${@}"; }
function BattleNet_update()               { _battlenet_py update "${@}"; }
function BattleNet_repair()               { _battlenet_py repair "${@}"; }
function BattleNet_repair_and_update()    { _battlenet_py repair_and_update "${@}"; }
function BattleNet_verify()               { _battlenet_py verify "${@}"; }
function BattleNet_uninstall()            { _battlenet_py uninstall "${@}"; }
function BattleNet_cancelinstall()        { _battlenet_py cancelinstall "${@}"; }
function BattleNet_getlaunchoptions()     { _battlenet_py getlaunchoptions "${@}"; }
function BattleNet_getsetting()         { _battlenet_py getsetting "${@}"; }
function BattleNet_savesetting()        { _battlenet_py savesetting "${@}"; }
