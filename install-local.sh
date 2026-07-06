#!/usr/bin/env bash
# Installe le fork local de SkullKey dans Decky.
# Usage : sudo bash ~/SkullKey/install-local.sh
# Reproduit la structure du zip decky-cli : contenu de defaults/ à la racine
# du plugin (main.py attend scripts/, conf_schemas/ et init.json à côté de lui).
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

systemctl restart plugin_loader
echo "✓ SkullKey (fork) installé — rouvre le QAM."
