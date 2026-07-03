# 🗝️ SkeletonKey

> 🌐 [EN](README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**Ключ, открывающий все магазины.** Играйте в библиотеки Epic Games, GOG и Amazon Games прямо из игрового режима на SteamOS / Bazzite — вход, установка, запуск. Без рабочего стола.

## Возможности

- 🎮 **100% игровой режим** — просматривайте, входите, устанавливайте и играйте, не касаясь рабочего стола
- 🏪 **Три магазина, бесплатно** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)) и Amazon Games ([nile](https://github.com/imLinguin/nile))
- 📺 **Медиа и приложения** — дополнительные разделы: ТВ и видео, Музыка, Облачный гейминг и Приложения (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 отобранных приложения), обновляются автоматически
- 🖼️ **Ярлыки как у родных игр** — установленные игры автоматически получают официальные обложки Steam (вертикальная капсула, hero, логотип), с gamesdb от GOG в качестве запасного варианта
- 📚 **Коллекции Steam** — установленные игры группируются по магазинам («Epic», «GOG», «Amazon») в вашей библиотеке
- ⚙️ **Proton под управлением Steam** — префиксы, настройки для каждой игры и лимиты FPS работают точно как у игр Steam
- 🔄 **Автообновление** — новые версии устанавливаются тихо в фоне (отключается в Настройках)
- 🌐 **9 языков** — интерфейс автоматически следует языку консоли (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Быстрый доступ** — цветные карточки магазинов в QAM, опциональный шорткат L3+R3 для открытия магазина где угодно

## Установка

Скачайте `SkeletonKey.zip` из [последнего релиза](https://github.com/Necrosiak/SkeletonKey/releases/latest) и установите через Decky Loader (режим разработчика → Установить из ZIP) или соберите из исходников:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Затем откройте плагин и установите зависимости магазинов в **Настройки → Зависимости**.

## Использование

1. Откройте меню быстрого доступа (…) → SkeletonKey
2. Выберите карточку магазина (Epic / GOG / Amazon) и войдите
3. Установите игру — она появится в вашей библиотеке Steam с обложками, в коллекции магазина
4. Играйте!

## Благодарности

SkeletonKey — форк [Junk-Store](https://github.com/ebenbruyns/junkstore) **Эбена Брюйнса** (BSD-3-Clause) — спасибо за надёжный фундамент. Движки магазинов: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) и [nile](https://github.com/imLinguin/nile).

Независимый проект сообщества, не связанный с Junk-Store, Valve, Epic Games, GOG или Amazon.

## Лицензия

BSD-3-Clause — см. [LICENSE](LICENSE).
