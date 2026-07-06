# 🗝️ SkullKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**La clé qui ouvre toutes les boutiques.** Jouez à vos bibliothèques Epic Games, GOG et Amazon Games directement depuis le mode jeu sur SteamOS / Bazzite — connexion, installation, lancement. Sans jamais passer par le mode bureau.

## Fonctionnalités

- 🎮 **100% mode jeu** — parcourir, se connecter, installer et jouer sans toucher au bureau
- 🏪 **Trois boutiques, gratuites** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)) et Amazon Games ([nile](https://github.com/imLinguin/nile))
- 📺 **Médias & applis** — des sections en plus pour TV & Vidéo, Musique, Jeu cloud et Applis & outils (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 applis triées), tenues à jour automatiquement
- 🖼️ **Raccourcis d'aspect natif** — les jeux installés reçoivent automatiquement l'artwork officiel Steam (jaquette verticale, bandeau, logo), avec la gamesdb de GOG en secours
- 📚 **Collections Steam** — les jeux installés sont regroupés par boutique (« Epic », « GOG », « Amazon ») dans votre bibliothèque
- ⚙️ **Proton géré par Steam** — préfixes, réglages par jeu et limite de FPS fonctionnent exactement comme pour les jeux Steam
- 🔄 **Mise à jour automatique** — les nouvelles versions s'installent silencieusement en arrière-plan (désactivable dans les Réglages)
- 🌐 **9 langues** — l'interface suit automatiquement la langue de votre console (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Accès rapide** — cartes colorées par boutique dans le QAM, raccourci L3+R3 optionnel pour ouvrir la boutique n'importe où

## Installation

Téléchargez `SkullKey.zip` depuis la [dernière release](https://github.com/Necrosiak/SkullKey/releases/latest) et installez-le via Decky Loader (mode développeur → Installer depuis un ZIP), ou compilez depuis les sources :

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

## Crédits

SkullKey est un fork de [Junk-Store](https://github.com/ebenbruyns/junkstore) d'**Eben Bruyns** (BSD-3-Clause) — merci pour les solides fondations. Moteurs de boutiques : [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) et [nile](https://github.com/imLinguin/nile).

Projet communautaire indépendant, non affilié à Junk-Store, Valve, Epic Games, GOG ni Amazon.

## Licence

BSD-3-Clause — voir [LICENSE](LICENSE).
