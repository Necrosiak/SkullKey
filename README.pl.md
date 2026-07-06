# 🗝️ SkullKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**Klucz, który otwiera każdy sklep.** Graj w swoje biblioteki Epic Games, GOG i Amazon Games bezpośrednio z trybu gry na SteamOS / Bazzite — logowanie, instalacja, uruchamianie. Bez trybu pulpitu.

## Funkcje

- 🎮 **100% tryb gry** — przeglądaj, loguj się, instaluj i graj bez dotykania pulpitu
- 🏪 **Trzy sklepy, za darmo** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)) i Amazon Games ([nile](https://github.com/imLinguin/nile))
- 📺 **Media i aplikacje** — dodatkowe sekcje TV i wideo, Muzyka, Granie w chmurze oraz Aplikacje i narzędzia (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 wybrane aplikacje), automatycznie aktualizowane
- 🖼️ **Natywnie wyglądające skróty** — zainstalowane gry automatycznie otrzymują oficjalne grafiki Steam (pionowa kapsuła, hero, logo), z gamesdb GOG jako zapasem
- 📚 **Kolekcje Steam** — zainstalowane gry są grupowane według sklepu („Epic", „GOG", „Amazon") w twojej bibliotece
- ⚙️ **Proton zarządzany przez Steam** — prefiksy, ustawienia gier i limity FPS działają dokładnie jak w grach Steam
- 🔄 **Automatyczne aktualizacje** — nowe wersje instalują się cicho w tle (można wyłączyć w Ustawieniach)
- 🌐 **9 języków** — interfejs automatycznie podąża za językiem konsoli (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Szybki dostęp** — kolorowe karty sklepów w QAM, opcjonalny skrót L3+R3 do otwierania sklepu w dowolnym miejscu

## Instalacja

Pobierz `SkullKey.zip` z [najnowszego wydania](https://github.com/Necrosiak/SkullKey/releases/latest) i zainstaluj przez Decky Loader (tryb dewelopera → Zainstaluj z ZIP), albo zbuduj ze źródeł:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Następnie otwórz wtyczkę i zainstaluj zależności sklepów w **Ustawienia → Zależności**.

## Użytkowanie

1. Otwórz menu szybkiego dostępu (…) → SkullKey
2. Wybierz kartę sklepu (Epic / GOG / Amazon) i zaloguj się
3. Zainstaluj grę — trafi do twojej biblioteki Steam z grafikami, w kolekcji sklepu
4. Graj!

## Podziękowania

SkullKey to fork [Junk-Store](https://github.com/ebenbruyns/junkstore) autorstwa **Ebena Bruynsa** (BSD-3-Clause) — dzięki za solidne fundamenty. Silniki sklepów: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) i [nile](https://github.com/imLinguin/nile).

Niezależny projekt społeczności, niepowiązany z Junk-Store, Valve, Epic Games, GOG ani Amazon.

## Licencja

BSD-3-Clause — zobacz [LICENSE](LICENSE).
