# 🗝️ SkullKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**La llave que abre todas las tiendas.** Juega a tus bibliotecas de Epic Games, GOG y Amazon Games directamente desde el modo juego en SteamOS / Bazzite: inicia sesión, instala y juega. Sin pasar por el modo escritorio.

## Características

- 🎮 **100 % modo juego** — explora, inicia sesión, instala y juega sin tocar el escritorio
- 🏪 **Tres tiendas, gratis** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)) y Amazon Games ([nile](https://github.com/imLinguin/nile))
- 📺 **Multimedia y apps** — secciones extra de TV y Vídeo, Música, Juego en la nube y Apps y herramientas (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 apps seleccionadas), actualizadas automáticamente
- 🖼️ **Accesos directos de aspecto nativo** — los juegos instalados reciben automáticamente el artwork oficial de Steam (cápsula vertical, hero, logo), con la gamesdb de GOG como respaldo
- 📚 **Colecciones de Steam** — los juegos instalados se agrupan por tienda («Epic», «GOG», «Amazon») en tu biblioteca
- ⚙️ **Proton gestionado por Steam** — prefijos, ajustes por juego y límites de FPS funcionan exactamente como en los juegos de Steam
- 🔄 **Actualización automática** — las nuevas versiones se instalan silenciosamente en segundo plano (desactivable en Ajustes)
- 🌐 **9 idiomas** — la interfaz sigue automáticamente el idioma de tu consola (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Acceso rápido** — tarjetas de colores por tienda en el QAM, atajo opcional L3+R3 para abrir la tienda en cualquier lugar

## Instalación

Descarga `SkullKey.zip` desde la [última versión](https://github.com/Necrosiak/SkullKey/releases/latest) e instálalo mediante Decky Loader (modo desarrollador → Instalar desde ZIP), o compila desde el código fuente:

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

## Créditos

SkullKey es un fork de [Junk-Store](https://github.com/ebenbruyns/junkstore) de **Eben Bruyns** (BSD-3-Clause): gracias por los sólidos cimientos. Motores de tiendas: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) y [nile](https://github.com/imLinguin/nile).

Proyecto comunitario independiente, no afiliado a Junk-Store, Valve, Epic Games, GOG ni Amazon.

## Licencia

BSD-3-Clause — ver [LICENSE](LICENSE).
