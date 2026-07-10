# 🗝️ SkullKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**The key that opens every store.** Play your Epic Games, GOG and Amazon Games libraries directly from Game Mode on SteamOS / Bazzite — login, install, launch. No desktop mode needed.

## Features

- 🎮 **100% Game Mode** — browse, log in, install and play without ever touching the desktop
- 🏪 **Four stores, free** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)), Amazon Games ([nile](https://github.com/imLinguin/nile)) and **miHoYo/HoYoverse**
- ✨ **miHoYo store** — Genshin Impact, Honkai: Star Rail, Zenless Zone Zero and Honkai Impact 3rd, installed from HoYoverse's official *sophon* channel: parallel chunk downloads (~100 MB/s), updates that only fetch changed files, resume after reboot, anti-cheat handled automatically (jadeite) for HI3/HSR
- 🩹 **miHoYo extras** — delta updates (download only the diff, ~4× smaller), voice-over language picker, integrity **check & repair**, and Zenless Zone Zero anti-cheat handled automatically
- 🏛️ **Classics Reborn** — 52 open-source native ports & recompilations of classics (Zelda, Mario 64, Perfect Dark, Diablo, Fallout, Doom, C&C Generals, Morrowind, Sonic Unleashed, Unreal Tournament, Freespace 2, LEGO Island…), installed from each project's official releases, with clear instructions for your original game files (9 languages)
- 👥 **One store space per Steam account (multi-account)** — every Steam user of the machine gets their own Epic/GOG/Amazon logins and library; switching the Steam account switches everything automatically (existing logins are kept by the account active at first run)
- 📦 **Games auto-update** — a daily background pass keeps every installed game current, on every store and for every account
- 📺 **Media & apps** — extra sections for TV & Video, Music, Cloud Gaming and Apps & Tools (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 curated apps), auto-kept up to date
- 🖼️ **Native-looking shortcuts** — installed games automatically get Steam's official artwork (vertical capsule, hero, logo), with GOG's gamesdb as fallback
- 📚 **Steam collections** — installed games are grouped per store ("Epic", "GOG", "Amazon") in your library
- ⚙️ **Proton handled by Steam** — prefixes, per-game settings and FPS limits work exactly like Steam games
- 🔄 **Auto-update** — new releases install silently in the background (can be disabled in Settings)
- 🌐 **9 languages** — the interface automatically follows your console language (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Quick access** — colored store cards in the QAM, optional L3+R3 shortcut to open the store anywhere
- 🐧 **Compatibility** — we actively work to support every OS that can run Steam in Gaming Mode / Big Picture (Linux for now): portable detection, no distro-specific assumptions Per-distro package notes: [docs/OS-NOTES.md](docs/OS-NOTES.md).

## 📸 Screenshots

<p align="center">
  <img src="docs/img/skullkey-epic.jpg" width="49%" alt="Epic Games library"/>
  <img src="docs/img/skullkey-mihoyo.jpg" width="49%" alt="miHoYo tab"/>
</p>
<p align="center">
  <img src="docs/img/skullkey-classics.jpg" width="49%" alt="Classics Reborn"/>
  <img src="docs/img/skullkey-game-details.jpg" width="49%" alt="Game details"/>
</p>
<p align="center">
  <img src="docs/img/skullkey-steam-collection.jpg" width="49%" alt="Steam collection"/>
  <img src="docs/img/skullkey-steam-game-page.jpg" width="49%" alt="Installed game in Steam"/>
</p>

## Installation

Via Decky Loader, no desktop needed:

1. Install [Decky Loader](https://decky.xyz/)
2. Enable **Developer Mode** in Decky's general settings
3. Decky settings → **Developer** → *Install plugin from URL*:
   `https://github.com/Necrosiak/SkullKey/releases/latest/download/SkullKey.zip`

Or build from source:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Then open the plugin and install the store dependencies from **Settings → Dependencies**.

## Usage

1. Open the Quick Access Menu (…) → SkullKey
2. Pick a store card (Epic / GOG / Amazon) and log in
3. Install a game — it lands in your Steam library with proper artwork, in a per-store collection
4. Play!

## 🐛 Issues & ideas — don't hesitate!

Found a bug, a rough edge, something misbehaving on your distro? Have an idea?
**Please open an [issue](https://github.com/Necrosiak/SkullKey/issues)** —
every report directly shapes what gets built next, and no report is too small.
To help us fix it fast, include if you can:

- your distro & version (Bazzite 42, CachyOS, Ubuntu 24.04…) and how Steam runs (Gaming Mode / Big Picture / desktop)
- the plugin version (Settings → About) and the store/tab involved
- what you did, what you expected, what happened instead
- logs: `~/homebrew/logs/SkullKey/` (dependency problems: `ensure_deps.log`)

Feature requests and "it works!" reports on unusual setups are just as
valuable — they tell us what to support next.

## Credits

SkullKey is a fork of [Junk-Store](https://github.com/ebenbruyns/junkstore) by **Eben Bruyns** (BSD-3-Clause) — thanks for the solid foundations. Store engines by the [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) and [nile](https://github.com/imLinguin/nile) projects.

This is an independent community project, not affiliated with Junk-Store, Valve, Epic Games, GOG or Amazon.

## License

BSD-3-Clause — see [LICENSE](LICENSE).
