# Changelog

## 1.10.0 — 2026-07-12

### Added
- **💾 Save backup & restore** — two new actions in the game menu of the
  Epic, GOG and Amazon stores (installed games only):
  - **Backup saves** snapshots the game's progression into
    `~/.local/share/skullkey-saves`;
  - **Restore saves** (with confirmation) puts the files back at their
    original locations.
  Powered by [ludusavi](https://github.com/mtkennerly/ludusavi): a native
  binary from `PATH` is used when present, otherwise the latest release is
  downloaded automatically into an isolated directory (isolated XDG dirs —
  your own ludusavi setup is never touched). The game is matched against the
  ludusavi manifest from its store title, and the backup scans the game's own
  Proton prefix (`compatdata/<id>/pfx`), so each Steam account's saves stay
  separate.
  Note: a "No save files found" result can be legitimate — some games only
  create their save folder after the first manual save.

## 1.9.0 — 2026-07-10

### Added
- **Classics Reborn grows to 52 ports** — 5 more legendary classics:
  **Freespace 2** (FreeSpace Open engine), **Unreal Tournament (1999)**
  (OldUnreal patch 469, native 64-bit Linux client), **LEGO Island**
  (isle-portable decompilation), **Freelancer** (Librelancer engine) and
  **Might and Magic VI–VIII** (OpenEnroth). Official Linux release binaries
  only, descriptions and original-files instructions in 9 languages.
- **docs/OS-NOTES.md** — per-distro package notes (Arch/CachyOS, Fedora,
  Bazzite/SteamOS, Debian/Ubuntu, openSUSE) for every feature that touches
  the system, linked from the READMEs.

### Changed
- The port executable finder now accepts glob hints (needed when the binary
  name is versioned, like Freespace 2's AppImage).
- READMEs (9 languages) refreshed: new "Issues & ideas — don't hesitate!"
  section explaining exactly what to include in a report, updated Classics
  count and the per-distro notes link.

## 1.8.2 — 2026-07-10

### Fixed
- **Debian/Ubuntu: store dependencies now install correctly — or say exactly
  why not.** Stock Debian/Ubuntu passes the old `import venv` probe but cannot
  actually create a virtualenv (`ensurepip` is stripped from the base python
  package), so the Epic/GOG/Amazon clients silently failed to build. The probe
  now tests `ensurepip`, and when no usable python is found the log shows the
  exact install command for the detected OS
  (`sudo apt install python3 python3-venv`, `sudo pacman -S python`, …).
- **Protontricks button: clear error instead of a dead path.** Without a
  native protontricks and without flatpak, the button used to point at a
  nonexistent `/bin/flatpak` and fail silently; it now shows what to install.

### Added
- openSUSE (`zypper`) is now covered by the OS-specific install hints.

## 1.8.1 — 2026-07-09

### Fixed
- **Update failures are now visible.** When installing an update fails (for
  example on a root-owned local install: Permission denied), the About panel
  shows the error instead of staying on "updating…" forever.

## 1.8.0 — 2026-07-09

### Changed
- **Stand-alone across distros — one build that checks what the machine has.**
  Nothing is assumed installed anymore: every external tool is detected at
  runtime, and when something is missing the plugin shows the exact install
  command for the detected OS (pacman / rpm-ostree / dnf / apt).
- **Epic no longer requires flatpak.** legendary now installs into a dedicated
  pip venv (same model as GOG/Amazon) when the legendary flatpak is not
  present; an existing flatpak install keeps working and stays preferred.
  Both backends share the same per-Steam-account login, so switching is
  seamless. Fixes the Epic tab erroring out on CachyOS/Arch installs without
  flatpak.
- **Epic dependencies now auto-provision at boot** like GOG and Amazon (small
  self-contained venv, silent).
- **protontricks**: the native binary is preferred when present; the flatpak
  remains the fallback.

### Added
- **Amazon login pre-check.** The login window needs the system GTK3 + WebKit2
  python bindings (present on Bazzite, not on stock Arch). The login button now
  checks them first and shows the exact package command for your OS instead of
  silently never opening a window.
- **git presence check** before installing nile (it is built from a local
  clone), with a clear message when missing.

## 1.7.0 — 2026-07-06

### Added
- **Classics Reborn grows to 47 ports** — 8 more open-source native ports &
  recompilations of classics: OpenTESArena (The Elder Scrolls: Arena),
  Arx Libertatis (Arx Fatalis), BStone (Blake Stone), OpenJazz (Jazz
  Jackrabbit), OpenBOR (Beats of Rage engine), OpenRA: Tiberian Dawn (C&C) and
  OpenRA: Dune 2000, and Warzone 2100. Official Linux release binaries, with
  original-files instructions in 9 languages.

## 1.6.0 — 2026-07-06

### Added
- **Voice-over picker** for miHoYo games. The game menu now has "Voice: English
  / 日本語 / 中文 / 한국어 / match console language" entries — pick a dub
  language and the pack is set and downloaded (for an installed game). Builds on
  the voice management added in 1.5.0.
- **Disk-space precheck.** The game size now also shows the free space on the
  install drive, and flags a fresh install that wouldn't fit
  ("⚠ not enough free space") before you start it.

## 1.5.0 — 2026-07-06

### Added
- **Verify & Repair for miHoYo games.** The "Verify / Repair" button now does a
  real integrity check: every file is re-hashed against the manifest (the
  trust-the-registry shortcut is bypassed) and only the corrupted or missing
  files are re-downloaded. Useful after a crash, power loss or a bad update.
- **Voice-over pack management for miHoYo games.** A fresh install now
  auto-selects the dub language pack matching the console language (English
  fallback for languages without a native VO) instead of leaving it to the
  in-game downloader. The selection is stored per game; `get-voices` /
  `set-voices` backend actions expose available packs and let the choice change
  (a picker UI can build on them). Existing installs are left untouched — no
  surprise multi-GB voice download.

## 1.4.2 — 2026-07-06

### Changed
- miHoYo game details now include a **controller note** (9 languages): the HoYo
  login screen is mouse-driven, so navigate it with keyboard/mouse and enable
  the controller layout in-game once logged in.

## 1.4.1 — 2026-07-06

### Fixed
- **miHoYo games no longer report "insufficient disk space" on immutable
  systems** (Bazzite/SteamOS). There the root `/` (composefs/ostree) is
  read-only with 0 bytes free and Wine maps `Z:` to `/`, so a game's in-game
  resource downloader that checks free space via `Z:` saw 0 free and refused
  to download — even with hundreds of GB free on `/var/home`. The launcher now
  sets up a Proton game drive (`s:`) pointing at the games folder: it exports
  `PROTON_SET_GAME_DRIVE=1` (the value must be exactly `1`; the previous
  `gamedrive` was a silent no-op) **and** `STEAM_COMPAT_LIBRARY_PATHS` (a
  parent of the install path — Proton skips the game drive without it, which
  Steam sets for real games but not for non-Steam shortcuts). The game then
  sees the real free space. Surfaced by Zenless Zone Zero; applies to all
  miHoYo games.

## 1.4.0 — 2026-07-06

### Added
- **Zenless Zone Zero (ZZZ) anti-cheat handled automatically.** ZZZ is not
  supported by jadeite; instead its global build runs on Proton with no
  anti-cheat bypass when the game's `config.ini` uses the Epic Games Store
  channel (`channel=1`, `sub_channel=3`, `cps=pcepic`). SkullKey now merges
  those keys into `config.ini` (preserving any other keys) at install and
  before every launch, so ZZZ starts on Proton out of the box. A recent Proton
  (GE-Proton recommended) is advised — the game details page says so. Community
  fix (jadeite issue #58 → notabug.org/Krock/dawn).

## 1.3.0 — 2026-07-06

### Added
- **Delta updates for miHoYo games.** A version bump now downloads only the
  *difference* between your installed version and the new one, instead of
  re-fetching every changed file in full. It uses HoYo's official sophon patch
  channel (`getPatchBuild`) and applies the per-file hdiff patches with
  `hpatchz` (HDiffPatch), auto-provisioned for your CPU architecture. For a
  Genshin version bump this is on the order of ~16 GB instead of ~74 GB.
  Fully additive and safe: any file that can't be patched (new file, a source
  file that doesn't match, or any error) automatically falls back to the
  normal chunk download, so the result is always a correct, verified install.

## 1.2.1 — 2026-07-06

### Changed
- **Store dependencies now auto-detect the OS.** The GOG (gogdl) and Amazon
  (nile) virtualenvs are built with the Python that works on the current OS:
  the Homebrew Python on Bazzite/SteamOS (whose atomic system Python lacks dev
  headers), or the system `python3` on Arch/CachyOS/Fedora/Debian (headers
  available). Bazzite behaviour is unchanged.
- `install-local.sh` derives the target user/home instead of hardcoding
  `/var/home/bazzite`, so the maintainer install script works off
  Fedora-atomic too.

## 1.2.0 — 2026-07-06

### Added
- **Multi-account** — every Steam account on the machine now has its own
  store space: Epic/GOG/Amazon logins, libraries, settings and Steam-shortcut
  mappings are per-account (`accounts/<accountid>/` in the plugin data dir),
  while installed game files stay shared on disk. The active account is
  resolved on every backend call (portable detection: `registry.vdf`
  ActiveUser, then `loginusers.vdf` MostRecent), so switching the Steam user
  takes effect immediately — no watcher, no restart. Existing logins are
  adopted by the account active at first run. Epic (legendary) is a flatpak
  that forces its XDG paths, so its per-account config is selected by
  atomically retargeting the `config/legendary` symlink.
- The daily games auto-update now iterates over **every account's** installed
  games (Epic/GOG/Amazon), not just the active one.

### Notes
- Repository made public — plugin auto-update (release-based) now works for
  everyone.

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
