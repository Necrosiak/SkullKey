# Changelog

## 1.1.0 — 2026-07-06

### Renamed
- The plugin is now **SkullKey** (formerly SkeletonKey). The idempotent system
  migration in `setup-deploy-rights.sh` keeps every existing Steam shortcut
  working (compat symlinks for the old data and scripts paths). The QAM icon
  is now a skull.

### Added
- **miHoYo store** — live HoYoPlay catalog (Genshin, Honkai: Star Rail,
  Zenless Zone Zero, Honkai Impact 3rd), downloads on the official **sophon**
  chunk channel: zstd chunks over 8 parallel keep-alive streams, per-file md5
  registry so updates only fetch changed files, resume across reboots,
  composed Steam artwork (4 slots), **jadeite** auto-injection for the
  HI3/HSR anti-cheat, localized details in 9 languages.
- **Classics Reborn tab** — 39 curated open-source native ports and
  recompilations of classics (Zelda OoT/MM/TP, Mario 64 & Kart, Perfect Dark,
  Star Fox 64, Diablo, Fallout 1&2, Doom, Doom 3, Quake, C&C Generals +
  Zero Hour built from EA's released source, Morrowind, RollerCoaster
  Tycoon 2, Heroes III, Gothic II, Sonic Unleashed…), official GitHub release
  binaries only, three install kinds (AppImage / archive / **Flatpak
  bundle**), original-files instructions localized in 9 languages, daily
  silent auto-update.
- **Daily auto-update orchestrator** (`autoupdate_games.py`) covering every
  store: Epic, GOG, Amazon, miHoYo and the Classics.
- Media section: enriched localized descriptions for the 34 apps
  (`media_i18n.py`).

### Fixed
- Stale hero banner / double logo: opening a game page now re-applies the 4
  artwork slots from the disk cache and heals stale Steam shortcut IDs.
- Persistent download bar on every platform (shared GameDetailsItem).
- Store language detection in Game Mode (plugin_loader runs without LANG —
  `/etc/locale.conf` fallback).
- Audio crackle in the store launchers (`PULSE_LATENCY_MSEC`).

## 1.0.0 — 2026-07-03

First release of **SkullKey**, a fork of Junk-Store by Eben Bruyns (BSD-3-Clause).

### Added
- **GOG store** (free) — full library, login via system webview, install/update/repair through gogdl, Proton prefixes via UMU
- **Amazon Games store** (free) — full library, login via system webview, installs through nile
- **Media & apps sections** — four extra tabs (TV & Video, Music, Cloud Gaming, Apps & Tools) with 34 curated apps installable from Game Mode: streaming web apps (Netflix, Disney+, Prime Video, HBO Max…) via StreamingServiceLauncher, Flathub apps (Jellyfin, Kodi, Plex, Moonlight, chiaki-ng, Lutris, Bottles, RetroDECK…) and standalone AppImages. Each app gets generated Steam artwork (brand gradient + logo) and stays up to date automatically (daily flatpak update / AppImage re-download on new build)
- **Steam collections** — installed games are automatically grouped per store ("Epic", "GOG", "Amazon") in the Steam library
- **Native Steam artwork** — installed games automatically get Steam's official capsules/hero/logo (resolved by exact title match), with GOG's gamesdb art as fallback
- **Release-based auto-update** — silent background updates (with toggle) + manual check/install button in Settings
- **Interface in 9 languages** (EN/FR/DE/ES/IT/PT/NL/PL/RU), automatically following the console language
- New UI: colored per-store cards in the QAM, themed game pages, clean Settings page (Settings / Dependencies / Logs / About)

### Changed
- Complete rename and rebrand from the Junk-Store fork base
- Settings/About page fully rewritten and reorganized

### Removed
- Upstream News feed (RSS), achievements/easter eggs, custom-backend downloader, upstream funding links
