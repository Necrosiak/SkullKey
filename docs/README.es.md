# 🗝️ SkullKey

> 🌐 [EN](../README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**La llave que abre todas las tiendas.** Juega a tus bibliotecas de Epic Games, GOG y Amazon Games directamente desde el modo juego en SteamOS / Bazzite: inicia sesión, instala y juega. Sin pasar por el modo escritorio.

## Características

- 🎮 **100 % modo juego** — explora, inicia sesión, instala y juega sin tocar el escritorio
- 🏪 **Cuatro tiendas, gratis** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)), Amazon Games ([nile](https://github.com/imLinguin/nile)) y **miHoYo/HoYoverse**
- ✨ **Tienda miHoYo** — Genshin Impact, Honkai: Star Rail, Zenless Zone Zero y Honkai Impact 3rd, instalados desde el canal oficial *sophon* de HoYoverse: descargas por chunks en paralelo (~100 MB/s), actualizaciones que solo bajan los archivos modificados, reanudación tras reinicio, anti-cheat gestionado automáticamente (jadeite) para HI3/HSR
- 🩹 **Extras miHoYo** — actualizaciones delta (solo el diff, ~4× más pequeñas), selector de idioma de doblaje, **verificación y reparación** de integridad, y anti-trampas de Zenless Zone Zero gestionado automáticamente
- 🏛️ **Classics Reborn** — 52 ports nativos open source y recompilaciones de clásicos (Zelda, Mario 64, Perfect Dark, Diablo, Fallout, Doom, C&C Generals, Morrowind, Sonic Unleashed, Unreal Tournament, Freespace 2, LEGO Island…), instalados desde las releases oficiales de cada proyecto, con instrucciones claras para tus archivos de juego originales (9 idiomas)
- ⛏️ **Minecraft** — Java Edition (mediante [Prism Launcher](https://prismlauncher.org), preconfigurado: inicia sesión con tu cuenta Microsoft y juega), Bedrock Edition (mediante [mcpelauncher](https://mcpelauncher.readthedocs.io) desde Flathub, mando nativo) y **modpacks de Modrinth** como accesos directos de Steam en un clic (búsqueda en vivo, versión fijable o actualizaciones automáticas diarias, copia automática de los mundos antes de cada cambio de versión)
- 👥 **Un espacio de tiendas por cuenta de Steam (multicuenta)** — cada usuario de Steam de la máquina tiene sus propios logins y bibliotecas de Epic/GOG/Amazon; cambiar de cuenta de Steam lo cambia todo automáticamente (los logins existentes quedan con la cuenta activa en el primer uso)
- 📦 **Actualización automática de juegos** — una pasada diaria en segundo plano mantiene al día todos los juegos instalados, en todas las tiendas y para todas las cuentas
- 💾 **Copia y restauración de partidas guardadas** — respalda el progreso de un juego desde su página con una acción (vía [ludusavi](https://github.com/mtkennerly/ludusavi), aprovisionado automáticamente) y restáuralo cuando quieras — juegos de Epic, GOG y Amazon, copias en `~/.local/share/skullkey-saves`
- 📺 **Multimedia y apps** — secciones extra de TV y Vídeo, Música, Juego en la nube y Apps y herramientas (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 apps seleccionadas), actualizadas automáticamente
- 🖼️ **Accesos directos de aspecto nativo** — los juegos instalados reciben automáticamente el artwork oficial de Steam (cápsula vertical, hero, logo), con la gamesdb de GOG como respaldo
- 📚 **Colecciones de Steam** — los juegos instalados se agrupan por tienda («Epic», «GOG», «Amazon») en tu biblioteca
- ⚙️ **Proton gestionado por Steam** — prefijos, ajustes por juego y límites de FPS funcionan exactamente como en los juegos de Steam
- 🔄 **Actualización automática** — las nuevas versiones se instalan silenciosamente en segundo plano (desactivable en Ajustes)
- 🌐 **9 idiomas** — la interfaz sigue automáticamente el idioma de tu consola (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Acceso rápido** — tarjetas de colores por tienda en el QAM, atajo opcional L3+R3 para abrir la tienda en cualquier lugar
- 🐧 **Compatibilidad** — trabajamos activamente para soportar todos los SO capaces de ejecutar Steam en modo juego / Big Picture (Linux por ahora): detección portable, sin suposiciones específicas de distribución Notas por distribución: [docs/OS-NOTES.md](OS-NOTES.md).

## 📸 Capturas de pantalla

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

## Instalación

Vía Decky Loader, sin pasar por el escritorio:

1. Instala [Decky Loader](https://decky.xyz/)
2. Activa el **modo desarrollador** en los ajustes generales de Decky
3. Ajustes de Decky → **Desarrollador** → *Instalar plugin desde URL*:
   `https://github.com/Necrosiak/SkullKey/releases/latest/download/SkullKey.zip`

O compila desde las fuentes:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Después abre el plugin e instala las dependencias de las tiendas desde **Ajustes → Dependencias**.

## Uso

1. Abre el menú de acceso rápido (…) → SkullKey
2. Elige una tarjeta de tienda (Epic / GOG / Amazon) e inicia sesión
3. Instala un juego: llegará a tu biblioteca de Steam con su artwork, en una colección por tienda
4. ¡A jugar!

## 🐛 Issues e ideas — ¡no lo dudes!

¿Un bug, algo que chirría, un comportamiento raro en tu distribución? ¿Una
idea? **Abre una [issue](https://github.com/Necrosiak/SkullKey/issues)** —
cada informe orienta directamente lo que se construye después, y ningún
informe es demasiado pequeño. Para ayudarnos a arreglarlo rápido, incluye si
puedes:

- tu distribución y versión (Bazzite 42, CachyOS, Ubuntu 24.04…) y cómo corre Steam (modo juego / Big Picture / escritorio)
- la versión del plugin (Ajustes → Acerca de) y la tienda/pestaña afectada
- qué hiciste, qué esperabas, qué pasó en su lugar
- logs: `~/homebrew/logs/SkullKey/` (problemas de dependencias: `ensure_deps.log`)

Las peticiones de funciones y los informes de «¡funciona!» en configuraciones
inusuales valen igual — nos dicen qué soportar después.

## Créditos

SkullKey es un fork de [Junk-Store](https://github.com/ebenbruyns/junkstore) de **Eben Bruyns** (BSD-3-Clause): gracias por los sólidos cimientos. Motores de tiendas: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) y [nile](https://github.com/imLinguin/nile).

Proyecto comunitario independiente, no afiliado a Junk-Store, Valve, Epic Games, GOG ni Amazon.

## Licencia

BSD-3-Clause — ver [LICENSE](../LICENSE).
