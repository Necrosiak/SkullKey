# 🗝️ SkeletonKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**Der Schlüssel, der jeden Shop öffnet.** Spiele deine Epic-Games-, GOG- und Amazon-Games-Bibliotheken direkt im Gaming-Modus auf SteamOS / Bazzite — anmelden, installieren, starten. Ganz ohne Desktop-Modus.

## Funktionen

- 🎮 **100 % Gaming-Modus** — stöbern, anmelden, installieren und spielen, ohne den Desktop zu berühren
- 🏪 **Drei Shops, kostenlos** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)) und Amazon Games ([nile](https://github.com/imLinguin/nile))
- 📺 **Medien & Apps** — zusätzliche Bereiche für TV & Video, Musik, Cloud-Gaming und Apps & Tools (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 kuratierte Apps), automatisch aktuell gehalten
- 🖼️ **Nativ aussehende Verknüpfungen** — installierte Spiele erhalten automatisch Steams offizielles Artwork (vertikale Kapsel, Hero, Logo), mit GOGs gamesdb als Fallback
- 📚 **Steam-Sammlungen** — installierte Spiele werden pro Shop („Epic", „GOG", „Amazon") in deiner Bibliothek gruppiert
- ⚙️ **Proton von Steam verwaltet** — Präfixe, Spieleinstellungen und FPS-Limits funktionieren genau wie bei Steam-Spielen
- 🔄 **Auto-Update** — neue Versionen installieren sich still im Hintergrund (in den Einstellungen abschaltbar)
- 🌐 **9 Sprachen** — die Oberfläche folgt automatisch der Konsolensprache (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Schnellzugriff** — farbige Shop-Karten im QAM, optionale L3+R3-Verknüpfung zum Öffnen des Shops von überall

## Installation

Lade `SkeletonKey.zip` aus dem [neuesten Release](https://github.com/Necrosiak/SkeletonKey/releases/latest) herunter und installiere es über Decky Loader (Entwicklermodus → Aus ZIP installieren), oder baue aus dem Quellcode:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Öffne dann das Plugin und installiere die Shop-Abhängigkeiten unter **Einstellungen → Abhängigkeiten**.

## Verwendung

1. Öffne das Schnellzugriffsmenü (…) → SkeletonKey
2. Wähle eine Shop-Karte (Epic / GOG / Amazon) und melde dich an
3. Installiere ein Spiel — es landet mit Artwork in deiner Steam-Bibliothek, in einer Sammlung pro Shop
4. Spielen!

## Danksagungen

SkeletonKey ist ein Fork von [Junk-Store](https://github.com/ebenbruyns/junkstore) von **Eben Bruyns** (BSD-3-Clause) — danke für das solide Fundament. Shop-Engines: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) und [nile](https://github.com/imLinguin/nile).

Unabhängiges Community-Projekt, nicht verbunden mit Junk-Store, Valve, Epic Games, GOG oder Amazon.

## Lizenz

BSD-3-Clause — siehe [LICENSE](LICENSE).
