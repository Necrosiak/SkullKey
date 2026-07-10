# 🗝️ SkullKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**La clé qui ouvre toutes les boutiques.** Jouez à vos bibliothèques Epic Games, GOG et Amazon Games directement depuis le mode jeu sur SteamOS / Bazzite — connexion, installation, lancement. Sans jamais passer par le mode bureau.

## Fonctionnalités

- 🎮 **100% mode jeu** — parcourir, se connecter, installer et jouer sans toucher au bureau
- 🏪 **Quatre boutiques, gratuites** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)), Amazon Games ([nile](https://github.com/imLinguin/nile)) et **miHoYo/HoYoverse**
- ✨ **Boutique miHoYo** — Genshin Impact, Honkai: Star Rail, Zenless Zone Zero et Honkai Impact 3rd, installés depuis le canal officiel *sophon* de HoYoverse : téléchargement par chunks en parallèle (~100 Mo/s), mises à jour qui ne prennent que les fichiers modifiés, reprise après redémarrage, anti-cheat géré automatiquement (jadeite) pour HI3/HSR
- 🩹 **Extras miHoYo** — mises à jour delta (ne télécharge que le diff, ~4× plus léger), sélecteur de langue de doublage, **vérification & réparation** d'intégrité, et anti-cheat de Zenless Zone Zero géré automatiquement
- 🏛️ **Classics Reborn** — 52 ports natifs open source et recompilations de classiques (Zelda, Mario 64, Perfect Dark, Diablo, Fallout, Doom, C&C Generals, Morrowind, Sonic Unleashed, Unreal Tournament, Freespace 2, LEGO Island…), installés depuis les releases officielles de chaque projet, avec des instructions claires pour vos fichiers de jeu originaux (9 langues)
- 👥 **Un espace boutiques par compte Steam (multi-comptes)** — chaque utilisateur Steam de la machine a ses propres logins et bibliothèques Epic/GOG/Amazon ; changer de compte Steam bascule tout automatiquement (les logins existants restent au compte actif à la première utilisation)
- 📦 **Mise à jour auto des jeux** — un passage quotidien en arrière-plan garde tous les jeux installés à jour, sur toutes les boutiques et pour tous les comptes
- 📺 **Médias & applis** — des sections en plus pour TV & Vidéo, Musique, Jeu cloud et Applis & outils (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 applis triées), tenues à jour automatiquement
- 🖼️ **Raccourcis d'aspect natif** — les jeux installés reçoivent automatiquement l'artwork officiel Steam (jaquette verticale, bandeau, logo), avec la gamesdb de GOG en secours
- 📚 **Collections Steam** — les jeux installés sont regroupés par boutique (« Epic », « GOG », « Amazon ») dans votre bibliothèque
- ⚙️ **Proton géré par Steam** — préfixes, réglages par jeu et limite de FPS fonctionnent exactement comme pour les jeux Steam
- 🔄 **Mise à jour automatique** — les nouvelles versions s'installent silencieusement en arrière-plan (désactivable dans les Réglages)
- 🌐 **9 langues** — l'interface suit automatiquement la langue de votre console (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Accès rapide** — cartes colorées par boutique dans le QAM, raccourci L3+R3 optionnel pour ouvrir la boutique n'importe où
- 🐧 **Compatibilité** — nous faisons le nécessaire pour prendre en charge tous les OS capables de faire tourner Steam en mode jeu / Big Picture (Linux pour le moment) : détection portable, aucune supposition propre à une distribution Notes par distribution : [docs/OS-NOTES.md](docs/OS-NOTES.md).

## Installation

Via Decky Loader, sans passer par le bureau :

1. Installez [Decky Loader](https://decky.xyz/)
2. Activez le **mode développeur** dans les réglages généraux de Decky
3. Réglages Decky → **Développeur** → *Installer un plugin depuis une URL* :
   `https://github.com/Necrosiak/SkullKey/releases/latest/download/SkullKey.zip`

Ou compilez depuis les sources :

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Ouvrez ensuite le plugin et installez les dépendances des boutiques depuis **Réglages → Dépendances**.

## Utilisation

1. Ouvrez le menu d'accès rapide (…) → SkullKey
2. Choisissez une carte boutique (Epic / GOG / Amazon) et connectez-vous
3. Installez un jeu — il arrive dans votre bibliothèque Steam avec son artwork, dans une collection par boutique
4. Jouez !

## 🐛 Issues et idées — n'hésitez pas !

Un bug, un truc qui accroche, un comportement bizarre sur votre distribution ?
Une idée ? **Ouvrez une [issue](https://github.com/Necrosiak/SkullKey/issues)**
— chaque retour oriente directement la suite du développement, et aucun
signalement n'est trop petit. Pour nous aider à corriger vite, indiquez si
possible :

- votre distribution et sa version (Bazzite 42, CachyOS, Ubuntu 24.04…) et comment Steam tourne (mode jeu / Big Picture / bureau)
- la version du plugin (Réglages → À propos) et la boutique/l'onglet concerné
- ce que vous avez fait, ce que vous attendiez, ce qui s'est passé à la place
- les logs : `~/homebrew/logs/SkullKey/` (problèmes de dépendances : `ensure_deps.log`)

Les demandes de fonctionnalités et les retours « ça marche ! » sur des configs
inhabituelles sont tout aussi précieux — ils nous disent quoi supporter ensuite.

## Crédits

SkullKey est un fork de [Junk-Store](https://github.com/ebenbruyns/junkstore) d'**Eben Bruyns** (BSD-3-Clause) — merci pour les solides fondations. Moteurs de boutiques : [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) et [nile](https://github.com/imLinguin/nile).

Projet communautaire indépendant, non affilié à Junk-Store, Valve, Epic Games, GOG ni Amazon.

## Licence

BSD-3-Clause — voir [LICENSE](LICENSE).
