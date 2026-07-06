# 🗝️ SkullKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**La chiave che apre tutti i negozi.** Gioca alle tue librerie Epic Games, GOG e Amazon Games direttamente dalla modalità gioco su SteamOS / Bazzite: accesso, installazione, avvio. Senza mai passare dalla modalità desktop.

## Funzionalità

- 🎮 **100% modalità gioco** — sfoglia, accedi, installa e gioca senza toccare il desktop
- 🏪 **Quattro store, gratis** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)), Amazon Games ([nile](https://github.com/imLinguin/nile)) e **miHoYo/HoYoverse**
- ✨ **Store miHoYo** — Genshin Impact, Honkai: Star Rail, Zenless Zone Zero e Honkai Impact 3rd, installati dal canale ufficiale *sophon* di HoYoverse: download a chunk in parallelo (~100 MB/s), aggiornamenti che scaricano solo i file modificati, ripresa dopo il riavvio, anti-cheat gestito automaticamente (jadeite) per HI3/HSR
- 🩹 **Extra miHoYo** — aggiornamenti delta (solo il diff, ~4× più piccoli), selettore lingua del doppiaggio, **verifica e riparazione** dell'integrità, e anti-cheat di Zenless Zone Zero gestito automaticamente
- 🏛️ **Classics Reborn** — 47 port nativi open source e ricompilazioni di classici (Zelda, Mario 64, Perfect Dark, Diablo, Fallout, Doom, C&C Generals, Morrowind, Sonic Unleashed…), installati dalle release ufficiali di ogni progetto, con istruzioni chiare per i tuoi file di gioco originali (9 lingue)
- 👥 **Uno spazio store per account Steam (multi-account)** — ogni utente Steam della macchina ha i propri login e librerie Epic/GOG/Amazon; cambiare account Steam cambia tutto automaticamente (i login esistenti restano all'account attivo al primo uso)
- 📦 **Aggiornamento automatico dei giochi** — un passaggio quotidiano in background tiene aggiornati tutti i giochi installati, su ogni store e per ogni account
- 📺 **Media e app** — sezioni extra per TV e Video, Musica, Cloud gaming e App e strumenti (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 app selezionate), mantenute aggiornate automaticamente
- 🖼️ **Collegamenti dall'aspetto nativo** — i giochi installati ricevono automaticamente l'artwork ufficiale di Steam (capsula verticale, hero, logo), con la gamesdb di GOG come riserva
- 📚 **Collezioni Steam** — i giochi installati vengono raggruppati per negozio («Epic», «GOG», «Amazon») nella tua libreria
- ⚙️ **Proton gestito da Steam** — prefissi, impostazioni per gioco e limiti FPS funzionano esattamente come per i giochi Steam
- 🔄 **Aggiornamento automatico** — le nuove versioni si installano silenziosamente in background (disattivabile nelle Impostazioni)
- 🌐 **9 lingue** — l'interfaccia segue automaticamente la lingua della console (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Accesso rapido** — schede colorate per negozio nel QAM, scorciatoia opzionale L3+R3 per aprire il negozio ovunque
- 🐧 **Compatibilità** — lavoriamo attivamente per supportare ogni OS in grado di eseguire Steam in modalità gioco / Big Picture (Linux per ora): rilevamento portabile, nessuna assunzione specifica di distribuzione

## Installazione

Scarica `SkullKey.zip` dall'[ultima release](https://github.com/Necrosiak/SkullKey/releases/latest) e installalo tramite Decky Loader (modalità sviluppatore → Installa da ZIP), oppure compila dai sorgenti:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Poi apri il plugin e installa le dipendenze dei negozi da **Impostazioni → Dipendenze**.

## Utilizzo

1. Apri il menu di accesso rapido (…) → SkullKey
2. Scegli una scheda negozio (Epic / GOG / Amazon) e accedi
3. Installa un gioco: arriverà nella tua libreria Steam con il suo artwork, in una collezione per negozio
4. Gioca!

## Riconoscimenti

SkullKey è un fork di [Junk-Store](https://github.com/ebenbruyns/junkstore) di **Eben Bruyns** (BSD-3-Clause): grazie per le solide fondamenta. Motori dei negozi: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) e [nile](https://github.com/imLinguin/nile).

Progetto comunitario indipendente, non affiliato a Junk-Store, Valve, Epic Games, GOG o Amazon.

## Licenza

BSD-3-Clause — vedi [LICENSE](LICENSE).
