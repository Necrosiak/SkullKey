#!/usr/bin/env bash

# Register MiHoYo as a platform with skullkey.sh
PLATFORMS+=("MiHoYo")

# only source the settings when this platform is the active one
if [[ "${PLATFORM}" == "MiHoYo" ]]; then
    source "${DECKY_PLUGIN_DIR}/scripts/Extensions/MiHoYo/settings.sh"
fi

MIHOYO_PY="${DECKY_PLUGIN_DIR}/scripts/Extensions/MiHoYo/mihoyo.py"

# Thin wrapper: every action is handled by mihoyo.py so nothing falls through to
# the generic (Epic) functions in shared.sh.
function _mihoyo_py() {
    python3 "${MIHOYO_PY}" "${@}"
}

function MiHoYo_init() { :; }

function MiHoYo_refresh() {
    echo "{\"Type\": \"RefreshContent\", \"Content\": {\"Message\": \"Refreshed\"}}"
}

# --- catalogue / details (implemented) ---------------------------------------
function MiHoYo_getgames()        { _mihoyo_py getgames "${@}"; }
function MiHoYo_getgamedetails()  { _mihoyo_py getgamedetails "${@}"; }
function MiHoYo_getgamesize()     { _mihoyo_py getgamesize "${@}"; }
function MiHoYo_getjsonimages()   { _mihoyo_py getjsonimages "${@}"; }
function MiHoYo_getprogress()     { _mihoyo_py getprogress "${@}"; }
function MiHoYo_loginstatus()     { _mihoyo_py loginstatus "${@}"; }
function MiHoYo_login-launch-options() { _mihoyo_py login-launch-options "${@}"; }

# --- install pipeline (milestone 2 — returns "coming soon" for now) ----------
function MiHoYo_download()          { _mihoyo_py download "${@}"; }
function MiHoYo_install()          { _mihoyo_py install "${@}"; }
function MiHoYo_update()           { _mihoyo_py update "${@}"; }
function MiHoYo_repair()           { _mihoyo_py repair "${@}"; }
function MiHoYo_repair_and_update(){ _mihoyo_py repair_and_update "${@}"; }
function MiHoYo_verify()           { _mihoyo_py verify "${@}"; }
function MiHoYo_uninstall()        { _mihoyo_py uninstall "${@}"; }
function MiHoYo_cancelinstall()    { _mihoyo_py cancelinstall "${@}"; }
function MiHoYo_protontricks()     { _mihoyo_py protontricks "${@}"; }
function MiHoYo_getlaunchoptions() { _mihoyo_py getlaunchoptions "${@}"; }
function MiHoYo_run-exe()          { _mihoyo_py run-exe "${@}"; }
function MiHoYo_get-exe-list()     { _mihoyo_py get-exe-list "${@}"; }
function MiHoYo_update-umu-id()    { _mihoyo_py update-umu-id "${@}"; }
