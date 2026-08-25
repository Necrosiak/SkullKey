#!/usr/bin/env bash
# accountid (32 bits) du compte Steam ACTIF.
# Sort "default" si indétectable (SkullKey reste utilisable sans Steam).
# SK_ACCOUNT_OVERRIDE force une valeur (tests / debug).
#
# ⚠️ Steam a CHANGÉ ses formats (constaté le 25/08/2026, cassait le multi-comptes) :
#   - registry.vdf n'expose plus "ActiveUser" (numérique) mais "AutoLoginUser",
#     qui porte le NOM de compte ("nanemakii59"), pas un id ;
#   - loginusers.vdf n'a plus "MostRecent", remplacé par "AutoLogin" + "Timestamp".
# Les deux sondes d'origine renvoyaient donc vide → repli "default" → le symlink
# de config legendary pointait vers un espace VIERGE et l'utilisateur se voyait
# « non connecté » alors que sa session Epic existait dans un autre dossier.
# On garde les anciennes clés : un Steam plus ancien doit continuer de marcher.

if [[ -n "${SK_ACCOUNT_OVERRIDE:-}" ]]; then
    echo "${SK_ACCOUNT_OVERRIDE}"
    exit 0
fi

STEAM_EPOCH=76561197960265728

reg="${HOME}/.steam/registry.vdf"

# ① registry.vdf "ActiveUser" — Steam ancien, mis à jour en direct. 0 = déconnecté.
if [[ -f "${reg}" ]]; then
    id=$(grep -oP '"ActiveUser"\s+"\K[0-9]+' "${reg}" 2>/dev/null | head -1)
    if [[ -n "${id}" && "${id}" != "0" ]]; then
        echo "${id}"
        exit 0
    fi
fi

# ② registry.vdf "AutoLoginUser" → nom de compte, à résoudre dans loginusers.vdf.
autologin_name=""
if [[ -f "${reg}" ]]; then
    autologin_name=$(grep -oP '"AutoLoginUser"\s+"\K[^"]+' "${reg}" 2>/dev/null | head -1)
fi

for root in "${HOME}/.steam/steam" "${HOME}/.local/share/Steam" "${HOME}/.steam/root"; do
    f="${root}/config/loginusers.vdf"
    [[ -f "${f}" ]] || continue

    # Un seul passage awk rend les 3 candidats, du plus sûr au moins sûr :
    #   nom correspondant à AutoLoginUser > MostRecent/AutoLogin à 1 > Timestamp max.
    read -r by_name by_flag by_time <<<"$(awk -v want="${autologin_name}" '
        /^[\t ]*"[0-9]{17}"[\t ]*$/ { gsub(/[\t "]/, ""); sid = $0; next }
        /"AccountName"/   { line=$0; gsub(/^[^"]*"AccountName"[\t ]*"/, "", line); gsub(/".*$/, "", line)
                            if (want != "" && line == want) named = sid }
        /"MostRecent"[\t ]+"1"/ { if (flagged == "") flagged = sid }
        /"AutoLogin"[\t ]+"1"/  { if (flagged == "") flagged = sid }
        /"Timestamp"/     { t=$0; gsub(/[^0-9]/, "", t)
                            if (t + 0 > best + 0) { best = t + 0; newest = sid } }
        END { print (named == "" ? "-" : named), (flagged == "" ? "-" : flagged), (newest == "" ? "-" : newest) }
    ' "${f}")"

    for id64 in "${by_name}" "${by_flag}" "${by_time}"; do
        if [[ "${id64}" =~ ^[0-9]{17}$ ]]; then
            echo $((id64 - STEAM_EPOCH))
            exit 0
        fi
    done
done

echo default
