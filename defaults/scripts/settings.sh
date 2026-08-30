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
# suivant. Les données trouvées hors d'un espace de compte sont ADOPTÉES par le
# compte actif (voir plus bas) — même principe que le multi-sessions Steamcord.
SK_ACCOUNT="$("${DECKY_PLUGIN_DIR}/scripts/steam-account.sh" 2>/dev/null || echo default)"
SK_ACCOUNTS_ROOT="${DECKY_PLUGIN_RUNTIME_DIR}/accounts"
SK_ACCOUNT_DIR="${SK_ACCOUNTS_ROOT}/${SK_ACCOUNT}"
mkdir -p "${SK_ACCOUNT_DIR}"

# ── récupération des données écrites hors de l'espace du compte ─────────────
# Deux façons d'atterrir au mauvais endroit, toutes deux vécues (#3) :
#
#  ① la RACINE du dossier de données. Les scripts lancés directement par Steam
#     (les login.sh des boutiques) ne sourcent que le settings.sh de LEUR
#     boutique, où SK_ACCOUNT_DIR retombait sur DECKY_PLUGIN_RUNTIME_DIR. La
#     connexion s'écrivait donc à côté de l'espace que la lecture du statut
#     consulte, et l'utilisateur restait « pas connecté » sur les trois
#     boutiques avec ses identifiants bien présents, un dossier plus haut.
#  ② l'espace "default", utilisé quand le compte Steam n'est pas identifiable
#     (Steam pas encore démarré). Dès qu'il le devient, l'espace réel était créé
#     VIDE et plus rien n'était repris — l'adoption ne jouait qu'au tout premier
#     lancement.
#
# Dans les deux cas la donnée appartient au compte qui se présente : on déplace
# ce qui MANQUE de ce côté-ci, jamais ce qui existe déjà. Rien n'est écrasé ni
# supprimé, et l'opération est sans effet une fois la reprise faite.
_sk_adopt_from() {
    local _src="$1" _f _e
    [[ -d "${_src}" ]] || return 0
    [[ "${_src}" == "${SK_ACCOUNT_DIR}" ]] && return 0
    for _f in epic.db gog.db amazon.db gog_auth.json nile legendary; do
        [[ -e "${_src}/${_f}" ]] || continue
        if [[ ! -e "${SK_ACCOUNT_DIR}/${_f}" ]]; then
            mv "${_src}/${_f}" "${SK_ACCOUNT_DIR}/${_f}"
        elif [[ -d "${_src}/${_f}" && -d "${SK_ACCOUNT_DIR}/${_f}" ]]; then
            # Cas réel : l'espace du compte a DÉJÀ un dossier legendary (créé
            # vide par un `legendary status`, avec config.ini et version.json)
            # pendant que le user.json vit dans le dossier échoué. Refuser la
            # reprise parce que le dossier existe laisserait l'utilisateur
            # déconnecté avec ses identifiants à côté. On complète donc entrée
            # par entrée, sans jamais écraser ce qui est déjà là.
            for _e in "${_src}/${_f}"/* "${_src}/${_f}"/.[!.]*; do
                [[ -e "${_e}" ]] || continue
                if [[ ! -e "${SK_ACCOUNT_DIR}/${_f}/$(basename "${_e}")" ]]; then
                    mv "${_e}" "${SK_ACCOUNT_DIR}/${_f}/"
                fi
            done
        fi
    done
}
_sk_adopt_from "${DECKY_PLUGIN_RUNTIME_DIR}"
if [[ "${SK_ACCOUNT}" != "default" ]]; then
    _sk_adopt_from "${SK_ACCOUNTS_ROOT}/default"
fi

export SK_ACCOUNT SK_ACCOUNT_DIR







