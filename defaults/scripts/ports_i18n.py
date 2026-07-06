#!/usr/bin/env python3
"""Localized texts for the Ports extension (9 UI languages, same rule as the
rest of SkullKey). Split out of ports.py the way media_i18n.py is: the
backend imports `desc_for`, `needs_line` and `howto_line`.

Every port needs files from the ORIGINAL game (ROM / disc image / MPQ…) that
we cannot distribute; `needs_line` explains which files and where to put them,
`howto_line` reminds that copying them requires Desktop Mode."""

import os

LANGS = ("en", "fr", "de", "es", "it", "pt", "nl", "pl", "ru")


def machine_lang_code():
    """2-letter language code of the machine locale (env vars first, then
    /etc/locale.conf — plugin_loader runs with no LANG in its environment)."""
    def _code(val):
        return val.replace("-", "_").split(":")[0].split(".")[0].split("_")[0].lower()
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        val = os.environ.get(var)
        if val:
            return _code(val)
    try:
        with open("/etc/locale.conf") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("LANG="):
                    return _code(line.split("=", 1)[1].strip().strip('"'))
    except OSError:
        pass
    return "en"


def _pick(table):
    lang = machine_lang_code()
    return table.get(lang, table["en"])


# ── how the original game files get in (templates) ──────────────────────────
# folder: ROM dropped anywhere in the game folder, auto-detected
# named:  ROM must have an exact filename
# pick:   the app asks for the file at first launch
_NEEDS_TMPL = {
    "folder": {
        "en": "Requires your own {game} ROM ({spec}): copy it into the game folder — it is picked up automatically at the next launch.",
        "fr": "Nécessite votre propre ROM de {game} ({spec}) : copiez-la dans le dossier du jeu — elle est détectée automatiquement au prochain lancement.",
        "de": "Benötigt dein eigenes {game}-ROM ({spec}): kopiere es in den Spielordner — es wird beim nächsten Start automatisch erkannt.",
        "es": "Requiere tu propia ROM de {game} ({spec}): cópiala en la carpeta del juego — se detecta automáticamente en el siguiente inicio.",
        "it": "Richiede la tua ROM di {game} ({spec}): copiala nella cartella del gioco — viene rilevata automaticamente al prossimo avvio.",
        "pt": "Requer a sua própria ROM de {game} ({spec}): copie-a para a pasta do jogo — é detetada automaticamente no próximo arranque.",
        "nl": "Vereist je eigen {game}-ROM ({spec}): kopieer die naar de spelmap — hij wordt bij de volgende start automatisch gevonden.",
        "pl": "Wymaga własnego ROM-u {game} ({spec}): skopiuj go do folderu gry — zostanie wykryty automatycznie przy następnym uruchomieniu.",
        "ru": "Требуется ваш собственный ROM {game} ({spec}): скопируйте его в папку игры — он будет найден автоматически при следующем запуске.",
    },
    "named": {
        "en": "Requires your own {game} ROM ({spec}), copied into the game folder under the exact name <b>{fname}</b>.",
        "fr": "Nécessite votre propre ROM de {game} ({spec}), copiée dans le dossier du jeu sous le nom exact <b>{fname}</b>.",
        "de": "Benötigt dein eigenes {game}-ROM ({spec}), kopiert in den Spielordner unter dem exakten Namen <b>{fname}</b>.",
        "es": "Requiere tu propia ROM de {game} ({spec}), copiada en la carpeta del juego con el nombre exacto <b>{fname}</b>.",
        "it": "Richiede la tua ROM di {game} ({spec}), copiata nella cartella del gioco con il nome esatto <b>{fname}</b>.",
        "pt": "Requer a sua própria ROM de {game} ({spec}), copiada para a pasta do jogo com o nome exato <b>{fname}</b>.",
        "nl": "Vereist je eigen {game}-ROM ({spec}), gekopieerd naar de spelmap met exact de naam <b>{fname}</b>.",
        "pl": "Wymaga własnego ROM-u {game} ({spec}), skopiowanego do folderu gry pod dokładną nazwą <b>{fname}</b>.",
        "ru": "Требуется ваш собственный ROM {game} ({spec}), скопированный в папку игры под точным именем <b>{fname}</b>.",
    },
    "files": {
        "en": "Requires the files of your own copy of {game} ({spec}): copy them into the game folder — they are picked up at the next launch.",
        "fr": "Nécessite les fichiers de votre propre copie de {game} ({spec}) : copiez-les dans le dossier du jeu — ils sont pris en compte au prochain lancement.",
        "de": "Benötigt die Dateien deiner eigenen Kopie von {game} ({spec}): kopiere sie in den Spielordner — sie werden beim nächsten Start erkannt.",
        "es": "Requiere los archivos de tu propia copia de {game} ({spec}): cópialos en la carpeta del juego — se detectan en el siguiente inicio.",
        "it": "Richiede i file della tua copia di {game} ({spec}): copiali nella cartella del gioco — vengono rilevati al prossimo avvio.",
        "pt": "Requer os ficheiros da sua própria cópia de {game} ({spec}): copie-os para a pasta do jogo — são detetados no próximo arranque.",
        "nl": "Vereist de bestanden van je eigen exemplaar van {game} ({spec}): kopieer ze naar de spelmap — ze worden bij de volgende start gevonden.",
        "pl": "Wymaga plików własnej kopii {game} ({spec}): skopiuj je do folderu gry — zostaną wykryte przy następnym uruchomieniu.",
        "ru": "Требуются файлы вашей собственной копии {game} ({spec}): скопируйте их в папку игры — они будут найдены при следующем запуске.",
    },
    "free": {
        "en": "Works out of the box — the original game content is free, nothing to copy.",
        "fr": "Fonctionne directement — le contenu du jeu original est gratuit, rien à copier.",
        "de": "Funktioniert sofort — der Inhalt des Originalspiels ist kostenlos, nichts zu kopieren.",
        "es": "Funciona directamente — el contenido del juego original es gratuito, nada que copiar.",
        "it": "Funziona subito — i contenuti del gioco originale sono gratuiti, niente da copiare.",
        "pt": "Funciona de imediato — o conteúdo do jogo original é gratuito, nada a copiar.",
        "nl": "Werkt direct — de content van het originele spel is gratis, niets te kopiëren.",
        "pl": "Działa od razu — zawartość oryginalnej gry jest darmowa, nic nie trzeba kopiować.",
        "ru": "Работает сразу — контент оригинальной игры бесплатен, копировать ничего не нужно.",
    },
    "optional": {
        "en": "Works right away (free content included). Optional: copy <b>{fname}</b> from your own {game} ({spec}) into the game folder to unlock the full game.",
        "fr": "Fonctionne immédiatement (contenu gratuit inclus). Optionnel : copiez <b>{fname}</b> depuis votre propre {game} ({spec}) dans le dossier du jeu pour débloquer le jeu complet.",
        "de": "Funktioniert sofort (kostenloser Inhalt enthalten). Optional: kopiere <b>{fname}</b> von deinem eigenen {game} ({spec}) in den Spielordner, um das volle Spiel freizuschalten.",
        "es": "Funciona de inmediato (contenido gratuito incluido). Opcional: copia <b>{fname}</b> de tu propio {game} ({spec}) a la carpeta del juego para desbloquear el juego completo.",
        "it": "Funziona subito (contenuto gratuito incluso). Facoltativo: copia <b>{fname}</b> dal tuo {game} ({spec}) nella cartella del gioco per sbloccare il gioco completo.",
        "pt": "Funciona de imediato (conteúdo gratuito incluído). Opcional: copie <b>{fname}</b> do seu próprio {game} ({spec}) para a pasta do jogo para desbloquear o jogo completo.",
        "nl": "Werkt meteen (gratis inhoud inbegrepen). Optioneel: kopieer <b>{fname}</b> van je eigen {game} ({spec}) naar de spelmap om het volledige spel te ontgrendelen.",
        "pl": "Działa od razu (darmowa zawartość w zestawie). Opcjonalnie: skopiuj <b>{fname}</b> z własnego {game} ({spec}) do folderu gry, aby odblokować pełną grę.",
        "ru": "Работает сразу (бесплатный контент включён). Опционально: скопируйте <b>{fname}</b> из вашей копии {game} ({spec}) в папку игры, чтобы открыть полную игру.",
    },
    "pick": {
        "en": "Requires your own copy of {game} ({spec}): the app asks for the file at first launch.",
        "fr": "Nécessite votre propre copie de {game} ({spec}) : l'application demande le fichier au premier lancement.",
        "de": "Benötigt deine eigene Kopie von {game} ({spec}): die App fragt beim ersten Start nach der Datei.",
        "es": "Requiere tu propia copia de {game} ({spec}): la aplicación pide el archivo en el primer inicio.",
        "it": "Richiede la tua copia di {game} ({spec}): l'app chiede il file al primo avvio.",
        "pt": "Requer a sua própria cópia de {game} ({spec}): a aplicação pede o ficheiro no primeiro arranque.",
        "nl": "Vereist je eigen exemplaar van {game} ({spec}): de app vraagt bij de eerste start om het bestand.",
        "pl": "Wymaga własnej kopii {game} ({spec}): aplikacja poprosi o plik przy pierwszym uruchomieniu.",
        "ru": "Требуется ваша собственная копия {game} ({spec}): приложение запросит файл при первом запуске.",
    },
}

_HOWTO = {
    "en": "⚠ Copying those files needs <b>Desktop Mode</b> — put them in <b>{dir}</b>.",
    "fr": "⚠ Copier ces fichiers demande le <b>mode Bureau</b> — placez-les dans <b>{dir}</b>.",
    "de": "⚠ Zum Kopieren dieser Dateien ist der <b>Desktop-Modus</b> nötig — lege sie in <b>{dir}</b> ab.",
    "es": "⚠ Copiar esos archivos requiere el <b>modo Escritorio</b> — colócalos en <b>{dir}</b>.",
    "it": "⚠ Copiare questi file richiede la <b>modalità Desktop</b> — mettili in <b>{dir}</b>.",
    "pt": "⚠ Copiar esses ficheiros exige o <b>modo Desktop</b> — coloque-os em <b>{dir}</b>.",
    "nl": "⚠ Voor het kopiëren van die bestanden is de <b>bureaubladmodus</b> nodig — zet ze in <b>{dir}</b>.",
    "pl": "⚠ Skopiowanie tych plików wymaga <b>trybu pulpitu</b> — umieść je w <b>{dir}</b>.",
    "ru": "⚠ Для копирования этих файлов нужен <b>режим рабочего стола</b> — поместите их в <b>{dir}</b>.",
}

# ── per-port descriptions ────────────────────────────────────────────────────
DESCS = {
    "dusklight": {
        "en": "Dusklight (formerly Dusk) — native PC port of The Legend of Zelda: Twilight Princess, built from the full decompilation. Unlocked framerate, gyro & mouse aim, mirror mode, 4K texture packs — well beyond emulation.",
        "fr": "Dusklight (ex-Dusk) — port PC natif de The Legend of Zelda: Twilight Princess, issu de la décompilation complète. Framerate débloqué, visée gyro/souris, mode miroir, packs de textures 4K — bien au-delà de l'émulation.",
        "de": "Dusklight (früher Dusk) — nativer PC-Port von The Legend of Zelda: Twilight Princess aus der vollständigen Dekompilierung. Entsperrte Framerate, Gyro- & Maus-Zielen, Spiegelmodus, 4K-Texturpakete — weit über Emulation hinaus.",
        "es": "Dusklight (antes Dusk) — port nativo para PC de The Legend of Zelda: Twilight Princess, fruto de la descompilación completa. Framerate desbloqueado, apuntado con giroscopio y ratón, modo espejo, texturas 4K — mucho más que la emulación.",
        "it": "Dusklight (ex Dusk) — port PC nativo di The Legend of Zelda: Twilight Princess, nato dalla decompilazione completa. Framerate sbloccato, mira con giroscopio e mouse, modalità specchio, texture 4K — ben oltre l'emulazione.",
        "pt": "Dusklight (antes Dusk) — port nativo para PC de The Legend of Zelda: Twilight Princess, criado a partir da descompilação completa. Framerate desbloqueado, mira por giroscópio e rato, modo espelho, texturas 4K — muito além da emulação.",
        "nl": "Dusklight (voorheen Dusk) — native pc-port van The Legend of Zelda: Twilight Princess, gebouwd op de volledige decompilatie. Onbeperkte framerate, gyro- en muisrichten, spiegelmodus, 4K-texturen — ver voorbij emulatie.",
        "pl": "Dusklight (dawniej Dusk) — natywny port PC The Legend of Zelda: Twilight Princess, zbudowany na pełnej dekompilacji. Odblokowany framerate, celowanie żyroskopem i myszą, tryb lustrzany, tekstury 4K — dużo więcej niż emulacja.",
        "ru": "Dusklight (ранее Dusk) — нативный ПК-порт The Legend of Zelda: Twilight Princess на основе полной декомпиляции. Разблокированный фреймрейт, прицеливание гироскопом и мышью, зеркальный режим, 4K-текстуры — куда больше, чем эмуляция.",
    },
    "soh": {
        "en": "Ship of Harkinian — the native PC port of The Legend of Zelda: Ocarina of Time. 60+ FPS, widescreen, gyro aim, randomizer, mods and countless quality-of-life options.",
        "fr": "Ship of Harkinian — le port PC natif de The Legend of Zelda: Ocarina of Time. 60+ FPS, écran large, visée gyro, randomizer, mods et d'innombrables options de confort.",
        "de": "Ship of Harkinian — der native PC-Port von The Legend of Zelda: Ocarina of Time. 60+ FPS, Breitbild, Gyro-Zielen, Randomizer, Mods und unzählige Komfortoptionen.",
        "es": "Ship of Harkinian — el port nativo para PC de The Legend of Zelda: Ocarina of Time. 60+ FPS, pantalla panorámica, apuntado con giroscopio, randomizer, mods y muchísimas opciones de confort.",
        "it": "Ship of Harkinian — il port PC nativo di The Legend of Zelda: Ocarina of Time. 60+ FPS, widescreen, mira col giroscopio, randomizer, mod e tantissime opzioni di comfort.",
        "pt": "Ship of Harkinian — o port nativo para PC de The Legend of Zelda: Ocarina of Time. 60+ FPS, ecrã panorâmico, mira por giroscópio, randomizer, mods e imensas opções de conforto.",
        "nl": "Ship of Harkinian — de native pc-port van The Legend of Zelda: Ocarina of Time. 60+ FPS, breedbeeld, gyro-richten, randomizer, mods en talloze comfortopties.",
        "pl": "Ship of Harkinian — natywny port PC The Legend of Zelda: Ocarina of Time. 60+ FPS, szeroki ekran, celowanie żyroskopem, randomizer, mody i mnóstwo udogodnień.",
        "ru": "Ship of Harkinian — нативный ПК-порт The Legend of Zelda: Ocarina of Time. 60+ FPS, широкий экран, гиро-прицеливание, рандомайзер, моды и масса удобств.",
    },
    "2s2h": {
        "en": "2 Ship 2 Harkinian — the native PC port of The Legend of Zelda: Majora's Mask, by the Ship of Harkinian team. High framerate, widescreen, enhancements and mod support.",
        "fr": "2 Ship 2 Harkinian — le port PC natif de The Legend of Zelda: Majora's Mask, par l'équipe de Ship of Harkinian. Framerate élevé, écran large, améliorations et support des mods.",
        "de": "2 Ship 2 Harkinian — der native PC-Port von The Legend of Zelda: Majora's Mask, vom Ship-of-Harkinian-Team. Hohe Framerate, Breitbild, Verbesserungen und Mod-Unterstützung.",
        "es": "2 Ship 2 Harkinian — el port nativo para PC de The Legend of Zelda: Majora's Mask, del equipo de Ship of Harkinian. Framerate alto, pantalla panorámica, mejoras y soporte de mods.",
        "it": "2 Ship 2 Harkinian — il port PC nativo di The Legend of Zelda: Majora's Mask, dal team di Ship of Harkinian. Framerate elevato, widescreen, migliorie e supporto mod.",
        "pt": "2 Ship 2 Harkinian — o port nativo para PC de The Legend of Zelda: Majora's Mask, pela equipa do Ship of Harkinian. Framerate alto, ecrã panorâmico, melhorias e suporte de mods.",
        "nl": "2 Ship 2 Harkinian — de native pc-port van The Legend of Zelda: Majora's Mask, door het Ship of Harkinian-team. Hoge framerate, breedbeeld, verbeteringen en modondersteuning.",
        "pl": "2 Ship 2 Harkinian — natywny port PC The Legend of Zelda: Majora's Mask od zespołu Ship of Harkinian. Wysoki framerate, szeroki ekran, ulepszenia i wsparcie modów.",
        "ru": "2 Ship 2 Harkinian — нативный ПК-порт The Legend of Zelda: Majora's Mask от команды Ship of Harkinian. Высокий фреймрейт, широкий экран, улучшения и поддержка модов.",
    },
    "zelda64recomp": {
        "en": "Zelda 64: Recompiled — Majora's Mask brought to PC through static recompilation. Instant load times, ultrawide, gyro aim, high framerate — the easiest setup of all.",
        "fr": "Zelda 64: Recompiled — Majora's Mask porté sur PC par recompilation statique. Chargements instantanés, ultrawide, visée gyro, framerate élevé — l'installation la plus simple de toutes.",
        "de": "Zelda 64: Recompiled — Majora's Mask per statischer Rekompilierung auf den PC gebracht. Sofortige Ladezeiten, Ultrawide, Gyro-Zielen, hohe Framerate — die einfachste Einrichtung von allen.",
        "es": "Zelda 64: Recompiled — Majora's Mask llevado a PC mediante recompilación estática. Cargas instantáneas, ultrawide, apuntado con giroscopio, framerate alto — la instalación más sencilla de todas.",
        "it": "Zelda 64: Recompiled — Majora's Mask portato su PC con la ricompilazione statica. Caricamenti istantanei, ultrawide, mira col giroscopio, framerate elevato — la configurazione più semplice di tutte.",
        "pt": "Zelda 64: Recompiled — Majora's Mask trazido para PC por recompilação estática. Carregamentos instantâneos, ultrawide, mira por giroscópio, framerate alto — a configuração mais simples de todas.",
        "nl": "Zelda 64: Recompiled — Majora's Mask naar de pc gebracht via statische hercompilatie. Directe laadtijden, ultrawide, gyro-richten, hoge framerate — de simpelste setup van allemaal.",
        "pl": "Zelda 64: Recompiled — Majora's Mask przeniesiona na PC dzięki statycznej rekompilacji. Błyskawiczne wczytywanie, ultrawide, celowanie żyroskopem, wysoki framerate — najprostsza konfiguracja ze wszystkich.",
        "ru": "Zelda 64: Recompiled — Majora's Mask на ПК через статическую рекомпиляцию. Мгновенные загрузки, ultrawide, гиро-прицеливание, высокий фреймрейт — самая простая установка из всех.",
    },
    "starship": {
        "en": "Starship — native PC port of Star Fox 64, by the Ship of Harkinian team. High framerate, widescreen and enhancements for the classic rail shooter.",
        "fr": "Starship — port PC natif de Star Fox 64, par l'équipe de Ship of Harkinian. Framerate élevé, écran large et améliorations pour le rail shooter culte.",
        "de": "Starship — nativer PC-Port von Star Fox 64, vom Ship-of-Harkinian-Team. Hohe Framerate, Breitbild und Verbesserungen für den kultigen Rail-Shooter.",
        "es": "Starship — port nativo para PC de Star Fox 64, del equipo de Ship of Harkinian. Framerate alto, pantalla panorámica y mejoras para el mítico shooter sobre raíles.",
        "it": "Starship — port PC nativo di Star Fox 64, dal team di Ship of Harkinian. Framerate elevato, widescreen e migliorie per il leggendario rail shooter.",
        "pt": "Starship — port nativo para PC de Star Fox 64, pela equipa do Ship of Harkinian. Framerate alto, ecrã panorâmico e melhorias para o lendário rail shooter.",
        "nl": "Starship — native pc-port van Star Fox 64, door het Ship of Harkinian-team. Hoge framerate, breedbeeld en verbeteringen voor de klassieke railshooter.",
        "pl": "Starship — natywny port PC Star Fox 64 od zespołu Ship of Harkinian. Wysoki framerate, szeroki ekran i ulepszenia kultowego rail shootera.",
        "ru": "Starship — нативный ПК-порт Star Fox 64 от команды Ship of Harkinian. Высокий фреймрейт, широкий экран и улучшения культового рельсового шутера.",
    },
    "spaghettikart": {
        "en": "SpaghettiKart — native PC port of Mario Kart 64, by the Ship of Harkinian team. Higher resolutions, enhancements and mod support for the kart classic.",
        "fr": "SpaghettiKart — port PC natif de Mario Kart 64, par l'équipe de Ship of Harkinian. Résolutions supérieures, améliorations et support des mods pour le kart culte.",
        "de": "SpaghettiKart — nativer PC-Port von Mario Kart 64, vom Ship-of-Harkinian-Team. Höhere Auflösungen, Verbesserungen und Mod-Unterstützung für den Kart-Klassiker.",
        "es": "SpaghettiKart — port nativo para PC de Mario Kart 64, del equipo de Ship of Harkinian. Resoluciones más altas, mejoras y soporte de mods para el clásico de karts.",
        "it": "SpaghettiKart — port PC nativo di Mario Kart 64, dal team di Ship of Harkinian. Risoluzioni più alte, migliorie e supporto mod per il classico dei kart.",
        "pt": "SpaghettiKart — port nativo para PC de Mario Kart 64, pela equipa do Ship of Harkinian. Resoluções mais altas, melhorias e suporte de mods para o clássico de karts.",
        "nl": "SpaghettiKart — native pc-port van Mario Kart 64, door het Ship of Harkinian-team. Hogere resoluties, verbeteringen en modondersteuning voor de kartklassieker.",
        "pl": "SpaghettiKart — natywny port PC Mario Kart 64 od zespołu Ship of Harkinian. Wyższe rozdzielczości, ulepszenia i wsparcie modów dla klasyka kartingu.",
        "ru": "SpaghettiKart — нативный ПК-порт Mario Kart 64 от команды Ship of Harkinian. Более высокие разрешения, улучшения и поддержка модов для классики картинга.",
    },
    "sm64coopdx": {
        "en": "sm64coopdx — Super Mario 64 with online co-op! Play the classic together over the network, with character mods and Lua extensions.",
        "fr": "sm64coopdx — Super Mario 64 en coop en ligne ! Jouez au classique à plusieurs en réseau, avec mods de personnages et extensions Lua.",
        "de": "sm64coopdx — Super Mario 64 mit Online-Koop! Spielt den Klassiker gemeinsam übers Netzwerk, mit Charakter-Mods und Lua-Erweiterungen.",
        "es": "sm64coopdx — ¡Super Mario 64 con cooperativo online! Juega al clásico en red con amigos, con mods de personajes y extensiones Lua.",
        "it": "sm64coopdx — Super Mario 64 in co-op online! Gioca al classico in rete con gli amici, con mod dei personaggi ed estensioni Lua.",
        "pt": "sm64coopdx — Super Mario 64 com cooperativo online! Jogue o clássico em rede com amigos, com mods de personagens e extensões Lua.",
        "nl": "sm64coopdx — Super Mario 64 met online co-op! Speel de klassieker samen via het netwerk, met karaktermods en Lua-extensies.",
        "pl": "sm64coopdx — Super Mario 64 z kooperacją online! Graj w klasyka wspólnie przez sieć, z modami postaci i rozszerzeniami Lua.",
        "ru": "sm64coopdx — Super Mario 64 с онлайн-кооперативом! Играйте в классику вместе по сети, с модами персонажей и Lua-расширениями.",
    },
    "perfect-dark": {
        "en": "Native PC port of Perfect Dark (N64). Modern mouse+keyboard or gamepad controls, 60 FPS, widescreen — the legendary spy shooter as it deserves.",
        "fr": "Port PC natif de Perfect Dark (N64). Contrôles modernes souris+clavier ou manette, 60 FPS, écran large — le shooter d'espionnage culte comme il le mérite.",
        "de": "Nativer PC-Port von Perfect Dark (N64). Moderne Maus+Tastatur- oder Gamepad-Steuerung, 60 FPS, Breitbild — der legendäre Agenten-Shooter, wie er es verdient.",
        "es": "Port nativo para PC de Perfect Dark (N64). Controles modernos con ratón+teclado o mando, 60 FPS, pantalla panorámica — el legendario shooter de espías como se merece.",
        "it": "Port PC nativo di Perfect Dark (N64). Controlli moderni mouse+tastiera o gamepad, 60 FPS, widescreen — il leggendario sparatutto di spionaggio come merita.",
        "pt": "Port nativo para PC de Perfect Dark (N64). Controlos modernos com rato+teclado ou comando, 60 FPS, ecrã panorâmico — o lendário shooter de espionagem como merece.",
        "nl": "Native pc-port van Perfect Dark (N64). Moderne muis+toetsenbord- of gamepadbesturing, 60 FPS, breedbeeld — de legendarische spionageshooter zoals het hoort.",
        "pl": "Natywny port PC Perfect Dark (N64). Nowoczesne sterowanie myszą+klawiaturą lub padem, 60 FPS, szeroki ekran — legendarna strzelanka szpiegowska w należnej formie.",
        "ru": "Нативный ПК-порт Perfect Dark (N64). Современное управление мышью+клавиатурой или геймпадом, 60 FPS, широкий экран — легендарный шпионский шутер в достойном виде.",
    },
    "sonic3air": {
        "en": "Sonic 3 – Angel Island Revisited: fan remaster of Sonic 3 & Knuckles. Widescreen, 60 FPS, time attack, achievements and tons of options.",
        "fr": "Sonic 3 – Angel Island Revisited : remaster fan de Sonic 3 & Knuckles. Écran large, 60 FPS, time attack, succès et des tonnes d'options.",
        "de": "Sonic 3 – Angel Island Revisited: Fan-Remaster von Sonic 3 & Knuckles. Breitbild, 60 FPS, Time Attack, Erfolge und jede Menge Optionen.",
        "es": "Sonic 3 – Angel Island Revisited: remáster fan de Sonic 3 & Knuckles. Pantalla panorámica, 60 FPS, contrarreloj, logros y toneladas de opciones.",
        "it": "Sonic 3 – Angel Island Revisited: remaster fan di Sonic 3 & Knuckles. Widescreen, 60 FPS, time attack, obiettivi e tonnellate di opzioni.",
        "pt": "Sonic 3 – Angel Island Revisited: remaster de fãs de Sonic 3 & Knuckles. Ecrã panorâmico, 60 FPS, contrarrelógio, conquistas e toneladas de opções.",
        "nl": "Sonic 3 – Angel Island Revisited: fan-remaster van Sonic 3 & Knuckles. Breedbeeld, 60 FPS, time attack, prestaties en bergen opties.",
        "pl": "Sonic 3 – Angel Island Revisited: fanowski remaster Sonic 3 & Knuckles. Szeroki ekran, 60 FPS, time attack, osiągnięcia i mnóstwo opcji.",
        "ru": "Sonic 3 – Angel Island Revisited: фанатский ремастер Sonic 3 & Knuckles. Широкий экран, 60 FPS, тайм-атака, достижения и масса настроек.",
    },
    "devilutionx": {
        "en": "DevilutionX — Diablo 1 rebuilt for modern systems. Plays the free shareware content out of the box; add your original MPQ for the full game and Hellfire.",
        "fr": "DevilutionX — Diablo 1 reconstruit pour les systèmes modernes. Joue le contenu shareware gratuit direct ; ajoutez votre MPQ d'origine pour le jeu complet et Hellfire.",
        "de": "DevilutionX — Diablo 1 für moderne Systeme neu aufgebaut. Spielt den kostenlosen Shareware-Inhalt sofort; füge dein Original-MPQ für das volle Spiel und Hellfire hinzu.",
        "es": "DevilutionX — Diablo 1 reconstruido para sistemas modernos. Juega el contenido shareware gratuito de inmediato; añade tu MPQ original para el juego completo y Hellfire.",
        "it": "DevilutionX — Diablo 1 ricostruito per i sistemi moderni. Gioca subito il contenuto shareware gratuito; aggiungi il tuo MPQ originale per il gioco completo e Hellfire.",
        "pt": "DevilutionX — Diablo 1 reconstruído para sistemas modernos. Joga o conteúdo shareware gratuito de imediato; adicione o seu MPQ original para o jogo completo e Hellfire.",
        "nl": "DevilutionX — Diablo 1 herbouwd voor moderne systemen. Speelt de gratis shareware-inhoud direct; voeg je originele MPQ toe voor het volledige spel en Hellfire.",
        "pl": "DevilutionX — Diablo 1 odbudowany dla współczesnych systemów. Od razu działa z darmową wersją shareware; dodaj oryginalny MPQ, aby zagrać w pełną grę i Hellfire.",
        "ru": "DevilutionX — Diablo 1, пересобранный для современных систем. Сразу играет бесплатный shareware-контент; добавьте свой оригинальный MPQ для полной игры и Hellfire.",
    },
    "opengoal": {
        "en": "OpenGOAL — Jak & Daxter reborn on PC through decompilation. The launcher installs and manages the games from your own ISO; 60 FPS, widescreen, mods.",
        "fr": "OpenGOAL — Jak & Daxter renaît sur PC par décompilation. Le launcher installe et gère les jeux depuis votre propre ISO ; 60 FPS, écran large, mods.",
        "de": "OpenGOAL — Jak & Daxter per Dekompilierung auf dem PC wiedergeboren. Der Launcher installiert und verwaltet die Spiele aus deinem eigenen ISO; 60 FPS, Breitbild, Mods.",
        "es": "OpenGOAL — Jak & Daxter renace en PC mediante descompilación. El launcher instala y gestiona los juegos desde tu propia ISO; 60 FPS, pantalla panorámica, mods.",
        "it": "OpenGOAL — Jak & Daxter rinasce su PC tramite decompilazione. Il launcher installa e gestisce i giochi dalla tua ISO; 60 FPS, widescreen, mod.",
        "pt": "OpenGOAL — Jak & Daxter renasce no PC por descompilação. O launcher instala e gere os jogos a partir do seu próprio ISO; 60 FPS, ecrã panorâmico, mods.",
        "nl": "OpenGOAL — Jak & Daxter herboren op de pc via decompilatie. De launcher installeert en beheert de games vanaf je eigen ISO; 60 FPS, breedbeeld, mods.",
        "pl": "OpenGOAL — Jak & Daxter odrodzony na PC dzięki dekompilacji. Launcher instaluje i zarządza grami z własnego ISO; 60 FPS, szeroki ekran, mody.",
        "ru": "OpenGOAL — Jak & Daxter возрождается на ПК через декомпиляцию. Лаунчер устанавливает игры с вашего собственного ISO; 60 FPS, широкий экран, моды.",
    },
    "fallout1-ce": {
        "en": "Fallout Community Edition — the original Fallout rebuilt natively. High resolutions, smooth scaling, gamepad support, countless engine fixes.",
        "fr": "Fallout Community Edition — le premier Fallout reconstruit en natif. Hautes résolutions, mise à l'échelle propre, support manette, moteur corrigé de partout.",
        "de": "Fallout Community Edition — das erste Fallout nativ neu aufgebaut. Hohe Auflösungen, sauberes Skalieren, Gamepad-Support, unzählige Engine-Fixes.",
        "es": "Fallout Community Edition — el primer Fallout reconstruido en nativo. Altas resoluciones, escalado limpio, soporte de mando, motor lleno de arreglos.",
        "it": "Fallout Community Edition — il primo Fallout ricostruito in nativo. Alte risoluzioni, scaling pulito, supporto gamepad, motore pieno di fix.",
        "pt": "Fallout Community Edition — o primeiro Fallout reconstruído em nativo. Altas resoluções, escala limpa, suporte de comando, motor cheio de correções.",
        "nl": "Fallout Community Edition — de eerste Fallout native herbouwd. Hoge resoluties, strak schalen, gamepad-ondersteuning, talloze engine-fixes.",
        "pl": "Fallout Community Edition — pierwszy Fallout odbudowany natywnie. Wysokie rozdzielczości, czyste skalowanie, obsługa pada, mnóstwo poprawek silnika.",
        "ru": "Fallout Community Edition — первый Fallout, нативно пересобранный. Высокие разрешения, чистое масштабирование, поддержка геймпада, множество исправлений движка.",
    },
    "fallout2-ce": {
        "en": "Fallout 2 Community Edition — the classic RPG rebuilt natively. High resolutions, gamepad support and a pile of engine fixes.",
        "fr": "Fallout 2 Community Edition — le RPG culte reconstruit en natif. Hautes résolutions, support manette et une pile de correctifs moteur.",
        "de": "Fallout 2 Community Edition — das Kult-RPG nativ neu aufgebaut. Hohe Auflösungen, Gamepad-Support und ein Stapel Engine-Fixes.",
        "es": "Fallout 2 Community Edition — el RPG de culto reconstruido en nativo. Altas resoluciones, soporte de mando y un montón de arreglos del motor.",
        "it": "Fallout 2 Community Edition — l'RPG di culto ricostruito in nativo. Alte risoluzioni, supporto gamepad e una pila di fix del motore.",
        "pt": "Fallout 2 Community Edition — o RPG de culto reconstruído em nativo. Altas resoluções, suporte de comando e uma pilha de correções do motor.",
        "nl": "Fallout 2 Community Edition — de cult-RPG native herbouwd. Hoge resoluties, gamepad-ondersteuning en een berg engine-fixes.",
        "pl": "Fallout 2 Community Edition — kultowe RPG odbudowane natywnie. Wysokie rozdzielczości, obsługa pada i mnóstwo poprawek silnika.",
        "ru": "Fallout 2 Community Edition — культовая RPG, нативно пересобранная. Высокие разрешения, поддержка геймпада и куча исправлений движка.",
    },
    "nxengine-evo": {
        "en": "NXEngine-evo — Cave Story, the freeware masterpiece, on a modern native engine. Widescreen, smooth scaling, gamepad support.",
        "fr": "NXEngine-evo — Cave Story, le chef-d'œuvre freeware, sur un moteur natif moderne. Écran large, mise à l'échelle propre, support manette.",
        "de": "NXEngine-evo — Cave Story, das Freeware-Meisterwerk, auf einer modernen nativen Engine. Breitbild, sauberes Skalieren, Gamepad-Support.",
        "es": "NXEngine-evo — Cave Story, la obra maestra freeware, en un motor nativo moderno. Pantalla panorámica, escalado limpio, soporte de mando.",
        "it": "NXEngine-evo — Cave Story, il capolavoro freeware, su un motore nativo moderno. Widescreen, scaling pulito, supporto gamepad.",
        "pt": "NXEngine-evo — Cave Story, a obra-prima freeware, num motor nativo moderno. Ecrã panorâmico, escala limpa, suporte de comando.",
        "nl": "NXEngine-evo — Cave Story, het freeware-meesterwerk, op een moderne native engine. Breedbeeld, strak schalen, gamepad-ondersteuning.",
        "pl": "NXEngine-evo — Cave Story, freeware'owe arcydzieło, na nowoczesnym natywnym silniku. Szeroki ekran, czyste skalowanie, obsługa pada.",
        "ru": "NXEngine-evo — Cave Story, бесплатный шедевр, на современном нативном движке. Широкий экран, чистое масштабирование, поддержка геймпада.",
    },
    "openra-ra": {
        "en": "OpenRA — Command & Conquer: Red Alert remastered for modern systems, with the free original assets downloaded automatically. Skirmish, campaigns, online multiplayer.",
        "fr": "OpenRA — Command & Conquer: Red Alert remis au goût du jour, avec les assets d'origine gratuits téléchargés automatiquement. Escarmouche, campagnes, multi en ligne.",
        "de": "OpenRA — Command & Conquer: Alarmstufe Rot für moderne Systeme, die kostenlosen Original-Assets werden automatisch geladen. Gefechte, Kampagnen, Online-Multiplayer.",
        "es": "OpenRA — Command & Conquer: Red Alert modernizado, con los assets originales gratuitos descargados automáticamente. Escaramuzas, campañas, multijugador online.",
        "it": "OpenRA — Command & Conquer: Red Alert modernizzato, con gli asset originali gratuiti scaricati automaticamente. Schermaglie, campagne, multiplayer online.",
        "pt": "OpenRA — Command & Conquer: Red Alert modernizado, com os assets originais gratuitos descarregados automaticamente. Escaramuças, campanhas, multijogador online.",
        "nl": "OpenRA — Command & Conquer: Red Alert gemoderniseerd, met de gratis originele assets automatisch gedownload. Skirmish, campagnes, online multiplayer.",
        "pl": "OpenRA — Command & Conquer: Red Alert unowocześniony, darmowe oryginalne zasoby pobierane automatycznie. Potyczki, kampanie, multiplayer online.",
        "ru": "OpenRA — Command & Conquer: Red Alert для современных систем, бесплатные оригинальные ресурсы скачиваются автоматически. Схватки, кампании, онлайн-мультиплеер.",
    },
    "corsixth": {
        "en": "CorsixTH — Theme Hospital reborn on an open engine. High resolutions, modern controls and bug fixes for the cult management game.",
        "fr": "CorsixTH — Theme Hospital ressuscité sur un moteur libre. Hautes résolutions, contrôles modernes et correctifs pour le jeu de gestion culte.",
        "de": "CorsixTH — Theme Hospital auf einer offenen Engine wiedergeboren. Hohe Auflösungen, moderne Steuerung und Bugfixes für das Kult-Aufbauspiel.",
        "es": "CorsixTH — Theme Hospital renacido en un motor libre. Altas resoluciones, controles modernos y arreglos para el juego de gestión de culto.",
        "it": "CorsixTH — Theme Hospital rinato su un motore libero. Alte risoluzioni, controlli moderni e fix per il gestionale di culto.",
        "pt": "CorsixTH — Theme Hospital renascido num motor livre. Altas resoluções, controlos modernos e correções para o jogo de gestão de culto.",
        "nl": "CorsixTH — Theme Hospital herboren op een open engine. Hoge resoluties, moderne besturing en bugfixes voor de cult-managementgame.",
        "pl": "CorsixTH — Theme Hospital odrodzony na otwartym silniku. Wysokie rozdzielczości, nowoczesne sterowanie i poprawki kultowej gry menedżerskiej.",
        "ru": "CorsixTH — Theme Hospital, возрождённый на открытом движке. Высокие разрешения, современное управление и исправления культовой стратегии.",
    },
    "dhewm3": {
        "en": "dhewm3 — Doom 3 on a maintained native engine. Widescreen, modern audio (OpenAL/EFX), mod support, countless fixes.",
        "fr": "dhewm3 — Doom 3 sur un moteur natif maintenu. Écran large, audio moderne (OpenAL/EFX), support des mods, correctifs en pagaille.",
        "de": "dhewm3 — Doom 3 auf einer gepflegten nativen Engine. Breitbild, moderner Sound (OpenAL/EFX), Mod-Unterstützung, unzählige Fixes.",
        "es": "dhewm3 — Doom 3 en un motor nativo mantenido. Pantalla panorámica, audio moderno (OpenAL/EFX), soporte de mods, montones de arreglos.",
        "it": "dhewm3 — Doom 3 su un motore nativo mantenuto. Widescreen, audio moderno (OpenAL/EFX), supporto mod, fix a bizzeffe.",
        "pt": "dhewm3 — Doom 3 num motor nativo mantido. Ecrã panorâmico, áudio moderno (OpenAL/EFX), suporte de mods, imensas correções.",
        "nl": "dhewm3 — Doom 3 op een onderhouden native engine. Breedbeeld, moderne audio (OpenAL/EFX), modondersteuning, talloze fixes.",
        "pl": "dhewm3 — Doom 3 na utrzymywanym natywnym silniku. Szeroki ekran, nowoczesne audio (OpenAL/EFX), wsparcie modów, mnóstwo poprawek.",
        "ru": "dhewm3 — Doom 3 на поддерживаемом нативном движке. Широкий экран, современный звук (OpenAL/EFX), поддержка модов, масса исправлений.",
    },
    "vkquake": {
        "en": "vkQuake — the original Quake on Vulkan. Blazing performance, high resolutions, mission packs support — the shareware episode works out of the box.",
        "fr": "vkQuake — le Quake originel sous Vulkan. Performances de feu, hautes résolutions, mission packs — l'épisode shareware fonctionne direct.",
        "de": "vkQuake — das originale Quake auf Vulkan. Rasante Performance, hohe Auflösungen, Mission-Packs — die Shareware-Episode läuft sofort.",
        "es": "vkQuake — el Quake original sobre Vulkan. Rendimiento brutal, altas resoluciones, packs de misiones — el episodio shareware funciona de inmediato.",
        "it": "vkQuake — il Quake originale su Vulkan. Prestazioni al fulmicotone, alte risoluzioni, mission pack — l'episodio shareware funziona subito.",
        "pt": "vkQuake — o Quake original em Vulkan. Desempenho brutal, altas resoluções, mission packs — o episódio shareware funciona de imediato.",
        "nl": "vkQuake — de originele Quake op Vulkan. Razendsnelle prestaties, hoge resoluties, mission packs — de shareware-episode werkt direct.",
        "pl": "vkQuake — oryginalny Quake na Vulkanie. Piorunująca wydajność, wysokie rozdzielczości, mission packi — odcinek shareware działa od razu.",
        "ru": "vkQuake — оригинальный Quake на Vulkan. Бешеная производительность, высокие разрешения, mission packs — shareware-эпизод работает сразу.",
    },
    "redriver2": {
        "en": "REDRIVER2 — Driver 2 reverse-engineered and running natively. Higher framerates, higher resolutions, restored content — the PS1 classic unleashed.",
        "fr": "REDRIVER2 — Driver 2 rétro-ingénié et tournant en natif. Framerate et résolutions supérieurs, contenu restauré — le classique PS1 déchaîné.",
        "de": "REDRIVER2 — Driver 2 reverse-engineered und nativ laufend. Höhere Framerates, höhere Auflösungen, wiederhergestellte Inhalte — der PS1-Klassiker entfesselt.",
        "es": "REDRIVER2 — Driver 2 con ingeniería inversa corriendo en nativo. Más framerate, más resolución, contenido restaurado — el clásico de PS1 desatado.",
        "it": "REDRIVER2 — Driver 2 con reverse engineering, gira in nativo. Framerate e risoluzioni superiori, contenuti ripristinati — il classico PS1 scatenato.",
        "pt": "REDRIVER2 — Driver 2 com engenharia reversa a correr em nativo. Framerates e resoluções superiores, conteúdo restaurado — o clássico PS1 à solta.",
        "nl": "REDRIVER2 — Driver 2 reverse-engineered en native draaiend. Hogere framerates, hogere resoluties, hersteld content — de PS1-klassieker losgelaten.",
        "pl": "REDRIVER2 — Driver 2 po inżynierii wstecznej, działa natywnie. Wyższy framerate, wyższe rozdzielczości, przywrócona zawartość — klasyk PS1 bez ograniczeń.",
        "ru": "REDRIVER2 — Driver 2 после реверс-инжиниринга, работает нативно. Выше фреймрейт и разрешения, восстановленный контент — классика PS1 без цепей.",
    },
    "daggerfall-unity": {
        "en": "Daggerfall Unity — The Elder Scrolls II reborn in Unity. Modern rendering, mods, quality-of-life everywhere — and the original game is officially free.",
        "fr": "Daggerfall Unity — The Elder Scrolls II renaît sous Unity. Rendu moderne, mods, confort partout — et le jeu original est officiellement gratuit.",
        "de": "Daggerfall Unity — The Elder Scrolls II in Unity wiedergeboren. Modernes Rendering, Mods, Komfort überall — und das Original ist offiziell kostenlos.",
        "es": "Daggerfall Unity — The Elder Scrolls II renace en Unity. Render moderno, mods, confort por todas partes — y el juego original es oficialmente gratis.",
        "it": "Daggerfall Unity — The Elder Scrolls II rinasce in Unity. Rendering moderno, mod, comfort ovunque — e il gioco originale è ufficialmente gratuito.",
        "pt": "Daggerfall Unity — The Elder Scrolls II renasce em Unity. Render moderno, mods, conforto em todo o lado — e o jogo original é oficialmente gratuito.",
        "nl": "Daggerfall Unity — The Elder Scrolls II herboren in Unity. Moderne rendering, mods, comfort overal — en het originele spel is officieel gratis.",
        "pl": "Daggerfall Unity — The Elder Scrolls II odrodzony w Unity. Nowoczesny rendering, mody, wygoda wszędzie — a oryginalna gra jest oficjalnie darmowa.",
        "ru": "Daggerfall Unity — The Elder Scrolls II, возрождённый на Unity. Современный рендер, моды, удобства повсюду — а оригинальная игра официально бесплатна.",
    },
    "fheroes2": {
        "en": "fheroes2 — Heroes of Might and Magic II on an open engine. Better AI, high resolutions, quality-of-life galore; the free demo content works too.",
        "fr": "fheroes2 — Heroes of Might and Magic II sur un moteur libre. Meilleure IA, hautes résolutions, confort à gogo ; le contenu de la démo gratuite marche aussi.",
        "de": "fheroes2 — Heroes of Might and Magic II auf einer offenen Engine. Bessere KI, hohe Auflösungen, Komfort satt; der kostenlose Demo-Inhalt funktioniert auch.",
        "es": "fheroes2 — Heroes of Might and Magic II en un motor libre. Mejor IA, altas resoluciones, confort a raudales; el contenido de la demo gratuita también funciona.",
        "it": "fheroes2 — Heroes of Might and Magic II su un motore libero. IA migliore, alte risoluzioni, comfort a volontà; funziona anche il contenuto della demo gratuita.",
        "pt": "fheroes2 — Heroes of Might and Magic II num motor livre. IA melhor, altas resoluções, conforto à farta; o conteúdo da demo gratuita também funciona.",
        "nl": "fheroes2 — Heroes of Might and Magic II op een open engine. Betere AI, hoge resoluties, volop comfort; de gratis demo-content werkt ook.",
        "pl": "fheroes2 — Heroes of Might and Magic II na otwartym silniku. Lepsze AI, wysokie rozdzielczości, mnóstwo udogodnień; darmowa zawartość demo też działa.",
        "ru": "fheroes2 — Heroes of Might and Magic II на открытом движке. Улучшенный ИИ, высокие разрешения, море удобств; бесплатный демо-контент тоже работает.",
    },
    "trx": {
        "en": "TRX — Tomb Raider I & II rebuilt natively (TR1X + TR2X). Modern controls, high resolutions, restored and optional content, endless fixes.",
        "fr": "TRX — Tomb Raider I & II reconstruits en natif (TR1X + TR2X). Contrôles modernes, hautes résolutions, contenu restauré et optionnel, correctifs à l'infini.",
        "de": "TRX — Tomb Raider I & II nativ neu aufgebaut (TR1X + TR2X). Moderne Steuerung, hohe Auflösungen, wiederhergestellte und optionale Inhalte, endlose Fixes.",
        "es": "TRX — Tomb Raider I & II reconstruidos en nativo (TR1X + TR2X). Controles modernos, altas resoluciones, contenido restaurado y opcional, arreglos sin fin.",
        "it": "TRX — Tomb Raider I & II ricostruiti in nativo (TR1X + TR2X). Controlli moderni, alte risoluzioni, contenuti ripristinati e opzionali, fix infiniti.",
        "pt": "TRX — Tomb Raider I & II reconstruídos em nativo (TR1X + TR2X). Controlos modernos, altas resoluções, conteúdo restaurado e opcional, correções sem fim.",
        "nl": "TRX — Tomb Raider I & II native herbouwd (TR1X + TR2X). Moderne besturing, hoge resoluties, hersteld en optioneel content, eindeloze fixes.",
        "pl": "TRX — Tomb Raider I & II odbudowane natywnie (TR1X + TR2X). Nowoczesne sterowanie, wysokie rozdzielczości, przywrócona i opcjonalna zawartość, poprawki bez końca.",
        "ru": "TRX — Tomb Raider I и II, нативно пересобранные (TR1X + TR2X). Современное управление, высокие разрешения, восстановленный и опциональный контент, бесконечные исправления.",
    },
    "generalsx": {
        "en": "GeneralsX — Command & Conquer Generals running natively on Linux, built from the official source code EA released. Vulkan rendering (DXVK), SDL3, quality-of-life patches — the real engine, no Wine.",
        "fr": "GeneralsX — Command & Conquer Generals en natif sur Linux, compilé depuis le code source officiel libéré par EA. Rendu Vulkan (DXVK), SDL3, correctifs de confort — le vrai moteur, sans Wine.",
        "de": "GeneralsX — Command & Conquer Generals nativ unter Linux, gebaut aus dem von EA veröffentlichten offiziellen Quellcode. Vulkan-Rendering (DXVK), SDL3, Komfort-Patches — die echte Engine, ohne Wine.",
        "es": "GeneralsX — Command & Conquer Generals nativo en Linux, compilado del código fuente oficial liberado por EA. Renderizado Vulkan (DXVK), SDL3, parches de confort — el motor real, sin Wine.",
        "it": "GeneralsX — Command & Conquer Generals nativo su Linux, compilato dal codice sorgente ufficiale rilasciato da EA. Rendering Vulkan (DXVK), SDL3, patch di comfort — il vero motore, senza Wine.",
        "pt": "GeneralsX — Command & Conquer Generals nativo em Linux, compilado do código-fonte oficial libertado pela EA. Renderização Vulkan (DXVK), SDL3, patches de conforto — o motor real, sem Wine.",
        "nl": "GeneralsX — Command & Conquer Generals native op Linux, gebouwd uit de officiële broncode die EA vrijgaf. Vulkan-rendering (DXVK), SDL3, comfortpatches — de echte engine, zonder Wine.",
        "pl": "GeneralsX — Command & Conquer Generals natywnie na Linuksie, zbudowany z oficjalnego kodu źródłowego udostępnionego przez EA. Rendering Vulkan (DXVK), SDL3, patche jakości życia — prawdziwy silnik, bez Wine.",
        "ru": "GeneralsX — Command & Conquer Generals нативно на Linux, собранный из официального исходного кода, открытого EA. Vulkan-рендер (DXVK), SDL3, патчи удобства — настоящий движок, без Wine.",
    },
    "generalsx-zh": {
        "en": "GeneralsX Zero Hour — the Zero Hour expansion running natively on Linux from EA's official source code. Same engine as GeneralsX: Vulkan (DXVK), SDL3, no Wine.",
        "fr": "GeneralsX Zero Hour — l'extension Zero Hour en natif sur Linux depuis le code source officiel d'EA. Même moteur que GeneralsX : Vulkan (DXVK), SDL3, sans Wine.",
        "de": "GeneralsX Zero Hour — die Zero-Hour-Erweiterung nativ unter Linux aus EAs offiziellem Quellcode. Gleiche Engine wie GeneralsX: Vulkan (DXVK), SDL3, ohne Wine.",
        "es": "GeneralsX Zero Hour — la expansión Zero Hour nativa en Linux desde el código fuente oficial de EA. Mismo motor que GeneralsX: Vulkan (DXVK), SDL3, sin Wine.",
        "it": "GeneralsX Zero Hour — l'espansione Zero Hour nativa su Linux dal codice sorgente ufficiale di EA. Stesso motore di GeneralsX: Vulkan (DXVK), SDL3, senza Wine.",
        "pt": "GeneralsX Zero Hour — a expansão Zero Hour nativa em Linux a partir do código-fonte oficial da EA. Mesmo motor que o GeneralsX: Vulkan (DXVK), SDL3, sem Wine.",
        "nl": "GeneralsX Zero Hour — de Zero Hour-uitbreiding native op Linux uit EA's officiële broncode. Zelfde engine als GeneralsX: Vulkan (DXVK), SDL3, zonder Wine.",
        "pl": "GeneralsX Zero Hour — dodatek Zero Hour natywnie na Linuksie z oficjalnego kodu źródłowego EA. Ten sam silnik co GeneralsX: Vulkan (DXVK), SDL3, bez Wine.",
        "ru": "GeneralsX Zero Hour — дополнение Zero Hour нативно на Linux из официального исходного кода EA. Тот же движок, что и GeneralsX: Vulkan (DXVK), SDL3, без Wine.",
    },
    "openmw": {
        "en": "OpenMW — a complete open-source engine for The Elder Scrolls III: Morrowind. Modern renderer, no old-engine bugs, huge draw distances, mod support. First launch opens the wizard: point it to your Morrowind installation.",
        "fr": "OpenMW — moteur open source complet pour The Elder Scrolls III: Morrowind. Rendu moderne, bugs du vieux moteur envolés, distances d'affichage énormes, support des mods. Au premier lancement l'assistant demande où est votre installation de Morrowind.",
        "de": "OpenMW — eine komplette Open-Source-Engine für The Elder Scrolls III: Morrowind. Moderner Renderer, keine Alt-Engine-Bugs, riesige Sichtweiten, Mod-Support. Beim ersten Start fragt der Assistent nach deiner Morrowind-Installation.",
        "es": "OpenMW — un motor open source completo para The Elder Scrolls III: Morrowind. Renderizador moderno, sin bugs del motor antiguo, distancias de dibujado enormes, soporte de mods. En el primer inicio el asistente pide tu instalación de Morrowind.",
        "it": "OpenMW — un motore open source completo per The Elder Scrolls III: Morrowind. Renderer moderno, niente bug del vecchio motore, distanze visive enormi, supporto mod. Al primo avvio la procedura guidata chiede la tua installazione di Morrowind.",
        "pt": "OpenMW — um motor open source completo para The Elder Scrolls III: Morrowind. Renderizador moderno, sem bugs do motor antigo, distâncias de visão enormes, suporte a mods. No primeiro arranque o assistente pede a sua instalação do Morrowind.",
        "nl": "OpenMW — een complete opensource-engine voor The Elder Scrolls III: Morrowind. Moderne renderer, geen oude-engine-bugs, enorme kijkafstanden, modsupport. Bij de eerste start vraagt de wizard naar je Morrowind-installatie.",
        "pl": "OpenMW — kompletny otwarty silnik dla The Elder Scrolls III: Morrowind. Nowoczesny renderer, brak błędów starego silnika, ogromny zasięg widzenia, wsparcie modów. Przy pierwszym uruchomieniu kreator pyta o instalację Morrowinda.",
        "ru": "OpenMW — полноценный открытый движок для The Elder Scrolls III: Morrowind. Современный рендер, никаких багов старого движка, огромная дальность прорисовки, поддержка модов. При первом запуске мастер спросит, где установлен Morrowind.",
    },
    "openrct2": {
        "en": "OpenRCT2 — RollerCoaster Tycoon 2 rebuilt as open source. Widescreen UI, fast-forward, multiplayer, hundreds of fixes; on first launch point it to your RCT2 files (GOG/Steam).",
        "fr": "OpenRCT2 — RollerCoaster Tycoon 2 reconstruit en open source. Interface écran large, avance rapide, multijoueur, des centaines de correctifs ; au premier lancement indiquez vos fichiers RCT2 (GOG/Steam).",
        "de": "OpenRCT2 — RollerCoaster Tycoon 2 als Open Source neu aufgebaut. Breitbild-UI, Schnellvorlauf, Multiplayer, hunderte Fixes; beim ersten Start auf deine RCT2-Dateien (GOG/Steam) verweisen.",
        "es": "OpenRCT2 — RollerCoaster Tycoon 2 reconstruido en open source. Interfaz panorámica, avance rápido, multijugador, cientos de arreglos; en el primer inicio indica tus archivos de RCT2 (GOG/Steam).",
        "it": "OpenRCT2 — RollerCoaster Tycoon 2 ricostruito open source. UI widescreen, avanzamento rapido, multiplayer, centinaia di fix; al primo avvio indica i tuoi file di RCT2 (GOG/Steam).",
        "pt": "OpenRCT2 — RollerCoaster Tycoon 2 reconstruído em open source. Interface widescreen, avanço rápido, multijogador, centenas de correções; no primeiro arranque indique os seus ficheiros do RCT2 (GOG/Steam).",
        "nl": "OpenRCT2 — RollerCoaster Tycoon 2 herbouwd als open source. Breedbeeld-UI, fast-forward, multiplayer, honderden fixes; wijs bij de eerste start je RCT2-bestanden (GOG/Steam) aan.",
        "pl": "OpenRCT2 — RollerCoaster Tycoon 2 odbudowany jako open source. Panoramiczny interfejs, przyspieszanie, multiplayer, setki poprawek; przy pierwszym uruchomieniu wskaż pliki RCT2 (GOG/Steam).",
        "ru": "OpenRCT2 — RollerCoaster Tycoon 2, пересобранный как open source. Широкоэкранный интерфейс, перемотка, мультиплеер, сотни исправлений; при первом запуске укажите файлы RCT2 (GOG/Steam).",
    },
    "augustus": {
        "en": "Augustus — enhanced open-source engine for Caesar III: bigger maps, roadblocks, zoom, UI upgrades and gameplay options on top of the faithful Julius base. Point it to your Caesar III folder on first launch.",
        "fr": "Augustus — moteur open source amélioré pour Caesar III : cartes plus grandes, barrages routiers, zoom, interface modernisée et options de gameplay au-dessus de la base fidèle Julius. Indiquez votre dossier Caesar III au premier lancement.",
        "de": "Augustus — verbesserte Open-Source-Engine für Caesar III: größere Karten, Straßensperren, Zoom, UI-Upgrades und Gameplay-Optionen auf der werktreuen Julius-Basis. Beim ersten Start auf deinen Caesar-III-Ordner verweisen.",
        "es": "Augustus — motor open source mejorado para Caesar III: mapas más grandes, controles de camino, zoom, mejoras de interfaz y opciones de juego sobre la base fiel Julius. Indica tu carpeta de Caesar III en el primer inicio.",
        "it": "Augustus — motore open source potenziato per Caesar III: mappe più grandi, posti di blocco, zoom, migliorie UI e opzioni di gameplay sulla base fedele Julius. Indica la cartella di Caesar III al primo avvio.",
        "pt": "Augustus — motor open source melhorado para Caesar III: mapas maiores, bloqueios de estrada, zoom, melhorias de interface e opções de jogo sobre a base fiel Julius. Indique a pasta do Caesar III no primeiro arranque.",
        "nl": "Augustus — verbeterde opensource-engine voor Caesar III: grotere kaarten, wegblokkades, zoom, UI-upgrades en gameplay-opties bovenop de getrouwe Julius-basis. Wijs bij de eerste start je Caesar III-map aan.",
        "pl": "Augustus — ulepszony otwarty silnik dla Caesar III: większe mapy, blokady dróg, zoom, ulepszenia interfejsu i opcje rozgrywki na wiernej bazie Julius. Wskaż folder Caesar III przy pierwszym uruchomieniu.",
        "ru": "Augustus — улучшенный открытый движок для Caesar III: карты больше, дорожные посты, зум, апгрейды интерфейса и игровые опции поверх точной базы Julius. При первом запуске укажите папку Caesar III.",
    },
    "vcmi": {
        "en": "VCMI — open-source engine for Heroes of Might and Magic III. High resolutions, mod manager, reworked AI, all expansions; the launcher imports the game data from your GOG copy on first run.",
        "fr": "VCMI — moteur open source pour Heroes of Might and Magic III. Hautes résolutions, gestionnaire de mods, IA retravaillée, toutes les extensions ; le launcher importe les données de votre copie GOG au premier lancement.",
        "de": "VCMI — Open-Source-Engine für Heroes of Might and Magic III. Hohe Auflösungen, Mod-Manager, überarbeitete KI, alle Erweiterungen; der Launcher importiert die Spieldaten deiner GOG-Kopie beim ersten Start.",
        "es": "VCMI — motor open source para Heroes of Might and Magic III. Altas resoluciones, gestor de mods, IA renovada, todas las expansiones; el launcher importa los datos de tu copia de GOG en el primer inicio.",
        "it": "VCMI — motore open source per Heroes of Might and Magic III. Alte risoluzioni, gestore mod, IA rivista, tutte le espansioni; il launcher importa i dati della tua copia GOG al primo avvio.",
        "pt": "VCMI — motor open source para Heroes of Might and Magic III. Altas resoluções, gestor de mods, IA renovada, todas as expansões; o launcher importa os dados da sua cópia GOG no primeiro arranque.",
        "nl": "VCMI — opensource-engine voor Heroes of Might and Magic III. Hoge resoluties, modmanager, herziene AI, alle uitbreidingen; de launcher importeert de speldata van je GOG-kopie bij de eerste start.",
        "pl": "VCMI — otwarty silnik dla Heroes of Might and Magic III. Wysokie rozdzielczości, menedżer modów, przerobione AI, wszystkie dodatki; launcher importuje dane gry z kopii GOG przy pierwszym uruchomieniu.",
        "ru": "VCMI — открытый движок для Heroes of Might and Magic III. Высокие разрешения, менеджер модов, переработанный ИИ, все дополнения; лаунчер импортирует данные игры из вашей копии GOG при первом запуске.",
    },
    "openjk": {
        "en": "OpenJK — the community engine for Star Wars Jedi Knight: Jedi Academy (single player + multiplayer). Native Linux, widescreen, bug fixes, mod support. Copy the base/ folder (*.pk3) from your game here.",
        "fr": "OpenJK — le moteur communautaire de Star Wars Jedi Knight: Jedi Academy (solo + multijoueur). Linux natif, écran large, corrections de bugs, support des mods. Copiez le dossier base/ (*.pk3) de votre jeu ici.",
        "de": "OpenJK — die Community-Engine für Star Wars Jedi Knight: Jedi Academy (Einzelspieler + Multiplayer). Natives Linux, Breitbild, Bugfixes, Mod-Support. Kopiere den base/-Ordner (*.pk3) deines Spiels hierher.",
        "es": "OpenJK — el motor comunitario de Star Wars Jedi Knight: Jedi Academy (campaña + multijugador). Linux nativo, panorámico, corrección de errores, soporte de mods. Copia aquí la carpeta base/ (*.pk3) de tu juego.",
        "it": "OpenJK — il motore della community per Star Wars Jedi Knight: Jedi Academy (singolo + multiplayer). Linux nativo, widescreen, bugfix, supporto mod. Copia qui la cartella base/ (*.pk3) del tuo gioco.",
        "pt": "OpenJK — o motor comunitário de Star Wars Jedi Knight: Jedi Academy (campanha + multijogador). Linux nativo, widescreen, correções, suporte a mods. Copie para aqui a pasta base/ (*.pk3) do seu jogo.",
        "nl": "OpenJK — de community-engine voor Star Wars Jedi Knight: Jedi Academy (singleplayer + multiplayer). Native Linux, breedbeeld, bugfixes, modsupport. Kopieer de base/-map (*.pk3) van je spel hierheen.",
        "pl": "OpenJK — społecznościowy silnik Star Wars Jedi Knight: Jedi Academy (kampania + multiplayer). Natywny Linux, panorama, poprawki błędów, wsparcie modów. Skopiuj tu folder base/ (*.pk3) ze swojej gry.",
        "ru": "OpenJK — комьюнити-движок Star Wars Jedi Knight: Jedi Academy (одиночная игра + мультиплеер). Нативный Linux, широкий экран, исправления багов, поддержка модов. Скопируйте сюда папку base/ (*.pk3) из вашей игры.",
    },
    "iortcw": {
        "en": "iortcw — Return to Castle Wolfenstein on the modern ioquake3 engine. Native Linux, high resolutions, OpenAL audio, fixed bugs. Copy the main/ folder from your RTCW install here.",
        "fr": "iortcw — Return to Castle Wolfenstein sur le moteur moderne ioquake3. Linux natif, hautes résolutions, audio OpenAL, bugs corrigés. Copiez le dossier main/ de votre installation RTCW ici.",
        "de": "iortcw — Return to Castle Wolfenstein auf der modernen ioquake3-Engine. Natives Linux, hohe Auflösungen, OpenAL-Audio, behobene Bugs. Kopiere den main/-Ordner deiner RTCW-Installation hierher.",
        "es": "iortcw — Return to Castle Wolfenstein sobre el motor moderno ioquake3. Linux nativo, altas resoluciones, audio OpenAL, errores corregidos. Copia aquí la carpeta main/ de tu instalación de RTCW.",
        "it": "iortcw — Return to Castle Wolfenstein sul motore moderno ioquake3. Linux nativo, alte risoluzioni, audio OpenAL, bug corretti. Copia qui la cartella main/ della tua installazione di RTCW.",
        "pt": "iortcw — Return to Castle Wolfenstein no motor moderno ioquake3. Linux nativo, altas resoluções, áudio OpenAL, bugs corrigidos. Copie para aqui a pasta main/ da sua instalação do RTCW.",
        "nl": "iortcw — Return to Castle Wolfenstein op de moderne ioquake3-engine. Native Linux, hoge resoluties, OpenAL-audio, opgeloste bugs. Kopieer de main/-map van je RTCW-installatie hierheen.",
        "pl": "iortcw — Return to Castle Wolfenstein na nowoczesnym silniku ioquake3. Natywny Linux, wysokie rozdzielczości, dźwięk OpenAL, naprawione błędy. Skopiuj tu folder main/ z instalacji RTCW.",
        "ru": "iortcw — Return to Castle Wolfenstein на современном движке ioquake3. Нативный Linux, высокие разрешения, звук OpenAL, исправленные баги. Скопируйте сюда папку main/ из вашей установки RTCW.",
    },
    "dethrace": {
        "en": "Dethrace — Carmageddon reverse-engineered and running natively. High resolutions, smooth framerate, all the carnage of 1997. Copy the DATA/ folder from your Carmageddon (GOG) into the game folder.",
        "fr": "Dethrace — Carmageddon rétro-ingéniéré et natif. Hautes résolutions, framerate fluide, tout le carnage de 1997. Copiez le dossier DATA/ de votre Carmageddon (GOG) dans le dossier du jeu.",
        "de": "Dethrace — Carmageddon per Reverse Engineering nativ zum Laufen gebracht. Hohe Auflösungen, flüssige Framerate, das ganze Gemetzel von 1997. Kopiere den DATA/-Ordner deines Carmageddon (GOG) in den Spielordner.",
        "es": "Dethrace — Carmageddon con ingeniería inversa y nativo. Altas resoluciones, framerate fluido, toda la carnicería de 1997. Copia la carpeta DATA/ de tu Carmageddon (GOG) a la carpeta del juego.",
        "it": "Dethrace — Carmageddon retro-ingegnerizzato e nativo. Alte risoluzioni, framerate fluido, tutta la carneficina del 1997. Copia la cartella DATA/ del tuo Carmageddon (GOG) nella cartella del gioco.",
        "pt": "Dethrace — Carmageddon com engenharia reversa e nativo. Altas resoluções, framerate fluido, toda a carnificina de 1997. Copie a pasta DATA/ do seu Carmageddon (GOG) para a pasta do jogo.",
        "nl": "Dethrace — Carmageddon reverse-engineered en native. Hoge resoluties, vloeiende framerate, alle bloedbaden van 1997. Kopieer de DATA/-map van je Carmageddon (GOG) naar de spelmap.",
        "pl": "Dethrace — Carmageddon po inżynierii wstecznej, działający natywnie. Wysokie rozdzielczości, płynny framerate, cała rzeź z 1997 roku. Skopiuj folder DATA/ ze swojego Carmageddona (GOG) do folderu gry.",
        "ru": "Dethrace — Carmageddon, восстановленный обратной разработкой и работающий нативно. Высокие разрешения, плавный фреймрейт, вся бойня 1997 года. Скопируйте папку DATA/ из вашего Carmageddon (GOG) в папку игры.",
    },
    "openmohaa": {
        "en": "OpenMoHAA — open-source engine for Medal of Honor: Allied Assault (plus Spearhead/Breakthrough). Native Linux, working multiplayer, actively developed. Copy the main/ folder from your MOHAA install here.",
        "fr": "OpenMoHAA — moteur open source de Medal of Honor: Allied Assault (plus Spearhead/Breakthrough). Linux natif, multijoueur fonctionnel, développement actif. Copiez le dossier main/ de votre installation MOHAA ici.",
        "de": "OpenMoHAA — Open-Source-Engine für Medal of Honor: Allied Assault (plus Spearhead/Breakthrough). Natives Linux, funktionierender Multiplayer, aktive Entwicklung. Kopiere den main/-Ordner deiner MOHAA-Installation hierher.",
        "es": "OpenMoHAA — motor open source de Medal of Honor: Allied Assault (más Spearhead/Breakthrough). Linux nativo, multijugador funcional, desarrollo activo. Copia aquí la carpeta main/ de tu instalación de MOHAA.",
        "it": "OpenMoHAA — motore open source di Medal of Honor: Allied Assault (più Spearhead/Breakthrough). Linux nativo, multiplayer funzionante, sviluppo attivo. Copia qui la cartella main/ della tua installazione di MOHAA.",
        "pt": "OpenMoHAA — motor open source de Medal of Honor: Allied Assault (mais Spearhead/Breakthrough). Linux nativo, multijogador funcional, desenvolvimento ativo. Copie para aqui a pasta main/ da sua instalação do MOHAA.",
        "nl": "OpenMoHAA — opensource-engine voor Medal of Honor: Allied Assault (plus Spearhead/Breakthrough). Native Linux, werkende multiplayer, actief ontwikkeld. Kopieer de main/-map van je MOHAA-installatie hierheen.",
        "pl": "OpenMoHAA — otwarty silnik Medal of Honor: Allied Assault (plus Spearhead/Breakthrough). Natywny Linux, działający multiplayer, aktywny rozwój. Skopiuj tu folder main/ z instalacji MOHAA.",
        "ru": "OpenMoHAA — открытый движок Medal of Honor: Allied Assault (плюс Spearhead/Breakthrough). Нативный Linux, рабочий мультиплеер, активная разработка. Скопируйте сюда папку main/ из вашей установки MOHAA.",
    },
    "ja2": {
        "en": "JA2 Stracciatella — the community engine for Jagged Alliance 2. Native Linux, higher resolutions, mods (including 1.13-style content), countless fixes. On first launch, point it to your JA2 installation.",
        "fr": "JA2 Stracciatella — le moteur communautaire de Jagged Alliance 2. Linux natif, résolutions supérieures, mods, d'innombrables correctifs. Au premier lancement, indiquez votre installation de JA2.",
        "de": "JA2 Stracciatella — die Community-Engine für Jagged Alliance 2. Natives Linux, höhere Auflösungen, Mods, unzählige Fixes. Beim ersten Start auf deine JA2-Installation verweisen.",
        "es": "JA2 Stracciatella — el motor comunitario de Jagged Alliance 2. Linux nativo, resoluciones más altas, mods, innumerables arreglos. En el primer inicio, indica tu instalación de JA2.",
        "it": "JA2 Stracciatella — il motore della community per Jagged Alliance 2. Linux nativo, risoluzioni più alte, mod, innumerevoli fix. Al primo avvio indica la tua installazione di JA2.",
        "pt": "JA2 Stracciatella — o motor comunitário de Jagged Alliance 2. Linux nativo, resoluções mais altas, mods, inúmeras correções. No primeiro arranque, indique a sua instalação do JA2.",
        "nl": "JA2 Stracciatella — de community-engine voor Jagged Alliance 2. Native Linux, hogere resoluties, mods, talloze fixes. Wijs bij de eerste start je JA2-installatie aan.",
        "pl": "JA2 Stracciatella — społecznościowy silnik Jagged Alliance 2. Natywny Linux, wyższe rozdzielczości, mody, niezliczone poprawki. Przy pierwszym uruchomieniu wskaż instalację JA2.",
        "ru": "JA2 Stracciatella — комьюнити-движок Jagged Alliance 2. Нативный Linux, более высокие разрешения, моды, бесчисленные исправления. При первом запуске укажите вашу установку JA2.",
    },
    "helion": {
        "en": "Helion — a modern high-performance Doom engine: rock-solid framerate even on giant maps, native Linux, gamepad friendly. Drop your .WAD in the game folder — the free shareware doom1.wad works too.",
        "fr": "Helion — un moteur Doom moderne ultra performant : framerate béton même sur les cartes géantes, Linux natif, compatible manette. Déposez votre .WAD dans le dossier du jeu — le doom1.wad shareware gratuit marche aussi.",
        "de": "Helion — eine moderne Hochleistungs-Doom-Engine: felsenfeste Framerate selbst auf Riesenkarten, natives Linux, gamepadfreundlich. Lege deine .WAD in den Spielordner — die kostenlose Shareware doom1.wad geht auch.",
        "es": "Helion — un motor Doom moderno de alto rendimiento: framerate sólido incluso en mapas gigantes, Linux nativo, apto para mando. Deja tu .WAD en la carpeta del juego — el doom1.wad shareware gratuito también vale.",
        "it": "Helion — un motore Doom moderno ad alte prestazioni: framerate solidissimo anche su mappe giganti, Linux nativo, amico del gamepad. Metti il tuo .WAD nella cartella del gioco — va bene anche il doom1.wad shareware gratuito.",
        "pt": "Helion — um motor Doom moderno de alto desempenho: framerate sólido mesmo em mapas gigantes, Linux nativo, amigável ao comando. Coloque o seu .WAD na pasta do jogo — o doom1.wad shareware gratuito também serve.",
        "nl": "Helion — een moderne high-performance Doom-engine: ijzersterke framerate zelfs op gigantische maps, native Linux, gamepadvriendelijk. Zet je .WAD in de spelmap — de gratis shareware doom1.wad werkt ook.",
        "pl": "Helion — nowoczesny, wydajny silnik Dooma: stabilny framerate nawet na ogromnych mapach, natywny Linux, przyjazny padom. Wrzuć swój .WAD do folderu gry — darmowy shareware'owy doom1.wad też działa.",
        "ru": "Helion — современный высокопроизводительный движок Doom: стабильный фреймрейт даже на гигантских картах, нативный Linux, дружит с геймпадом. Положите ваш .WAD в папку игры — бесплатный shareware doom1.wad тоже подойдёт.",
    },
    "openomf": {
        "en": "OpenOMF — open-source remake of One Must Fall 2097, the classic robot fighting game. The original was released as freeware, so everything you need is easy to get; net play included.",
        "fr": "OpenOMF — remake open source de One Must Fall 2097, le classique du combat de robots. L'original est devenu freeware, donc tout le nécessaire s'obtient facilement ; jeu en réseau inclus.",
        "de": "OpenOMF — Open-Source-Remake von One Must Fall 2097, dem Klassiker der Roboterkämpfe. Das Original ist Freeware, alles Nötige ist leicht zu bekommen; Netzwerkspiel inklusive.",
        "es": "OpenOMF — remake open source de One Must Fall 2097, el clásico de lucha de robots. El original es freeware, así que todo lo necesario se consigue fácil; juego en red incluido.",
        "it": "OpenOMF — remake open source di One Must Fall 2097, il classico dei combattimenti tra robot. L'originale è freeware, quindi tutto il necessario si trova facilmente; gioco in rete incluso.",
        "pt": "OpenOMF — remake open source de One Must Fall 2097, o clássico de luta de robôs. O original tornou-se freeware, por isso tudo o que precisa é fácil de obter; jogo em rede incluído.",
        "nl": "OpenOMF — opensource-remake van One Must Fall 2097, de klassieke robotvechter. Het origineel is freeware, dus alles wat je nodig hebt is makkelijk te krijgen; netwerkspel inbegrepen.",
        "pl": "OpenOMF — otwarty remake One Must Fall 2097, klasyki walk robotów. Oryginał został freeware, więc wszystko, czego trzeba, łatwo zdobyć; gra sieciowa w zestawie.",
        "ru": "OpenOMF — открытый ремейк One Must Fall 2097, классического файтинга роботов. Оригинал стал freeware, так что всё нужное легко достать; сетевая игра включена.",
    },
    "opensupaplex": {
        "en": "OpenSupaplex — faithful open-source port of Supaplex, the legendary puzzle game. The game content ships with it: install and play.",
        "fr": "OpenSupaplex — port open source fidèle de Supaplex, le jeu de réflexion légendaire. Le contenu du jeu est fourni : installez et jouez.",
        "de": "OpenSupaplex — werktreuer Open-Source-Port von Supaplex, dem legendären Puzzlespiel. Der Spielinhalt ist dabei: installieren und spielen.",
        "es": "OpenSupaplex — port open source fiel de Supaplex, el legendario juego de puzles. El contenido del juego viene incluido: instala y juega.",
        "it": "OpenSupaplex — port open source fedele di Supaplex, il leggendario rompicapo. Il contenuto del gioco è incluso: installa e gioca.",
        "pt": "OpenSupaplex — port open source fiel de Supaplex, o lendário jogo de puzzles. O conteúdo do jogo vem incluído: instale e jogue.",
        "nl": "OpenSupaplex — getrouwe opensource-port van Supaplex, het legendarische puzzelspel. De spelinhoud zit erbij: installeren en spelen.",
        "pl": "OpenSupaplex — wierny otwarty port Supaplexa, legendarnej gry logicznej. Zawartość gry jest dołączona: zainstaluj i graj.",
        "ru": "OpenSupaplex — точный открытый порт Supaplex, легендарной головоломки. Контент игры идёт в комплекте: установил и играешь.",
    },
    "descent3": {
        "en": "Descent 3 — the official open-source release of the 6-degrees-of-freedom shooter, maintained by the community (1.5 patch: native Linux, modern resolutions). Copy the .hog files and movies from your GOG/Steam copy into the game folder.",
        "fr": "Descent 3 — la version open source officielle du shooter à 6 degrés de liberté, maintenue par la communauté (patch 1.5 : Linux natif, résolutions modernes). Copiez les fichiers .hog et les vidéos de votre copie GOG/Steam dans le dossier du jeu.",
        "de": "Descent 3 — die offizielle Open-Source-Version des 6-Freiheitsgrade-Shooters, von der Community gepflegt (1.5-Patch: natives Linux, moderne Auflösungen). Kopiere die .hog-Dateien und Videos deiner GOG/Steam-Kopie in den Spielordner.",
        "es": "Descent 3 — la versión open source oficial del shooter de 6 grados de libertad, mantenida por la comunidad (parche 1.5: Linux nativo, resoluciones modernas). Copia los archivos .hog y los vídeos de tu copia GOG/Steam a la carpeta del juego.",
        "it": "Descent 3 — la versione open source ufficiale dello sparatutto a 6 gradi di libertà, mantenuta dalla community (patch 1.5: Linux nativo, risoluzioni moderne). Copia i file .hog e i filmati della tua copia GOG/Steam nella cartella del gioco.",
        "pt": "Descent 3 — a versão open source oficial do shooter com 6 graus de liberdade, mantida pela comunidade (patch 1.5: Linux nativo, resoluções modernas). Copie os ficheiros .hog e os vídeos da sua cópia GOG/Steam para a pasta do jogo.",
        "nl": "Descent 3 — de officiële opensource-versie van de 6-vrijheidsgraden-shooter, onderhouden door de community (1.5-patch: native Linux, moderne resoluties). Kopieer de .hog-bestanden en video's van je GOG/Steam-kopie naar de spelmap.",
        "pl": "Descent 3 — oficjalne otwarte wydanie strzelanki o 6 stopniach swobody, utrzymywane przez społeczność (patch 1.5: natywny Linux, nowoczesne rozdzielczości). Skopiuj pliki .hog i filmy z kopii GOG/Steam do folderu gry.",
        "ru": "Descent 3 — официальный открытый релиз шутера с 6 степенями свободы, поддерживаемый сообществом (патч 1.5: нативный Linux, современные разрешения). Скопируйте файлы .hog и видео из вашей копии GOG/Steam в папку игры.",
    },
    "opengothic": {
        "en": "OpenGothic — full open-source reimplementation of the Gothic II: Night of the Raven engine. Modern Vulkan renderer, better performance, same dark Khorinis. Copy your complete Gothic II install into a Gothic2/ subfolder of the game folder.",
        "fr": "OpenGothic — réimplémentation open source complète du moteur de Gothic II : Night of the Raven. Rendu Vulkan moderne, meilleures performances, le même Khorinis sombre. Copiez votre installation complète de Gothic II dans un sous-dossier Gothic2/ du dossier du jeu.",
        "de": "OpenGothic — vollständige Open-Source-Reimplementierung der Engine von Gothic II: Die Nacht des Raben. Moderner Vulkan-Renderer, bessere Performance, dasselbe düstere Khorinis. Kopiere deine komplette Gothic-II-Installation in einen Unterordner Gothic2/ des Spielordners.",
        "es": "OpenGothic — reimplementación open source completa del motor de Gothic II: Night of the Raven. Renderizador Vulkan moderno, mejor rendimiento, el mismo Khorinis sombrío. Copia tu instalación completa de Gothic II en una subcarpeta Gothic2/ de la carpeta del juego.",
        "it": "OpenGothic — reimplementazione open source completa del motore di Gothic II: Night of the Raven. Renderer Vulkan moderno, prestazioni migliori, la stessa cupa Khorinis. Copia la tua installazione completa di Gothic II in una sottocartella Gothic2/ della cartella del gioco.",
        "pt": "OpenGothic — reimplementação open source completa do motor de Gothic II: Night of the Raven. Renderizador Vulkan moderno, melhor desempenho, a mesma Khorinis sombria. Copie a sua instalação completa do Gothic II para uma subpasta Gothic2/ da pasta do jogo.",
        "nl": "OpenGothic — volledige opensource-herimplementatie van de engine van Gothic II: Night of the Raven. Moderne Vulkan-renderer, betere prestaties, hetzelfde duistere Khorinis. Kopieer je volledige Gothic II-installatie naar een submap Gothic2/ van de spelmap.",
        "pl": "OpenGothic — pełna otwarta reimplementacja silnika Gothic II: Noc Kruka. Nowoczesny renderer Vulkan, lepsza wydajność, to samo mroczne Khorinis. Skopiuj pełną instalację Gothic II do podfolderu Gothic2/ w folderze gry.",
        "ru": "OpenGothic — полная открытая реализация движка Gothic II: Ночь Ворона. Современный Vulkan-рендер, лучшая производительность, тот же мрачный Хоринис. Скопируйте полную установку Gothic II в подпапку Gothic2/ папки игры.",
    },
    "unleashedrecomp": {
        "en": "Unleashed Recompiled — Sonic Unleashed statically recompiled from Xbox 360 to native PC. High framerates, ultrawide, better load times. On first launch the built-in installer asks for a dump of your own game (+ update).",
        "fr": "Unleashed Recompiled — Sonic Unleashed recompilé statiquement de la Xbox 360 vers le PC natif. Framerates élevés, ultrawide, chargements plus rapides. Au premier lancement, l'installateur intégré demande un dump de votre propre jeu (+ mise à jour).",
        "de": "Unleashed Recompiled — Sonic Unleashed statisch von der Xbox 360 auf nativen PC rekompiliert. Hohe Frameraten, Ultrawide, schnellere Ladezeiten. Beim ersten Start fragt der integrierte Installer nach einem Dump deines eigenen Spiels (+ Update).",
        "es": "Unleashed Recompiled — Sonic Unleashed recompilado estáticamente de Xbox 360 a PC nativo. Framerates altos, ultrawide, cargas más rápidas. En el primer inicio el instalador integrado pide un volcado de tu propio juego (+ actualización).",
        "it": "Unleashed Recompiled — Sonic Unleashed ricompilato staticamente da Xbox 360 a PC nativo. Framerate alti, ultrawide, caricamenti più rapidi. Al primo avvio l'installer integrato chiede un dump del tuo gioco (+ aggiornamento).",
        "pt": "Unleashed Recompiled — Sonic Unleashed recompilado estaticamente da Xbox 360 para PC nativo. Framerates altos, ultrawide, carregamentos mais rápidos. No primeiro arranque o instalador integrado pede um dump do seu próprio jogo (+ atualização).",
        "nl": "Unleashed Recompiled — Sonic Unleashed statisch gerecompileerd van Xbox 360 naar native pc. Hoge framerates, ultrawide, snellere laadtijden. Bij de eerste start vraagt de ingebouwde installer om een dump van je eigen spel (+ update).",
        "pl": "Unleashed Recompiled — Sonic Unleashed statycznie zrekompilowany z Xbox 360 na natywne PC. Wysokie framerate'y, ultrawide, szybsze wczytywanie. Przy pierwszym uruchomieniu wbudowany instalator poprosi o zrzut własnej gry (+ aktualizację).",
        "ru": "Unleashed Recompiled — Sonic Unleashed, статически рекомпилированный с Xbox 360 в нативный ПК. Высокий фреймрейт, ultrawide, быстрые загрузки. При первом запуске встроенный установщик запросит дамп вашей игры (+ обновление).",
    },
}


def desc_for(shortname):
    return _pick(DESCS.get(shortname, {"en": ""}))


def needs_line(port):
    """Localized 'which original files and how' sentence for a port dict
    (fields: needs = (template, game, spec[, fname]))."""
    needs = port.get("needs")
    if not needs:
        return ""
    tmpl, game, spec = needs[0], needs[1], needs[2]
    fname = needs[3] if len(needs) > 3 else ""
    return _pick(_NEEDS_TMPL[tmpl]).format(game=game, spec=spec, fname=fname)


def howto_line(directory):
    return _pick(_HOWTO).format(dir=directory)
