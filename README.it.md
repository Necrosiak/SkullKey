# 🗝️ SkeletonKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**La chiave che apre tutti i negozi.** Gioca alle tue librerie Epic Games, GOG e Amazon Games direttamente dalla modalità gioco su SteamOS / Bazzite: accesso, installazione, avvio. Senza mai passare dalla modalità desktop.

## Funzionalità

- 🎮 **100% modalità gioco** — sfoglia, accedi, installa e gioca senza toccare il desktop
- 🏪 **Tre negozi, gratuiti** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)) e Amazon Games ([nile](https://github.com/imLinguin/nile))
- 📺 **Media e app** — sezioni extra per TV e Video, Musica, Cloud gaming e App e strumenti (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 app selezionate), mantenute aggiornate automaticamente
- 🖼️ **Collegamenti dall'aspetto nativo** — i giochi installati ricevono automaticamente l'artwork ufficiale di Steam (capsula verticale, hero, logo), con la gamesdb di GOG come riserva
- 📚 **Collezioni Steam** — i giochi installati vengono raggruppati per negozio («Epic», «GOG», «Amazon») nella tua libreria
- ⚙️ **Proton gestito da Steam** — prefissi, impostazioni per gioco e limiti FPS funzionano esattamente come per i giochi Steam
- 🔄 **Aggiornamento automatico** — le nuove versioni si installano silenziosamente in background (disattivabile nelle Impostazioni)
- 🌐 **9 lingue** — l'interfaccia segue automaticamente la lingua della console (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Accesso rapido** — schede colorate per negozio nel QAM, scorciatoia opzionale L3+R3 per aprire il negozio ovunque

## Installazione

Scarica `SkeletonKey.zip` dall'[ultima release](https://github.com/Necrosiak/SkeletonKey/releases/latest) e installalo tramite Decky Loader (modalità sviluppatore → Installa da ZIP), oppure compila dai sorgenti:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Poi apri il plugin e installa le dipendenze dei negozi da **Impostazioni → Dipendenze**.

## Utilizzo

1. Apri il menu di accesso rapido (…) → SkeletonKey
2. Scegli una scheda negozio (Epic / GOG / Amazon) e accedi
3. Installa un gioco: arriverà nella tua libreria Steam con il suo artwork, in una collezione per negozio
4. Gioca!

## Riconoscimenti

SkeletonKey è un fork di [Junk-Store](https://github.com/ebenbruyns/junkstore) di **Eben Bruyns** (BSD-3-Clause): grazie per le solide fondamenta. Motori dei negozi: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) e [nile](https://github.com/imLinguin/nile).

Progetto comunitario indipendente, non affiliato a Junk-Store, Valve, Epic Games, GOG o Amazon.

## Licenza

BSD-3-Clause — vedi [LICENSE](LICENSE).
