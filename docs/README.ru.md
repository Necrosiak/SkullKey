# 🗝️ SkullKey

> 🌐 [EN](../README.md) · [FR](README.fr.md) · [DE](README.de.md) · [ES](README.es.md) · [IT](README.it.md) · [PT](README.pt.md) · [NL](README.nl.md) · [PL](README.pl.md) · [RU](README.ru.md)

**Ключ, открывающий все магазины.** Играйте в библиотеки Epic Games, GOG и Amazon Games прямо из игрового режима на SteamOS / Bazzite — вход, установка, запуск. Без рабочего стола.

## Возможности

- 🎮 **100% игровой режим** — просматривайте, входите, устанавливайте и играйте, не касаясь рабочего стола
- 🏪 **Четыре магазина, бесплатно** — Epic Games ([Legendary](https://github.com/derrod/legendary)), GOG ([gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl)), Amazon Games ([nile](https://github.com/imLinguin/nile)) и **miHoYo/HoYoverse**
- ✨ **Магазин miHoYo** — Genshin Impact, Honkai: Star Rail, Zenless Zone Zero и Honkai Impact 3rd, установка с официального канала *sophon* HoYoverse: параллельная загрузка чанков (~100 МБ/с), обновления скачивают только изменённые файлы, возобновление после перезагрузки, античит настраивается автоматически (jadeite) для HI3/HSR
- 🩹 **Дополнения miHoYo** — дельта-обновления (только разница, ~4× меньше), выбор языка озвучки, **проверка и восстановление** целостности и автоматически обрабатываемый античит Zenless Zone Zero
- 🏛️ **Classics Reborn** — 52 нативных open-source портов и рекомпиляций классики (Zelda, Mario 64, Perfect Dark, Diablo, Fallout, Doom, C&C Generals, Morrowind, Sonic Unleashed, Unreal Tournament, Freespace 2, LEGO Island…), установка из официальных релизов каждого проекта, с понятными инструкциями для ваших оригинальных файлов игры (9 языков)
- 👥 **Отдельное пространство магазинов на каждый аккаунт Steam (мультиаккаунт)** — у каждого пользователя Steam на машине свои логины и библиотеки Epic/GOG/Amazon; смена аккаунта Steam переключает всё автоматически (существующие логины остаются за аккаунтом, активным при первом использовании)
- 📦 **Автообновление игр** — ежедневный фоновый проход держит все установленные игры в актуальном состоянии, во всех магазинах и для всех аккаунтов
- 📺 **Медиа и приложения** — дополнительные разделы: ТВ и видео, Музыка, Облачный гейминг и Приложения (Netflix, Jellyfin, Kodi, Moonlight, Lutris… 34 отобранных приложения), обновляются автоматически
- 🖼️ **Ярлыки как у родных игр** — установленные игры автоматически получают официальные обложки Steam (вертикальная капсула, hero, логотип), с gamesdb от GOG в качестве запасного варианта
- 📚 **Коллекции Steam** — установленные игры группируются по магазинам («Epic», «GOG», «Amazon») в вашей библиотеке
- ⚙️ **Proton под управлением Steam** — префиксы, настройки для каждой игры и лимиты FPS работают точно как у игр Steam
- 🔄 **Автообновление** — новые версии устанавливаются тихо в фоне (отключается в Настройках)
- 🌐 **9 языков** — интерфейс автоматически следует языку консоли (EN/FR/DE/ES/IT/PT/NL/PL/RU)
- 🕹️ **Быстрый доступ** — цветные карточки магазинов в QAM, опциональный шорткат L3+R3 для открытия магазина где угодно
- 🐧 **Совместимость** — мы активно работаем над поддержкой любой ОС, способной запускать Steam в игровом режиме / Big Picture (пока Linux): переносимое определение, никаких допущений под конкретный дистрибутив Заметки по дистрибутивам: [docs/OS-NOTES.md](OS-NOTES.md).

## 📸 Скриншоты

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

## Установка

Через Decky Loader, без рабочего стола:

1. Установите [Decky Loader](https://decky.xyz/)
2. Включите **режим разработчика** в общих настройках Decky
3. Настройки Decky → **Разработчик** → *Установить плагин по URL*:
   `https://github.com/Necrosiak/SkullKey/releases/latest/download/SkullKey.zip`

Или соберите из исходников:

```bash
pnpm install && pnpm run build
sudo bash install-local.sh
```

Затем откройте плагин и установите зависимости магазинов в **Настройки → Зависимости**.

## Использование

1. Откройте меню быстрого доступа (…) → SkullKey
2. Выберите карточку магазина (Epic / GOG / Amazon) и войдите
3. Установите игру — она появится в вашей библиотеке Steam с обложками, в коллекции магазина
4. Играйте!

## 🐛 Issues и идеи — не стесняйтесь!

Баг, шероховатость, странное поведение на вашем дистрибутиве? Есть идея?
**Откройте [issue](https://github.com/Necrosiak/SkullKey/issues)** — каждый
отчёт напрямую определяет, что будет сделано дальше, и ни один отчёт не
бывает слишком мелким. Чтобы мы быстро всё исправили, укажите по возможности:

- дистрибутив и версию (Bazzite 42, CachyOS, Ubuntu 24.04…) и как запущен Steam (игровой режим / Big Picture / рабочий стол)
- версию плагина (Настройки → О плагине) и затронутый магазин/вкладку
- что вы делали, чего ожидали, что произошло вместо этого
- логи: `~/homebrew/logs/SkullKey/` (проблемы зависимостей: `ensure_deps.log`)

Запросы функций и отчёты «работает!» на необычных конфигурациях так же
ценны — они подсказывают, что поддерживать дальше.

## Благодарности

SkullKey — форк [Junk-Store](https://github.com/ebenbruyns/junkstore) **Эбена Брюйнса** (BSD-3-Clause) — спасибо за надёжный фундамент. Движки магазинов: [Legendary](https://github.com/derrod/legendary), [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) и [nile](https://github.com/imLinguin/nile).

Независимый проект сообщества, не связанный с Junk-Store, Valve, Epic Games, GOG или Amazon.

## Лицензия

BSD-3-Clause — см. [LICENSE](../LICENSE).
