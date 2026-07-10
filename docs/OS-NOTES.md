# OS notes — SkullKey on any Linux distribution

SkullKey ships **one build for every Linux distro**. Nothing is assumed
installed: every external tool is detected at runtime, and when something is
missing the plugin shows (in the QAM or in the logs) the **exact install
command for the package manager it detected** (pacman / rpm-ostree / dnf /
zypper / apt). This page sums up what each feature relies on, so you can
prepare a machine ahead of time or fix a missing dependency at a glance.

The plugin itself only requires **Steam + [Decky Loader](https://decky.xyz/)**
— any distro able to run Steam in Gaming Mode / Big Picture works.

## Store clients (Epic / GOG / Amazon)

The store backends (legendary, gogdl, nile) are built automatically at boot
into small self-contained pip virtualenvs. This needs a `python3` able to
create virtualenvs (with `ensurepip`):

| Distro | What to do |
|---|---|
| Arch / CachyOS | nothing — `python` ships with venv support |
| Fedora | nothing — `python3` ships with venv support |
| Bazzite / SteamOS | nothing — the Homebrew python is used automatically |
| Debian / Ubuntu | `sudo apt install python3 python3-venv` (stock installs strip `ensurepip`) |
| openSUSE | `sudo zypper install python3` |

If a **legendary flatpak** is already installed (historical Bazzite setups),
it keeps being used — both backends share the same login.

`git` is also needed once to build the Amazon client (nile):
`pacman -S git` / `dnf install git` / `apt install git` / `zypper install git`.

## Amazon login window

The Amazon login opens in a small GTK window and needs the system GTK3 +
WebKit2 python bindings (present on Bazzite, **not** on stock Arch):

| Distro | Command |
|---|---|
| Arch / CachyOS | `sudo pacman -S python-gobject webkit2gtk-4.1` |
| Fedora | `sudo dnf install python3-gobject webkit2gtk4.1` |
| Bazzite | `rpm-ostree install python3-gobject webkit2gtk4.1` (usually preinstalled) |
| Debian / Ubuntu | `sudo apt install python3-gi gir1.2-webkit2-4.1` |
| openSUSE | `sudo zypper install python3-gobject typelib-1_0-WebKit2-4_1` |

The login button checks this **before** opening and shows the right command
if something is missing.

## Playing the games (Proton)

Windows games from Epic/GOG/Amazon/miHoYo run through Steam's own Proton
(the bundled [umu](https://github.com/Open-Wine-Components/umu-launcher)
launcher is used under the hood) — **GE-Proton recommended**, selectable
per game in Steam like any other title. Nothing distro-specific.

## protontricks (optional)

Used by the per-game "Protontricks" button. The **native package is preferred**
(`pacman -S protontricks`, `dnf install protontricks`, `apt install protontricks`),
the flatpak (`com.github.Matoking.protontricks`) is the fallback. Without
either, the button explains what to install.

## Classics Reborn

AppImage and archive ports need nothing. A few ports ship as **flatpak
bundles** (e.g. Warzone 2100, C&C Generals) → they need `flatpak` installed.

## miHoYo store

Fully self-contained: the sophon downloader, the delta patcher (hpatchz is
auto-provisioned) and the anti-cheat helpers need no system package.

---

Something missing for your distro?
[Open an issue](https://github.com/Necrosiak/SkullKey/issues) — reports from
non-Bazzite systems are exactly what makes this page grow.
