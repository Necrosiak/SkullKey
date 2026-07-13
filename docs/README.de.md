# 🗝️ SkullKey

> 🌐 [EN](../README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**Der Schlüssel, der jeden Shop öffnet.** Spiele deine Epic-Games-, GOG- und Amazon-Games-Bibliotheken direkt im Gaming-Modus auf SteamOS / Bazzite — anmelden, installieren, starten. Ganz ohne Desktop-Modus.

## Funktionen

- 🎮 **100 % Gaming-Modus** — stöbern, anmelden, installieren und spielen, ohne den Desktop zu berühren
- 🏪 **Vier Stores, kostenlos** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)), Amazon Games ([nile](https://github.com/imLinguin/nile)) und **miHoYo/HoYoverse**
- ✨ **miHoYo-Store** — Genshin Impact, Honkai: Star Rail, Zenless Zone Zero und Honkai Impact 3rd, installiert über HoYoverses offiziellen *sophon*-Kanal: parallele Chunk-Downloads (~100 MB/s), Updates laden nur geänderte Dateien, Fortsetzen nach Neustart, Anti-Cheat automatisch geregelt (jadeite) für HI3/HSR
- 🩹 **miHoYo-Extras** — Delta-Updates (nur der Diff, ~4× kleiner), Sprachauswahl für die Vertonung, Integritäts-**Prüfung & Reparatur** und automatisch gehandhabter Zenless-Zone-Zero-Anti-Cheat
- 🏛️ **Classics Reborn** — 52 native Open-Source-Ports & Rekompilierungen von Klassikern (Zelda, Mario 64, Perfect Dark, Diablo, Fallout, Doom, C&C Generals, Morrowind, Sonic Unleashed, Unreal Tournament, Freespace 2, LEGO Island…), installiert aus den offiziellen Releases jedes Projekts, mit klaren Anleitungen für deine Original-Spieldateien (9 Sprachen)
- ⛏️ **Minecraft** — Java Edition (über [Prism Launcher](https://prismlauncher.org), vorkonfiguriert: mit dem Microsoft-Konto anmelden und spielen), Bedrock Edition (über [mcpelauncher](https://mcpelauncher.readthedocs.io) von Flathub, native Controller-Unterstützung) und **Modrinth-Modpacks** als Ein-Klick-Steam-Verknüpfungen (Live-Suche, Version anpinnen oder tägliche Auto-Updates, automatische Welten-Backups vor jedem Versionswechsel)
- 👥 **Ein Store-Bereich pro Steam-Konto (Multi-Account)** — jeder Steam-Nutzer der Maschine hat eigene Epic/GOG/Amazon-Logins und Bibliotheken; der Wechsel des Steam-Kontos schaltet alles automatisch um (bestehende Logins bleiben beim beim ersten Start aktiven Konto)
- 📦 **Auto-Update der Spiele** — ein täglicher Hintergrund-Durchlauf hält alle installierten Spiele aktuell, in jedem Store und für jedes Konto
- 💾 **Spielstand-Backup & -Wiederherstellung** — sichere den Fortschritt eines Spiels von seiner Seite aus mit einer Aktion (via [ludusavi](https://github.com/mtkennerly/ludusavi), automatisch bereitgestellt) und stelle ihn bei Bedarf wieder her — Epic-, GOG- und Amazon-Spiele, Backups in `~/.local/share/skullkey-saves`
- 📺 **Medien & Apps** — zusätzliche Bereiche für TV & Video, Musik, Cloud-Gaming und Apps & Tools (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 kuratierte Apps), automatisch aktuell gehalten
- 🖼️ **Nativ aussehende Verknüpfungen** — installierte Spiele erhalten automatisch Steams offizielles Artwork (vertikale Kapsel, Hero, Logo), mit GOGs gamesdb als Fallback
- 📚 **Steam-Sammlungen** — installierte Spiele werden pro Shop („Epic", „GOG", „Amazon") in deiner Bibliothek gruppiert
- ⚙️ **Proton von Steam verwaltet** — Präfixe, Spieleinstellungen und FPS-Limits funktionieren genau wie bei Steam-Spielen
- 🔄 **Auto-Update** — neue Versionen installieren sich still im Hintergrund (in den Einstellungen abschaltbar)
- 🌐 **9 Sprachen** — die Oberfläche folgt automatisch der Konsolensprache (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Schnellzugriff** — farbige Shop-Karten im QAM, optionale L3+R3-Verknüpfung zum Öffnen des Shops von überall
- 🐧 **Kompatibilität** — wir arbeiten aktiv daran, jedes OS zu unterstützen, das Steam im Gaming Mode / Big Picture ausführen kann (derzeit Linux): portable Erkennung, keine distributionsspezifischen Annahmen Hinweise pro Distribution: [docs/OS-NOTES.md](OS-NOTES.md).

## 📸 Screenshots

<p align="center">
  <img src="img/skullkey-epic.jpg" width="49%" alt="Epic Games library"/>
  <img src="img/skullkey-mihoyo.jpg" width="49%" alt="miHoYo tab"/>
</p>
<p align="center">
  <img src="img/skullkey-classics.jpg" width="49%" alt="Classics Reborn"/>
  <img src="img/skullkey-game-details.jpg" width="49%" alt="Game details"/>
</p>
<p align="center">
  <img src="img/skullkey-steam-collection.jpg" width="49%" alt="Steam collection"/>
  <img src="img/skullkey-steam-game-page.jpg" width="49%" alt="Installed game in Steam"/>
</p>

## Installation

Via Decky Loader, ganz ohne Desktop:

1. [Decky Loader](https://decky.xyz/) installieren
2. **Entwicklermodus** in Deckys allgemeinen Einstellungen aktivieren
3. Decky-Einstellungen → **Entwickler** → *Plugin von URL installieren*:
   `https://github.com/Necrosiak/SkullKey/releases/latest/download/SkullKey.zip`

Oder aus dem Quellcode bauen:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Öffne dann das Plugin und installiere die Shop-Abhängigkeiten unter **Einstellungen → Abhängigkeiten**.

## Verwendung

1. Öffne das Schnellzugriffsmenü (…) → SkullKey
2. Wähle eine Shop-Karte (Epic / GOG / Amazon) und melde dich an
3. Installiere ein Spiel — es landet mit Artwork in deiner Steam-Bibliothek, in einer Sammlung pro Shop
4. Spielen!

## 🐛 Issues & Ideen — nur her damit!

Ein Bug, eine Ecke, die hakt, etwas Seltsames auf deiner Distribution? Eine
Idee? **Bitte eröffne ein [Issue](https://github.com/Necrosiak/SkullKey/issues)**
— jede Meldung bestimmt direkt mit, was als Nächstes gebaut wird, und keine
Meldung ist zu klein. Damit wir schnell fixen können, gib wenn möglich an:

- deine Distribution & Version (Bazzite 42, CachyOS, Ubuntu 24.04…) und wie Steam läuft (Gaming Mode / Big Picture / Desktop)
- die Plugin-Version (Einstellungen → Über) und den betroffenen Store/Tab
- was du getan hast, was du erwartet hast, was stattdessen passiert ist
- Logs: `~/homebrew/logs/SkullKey/` (Abhängigkeitsprobleme: `ensure_deps.log`)

Feature-Wünsche und „läuft!“-Meldungen von ungewöhnlichen Setups sind genauso
wertvoll — sie sagen uns, was wir als Nächstes unterstützen sollen.

## Danksagungen

SkullKey ist ein Fork von [Junk-Store](https://github.com/ebenbruyns/junkstore) von **Eben Bruyns** (BSD-3-Clause) — danke für das solide Fundament. Shop-Engines: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) und [nile](https://github.com/imLinguin/nile).

Unabhängiges Community-Projekt, nicht verbunden mit Junk-Store, Valve, Epic Games, GOG oder Amazon.

## Lizenz

BSD-3-Clause — siehe [LICENSE](../LICENSE).
