#!/usr/bin/env bash
# À lancer UNE FOIS avec sudo : installe le script de déploiement canonique
# root-owned + la règle sudoers NOPASSWD, comme bc250-toolkit-deploy.
# Migre aussi (idempotent) tout ce qui reste de l'ancien nom Junk-Store :
# données, logs, venvs gogdl/nile, ancien plugin déployé, anciens droits.
# Ensuite : sudo -n /usr/local/bin/skeletonkey-deploy (sans mot de passe).
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Lance-moi avec sudo : sudo bash $0" >&2
    exit 1
fi

HOMEDIR=/var/home/bazzite

# ---- Migration depuis Junk-Store (ne fait rien si déjà migré) ----
if [ -d "$HOMEDIR/homebrew/data/Junk-Store" ] && [ ! -d "$HOMEDIR/homebrew/data/SkeletonKey" ]; then
    mv "$HOMEDIR/homebrew/data/Junk-Store" "$HOMEDIR/homebrew/data/SkeletonKey"
    echo "✓ Données migrées (tokens + bases de jeux)"
fi
if [ -d "$HOMEDIR/homebrew/logs/Junk-Store" ] && [ ! -d "$HOMEDIR/homebrew/logs/SkeletonKey" ]; then
    mv "$HOMEDIR/homebrew/logs/Junk-Store" "$HOMEDIR/homebrew/logs/SkeletonKey"
    echo "✓ Logs migrés"
fi
for tool in gogdl nile; do
    OLD="$HOMEDIR/.local/share/junkstore-$tool"
    NEW="$HOMEDIR/.local/share/skeletonkey-$tool"
    [ -L "$NEW" ] && rm "$NEW"
    if [ -d "$OLD" ] && [ ! -d "$NEW" ]; then
        mv "$OLD" "$NEW"
        # un venv déplacé garde des chemins absolus dans ses scripts bin/
        grep -rlZ "junkstore-$tool" "$NEW/bin" 2>/dev/null | xargs -0 -r sed -i "s|junkstore-$tool|skeletonkey-$tool|g"
        echo "✓ venv $tool migré"
    fi
done
rm -rf "$HOMEDIR/homebrew/plugins/Junk-Store"
rm -f /usr/local/bin/junkstore-deploy /etc/sudoers.d/junkstore-deploy

# ---- Script de déploiement canonique ----
cat > /usr/local/bin/skeletonkey-deploy <<'EOF'
#!/usr/bin/env bash
# Déploiement SkeletonKey — script CANONIQUE root-owned, autorisé
# passwordless via /etc/sudoers.d/skeletonkey-deploy. Copie le repo source vers
# le plugin déployé (layout zip decky : defaults/ à la racine), puis
# redémarre plugin_loader. Aucun argument.
set -euo pipefail
SRC=/var/home/bazzite/SkeletonKey
DST=/var/home/bazzite/homebrew/plugins/SkeletonKey

[ -f "$SRC/dist/index.js" ] || { echo "dist/index.js manquant — lance 'pnpm run build' d'abord" >&2; exit 1; }

rm -rf "$DST"
mkdir -p "$DST/dist" "$DST/py_modules"
cp "$SRC/dist/index.js" "$DST/dist/"
cp "$SRC"/main.py "$SRC"/updater.py "$SRC"/plugin.json "$SRC"/package.json "$SRC"/LICENSE "$SRC"/README.md "$DST/"
cp -r "$SRC/defaults/scripts" "$DST/scripts"
cp -r "$SRC/defaults/conf_schemas" "$DST/conf_schemas"
cp "$SRC/defaults/init.json" "$DST/"
touch "$DST/py_modules/.keep"
# user-owned so the plugin backend (user) can self-update in place
chown -R bazzite:bazzite "$DST"
chmod -R a+rX "$DST"
find "$DST/scripts" \( -name '*.sh' -o -name '*.py' \) -exec chmod a+rx {} +

systemctl restart plugin_loader
echo "✓ SkeletonKey déployé — rouvre le QAM."
EOF
chmod 755 /usr/local/bin/skeletonkey-deploy

echo "bazzite ALL=(root) NOPASSWD: /usr/local/bin/skeletonkey-deploy" > /etc/sudoers.d/skeletonkey-deploy
chmod 440 /etc/sudoers.d/skeletonkey-deploy
visudo -c -f /etc/sudoers.d/skeletonkey-deploy

/usr/local/bin/skeletonkey-deploy
echo "✓ Droits installés : 'sudo -n /usr/local/bin/skeletonkey-deploy' est maintenant passwordless."
