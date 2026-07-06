#!/usr/bin/env bash
# accountid (32 bits) du compte Steam ACTIF — même logique que Steamcord :
# registry.vdf ActiveUser d'abord (mis à jour en live au changement de
# session ; 0 = déconnecté, ignoré), puis loginusers.vdf MostRecent
# (SteamID64 → accountid), sur les racines Steam usuelles toutes distros.
# Sort "default" si indétectable (SkullKey reste utilisable sans Steam).
# SK_ACCOUNT_OVERRIDE force une valeur (tests / debug).

if [[ -n "${SK_ACCOUNT_OVERRIDE:-}" ]]; then
    echo "${SK_ACCOUNT_OVERRIDE}"
    exit 0
fi

reg="${HOME}/.steam/registry.vdf"
if [[ -f "${reg}" ]]; then
    id=$(grep -oP '"ActiveUser"\s+"\K[0-9]+' "${reg}" 2>/dev/null | head -1)
    if [[ -n "${id}" && "${id}" != "0" ]]; then
        echo "${id}"
        exit 0
    fi
fi

for root in "${HOME}/.steam/steam" "${HOME}/.local/share/Steam" "${HOME}/.steam/root"; do
    f="${root}/config/loginusers.vdf"
    [[ -f "${f}" ]] || continue
    id64=$(awk '
        /^[\t ]*"[0-9]{17}"[\t ]*$/ { gsub(/[\t "]/, ""); sid = $0 }
        /"MostRecent"[\t ]+"1"/     { print sid; exit }
    ' "${f}")
    if [[ -n "${id64}" ]]; then
        echo $((id64 - 76561197960265728))
        exit 0
    fi
done

echo default
