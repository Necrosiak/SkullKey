#!/usr/bin/env bash
# Installe le fork local de SkullKey dans Decky.
# Usage : sudo bash ~/SkullKey/install-local.sh
# Reproduit la structure du zip decky-cli : contenu de defaults/ à la racine
# du plugin (main.py attend scripts/, conf_schemas/ et init.json à côté de lui).
set -euo pipefail

# Auto-détection de l'utilisateur/home cible (portable hors Bazzite : le home
# est /var/home/<user> sur Fedora atomic, /home/<user> ailleurs).
TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
: "${TARGET_HOME:=$HOME}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="$TARGET_HOME/homebrew/plugins/SkullKey"

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
chown -R "$TARGET_USER:$TARGET_USER" "$DST"
chmod -R a+rX "$DST"
find "$DST/scripts" \( -name '*.sh' -o -name '*.py' \) -exec chmod a+rx {} +

systemctl restart plugin_loader
echo "✓ SkullKey (fork) installé — rouvre le QAM."
