#!/usr/bin/env bash
# À lancer UNE FOIS avec sudo : installe le script de déploiement canonique
# root-owned + la règle sudoers NOPASSWD, comme bc250-toolkit-deploy.
# Migre aussi (idempotent) tout ce qui reste de l'ancien nom SkeletonKey :
# données, logs, venvs gogdl/nile, ancien plugin déployé, anciens droits —
# en laissant des SYMLINKS de compatibilité pour que les raccourcis Steam
# existants (chemins absolus vers …/SkeletonKey/…) continuent de marcher.
# Ensuite : sudo -n /usr/local/bin/skullkey-deploy (sans mot de passe).
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Lance-moi avec sudo : sudo bash $0" >&2
    exit 1
fi

HOMEDIR=/var/home/bazzite

# ---- Migration depuis SkeletonKey (ne fait rien si déjà migré) ----
# Données : mv + symlink de compat (les raccourcis médias/ports pointent sur
# homebrew/data/SkeletonKey/{media,ports}_scripts/*.sh en chemin absolu).
if [ -d "$HOMEDIR/homebrew/data/SkeletonKey" ] && [ ! -L "$HOMEDIR/homebrew/data/SkeletonKey" ] \
   && [ ! -d "$HOMEDIR/homebrew/data/SkullKey" ]; then
    mv "$HOMEDIR/homebrew/data/SkeletonKey" "$HOMEDIR/homebrew/data/SkullKey"
    ln -s SkullKey "$HOMEDIR/homebrew/data/SkeletonKey"
    chown -h bazzite:bazzite "$HOMEDIR/homebrew/data/SkeletonKey"
    echo "✓ Données migrées (+ symlink de compat SkeletonKey → SkullKey)"
fi
if [ -d "$HOMEDIR/homebrew/logs/SkeletonKey" ] && [ ! -d "$HOMEDIR/homebrew/logs/SkullKey" ]; then
    mv "$HOMEDIR/homebrew/logs/SkeletonKey" "$HOMEDIR/homebrew/logs/SkullKey"
    echo "✓ Logs migrés"
fi
for tool in gogdl nile; do
    OLD="$HOMEDIR/.local/share/skeletonkey-$tool"
    NEW="$HOMEDIR/.local/share/skullkey-$tool"
    [ -L "$NEW" ] && rm "$NEW"
    if [ -d "$OLD" ] && [ ! -d "$NEW" ]; then
        mv "$OLD" "$NEW"
        # un venv déplacé garde des chemins absolus dans ses scripts bin/
        grep -rlZ "skeletonkey-$tool" "$NEW/bin" 2>/dev/null | xargs -0 -r sed -i "s|skeletonkey-$tool|skullkey-$tool|g"
        echo "✓ venv $tool migré"
    fi
done
rm -f /usr/local/bin/skeletonkey-deploy /etc/sudoers.d/skeletonkey-deploy

# ---- Script de déploiement canonique ----
cat > /usr/local/bin/skullkey-deploy <<'EOF'
#!/usr/bin/env bash
# Déploiement SkullKey — script CANONIQUE root-owned, autorisé
# passwordless via /etc/sudoers.d/skullkey-deploy. Copie le repo source vers
# le plugin déployé (layout zip decky : defaults/ à la racine), puis
# redémarre plugin_loader. Aucun argument.
set -euo pipefail
SRC=/var/home/bazzite/SkullKey
DST=/var/home/bazzite/homebrew/plugins/SkullKey

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

# Stub de compat pour les raccourcis Steam existants : les launchers des
# boutiques pointent en absolu sur …/plugins/SkeletonKey/scripts/… ; on garde
# un dossier stub SANS plugin.json (ignoré par plugin_loader) dont scripts/
# est un symlink vers les scripts SkullKey.
OLD=/var/home/bazzite/homebrew/plugins/SkeletonKey
if [ ! -e "$OLD/plugin.json" ]; then
    rm -rf "$OLD"
    mkdir -p "$OLD"
    ln -s ../SkullKey/scripts "$OLD/scripts"
    chown -R -h bazzite:bazzite "$OLD"
fi

systemctl restart plugin_loader
echo "✓ SkullKey déployé — rouvre le QAM."
EOF
chmod 755 /usr/local/bin/skullkey-deploy

echo "bazzite ALL=(root) NOPASSWD: /usr/local/bin/skullkey-deploy" > /etc/sudoers.d/skullkey-deploy
chmod 440 /etc/sudoers.d/skullkey-deploy
visudo -c -f /etc/sudoers.d/skullkey-deploy

# L'ancien plugin déployé (avec plugin.json) laisse la place au stub de compat
if [ -e "$HOMEDIR/homebrew/plugins/SkeletonKey/plugin.json" ]; then
    rm -rf "$HOMEDIR/homebrew/plugins/SkeletonKey"
fi

/usr/local/bin/skullkey-deploy
echo "✓ Droits installés : 'sudo -n /usr/local/bin/skullkey-deploy' est maintenant passwordless."
