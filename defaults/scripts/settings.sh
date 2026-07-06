#!/usr/bin/env bash

if [[ -z "${DECKY_PLUGIN_DIR}" ]]; then
    export DECKY_PLUGIN_DIR="${HOME}/homebrew/plugins/SkullKey"
fi
if [[ -z "${DECKY_PLUGIN_RUNTIME_DIR}" ]]; then
    export DECKY_PLUGIN_RUNTIME_DIR="${HOME}/homebrew/data/SkullKey"
fi
if [[ -z "${DECKY_PLUGIN_LOG_DIR}" ]]; then
    export DECKY_PLUGIN_LOG_DIR="${HOME}/homebrew/logs/SkullKey"
fi

Extensions="Extensions"

# ── multi-comptes : un espace boutiques par compte Steam ────────────────────
# Chaque compte Steam de la machine a ses propres logins/DB Epic-GOG-Amazon
# (les jeux installés sur disque restent partagés). Résolu à CHAQUE appel :
# pas de watcher, le changement de compte Steam est pris en compte au call
# suivant. À la toute première exécution, les fichiers existants (session du
# propriétaire) sont ADOPTÉS par le compte actif — même principe que le
# multi-sessions Steamcord.
SK_ACCOUNT="$("${DECKY_PLUGIN_DIR}/scripts/steam-account.sh" 2>/dev/null || echo default)"
SK_ACCOUNTS_ROOT="${DECKY_PLUGIN_RUNTIME_DIR}/accounts"
SK_ACCOUNT_DIR="${SK_ACCOUNTS_ROOT}/${SK_ACCOUNT}"
if [[ ! -d "${SK_ACCOUNT_DIR}" ]]; then
    _sk_first=1
    if [[ -d "${SK_ACCOUNTS_ROOT}" ]] && [[ -n "$(ls -A "${SK_ACCOUNTS_ROOT}" 2>/dev/null)" ]]; then
        _sk_first=0
    fi
    mkdir -p "${SK_ACCOUNT_DIR}"
    if [[ "${_sk_first}" == "1" ]]; then
        for _sk_f in epic.db gog.db amazon.db gog_auth.json nile; do
            if [[ -e "${DECKY_PLUGIN_RUNTIME_DIR}/${_sk_f}" ]]; then
                mv "${DECKY_PLUGIN_RUNTIME_DIR}/${_sk_f}" "${SK_ACCOUNT_DIR}/${_sk_f}"
            fi
        done
    fi
fi
export SK_ACCOUNT SK_ACCOUNT_DIR







