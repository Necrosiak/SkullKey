"""Localized rich descriptions for the Media & Apps catalogue.

House rule: everything we author is either English or ALL nine plugin
languages (en/fr/de/es/it/pt/nl/pl/ru) — here it's all nine.  Lookup order:
DESCS[shortname][machine language] → DESCS[shortname]["en"] → the short
CATALOG desc kept in media.py as the ultimate fallback.
"""

import os


def machine_lang_code():
    """2-letter language code of the machine locale. Env vars first, then
    /etc/locale.conf — plugin_loader (systemd) has no LANG in its env."""
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


def desc_for(app):
    """Rich localized description for a CATALOG app dict (fallbacks: en → CATALOG desc)."""
    d = DESCS.get(app.get("shortname"), {})
    return d.get(machine_lang_code()) or d.get("en") or app.get("desc", "")


# ── Controller status per app ──────────────────────────────────────────────
# "ok"      → works with the controller out of the box
# "layout"  → app runs fine but its UI needs a Steam controller layout
#             (e.g. dpad→arrow keys / trackpad-mouse) to be navigated
# "desktop" → desktop tool: keyboard/mouse UI, best used in desktop mode or
#             with a mouse-style Steam layout
PAD_STATUS = {
    # SSL webapps ship gamepad navigation; VacuumTube/couch clients are pad-first
    "youtube": "ok", "netflix": "ok", "disney-plus": "ok", "prime-video": "ok",
    "apple-tv": "ok", "hbo-max": "ok", "hulu": "ok", "paramount-plus": "ok",
    "peacock": "ok", "crunchyroll": "ok", "curiosity-stream": "ok",
    "sling-tv": "ok", "vimeo": "ok", "youtube-tv": "ok",
    "plex": "ok", "kodi": "ok",
    "jellyfin": "layout", "stremio": "layout",
    "spotify": "ok", "youtube-music": "ok",
    "tidal": "layout", "deezer": "layout",
    "geforce-now": "ok", "xbox-cloud": "ok", "amazon-luna": "ok",
    "moonlight": "ok", "chiaki": "ok", "greenlight": "ok",
    "parsec": "layout",
    "lutris": "desktop", "bottles": "desktop", "retrodeck": "ok",
    "protonup-qt": "desktop", "flatseal": "desktop",
}

_PAD_LABELS = {
    "en": {"ok": "Controller: works out of the box.",
           "layout": "Controller: set a Steam controller layout (d-pad → arrow keys / trackpad mouse) to navigate the interface.",
           "desktop": "Controller: desktop tool — use in desktop mode or with a mouse-style Steam layout."},
    "fr": {"ok": "Manette : fonctionne directement.",
           "layout": "Manette : configure un layout manette Steam (croix → flèches / trackpad souris) pour naviguer dans l'interface.",
           "desktop": "Manette : outil bureau — à utiliser en mode bureau ou avec un layout Steam façon souris."},
    "de": {"ok": "Controller: funktioniert sofort.",
           "layout": "Controller: ein Steam-Controller-Layout einstellen (Steuerkreuz → Pfeiltasten / Trackpad-Maus), um die Oberfläche zu bedienen.",
           "desktop": "Controller: Desktop-Tool — im Desktop-Modus oder mit einem Maus-Layout in Steam verwenden."},
    "es": {"ok": "Mando: funciona directamente.",
           "layout": "Mando: configura un layout de mando en Steam (cruceta → flechas / trackpad ratón) para navegar por la interfaz.",
           "desktop": "Mando: herramienta de escritorio — úsala en modo escritorio o con un layout de Steam tipo ratón."},
    "it": {"ok": "Controller: funziona subito.",
           "layout": "Controller: imposta un layout controller di Steam (croce → frecce / trackpad mouse) per navigare nell'interfaccia.",
           "desktop": "Controller: strumento desktop — da usare in modalità desktop o con un layout Steam stile mouse."},
    "pt": {"ok": "Comando: funciona logo à partida.",
           "layout": "Comando: define um layout de comando no Steam (cruzeta → setas / trackpad rato) para navegar na interface.",
           "desktop": "Comando: ferramenta de desktop — usa em modo desktop ou com um layout Steam tipo rato."},
    "nl": {"ok": "Controller: werkt direct.",
           "layout": "Controller: stel een Steam-controllerlayout in (d-pad → pijltjestoetsen / trackpad-muis) om de interface te bedienen.",
           "desktop": "Controller: desktoptool — gebruik in desktopmodus of met een muisachtige Steam-layout."},
    "pl": {"ok": "Pad: działa od razu.",
           "layout": "Pad: ustaw układ pada w Steam (krzyżak → strzałki / gładzik jako mysz), aby poruszać się po interfejsie.",
           "desktop": "Pad: narzędzie pulpitowe — używaj w trybie pulpitu albo z układem Steam w stylu myszy."},
    "ru": {"ok": "Геймпад: работает сразу.",
           "layout": "Геймпад: настройте раскладку контроллера в Steam (крестовина → стрелки / трекпад-мышь), чтобы перемещаться по интерфейсу.",
           "desktop": "Геймпад: настольный инструмент — используйте в режиме рабочего стола или с раскладкой Steam в стиле мыши."},
}


def pad_line(app):
    """Localized one-liner describing controller support for a CATALOG app."""
    status = PAD_STATUS.get(app.get("shortname"))
    if not status:
        return ""
    lab = _PAD_LABELS.get(machine_lang_code(), _PAD_LABELS["en"])
    return "🎮 " + lab[status]


DESCS = {
    # ── TV & video ─────────────────────────────────────────────────────────
    "youtube": {
        "en": "YouTube in its official TV (leanback) interface via VacuumTube, designed for couch navigation with the controller. Sign in with your Google account for subscriptions, history and 4K playback, with optional SponsorBlock.",
        "fr": "YouTube dans son interface TV officielle (leanback) via VacuumTube, pensée pour la navigation manette depuis le canapé. Connecte ton compte Google pour les abonnements, l'historique et la lecture 4K, avec SponsorBlock en option.",
        "de": "YouTube in der offiziellen TV-Oberfläche (Leanback) über VacuumTube, gemacht für die Controller-Bedienung vom Sofa. Mit Google-Konto anmelden für Abos, Verlauf und 4K-Wiedergabe, optional mit SponsorBlock.",
        "es": "YouTube con su interfaz oficial de TV (leanback) vía VacuumTube, pensada para navegar con el mando desde el sofá. Inicia sesión con tu cuenta de Google para suscripciones, historial y reproducción 4K, con SponsorBlock opcional.",
        "it": "YouTube nella sua interfaccia TV ufficiale (leanback) tramite VacuumTube, pensata per la navigazione col controller dal divano. Accedi col tuo account Google per iscrizioni, cronologia e riproduzione 4K, con SponsorBlock opzionale.",
        "pt": "YouTube na sua interface oficial de TV (leanback) via VacuumTube, feita para navegar com o comando a partir do sofá. Inicia sessão com a tua conta Google para subscrições, histórico e reprodução 4K, com SponsorBlock opcional.",
        "nl": "YouTube in de officiële tv-interface (leanback) via VacuumTube, gemaakt voor bediening met de controller vanaf de bank. Log in met je Google-account voor abonnementen, geschiedenis en 4K-weergave, met optionele SponsorBlock.",
        "pl": "YouTube w oficjalnym interfejsie TV (leanback) przez VacuumTube, stworzony do nawigacji padem z kanapy. Zaloguj się kontem Google, by mieć subskrypcje, historię i odtwarzanie 4K, z opcjonalnym SponsorBlock.",
        "ru": "YouTube в официальном ТВ-интерфейсе (leanback) через VacuumTube — для навигации геймпадом с дивана. Войдите в аккаунт Google: подписки, история и 4K-воспроизведение, опционально SponsorBlock.",
    },
    "netflix": {
        "en": "The full Netflix experience as a dedicated web app: sign in, pick your profile and stream films and series with subtitles and multiple audio tracks. Widevine DRM and controller navigation work out of the box in game mode.",
        "fr": "L'expérience Netflix complète en web app dédiée : connecte-toi, choisis ton profil et regarde films et séries avec sous-titres et pistes audio multiples. Le DRM Widevine et la navigation manette fonctionnent directement en mode jeu.",
        "de": "Das volle Netflix-Erlebnis als eigene Web-App: anmelden, Profil wählen und Filme und Serien mit Untertiteln und mehreren Tonspuren streamen. Widevine-DRM und Controller-Bedienung funktionieren im Spielmodus sofort.",
        "es": "La experiencia Netflix completa como web app dedicada: inicia sesión, elige tu perfil y disfruta de películas y series con subtítulos y varias pistas de audio. El DRM Widevine y la navegación con mando funcionan directamente en modo juego.",
        "it": "L'esperienza Netflix completa come web app dedicata: accedi, scegli il profilo e guarda film e serie con sottotitoli e più tracce audio. DRM Widevine e navigazione col controller funzionano subito in modalità gioco.",
        "pt": "A experiência Netflix completa numa web app dedicada: inicia sessão, escolhe o teu perfil e vê filmes e séries com legendas e várias faixas de áudio. O DRM Widevine e a navegação com comando funcionam logo em modo de jogo.",
        "nl": "De volledige Netflix-ervaring als aparte webapp: log in, kies je profiel en stream films en series met ondertitels en meerdere audiosporen. Widevine-DRM en controllerbediening werken direct in de gamemodus.",
        "pl": "Pełny Netflix jako dedykowana aplikacja webowa: zaloguj się, wybierz profil i oglądaj filmy oraz seriale z napisami i wieloma ścieżkami audio. DRM Widevine i nawigacja padem działają od razu w trybie gry.",
        "ru": "Полноценный Netflix как отдельное веб-приложение: войдите, выберите профиль и смотрите фильмы и сериалы с субтитрами и несколькими звуковыми дорожками. Widevine DRM и управление геймпадом работают сразу в игровом режиме.",
    },
    "disney-plus": {
        "en": "Films and series from Disney, Pixar, Marvel, Star Wars and National Geographic in a dedicated web app. Widevine DRM and controller navigation included — sign in and stream straight from game mode.",
        "fr": "Les films et séries Disney, Pixar, Marvel, Star Wars et National Geographic en web app dédiée. DRM Widevine et navigation manette inclus — connecte-toi et regarde directement depuis le mode jeu.",
        "de": "Filme und Serien von Disney, Pixar, Marvel, Star Wars und National Geographic als eigene Web-App. Widevine-DRM und Controller-Bedienung inklusive — anmelden und direkt im Spielmodus streamen.",
        "es": "Películas y series de Disney, Pixar, Marvel, Star Wars y National Geographic en una web app dedicada. DRM Widevine y navegación con mando incluidos: inicia sesión y reproduce directamente desde el modo juego.",
        "it": "Film e serie di Disney, Pixar, Marvel, Star Wars e National Geographic in una web app dedicata. DRM Widevine e navigazione col controller inclusi: accedi e guarda direttamente dalla modalità gioco.",
        "pt": "Filmes e séries da Disney, Pixar, Marvel, Star Wars e National Geographic numa web app dedicada. DRM Widevine e navegação com comando incluídos — inicia sessão e vê diretamente no modo de jogo.",
        "nl": "Films en series van Disney, Pixar, Marvel, Star Wars en National Geographic als aparte webapp. Widevine-DRM en controllerbediening inbegrepen — log in en stream direct vanuit de gamemodus.",
        "pl": "Filmy i seriale Disneya, Pixara, Marvela, Star Wars i National Geographic w dedykowanej aplikacji webowej. DRM Widevine i nawigacja padem w zestawie — zaloguj się i oglądaj prosto z trybu gry.",
        "ru": "Фильмы и сериалы Disney, Pixar, Marvel, Star Wars и National Geographic в отдельном веб-приложении. Widevine DRM и управление геймпадом в комплекте — войдите и смотрите прямо из игрового режима.",
    },
    "prime-video": {
        "en": "Amazon's streaming service — included with a Prime subscription — with its films, series and Amazon Originals. Runs as a web app with Widevine DRM and full controller support.",
        "fr": "Le streaming d'Amazon — inclus avec l'abonnement Prime — avec ses films, séries et Amazon Originals. Tourne en web app avec DRM Widevine et prise en charge complète de la manette.",
        "de": "Amazons Streaming-Dienst — im Prime-Abo enthalten — mit Filmen, Serien und Amazon Originals. Läuft als Web-App mit Widevine-DRM und voller Controller-Unterstützung.",
        "es": "El streaming de Amazon —incluido con la suscripción Prime— con sus películas, series y Amazon Originals. Funciona como web app con DRM Widevine y soporte completo de mando.",
        "it": "Lo streaming di Amazon — incluso nell'abbonamento Prime — con film, serie e Amazon Originals. Funziona come web app con DRM Widevine e pieno supporto del controller.",
        "pt": "O streaming da Amazon — incluído na subscrição Prime — com filmes, séries e Amazon Originals. Corre como web app com DRM Widevine e suporte total de comando.",
        "nl": "De streamingdienst van Amazon — inbegrepen bij een Prime-abonnement — met films, series en Amazon Originals. Draait als webapp met Widevine-DRM en volledige controllerondersteuning.",
        "pl": "Serwis streamingowy Amazona — w ramach subskrypcji Prime — z filmami, serialami i Amazon Originals. Działa jako aplikacja webowa z DRM Widevine i pełną obsługą pada.",
        "ru": "Стриминг Amazon — входит в подписку Prime — с фильмами, сериалами и Amazon Originals. Работает как веб-приложение с Widevine DRM и полной поддержкой геймпада.",
    },
    "apple-tv": {
        "en": "Apple TV+ and its award-winning Apple Originals in a dedicated web app. Sign in with your Apple account; Widevine DRM and controller navigation are handled for you.",
        "fr": "Apple TV+ et ses Apple Originals primés en web app dédiée. Connecte-toi avec ton compte Apple ; le DRM Widevine et la navigation manette sont gérés pour toi.",
        "de": "Apple TV+ und seine preisgekrönten Apple Originals als eigene Web-App. Mit dem Apple-Konto anmelden; Widevine-DRM und Controller-Bedienung sind bereits eingerichtet.",
        "es": "Apple TV+ y sus premiados Apple Originals en una web app dedicada. Inicia sesión con tu cuenta de Apple; el DRM Widevine y la navegación con mando ya están resueltos.",
        "it": "Apple TV+ e i suoi premiati Apple Originals in una web app dedicata. Accedi col tuo account Apple; DRM Widevine e navigazione col controller sono già gestiti.",
        "pt": "Apple TV+ e os seus premiados Apple Originals numa web app dedicada. Inicia sessão com a tua conta Apple; o DRM Widevine e a navegação com comando já estão tratados.",
        "nl": "Apple TV+ en zijn bekroonde Apple Originals als aparte webapp. Log in met je Apple-account; Widevine-DRM en controllerbediening zijn al geregeld.",
        "pl": "Apple TV+ i nagradzane Apple Originals w dedykowanej aplikacji webowej. Zaloguj się kontem Apple; DRM Widevine i nawigacja padem są już ogarnięte.",
        "ru": "Apple TV+ и его отмеченные наградами Apple Originals в отдельном веб-приложении. Войдите с аккаунтом Apple; Widevine DRM и управление геймпадом уже настроены.",
    },
    "hbo-max": {
        "en": "HBO series, Warner Bros. films and Max exclusives in a dedicated web app. Widevine DRM and controller navigation included for streaming straight from game mode.",
        "fr": "Les séries HBO, les films Warner Bros. et les exclusivités Max en web app dédiée. DRM Widevine et navigation manette inclus pour regarder directement depuis le mode jeu.",
        "de": "HBO-Serien, Warner-Bros.-Filme und Max-Exklusives als eigene Web-App. Widevine-DRM und Controller-Bedienung inklusive — Streaming direkt im Spielmodus.",
        "es": "Series de HBO, películas de Warner Bros. y exclusivos de Max en una web app dedicada. DRM Widevine y navegación con mando incluidos para ver directamente desde el modo juego.",
        "it": "Serie HBO, film Warner Bros. ed esclusive Max in una web app dedicata. DRM Widevine e navigazione col controller inclusi per guardare direttamente dalla modalità gioco.",
        "pt": "Séries HBO, filmes Warner Bros. e exclusivos Max numa web app dedicada. DRM Widevine e navegação com comando incluídos para ver diretamente no modo de jogo.",
        "nl": "HBO-series, Warner Bros.-films en Max-exclusives als aparte webapp. Widevine-DRM en controllerbediening inbegrepen om direct vanuit de gamemodus te streamen.",
        "pl": "Seriale HBO, filmy Warner Bros. i tytuły ekskluzywne Max w dedykowanej aplikacji webowej. DRM Widevine i nawigacja padem w zestawie — oglądaj prosto z trybu gry.",
        "ru": "Сериалы HBO, фильмы Warner Bros. и эксклюзивы Max в отдельном веб-приложении. Widevine DRM и управление геймпадом в комплекте — смотрите прямо из игрового режима.",
    },
    "hulu": {
        "en": "Hulu's series, films and next-day TV episodes (US service) in a dedicated web app. Widevine DRM and controller navigation included.",
        "fr": "Les séries, films et épisodes TV du lendemain de Hulu (service US) en web app dédiée. DRM Widevine et navigation manette inclus.",
        "de": "Hulus Serien, Filme und TV-Folgen vom Vortag (US-Dienst) als eigene Web-App. Widevine-DRM und Controller-Bedienung inklusive.",
        "es": "Las series, películas y episodios de TV del día siguiente de Hulu (servicio de EE. UU.) en una web app dedicada. DRM Widevine y navegación con mando incluidos.",
        "it": "Serie, film ed episodi TV del giorno dopo di Hulu (servizio USA) in una web app dedicata. DRM Widevine e navigazione col controller inclusi.",
        "pt": "As séries, filmes e episódios de TV do dia seguinte da Hulu (serviço dos EUA) numa web app dedicada. DRM Widevine e navegação com comando incluídos.",
        "nl": "Hulu's series, films en tv-afleveringen van de volgende dag (Amerikaanse dienst) als aparte webapp. Widevine-DRM en controllerbediening inbegrepen.",
        "pl": "Seriale, filmy i odcinki TV z następnego dnia od Hulu (usługa USA) w dedykowanej aplikacji webowej. DRM Widevine i nawigacja padem w zestawie.",
        "ru": "Сериалы, фильмы и свежие ТВ-эпизоды Hulu (сервис для США) в отдельном веб-приложении. Widevine DRM и управление геймпадом в комплекте.",
    },
    "paramount-plus": {
        "en": "Series and films from Paramount, CBS and Nickelodeon, plus live sport depending on region. Web app with Widevine DRM and controller support.",
        "fr": "Les séries et films Paramount, CBS et Nickelodeon, plus du sport en direct selon la région. Web app avec DRM Widevine et prise en charge manette.",
        "de": "Serien und Filme von Paramount, CBS und Nickelodeon, plus Live-Sport je nach Region. Web-App mit Widevine-DRM und Controller-Unterstützung.",
        "es": "Series y películas de Paramount, CBS y Nickelodeon, además de deporte en directo según la región. Web app con DRM Widevine y soporte de mando.",
        "it": "Serie e film di Paramount, CBS e Nickelodeon, più sport in diretta a seconda della regione. Web app con DRM Widevine e supporto del controller.",
        "pt": "Séries e filmes da Paramount, CBS e Nickelodeon, além de desporto ao vivo conforme a região. Web app com DRM Widevine e suporte de comando.",
        "nl": "Series en films van Paramount, CBS en Nickelodeon, plus live sport afhankelijk van de regio. Webapp met Widevine-DRM en controllerondersteuning.",
        "pl": "Seriale i filmy Paramount, CBS i Nickelodeon, a także sport na żywo w zależności od regionu. Aplikacja webowa z DRM Widevine i obsługą pada.",
        "ru": "Сериалы и фильмы Paramount, CBS и Nickelodeon, плюс спорт в прямом эфире в зависимости от региона. Веб-приложение с Widevine DRM и поддержкой геймпада.",
    },
    "peacock": {
        "en": "NBCUniversal's streaming service (US): series, films, live sport and news. Web app with Widevine DRM and controller support.",
        "fr": "Le streaming de NBCUniversal (US) : séries, films, sport en direct et infos. Web app avec DRM Widevine et prise en charge manette.",
        "de": "Der Streaming-Dienst von NBCUniversal (USA): Serien, Filme, Live-Sport und Nachrichten. Web-App mit Widevine-DRM und Controller-Unterstützung.",
        "es": "El streaming de NBCUniversal (EE. UU.): series, películas, deporte en directo y noticias. Web app con DRM Widevine y soporte de mando.",
        "it": "Lo streaming di NBCUniversal (USA): serie, film, sport in diretta e notizie. Web app con DRM Widevine e supporto del controller.",
        "pt": "O streaming da NBCUniversal (EUA): séries, filmes, desporto ao vivo e notícias. Web app com DRM Widevine e suporte de comando.",
        "nl": "De streamingdienst van NBCUniversal (VS): series, films, live sport en nieuws. Webapp met Widevine-DRM en controllerondersteuning.",
        "pl": "Serwis streamingowy NBCUniversal (USA): seriale, filmy, sport na żywo i wiadomości. Aplikacja webowa z DRM Widevine i obsługą pada.",
        "ru": "Стриминговый сервис NBCUniversal (США): сериалы, фильмы, спорт в прямом эфире и новости. Веб-приложение с Widevine DRM и поддержкой геймпада.",
    },
    "crunchyroll": {
        "en": "The world's largest anime catalogue: simulcasts shortly after Japan, with subs and dubs. Standalone community AppImage — sign in with your Crunchyroll account.",
        "fr": "Le plus grand catalogue d'anime au monde : simulcasts peu après le Japon, en VOSTFR et VF. AppImage communautaire autonome — connecte-toi avec ton compte Crunchyroll.",
        "de": "Der größte Anime-Katalog der Welt: Simulcasts kurz nach Japan, mit Untertiteln und Synchro. Eigenständiges Community-AppImage — mit dem Crunchyroll-Konto anmelden.",
        "es": "El mayor catálogo de anime del mundo: simulcasts poco después de Japón, con subtítulos y doblaje. AppImage comunitaria independiente: inicia sesión con tu cuenta de Crunchyroll.",
        "it": "Il più grande catalogo di anime al mondo: simulcast poco dopo il Giappone, con sottotitoli e doppiaggio. AppImage comunitaria autonoma — accedi col tuo account Crunchyroll.",
        "pt": "O maior catálogo de anime do mundo: simulcasts pouco depois do Japão, com legendas e dobragem. AppImage comunitária autónoma — inicia sessão com a tua conta Crunchyroll.",
        "nl": "De grootste animecatalogus ter wereld: simulcasts kort na Japan, met ondertitels en nasynchronisatie. Zelfstandige community-AppImage — log in met je Crunchyroll-account.",
        "pl": "Największy katalog anime na świecie: simulcasty tuż po Japonii, z napisami i dubbingiem. Samodzielny społecznościowy AppImage — zaloguj się kontem Crunchyroll.",
        "ru": "Крупнейший в мире каталог аниме: симулкасты вскоре после Японии, с субтитрами и дубляжом. Автономный AppImage от сообщества — войдите с аккаунтом Crunchyroll.",
    },
    "curiosity-stream": {
        "en": "Thousands of documentaries about science, history, nature and technology, from a service dedicated to non-fiction. Web app with controller support.",
        "fr": "Des milliers de documentaires sur la science, l'histoire, la nature et la technologie, par un service dédié au réel. Web app avec prise en charge manette.",
        "de": "Tausende Dokumentationen über Wissenschaft, Geschichte, Natur und Technik von einem auf Non-Fiction spezialisierten Dienst. Web-App mit Controller-Unterstützung.",
        "es": "Miles de documentales sobre ciencia, historia, naturaleza y tecnología, de un servicio dedicado a la no ficción. Web app con soporte de mando.",
        "it": "Migliaia di documentari su scienza, storia, natura e tecnologia, da un servizio dedicato alla non-fiction. Web app con supporto del controller.",
        "pt": "Milhares de documentários sobre ciência, história, natureza e tecnologia, de um serviço dedicado à não-ficção. Web app com suporte de comando.",
        "nl": "Duizenden documentaires over wetenschap, geschiedenis, natuur en techniek, van een dienst gewijd aan non-fictie. Webapp met controllerondersteuning.",
        "pl": "Tysiące filmów dokumentalnych o nauce, historii, przyrodzie i technologii, od serwisu poświęconego non-fiction. Aplikacja webowa z obsługą pada.",
        "ru": "Тысячи документальных фильмов о науке, истории, природе и технологиях от сервиса, посвящённого нон-фикшн. Веб-приложение с поддержкой геймпада.",
    },
    "sling-tv": {
        "en": "Live US TV over the internet: news, sport and entertainment channel packs. Web app with Widevine DRM and controller support.",
        "fr": "La TV US en direct par internet : bouquets de chaînes info, sport et divertissement. Web app avec DRM Widevine et prise en charge manette.",
        "de": "US-Live-TV übers Internet: Senderpakete für Nachrichten, Sport und Unterhaltung. Web-App mit Widevine-DRM und Controller-Unterstützung.",
        "es": "TV en directo de EE. UU. por internet: paquetes de canales de noticias, deporte y entretenimiento. Web app con DRM Widevine y soporte de mando.",
        "it": "TV USA in diretta via internet: pacchetti di canali di notizie, sport e intrattenimento. Web app con DRM Widevine e supporto del controller.",
        "pt": "TV dos EUA em direto pela internet: pacotes de canais de notícias, desporto e entretenimento. Web app com DRM Widevine e suporte de comando.",
        "nl": "Live Amerikaanse tv via internet: zenderpakketten met nieuws, sport en entertainment. Webapp met Widevine-DRM en controllerondersteuning.",
        "pl": "Amerykańska telewizja na żywo przez internet: pakiety kanałów z wiadomościami, sportem i rozrywką. Aplikacja webowa z DRM Widevine i obsługą pada.",
        "ru": "Американское живое ТВ через интернет: пакеты новостных, спортивных и развлекательных каналов. Веб-приложение с Widevine DRM и поддержкой геймпада.",
    },
    "vimeo": {
        "en": "High-quality, ad-free videos from independent creators and filmmakers. Web app with controller support.",
        "fr": "Des vidéos de qualité, sans pub, de créateurs et cinéastes indépendants. Web app avec prise en charge manette.",
        "de": "Hochwertige, werbefreie Videos von unabhängigen Kreativen und Filmemachern. Web-App mit Controller-Unterstützung.",
        "es": "Vídeos de calidad, sin anuncios, de creadores y cineastas independientes. Web app con soporte de mando.",
        "it": "Video di qualità, senza pubblicità, da creatori e registi indipendenti. Web app con supporto del controller.",
        "pt": "Vídeos de qualidade, sem anúncios, de criadores e cineastas independentes. Web app com suporte de comando.",
        "nl": "Hoogwaardige, reclamevrije video's van onafhankelijke makers en filmmakers. Webapp met controllerondersteuning.",
        "pl": "Wysokiej jakości filmy bez reklam od niezależnych twórców i filmowców. Aplikacja webowa z obsługą pada.",
        "ru": "Качественные видео без рекламы от независимых авторов и режиссёров. Веб-приложение с поддержкой геймпада.",
    },
    "youtube-tv": {
        "en": "Live US TV in YouTube's interface: national networks, sport and an unlimited cloud DVR. Web app with controller support.",
        "fr": "La TV US en direct dans l'interface YouTube : grandes chaînes, sport et enregistreur cloud illimité. Web app avec prise en charge manette.",
        "de": "US-Live-TV in der YouTube-Oberfläche: große Sender, Sport und unbegrenzter Cloud-Rekorder. Web-App mit Controller-Unterstützung.",
        "es": "TV en directo de EE. UU. con la interfaz de YouTube: grandes cadenas, deporte y DVR en la nube ilimitado. Web app con soporte de mando.",
        "it": "TV USA in diretta nell'interfaccia YouTube: grandi reti, sport e videoregistratore cloud illimitato. Web app con supporto del controller.",
        "pt": "TV dos EUA em direto na interface do YouTube: grandes canais, desporto e gravador na nuvem ilimitado. Web app com suporte de comando.",
        "nl": "Live Amerikaanse tv in de YouTube-interface: grote zenders, sport en onbeperkte cloud-dvr. Webapp met controllerondersteuning.",
        "pl": "Amerykańska telewizja na żywo w interfejsie YouTube: duże stacje, sport i nielimitowany rejestrator w chmurze. Aplikacja webowa z obsługą pada.",
        "ru": "Американское живое ТВ в интерфейсе YouTube: крупные каналы, спорт и безлимитный облачный видеорегистратор. Веб-приложение с поддержкой геймпада.",
    },
    "plex": {
        "en": "The couch interface for your Plex server: films, series, music and photos with controller-first navigation. Also includes Plex's free ad-supported films and live channels.",
        "fr": "L'interface canapé de ton serveur Plex : films, séries, musique et photos, navigation pensée manette. Inclut aussi les films gratuits (avec pub) et chaînes live de Plex.",
        "de": "Die Sofa-Oberfläche für deinen Plex-Server: Filme, Serien, Musik und Fotos, Bedienung ganz auf den Controller ausgelegt. Enthält auch die kostenlosen werbefinanzierten Filme und Live-Kanäle von Plex.",
        "es": "La interfaz de sofá para tu servidor Plex: películas, series, música y fotos con navegación pensada para el mando. Incluye además las películas gratis (con anuncios) y canales en directo de Plex.",
        "it": "L'interfaccia da divano per il tuo server Plex: film, serie, musica e foto con navigazione pensata per il controller. Include anche i film gratuiti (con pubblicità) e i canali live di Plex.",
        "pt": "A interface de sofá para o teu servidor Plex: filmes, séries, música e fotos com navegação pensada para o comando. Inclui ainda os filmes gratuitos (com anúncios) e canais ao vivo do Plex.",
        "nl": "De bankinterface voor je Plex-server: films, series, muziek en foto's met bediening gericht op de controller. Bevat ook de gratis films (met reclame) en livekanalen van Plex.",
        "pl": "Kanapowy interfejs dla twojego serwera Plex: filmy, seriale, muzyka i zdjęcia z nawigacją zaprojektowaną pod pada. Zawiera też darmowe filmy (z reklamami) i kanały na żywo od Plex.",
        "ru": "Диванный интерфейс для вашего сервера Plex: фильмы, сериалы, музыка и фото с навигацией под геймпад. Включает также бесплатные фильмы (с рекламой) и живые каналы Plex.",
    },
    "jellyfin": {
        "en": "Desktop client for your Jellyfin server — the free, open-source media server. Browse and play your films, series and music from the couch.",
        "fr": "Client desktop pour ton serveur Jellyfin — le serveur multimédia libre et gratuit. Parcours et lis tes films, séries et musiques depuis le canapé.",
        "de": "Desktop-Client für deinen Jellyfin-Server — den freien Open-Source-Medienserver. Durchstöbere und spiele deine Filme, Serien und Musik vom Sofa aus.",
        "es": "Cliente de escritorio para tu servidor Jellyfin, el servidor multimedia libre y gratuito. Explora y reproduce tus películas, series y música desde el sofá.",
        "it": "Client desktop per il tuo server Jellyfin — il media server libero e open source. Sfoglia e riproduci film, serie e musica direttamente dal divano.",
        "pt": "Cliente de desktop para o teu servidor Jellyfin — o servidor multimédia livre e gratuito. Explora e reproduz os teus filmes, séries e música a partir do sofá.",
        "nl": "Desktopclient voor je Jellyfin-server — de gratis opensource-mediaserver. Blader door en speel je films, series en muziek af vanaf de bank.",
        "pl": "Klient desktopowy dla twojego serwera Jellyfin — darmowego, otwartego serwera multimediów. Przeglądaj i odtwarzaj filmy, seriale i muzykę prosto z kanapy.",
        "ru": "Настольный клиент для вашего сервера Jellyfin — свободного медиасервера с открытым кодом. Просматривайте и воспроизводите фильмы, сериалы и музыку прямо с дивана.",
    },
    "kodi": {
        "en": "The veteran open-source media center: local library, network shares, music, photos and a huge add-on ecosystem. Its TV-style interface is fully navigable with a controller.",
        "fr": "Le vétéran des media centers open source : bibliothèque locale, partages réseau, musique, photos et un immense écosystème d'extensions. Son interface façon TV se pilote entièrement à la manette.",
        "de": "Der Veteran unter den Open-Source-Mediacentern: lokale Bibliothek, Netzwerkfreigaben, Musik, Fotos und ein riesiges Add-on-Ökosystem. Die TV-artige Oberfläche lässt sich komplett mit dem Controller bedienen.",
        "es": "El veterano de los media centers open source: biblioteca local, recursos de red, música, fotos y un enorme ecosistema de add-ons. Su interfaz estilo TV se maneja por completo con el mando.",
        "it": "Il veterano dei media center open source: libreria locale, condivisioni di rete, musica, foto e un enorme ecosistema di add-on. La sua interfaccia in stile TV si naviga interamente col controller.",
        "pt": "O veterano dos media centers open source: biblioteca local, partilhas de rede, música, fotos e um enorme ecossistema de add-ons. A sua interface estilo TV navega-se totalmente com o comando.",
        "nl": "De veteraan onder de opensource-mediacenters: lokale bibliotheek, netwerkshares, muziek, foto's en een enorm add-on-ecosysteem. De tv-achtige interface is volledig met een controller te bedienen.",
        "pl": "Weteran wśród otwartych centrów multimedialnych: lokalna biblioteka, udziały sieciowe, muzyka, zdjęcia i ogromny ekosystem dodatków. Jego telewizyjny interfejs w pełni obsłużysz padem.",
        "ru": "Ветеран среди медиацентров с открытым кодом: локальная библиотека, сетевые ресурсы, музыка, фото и огромная экосистема дополнений. ТВ-интерфейс полностью управляется геймпадом.",
    },
    "stremio": {
        "en": "One hub for your video sources: catalogues and community add-ons, watch-progress sync and a TV-friendly interface. Sign in with a Stremio account to sync your library across devices.",
        "fr": "Un hub unique pour tes sources vidéo : catalogues et extensions communautaires, reprise de lecture synchronisée et interface adaptée TV. Connecte un compte Stremio pour synchroniser ta bibliothèque entre appareils.",
        "de": "Ein Hub für deine Videoquellen: Kataloge und Community-Add-ons, synchronisierter Wiedergabefortschritt und eine TV-freundliche Oberfläche. Mit Stremio-Konto anmelden, um die Bibliothek geräteübergreifend zu synchronisieren.",
        "es": "Un único hub para tus fuentes de vídeo: catálogos y add-ons comunitarios, progreso de visionado sincronizado e interfaz apta para TV. Inicia sesión con una cuenta Stremio para sincronizar tu biblioteca entre dispositivos.",
        "it": "Un unico hub per le tue fonti video: cataloghi e add-on della community, avanzamento di visione sincronizzato e interfaccia adatta alla TV. Accedi con un account Stremio per sincronizzare la libreria tra dispositivi.",
        "pt": "Um único hub para as tuas fontes de vídeo: catálogos e add-ons da comunidade, progresso de visualização sincronizado e interface adequada à TV. Inicia sessão com uma conta Stremio para sincronizar a biblioteca entre dispositivos.",
        "nl": "Eén hub voor je videobronnen: catalogi en community-add-ons, gesynchroniseerde kijkvoortgang en een tv-vriendelijke interface. Log in met een Stremio-account om je bibliotheek tussen apparaten te synchroniseren.",
        "pl": "Jeden hub dla twoich źródeł wideo: katalogi i dodatki społeczności, synchronizacja postępu oglądania i interfejs przyjazny TV. Zaloguj się kontem Stremio, by synchronizować bibliotekę między urządzeniami.",
        "ru": "Единый хаб для ваших видеоисточников: каталоги и дополнения сообщества, синхронизация прогресса просмотра и ТВ-интерфейс. Войдите с аккаунтом Stremio, чтобы синхронизировать библиотеку между устройствами.",
    },

    # ── Music ──────────────────────────────────────────────────────────────
    "spotify": {
        "en": "Spotify's web player as a dedicated app: playlists, albums, podcasts and recommendations. Sign in with your account (free or Premium); navigation works with the controller.",
        "fr": "Le lecteur web de Spotify en app dédiée : playlists, albums, podcasts et recommandations. Connecte ton compte (gratuit ou Premium) ; la navigation fonctionne à la manette.",
        "de": "Der Spotify-Webplayer als eigene App: Playlists, Alben, Podcasts und Empfehlungen. Mit dem Konto anmelden (kostenlos oder Premium); die Bedienung funktioniert mit dem Controller.",
        "es": "El reproductor web de Spotify como app dedicada: playlists, álbumes, pódcasts y recomendaciones. Inicia sesión con tu cuenta (gratis o Premium); la navegación funciona con el mando.",
        "it": "Il player web di Spotify come app dedicata: playlist, album, podcast e consigli. Accedi col tuo account (gratuito o Premium); la navigazione funziona col controller.",
        "pt": "O leitor web do Spotify como app dedicada: playlists, álbuns, podcasts e recomendações. Inicia sessão com a tua conta (gratuita ou Premium); a navegação funciona com o comando.",
        "nl": "De webspeler van Spotify als aparte app: afspeellijsten, albums, podcasts en aanbevelingen. Log in met je account (gratis of Premium); de bediening werkt met de controller.",
        "pl": "Webowy odtwarzacz Spotify jako dedykowana aplikacja: playlisty, albumy, podcasty i rekomendacje. Zaloguj się kontem (darmowym lub Premium); nawigacja działa padem.",
        "ru": "Веб-плеер Spotify как отдельное приложение: плейлисты, альбомы, подкасты и рекомендации. Войдите в аккаунт (бесплатный или Premium); навигация работает с геймпада.",
    },
    "youtube-music": {
        "en": "YouTube Music as a dedicated web app: your mixes, playlists and the huge YouTube catalogue including live versions and covers. Sign in with your Google account; controller navigation included.",
        "fr": "YouTube Music en web app dédiée : tes mix, playlists et l'immense catalogue YouTube, lives et reprises compris. Connecte ton compte Google ; navigation manette incluse.",
        "de": "YouTube Music als eigene Web-App: deine Mixe, Playlists und der riesige YouTube-Katalog inklusive Live-Versionen und Covern. Mit Google-Konto anmelden; Controller-Bedienung inklusive.",
        "es": "YouTube Music como web app dedicada: tus mixes, playlists y el enorme catálogo de YouTube, con directos y versiones. Inicia sesión con tu cuenta de Google; navegación con mando incluida.",
        "it": "YouTube Music come web app dedicata: i tuoi mix, le playlist e l'enorme catalogo YouTube, con live e cover. Accedi col tuo account Google; navigazione col controller inclusa.",
        "pt": "YouTube Music como web app dedicada: os teus mixes, playlists e o enorme catálogo do YouTube, incluindo versões ao vivo e covers. Inicia sessão com a tua conta Google; navegação com comando incluída.",
        "nl": "YouTube Music als aparte webapp: je mixen, afspeellijsten en de enorme YouTube-catalogus, inclusief liveversies en covers. Log in met je Google-account; controllerbediening inbegrepen.",
        "pl": "YouTube Music jako dedykowana aplikacja webowa: twoje miksy, playlisty i ogromny katalog YouTube, w tym wersje na żywo i covery. Zaloguj się kontem Google; nawigacja padem w zestawie.",
        "ru": "YouTube Music как отдельное веб-приложение: ваши миксы, плейлисты и огромный каталог YouTube, включая живые версии и каверы. Войдите с аккаунтом Google; управление геймпадом в комплекте.",
    },
    "tidal": {
        "en": "Community desktop client for TIDAL with lossless Hi-Fi and Dolby Atmos streaming (subscription required). Sign in with your TIDAL account and control playback from the couch.",
        "fr": "Client desktop communautaire pour TIDAL avec streaming Hi-Fi sans perte et Dolby Atmos (abonnement requis). Connecte ton compte TIDAL et pilote la lecture depuis le canapé.",
        "de": "Community-Desktop-Client für TIDAL mit verlustfreiem Hi-Fi- und Dolby-Atmos-Streaming (Abo erforderlich). Mit dem TIDAL-Konto anmelden und die Wiedergabe vom Sofa aus steuern.",
        "es": "Cliente de escritorio comunitario para TIDAL con streaming Hi-Fi sin pérdidas y Dolby Atmos (requiere suscripción). Inicia sesión con tu cuenta TIDAL y controla la reproducción desde el sofá.",
        "it": "Client desktop della community per TIDAL con streaming Hi-Fi lossless e Dolby Atmos (abbonamento richiesto). Accedi col tuo account TIDAL e controlla la riproduzione dal divano.",
        "pt": "Cliente de desktop da comunidade para o TIDAL com streaming Hi-Fi sem perdas e Dolby Atmos (requer subscrição). Inicia sessão com a tua conta TIDAL e controla a reprodução do sofá.",
        "nl": "Community-desktopclient voor TIDAL met lossless hifi- en Dolby Atmos-streaming (abonnement vereist). Log in met je TIDAL-account en bedien het afspelen vanaf de bank.",
        "pl": "Społecznościowy klient desktopowy TIDAL ze streamingiem bezstratnym Hi-Fi i Dolby Atmos (wymagana subskrypcja). Zaloguj się kontem TIDAL i steruj odtwarzaniem z kanapy.",
        "ru": "Клиент TIDAL от сообщества с потоковым Hi-Fi без потерь и Dolby Atmos (нужна подписка). Войдите с аккаунтом TIDAL и управляйте воспроизведением с дивана.",
    },
    "deezer": {
        "en": "Desktop client for Deezer: playlists, the personalised Flow, podcasts and lossless streaming with a compatible subscription. Sign in with your Deezer account.",
        "fr": "Client desktop pour Deezer : playlists, le Flow personnalisé, podcasts et streaming sans perte avec un abonnement compatible. Connecte ton compte Deezer.",
        "de": "Desktop-Client für Deezer: Playlists, der personalisierte Flow, Podcasts und verlustfreies Streaming mit passendem Abo. Mit dem Deezer-Konto anmelden.",
        "es": "Cliente de escritorio para Deezer: playlists, el Flow personalizado, pódcasts y streaming sin pérdidas con una suscripción compatible. Inicia sesión con tu cuenta de Deezer.",
        "it": "Client desktop per Deezer: playlist, il Flow personalizzato, podcast e streaming lossless con un abbonamento compatibile. Accedi col tuo account Deezer.",
        "pt": "Cliente de desktop para o Deezer: playlists, o Flow personalizado, podcasts e streaming sem perdas com uma subscrição compatível. Inicia sessão com a tua conta Deezer.",
        "nl": "Desktopclient voor Deezer: afspeellijsten, de gepersonaliseerde Flow, podcasts en lossless streaming met een geschikt abonnement. Log in met je Deezer-account.",
        "pl": "Klient desktopowy Deezera: playlisty, spersonalizowany Flow, podcasty i streaming bezstratny z odpowiednią subskrypcją. Zaloguj się kontem Deezer.",
        "ru": "Настольный клиент Deezer: плейлисты, персональный Flow, подкасты и стриминг без потерь с подходящей подпиской. Войдите с аккаунтом Deezer.",
    },

    # ── Cloud gaming ───────────────────────────────────────────────────────
    "geforce-now": {
        "en": "NVIDIA's cloud gaming: play games you already own on Steam, Epic and other stores, rendered on RTX servers — nothing to install locally. Web app with full controller support; a free tier is available.",
        "fr": "Le cloud gaming de NVIDIA : joue aux jeux que tu possèdes déjà sur Steam, Epic et d'autres boutiques, rendus sur des serveurs RTX — rien à installer en local. Web app avec prise en charge complète de la manette ; une offre gratuite existe.",
        "de": "NVIDIAs Cloud-Gaming: Spiele, die du auf Steam, Epic und anderen Stores schon besitzt, gerendert auf RTX-Servern — nichts lokal zu installieren. Web-App mit voller Controller-Unterstützung; es gibt eine Gratis-Stufe.",
        "es": "El cloud gaming de NVIDIA: juega a los títulos que ya posees en Steam, Epic y otras tiendas, renderizados en servidores RTX, sin instalar nada en local. Web app con soporte completo de mando; hay un nivel gratuito.",
        "it": "Il cloud gaming di NVIDIA: gioca ai titoli che già possiedi su Steam, Epic e altri store, renderizzati su server RTX — niente da installare in locale. Web app con pieno supporto del controller; esiste un piano gratuito.",
        "pt": "O cloud gaming da NVIDIA: joga os títulos que já tens na Steam, Epic e outras lojas, renderizados em servidores RTX — nada para instalar localmente. Web app com suporte total de comando; existe um plano gratuito.",
        "nl": "Cloudgaming van NVIDIA: speel games die je al bezit op Steam, Epic en andere winkels, gerenderd op RTX-servers — niets lokaal te installeren. Webapp met volledige controllerondersteuning; er is een gratis niveau.",
        "pl": "Cloud gaming NVIDII: graj w tytuły, które już masz na Steam, Epic i w innych sklepach, renderowane na serwerach RTX — nic nie instalujesz lokalnie. Aplikacja webowa z pełną obsługą pada; dostępny jest darmowy plan.",
        "ru": "Облачный гейминг NVIDIA: играйте в игры, которые уже есть у вас в Steam, Epic и других магазинах, — рендеринг на серверах RTX, локально ничего не ставится. Веб-приложение с полной поддержкой геймпада; есть бесплатный тариф.",
    },
    "xbox-cloud": {
        "en": "Stream hundreds of Game Pass Ultimate titles straight from Microsoft's cloud, with no installation. Web app with full controller support.",
        "fr": "Streame des centaines de jeux Game Pass Ultimate directement depuis le cloud de Microsoft, sans installation. Web app avec prise en charge complète de la manette.",
        "de": "Streame Hunderte Game-Pass-Ultimate-Titel direkt aus Microsofts Cloud, ohne Installation. Web-App mit voller Controller-Unterstützung.",
        "es": "Juega en streaming a cientos de títulos de Game Pass Ultimate directamente desde la nube de Microsoft, sin instalación. Web app con soporte completo de mando.",
        "it": "Gioca in streaming a centinaia di titoli Game Pass Ultimate direttamente dal cloud di Microsoft, senza installazione. Web app con pieno supporto del controller.",
        "pt": "Joga em streaming centenas de títulos do Game Pass Ultimate diretamente da nuvem da Microsoft, sem instalação. Web app com suporte total de comando.",
        "nl": "Stream honderden Game Pass Ultimate-titels rechtstreeks uit de cloud van Microsoft, zonder installatie. Webapp met volledige controllerondersteuning.",
        "pl": "Streamuj setki tytułów z Game Pass Ultimate prosto z chmury Microsoftu, bez instalacji. Aplikacja webowa z pełną obsługą pada.",
        "ru": "Стримьте сотни игр Game Pass Ultimate прямо из облака Microsoft, без установки. Веб-приложение с полной поддержкой геймпада.",
    },
    "amazon-luna": {
        "en": "Amazon's cloud gaming with channel-based catalogues, including titles included with Prime (availability depends on region). Web app with controller support.",
        "fr": "Le cloud gaming d'Amazon avec ses catalogues par chaînes, dont des jeux inclus avec Prime (disponibilité selon la région). Web app avec prise en charge manette.",
        "de": "Amazons Cloud-Gaming mit kanalbasierten Katalogen, darunter Titel im Prime-Abo (Verfügbarkeit je nach Region). Web-App mit Controller-Unterstützung.",
        "es": "El cloud gaming de Amazon con catálogos por canales, incluidos juegos con Prime (disponibilidad según la región). Web app con soporte de mando.",
        "it": "Il cloud gaming di Amazon con cataloghi a canali, inclusi titoli compresi con Prime (disponibilità a seconda della regione). Web app con supporto del controller.",
        "pt": "O cloud gaming da Amazon com catálogos por canais, incluindo títulos incluídos no Prime (disponibilidade conforme a região). Web app com suporte de comando.",
        "nl": "Cloudgaming van Amazon met kanaalgebaseerde catalogi, waaronder titels bij Prime (beschikbaarheid per regio). Webapp met controllerondersteuning.",
        "pl": "Cloud gaming Amazona z katalogami w formie kanałów, w tym gry w ramach Prime (dostępność zależna od regionu). Aplikacja webowa z obsługą pada.",
        "ru": "Облачный гейминг Amazon с каталогами-каналами, включая игры в составе Prime (доступность зависит от региона). Веб-приложение с поддержкой геймпада.",
    },
    "moonlight": {
        "en": "Stream your own gaming PC to this machine with very low latency, from a Sunshine or NVIDIA GameStream host. Up to 4K/HDR, with full controller passthrough.",
        "fr": "Streame ton propre PC de jeu vers cette machine avec une latence très faible, depuis un hôte Sunshine ou NVIDIA GameStream. Jusqu'à la 4K/HDR, avec passthrough complet de la manette.",
        "de": "Streame deinen eigenen Gaming-PC mit sehr geringer Latenz auf diese Maschine, von einem Sunshine- oder NVIDIA-GameStream-Host. Bis zu 4K/HDR, mit vollem Controller-Passthrough.",
        "es": "Transmite tu propio PC de juegos a esta máquina con latencia muy baja, desde un host Sunshine o NVIDIA GameStream. Hasta 4K/HDR, con paso completo del mando.",
        "it": "Trasmetti il tuo PC da gioco a questa macchina con latenza bassissima, da un host Sunshine o NVIDIA GameStream. Fino a 4K/HDR, con passthrough completo del controller.",
        "pt": "Transmite o teu próprio PC de jogos para esta máquina com latência muito baixa, a partir de um host Sunshine ou NVIDIA GameStream. Até 4K/HDR, com passagem total do comando.",
        "nl": "Stream je eigen game-pc naar deze machine met zeer lage latentie, vanaf een Sunshine- of NVIDIA GameStream-host. Tot 4K/HDR, met volledige controller-passthrough.",
        "pl": "Streamuj własny komputer do gier na tę maszynę z bardzo małym opóźnieniem, z hosta Sunshine lub NVIDIA GameStream. Do 4K/HDR, z pełnym przekazywaniem pada.",
        "ru": "Стримьте свой игровой ПК на эту машину с очень низкой задержкой — с хоста Sunshine или NVIDIA GameStream. До 4K/HDR, с полной поддержкой геймпада.",
    },
    "chiaki": {
        "en": "PlayStation 4/5 Remote Play client: stream your console to this machine over the network. Pair it once with your PSN account; controller and audio are handled.",
        "fr": "Client Remote Play PlayStation 4/5 : streame ta console vers cette machine par le réseau. Appaire-la une fois avec ton compte PSN ; manette et audio sont gérés.",
        "de": "Remote-Play-Client für PlayStation 4/5: streame deine Konsole übers Netzwerk auf diese Maschine. Einmal mit dem PSN-Konto koppeln; Controller und Audio sind eingerichtet.",
        "es": "Cliente de Remote Play para PlayStation 4/5: transmite tu consola a esta máquina por la red. Empareja una vez con tu cuenta PSN; mando y audio quedan resueltos.",
        "it": "Client Remote Play per PlayStation 4/5: trasmetti la tua console a questa macchina via rete. Associala una volta col tuo account PSN; controller e audio sono gestiti.",
        "pt": "Cliente de Remote Play para PlayStation 4/5: transmite a tua consola para esta máquina pela rede. Emparelha uma vez com a tua conta PSN; comando e áudio ficam tratados.",
        "nl": "Remote Play-client voor PlayStation 4/5: stream je console via het netwerk naar deze machine. Koppel eenmalig met je PSN-account; controller en audio zijn geregeld.",
        "pl": "Klient Remote Play dla PlayStation 4/5: streamuj konsolę na tę maszynę przez sieć. Sparuj raz z kontem PSN; pad i dźwięk są obsłużone.",
        "ru": "Клиент Remote Play для PlayStation 4/5: стримьте консоль на эту машину по сети. Один раз свяжите с аккаунтом PSN; геймпад и звук работают из коробки.",
    },
    "greenlight": {
        "en": "Unofficial Xbox client: stream your own console over the local network, or xCloud titles from the cloud. Controller-first and comfortable in game mode.",
        "fr": "Client Xbox non officiel : streame ta propre console en réseau local, ou les jeux xCloud depuis le cloud. Pensé manette, confortable en mode jeu.",
        "de": "Inoffizieller Xbox-Client: streame deine eigene Konsole übers lokale Netzwerk oder xCloud-Titel aus der Cloud. Controller-orientiert und bequem im Spielmodus.",
        "es": "Cliente no oficial de Xbox: transmite tu propia consola por la red local, o títulos de xCloud desde la nube. Pensado para el mando y cómodo en modo juego.",
        "it": "Client Xbox non ufficiale: trasmetti la tua console sulla rete locale, o i titoli xCloud dal cloud. Pensato per il controller e comodo in modalità gioco.",
        "pt": "Cliente Xbox não oficial: transmite a tua própria consola pela rede local, ou títulos xCloud a partir da nuvem. Pensado para o comando e confortável em modo de jogo.",
        "nl": "Onofficiële Xbox-client: stream je eigen console via het lokale netwerk, of xCloud-titels uit de cloud. Gericht op de controller en comfortabel in de gamemodus.",
        "pl": "Nieoficjalny klient Xbox: streamuj własną konsolę przez sieć lokalną lub tytuły xCloud z chmury. Zaprojektowany pod pada, wygodny w trybie gry.",
        "ru": "Неофициальный клиент Xbox: стримьте собственную консоль по локальной сети или игры xCloud из облака. Ориентирован на геймпад, удобен в игровом режиме.",
    },
    "parsec": {
        "en": "Low-latency remote desktop and game streaming: connect to your own PC from anywhere, or play together with friends remotely. Sign in with a Parsec account.",
        "fr": "Bureau à distance et streaming de jeu à faible latence : connecte-toi à ton propre PC de n'importe où, ou joue à distance avec des amis. Connexion avec un compte Parsec.",
        "de": "Remote-Desktop und Spiele-Streaming mit geringer Latenz: verbinde dich von überall mit deinem eigenen PC oder spiele aus der Ferne mit Freunden. Anmeldung mit einem Parsec-Konto.",
        "es": "Escritorio remoto y streaming de juegos de baja latencia: conéctate a tu propio PC desde cualquier lugar, o juega a distancia con amigos. Inicia sesión con una cuenta Parsec.",
        "it": "Desktop remoto e streaming di giochi a bassa latenza: collegati al tuo PC da ovunque, o gioca a distanza con gli amici. Accesso con un account Parsec.",
        "pt": "Ambiente de trabalho remoto e streaming de jogos de baixa latência: liga-te ao teu próprio PC de qualquer lugar, ou joga à distância com amigos. Inicia sessão com uma conta Parsec.",
        "nl": "Extern bureaublad en gamestreaming met lage latentie: verbind overal met je eigen pc, of speel op afstand met vrienden. Log in met een Parsec-account.",
        "pl": "Zdalny pulpit i streaming gier o niskim opóźnieniu: łącz się ze swoim komputerem skądkolwiek lub graj zdalnie ze znajomymi. Zaloguj się kontem Parsec.",
        "ru": "Удалённый рабочий стол и стриминг игр с низкой задержкой: подключайтесь к своему ПК откуда угодно или играйте с друзьями удалённо. Вход с аккаунтом Parsec.",
    },

    # ── Apps & tools ───────────────────────────────────────────────────────
    "lutris": {
        "en": "Open gaming platform that installs and organises games from GOG, emulators, Wine and more, with community install scripts. A desktop-mode companion for everything that isn't on Steam.",
        "fr": "Plateforme de jeu ouverte qui installe et organise les jeux GOG, les émulateurs, Wine et plus, avec des scripts d'installation communautaires. Un compagnon en mode bureau pour tout ce qui n'est pas sur Steam.",
        "de": "Offene Gaming-Plattform, die Spiele von GOG, Emulatoren, Wine und mehr installiert und organisiert, mit Community-Installationsskripten. Ein Begleiter im Desktop-Modus für alles, was nicht auf Steam ist.",
        "es": "Plataforma de juego abierta que instala y organiza juegos de GOG, emuladores, Wine y más, con scripts de instalación comunitarios. Un compañero en modo escritorio para todo lo que no está en Steam.",
        "it": "Piattaforma di gioco aperta che installa e organizza giochi GOG, emulatori, Wine e altro, con script d'installazione della community. Un compagno in modalità desktop per tutto ciò che non è su Steam.",
        "pt": "Plataforma de jogo aberta que instala e organiza jogos da GOG, emuladores, Wine e mais, com scripts de instalação da comunidade. Um companheiro em modo desktop para tudo o que não está na Steam.",
        "nl": "Open gamingplatform dat games van GOG, emulators, Wine en meer installeert en organiseert, met community-installatiescripts. Een metgezel in desktopmodus voor alles wat niet op Steam staat.",
        "pl": "Otwarta platforma gamingowa, która instaluje i porządkuje gry z GOG, emulatory, Wine i więcej, z instalacyjnymi skryptami społeczności. Towarzysz w trybie pulpitu dla wszystkiego, czego nie ma na Steamie.",
        "ru": "Открытая игровая платформа, которая устанавливает и упорядочивает игры GOG, эмуляторы, Wine и другое, с установочными скриптами сообщества. Помощник в режиме рабочего стола для всего, чего нет в Steam.",
    },
    "bottles": {
        "en": "Run Windows software and games in cleanly managed Wine prefixes (“bottles”), each with its own settings and dependencies. Best driven in desktop mode.",
        "fr": "Fais tourner logiciels et jeux Windows dans des préfixes Wine proprement gérés (« bottles »), chacun avec ses réglages et dépendances. À piloter de préférence en mode bureau.",
        "de": "Führe Windows-Software und -Spiele in sauber verwalteten Wine-Präfixen („Bottles“) aus, jedes mit eigenen Einstellungen und Abhängigkeiten. Am besten im Desktop-Modus zu bedienen.",
        "es": "Ejecuta software y juegos de Windows en prefijos de Wine bien gestionados («bottles»), cada uno con sus ajustes y dependencias. Se maneja mejor en modo escritorio.",
        "it": "Esegui software e giochi Windows in prefissi Wine gestiti con ordine («bottles»), ognuno con le proprie impostazioni e dipendenze. Da usare preferibilmente in modalità desktop.",
        "pt": "Corre software e jogos Windows em prefixos Wine bem geridos («bottles»), cada um com as suas definições e dependências. Melhor utilizado em modo desktop.",
        "nl": "Draai Windows-software en -games in netjes beheerde Wine-prefixes (“bottles”), elk met eigen instellingen en afhankelijkheden. Het best te bedienen in desktopmodus.",
        "pl": "Uruchamiaj windowsowe programy i gry w porządnie zarządzanych prefiksach Wine („bottles”), każdy z własnymi ustawieniami i zależnościami. Najlepiej obsługiwać w trybie pulpitu.",
        "ru": "Запускайте программы и игры Windows в аккуратно управляемых префиксах Wine («bottles»), у каждого свои настройки и зависимости. Удобнее всего в режиме рабочего стола.",
    },
    "retrodeck": {
        "en": "All-in-one retro gaming: the EmulationStation interface plus preconfigured emulators for dozens of consoles. Drop your ROMs and BIOS files in and play — fully controller-driven.",
        "fr": "Le rétrogaming tout-en-un : l'interface EmulationStation plus des émulateurs préconfigurés pour des dizaines de consoles. Dépose tes ROMs et BIOS et joue — entièrement pilotable à la manette.",
        "de": "Retro-Gaming all-in-one: die EmulationStation-Oberfläche plus vorkonfigurierte Emulatoren für Dutzende Konsolen. ROMs und BIOS-Dateien ablegen und losspielen — komplett per Controller bedienbar.",
        "es": "Retrogaming todo en uno: la interfaz EmulationStation más emuladores preconfigurados para decenas de consolas. Copia tus ROMs y BIOS y juega — se maneja por completo con el mando.",
        "it": "Il retrogaming tutto-in-uno: l'interfaccia EmulationStation più emulatori preconfigurati per decine di console. Copia le tue ROM e i BIOS e gioca — interamente guidato dal controller.",
        "pt": "Retro gaming tudo-em-um: a interface EmulationStation mais emuladores pré-configurados para dezenas de consolas. Coloca as tuas ROMs e BIOS e joga — totalmente controlável com o comando.",
        "nl": "Alles-in-één retrogaming: de EmulationStation-interface plus voorgeconfigureerde emulators voor tientallen consoles. Zet je ROM's en BIOS-bestanden erin en speel — volledig met de controller te bedienen.",
        "pl": "Retro granie wszystko-w-jednym: interfejs EmulationStation plus wstępnie skonfigurowane emulatory dziesiątek konsol. Wrzuć ROM-y i BIOS-y i graj — w pełni sterowane padem.",
        "ru": "Ретрогейминг всё-в-одном: интерфейс EmulationStation плюс преднастроенные эмуляторы для десятков консолей. Закиньте ROM и BIOS — и играйте, всё управляется геймпадом.",
    },
    "protonup-qt": {
        "en": "Install and update compatibility tools for Steam — GE-Proton, Luxtorpeda and more — in a couple of clicks. Handy right after adding non-Steam games that need a specific Proton.",
        "fr": "Installe et met à jour les outils de compatibilité pour Steam — GE-Proton, Luxtorpeda et plus — en deux clics. Pratique juste après avoir ajouté des jeux non-Steam qui demandent un Proton précis.",
        "de": "Installiere und aktualisiere Kompatibilitätstools für Steam — GE-Proton, Luxtorpeda und mehr — mit ein paar Klicks. Praktisch direkt nach dem Hinzufügen von Nicht-Steam-Spielen, die ein bestimmtes Proton brauchen.",
        "es": "Instala y actualiza herramientas de compatibilidad para Steam —GE-Proton, Luxtorpeda y más— en un par de clics. Útil justo después de añadir juegos que no son de Steam y requieren un Proton concreto.",
        "it": "Installa e aggiorna gli strumenti di compatibilità per Steam — GE-Proton, Luxtorpeda e altri — in un paio di clic. Comodo subito dopo aver aggiunto giochi non-Steam che richiedono un Proton specifico.",
        "pt": "Instala e atualiza ferramentas de compatibilidade para a Steam — GE-Proton, Luxtorpeda e mais — em dois cliques. Útil logo após adicionares jogos não-Steam que precisam de um Proton específico.",
        "nl": "Installeer en update compatibiliteitstools voor Steam — GE-Proton, Luxtorpeda en meer — in een paar klikken. Handig direct na het toevoegen van niet-Steam-games die een specifieke Proton nodig hebben.",
        "pl": "Instaluj i aktualizuj narzędzia zgodności dla Steam — GE-Proton, Luxtorpeda i inne — w kilka kliknięć. Przydatne zaraz po dodaniu gier spoza Steama, które wymagają konkretnego Protona.",
        "ru": "Устанавливайте и обновляйте инструменты совместимости для Steam — GE-Proton, Luxtorpeda и другие — в пару кликов. Полезно сразу после добавления не-Steam игр, которым нужен конкретный Proton.",
    },
    "flatseal": {
        "en": "Review and edit the permissions of your installed Flatpak apps: filesystem, devices, network and more. Useful to unlock a feature or tighten an app's sandbox.",
        "fr": "Consulte et modifie les permissions de tes applis Flatpak installées : système de fichiers, périphériques, réseau et plus. Utile pour débloquer une fonction ou renforcer le bac à sable d'une appli.",
        "de": "Prüfe und bearbeite die Berechtigungen deiner installierten Flatpak-Apps: Dateisystem, Geräte, Netzwerk und mehr. Nützlich, um eine Funktion freizuschalten oder die Sandbox einer App zu verschärfen.",
        "es": "Revisa y edita los permisos de tus aplicaciones Flatpak instaladas: sistema de archivos, dispositivos, red y más. Útil para desbloquear una función o endurecer el sandbox de una app.",
        "it": "Controlla e modifica i permessi delle tue app Flatpak installate: filesystem, dispositivi, rete e altro. Utile per sbloccare una funzione o irrigidire la sandbox di un'app.",
        "pt": "Consulta e edita as permissões das tuas apps Flatpak instaladas: sistema de ficheiros, dispositivos, rede e mais. Útil para desbloquear uma função ou reforçar a sandbox de uma app.",
        "nl": "Bekijk en bewerk de rechten van je geïnstalleerde Flatpak-apps: bestandssysteem, apparaten, netwerk en meer. Handig om een functie te ontgrendelen of de sandbox van een app aan te scherpen.",
        "pl": "Przeglądaj i edytuj uprawnienia zainstalowanych aplikacji Flatpak: system plików, urządzenia, sieć i więcej. Przydatne, by odblokować funkcję albo zaostrzyć piaskownicę aplikacji.",
        "ru": "Просматривайте и меняйте разрешения установленных Flatpak-приложений: файловая система, устройства, сеть и другое. Полезно, чтобы разблокировать функцию или ужесточить песочницу приложения.",
    },
}
