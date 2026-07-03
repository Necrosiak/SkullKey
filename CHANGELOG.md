# Changelog

## 1.0.0 — 2026-07-03

First release of **SkeletonKey**, a fork of Junk-Store by Eben Bruyns (BSD-3-Clause).

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
