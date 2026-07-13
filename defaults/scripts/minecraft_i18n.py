#!/usr/bin/env python3
"""Localized texts for the Minecraft extension (9 UI languages, same rule as
the rest of SkullKey). Split out of minecraft.py the way ports_i18n.py is:
the backend imports `desc_for`, `pack_desc` and `uninstall_note`.

Both editions are installed through their legitimate launchers, which
require an account that owns the game — the descriptions say so explicitly
(Microsoft account for Java via Prism, Google Play purchase for Bedrock via
mcpelauncher)."""

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


_DESC = {
    "java": {
        "en": "Minecraft: Java Edition through Prism Launcher (open source). One-time setup: at first launch, sign in with a Microsoft account that owns the game — afterwards this shortcut boots straight into the latest Minecraft release (kept up to date daily). Java itself is downloaded automatically. Keyboard/mouse oriented: use a Steam Input layout in Game Mode, or add a controller mod via Prism Launcher.",
        "fr": "Minecraft : Java Edition via Prism Launcher (open source). Configuration unique : au premier lancement, connectez-vous avec un compte Microsoft possédant le jeu — ensuite ce raccourci démarre directement la dernière version de Minecraft (maintenue à jour quotidiennement). Java est téléchargé automatiquement. Pensé clavier/souris : utilisez une disposition Steam Input en mode jeu, ou ajoutez un mod manette via Prism Launcher.",
        "de": "Minecraft: Java Edition über Prism Launcher (Open Source). Einmalige Einrichtung: Beim ersten Start mit einem Microsoft-Konto anmelden, das das Spiel besitzt — danach startet diese Verknüpfung direkt die neueste Minecraft-Version (täglich aktuell gehalten). Java wird automatisch heruntergeladen. Auf Tastatur/Maus ausgelegt: Nutze im Gaming-Modus ein Steam-Input-Layout oder installiere über Prism Launcher eine Controller-Mod.",
        "es": "Minecraft: Java Edition mediante Prism Launcher (código abierto). Configuración única: en el primer inicio, inicia sesión con una cuenta Microsoft que posea el juego — después este acceso directo arranca directamente la última versión de Minecraft (actualizada a diario). Java se descarga automáticamente. Orientado a teclado/ratón: usa una disposición de Steam Input en el modo juego o añade un mod de mando desde Prism Launcher.",
        "it": "Minecraft: Java Edition tramite Prism Launcher (open source). Configurazione unica: al primo avvio accedi con un account Microsoft che possiede il gioco — poi questa scorciatoia avvia direttamente l'ultima versione di Minecraft (aggiornata ogni giorno). Java viene scaricato automaticamente. Pensato per tastiera/mouse: usa un layout Steam Input in modalità gioco oppure aggiungi una mod per controller da Prism Launcher.",
        "pt": "Minecraft: Java Edition através do Prism Launcher (código aberto). Configuração única: no primeiro arranque, inicie sessão com uma conta Microsoft que possua o jogo — depois este atalho arranca diretamente a versão mais recente do Minecraft (mantida atualizada diariamente). O Java é descarregado automaticamente. Orientado a teclado/rato: use um esquema Steam Input no modo de jogo ou adicione um mod de comando via Prism Launcher.",
        "nl": "Minecraft: Java Edition via Prism Launcher (open source). Eenmalige installatie: log bij de eerste start in met een Microsoft-account dat het spel bezit — daarna start deze snelkoppeling direct de nieuwste Minecraft-versie (dagelijks bijgewerkt). Java wordt automatisch gedownload. Gericht op toetsenbord/muis: gebruik een Steam Input-indeling in de gamemodus of voeg via Prism Launcher een controller-mod toe.",
        "pl": "Minecraft: Java Edition przez Prism Launcher (open source). Jednorazowa konfiguracja: przy pierwszym uruchomieniu zaloguj się kontem Microsoft posiadającym grę — potem ten skrót uruchamia od razu najnowszą wersję Minecrafta (aktualizowaną codziennie). Java pobiera się automatycznie. Nastawione na klawiaturę/mysz: użyj układu Steam Input w trybie gry albo dodaj moda do pada przez Prism Launcher.",
        "ru": "Minecraft: Java Edition через Prism Launcher (открытый исходный код). Разовая настройка: при первом запуске войдите в учётную запись Microsoft, владеющую игрой — затем этот ярлык сразу запускает последнюю версию Minecraft (обновляется ежедневно). Java скачивается автоматически. Рассчитано на клавиатуру/мышь: используйте раскладку Steam Input в игровом режиме или добавьте мод для геймпада через Prism Launcher.",
    },
    "bedrock": {
        "en": "Minecraft: Bedrock Edition through the community mcpelauncher (installed from Flathub). Sign in with a Google account that owns Minecraft on Google Play — the launcher then downloads the game itself. Native controller support, the best fit for Game Mode. The launcher is updated silently every day; your worlds are kept if you uninstall.",
        "fr": "Minecraft : Bedrock Edition via le launcher communautaire mcpelauncher (installé depuis Flathub). Connectez-vous avec un compte Google possédant Minecraft sur Google Play — le launcher télécharge ensuite le jeu lui-même. Manette gérée nativement, l'idéal pour le mode jeu. Le launcher se met à jour silencieusement chaque jour ; vos mondes sont conservés en cas de désinstallation.",
        "de": "Minecraft: Bedrock Edition über den Community-Launcher mcpelauncher (von Flathub installiert). Melde dich mit einem Google-Konto an, das Minecraft bei Google Play besitzt — der Launcher lädt das Spiel dann selbst herunter. Native Controller-Unterstützung, ideal für den Gaming-Modus. Der Launcher aktualisiert sich täglich im Hintergrund; deine Welten bleiben bei einer Deinstallation erhalten.",
        "es": "Minecraft: Bedrock Edition mediante el launcher comunitario mcpelauncher (instalado desde Flathub). Inicia sesión con una cuenta de Google que posea Minecraft en Google Play — el launcher descarga entonces el juego. Compatibilidad nativa con mando, lo ideal para el modo juego. El launcher se actualiza en silencio cada día; tus mundos se conservan si lo desinstalas.",
        "it": "Minecraft: Bedrock Edition tramite il launcher comunitario mcpelauncher (installato da Flathub). Accedi con un account Google che possiede Minecraft su Google Play — il launcher scarica poi il gioco. Supporto nativo del controller, l'ideale per la modalità gioco. Il launcher si aggiorna in silenzio ogni giorno; i tuoi mondi restano se lo disinstalli.",
        "pt": "Minecraft: Bedrock Edition através do launcher comunitário mcpelauncher (instalado a partir do Flathub). Inicie sessão com uma conta Google que possua o Minecraft na Google Play — o launcher descarrega depois o próprio jogo. Suporte nativo de comando, o ideal para o modo de jogo. O launcher atualiza-se silenciosamente todos os dias; os seus mundos são mantidos se desinstalar.",
        "nl": "Minecraft: Bedrock Edition via de community-launcher mcpelauncher (geïnstalleerd vanaf Flathub). Log in met een Google-account dat Minecraft op Google Play bezit — de launcher downloadt daarna zelf het spel. Native controllerondersteuning, ideaal voor de gamemodus. De launcher wordt dagelijks stil bijgewerkt; je werelden blijven bewaard bij verwijderen.",
        "pl": "Minecraft: Bedrock Edition przez społecznościowy launcher mcpelauncher (instalowany z Flathub). Zaloguj się kontem Google posiadającym Minecrafta w Google Play — launcher sam pobierze grę. Natywna obsługa pada, idealne do trybu gry. Launcher aktualizuje się codziennie po cichu; twoje światy zostają po odinstalowaniu.",
        "ru": "Minecraft: Bedrock Edition через комьюнити-лаунчер mcpelauncher (устанавливается из Flathub). Войдите в аккаунт Google, владеющий Minecraft в Google Play — лаунчер сам скачает игру. Нативная поддержка геймпада — идеально для игрового режима. Лаунчер обновляется ежедневно в фоне; ваши миры сохраняются при удалении.",
    },
    "prism": {
        "en": "The Prism Launcher interface itself: manage instances, Microsoft accounts, individual mods and resource packs for everything installed from this tab. Best used in Desktop Mode with mouse and keyboard.",
        "fr": "L'interface de Prism Launcher elle-même : gérez les instances, les comptes Microsoft, les mods à l'unité et les packs de ressources de tout ce qui est installé depuis cet onglet. À utiliser de préférence en mode bureau, au clavier/souris.",
        "de": "Die Prism-Launcher-Oberfläche selbst: Verwalte Instanzen, Microsoft-Konten, einzelne Mods und Ressourcenpakete für alles, was über diesen Tab installiert wurde. Am besten im Desktop-Modus mit Maus und Tastatur.",
        "es": "La propia interfaz de Prism Launcher: gestiona instancias, cuentas Microsoft, mods sueltos y paquetes de recursos de todo lo instalado desde esta pestaña. Mejor en modo escritorio con ratón y teclado.",
        "it": "L'interfaccia di Prism Launcher: gestisci istanze, account Microsoft, singole mod e resource pack di tutto ciò che è installato da questa scheda. Da usare preferibilmente in modalità desktop con mouse e tastiera.",
        "pt": "A própria interface do Prism Launcher: faça a gestão de instâncias, contas Microsoft, mods individuais e pacotes de recursos de tudo o que foi instalado a partir deste separador. Melhor no modo de secretária com rato e teclado.",
        "nl": "De Prism Launcher-interface zelf: beheer instanties, Microsoft-accounts, losse mods en resourcepacks van alles wat via dit tabblad is geïnstalleerd. Het handigst in de desktopmodus met muis en toetsenbord.",
        "pl": "Sam interfejs Prism Launchera: zarządzaj instancjami, kontami Microsoft, pojedynczymi modami i paczkami zasobów wszystkiego, co zainstalowano z tej karty. Najlepiej w trybie pulpitu z myszą i klawiaturą.",
        "ru": "Собственно интерфейс Prism Launcher: управляйте экземплярами, учётными записями Microsoft, отдельными модами и наборами ресурсов всего, что установлено с этой вкладки. Удобнее всего в режиме рабочего стола с мышью и клавиатурой.",
    },
}

_PACK = {
    "en": "Modrinth modpack{ver}, installed as its own Prism instance with its own Steam shortcut. Requires Minecraft: Java Edition — sign in with your Microsoft account in Prism at first launch. Minecraft, the mod loader and Java download automatically; the pack's mods are kept up to date daily.",
    "fr": "Modpack Modrinth{ver}, installé comme instance Prism séparée avec son propre raccourci Steam. Nécessite Minecraft : Java Edition — connectez-vous avec votre compte Microsoft dans Prism au premier lancement. Minecraft, le mod loader et Java se téléchargent automatiquement ; les mods du pack sont maintenus à jour quotidiennement.",
    "de": "Modrinth-Modpack{ver}, installiert als eigene Prism-Instanz mit eigener Steam-Verknüpfung. Benötigt Minecraft: Java Edition — melde dich beim ersten Start in Prism mit deinem Microsoft-Konto an. Minecraft, der Mod-Loader und Java werden automatisch heruntergeladen; die Mods des Packs werden täglich aktuell gehalten.",
    "es": "Modpack de Modrinth{ver}, instalado como instancia de Prism independiente con su propio acceso directo de Steam. Requiere Minecraft: Java Edition — inicia sesión con tu cuenta Microsoft en Prism en el primer arranque. Minecraft, el mod loader y Java se descargan automáticamente; los mods del pack se mantienen al día a diario.",
    "it": "Modpack Modrinth{ver}, installato come istanza Prism separata con la propria scorciatoia Steam. Richiede Minecraft: Java Edition — accedi con il tuo account Microsoft in Prism al primo avvio. Minecraft, il mod loader e Java si scaricano automaticamente; le mod del pack vengono aggiornate ogni giorno.",
    "pt": "Modpack do Modrinth{ver}, instalado como instância Prism separada com o seu próprio atalho Steam. Requer Minecraft: Java Edition — inicie sessão com a sua conta Microsoft no Prism no primeiro arranque. O Minecraft, o mod loader e o Java são descarregados automaticamente; os mods do pack são mantidos atualizados diariamente.",
    "nl": "Modrinth-modpack{ver}, geïnstalleerd als eigen Prism-instantie met een eigen Steam-snelkoppeling. Vereist Minecraft: Java Edition — log bij de eerste start in Prism in met je Microsoft-account. Minecraft, de modloader en Java worden automatisch gedownload; de mods van het pack worden dagelijks bijgewerkt.",
    "pl": "Modpack z Modrinth{ver}, instalowany jako osobna instancja Prism z własnym skrótem Steam. Wymaga Minecraft: Java Edition — przy pierwszym uruchomieniu zaloguj się w Prism kontem Microsoft. Minecraft, mod loader i Java pobierają się automatycznie; mody paczki są codziennie aktualizowane.",
    "ru": "Модпак с Modrinth{ver}, устанавливается как отдельный экземпляр Prism со своим ярлыком Steam. Требуется Minecraft: Java Edition — при первом запуске войдите в Prism с учётной записью Microsoft. Minecraft, загрузчик модов и Java скачиваются автоматически; моды пака обновляются ежедневно.",
}

_PACK_VER = {
    "en": " for Minecraft Java {mc}{loader}",
    "fr": " pour Minecraft Java {mc}{loader}",
    "de": " für Minecraft Java {mc}{loader}",
    "es": " para Minecraft Java {mc}{loader}",
    "it": " per Minecraft Java {mc}{loader}",
    "pt": " para Minecraft Java {mc}{loader}",
    "nl": " voor Minecraft Java {mc}{loader}",
    "pl": " dla Minecrafta Java {mc}{loader}",
    "ru": " для Minecraft Java {mc}{loader}",
}

_UNINSTALL = {
    "en": "⚠️ Uninstalling removes this instance and its settings; a backup of your worlds is kept and can be brought back with « Restore worlds backup » after a reinstall.",
    "fr": "⚠️ La désinstallation supprime cette instance et ses réglages ; un backup de vos mondes est conservé et se restaure avec « Restore worlds backup » après réinstallation.",
    "de": "⚠️ Beim Deinstallieren werden Instanz und Einstellungen entfernt; ein Backup deiner Welten bleibt erhalten und lässt sich nach einer Neuinstallation mit « Restore worlds backup » zurückholen.",
    "es": "⚠️ Al desinstalar se elimina esta instancia y sus ajustes; se conserva una copia de tus mundos, recuperable con « Restore worlds backup » tras reinstalar.",
    "it": "⚠️ La disinstallazione rimuove l'istanza e le impostazioni; un backup dei tuoi mondi viene conservato e si ripristina con « Restore worlds backup » dopo la reinstallazione.",
    "pt": "⚠️ A desinstalação remove esta instância e as suas definições; é mantida uma cópia dos seus mundos, recuperável com « Restore worlds backup » após reinstalar.",
    "nl": "⚠️ Bij het verwijderen worden de instantie en instellingen gewist; een back-up van je werelden blijft bewaard en is na herinstallatie terug te zetten met « Restore worlds backup ».",
    "pl": "⚠️ Odinstalowanie usuwa instancję i ustawienia; kopia twoich światów zostaje zachowana i można ją przywrócić przez « Restore worlds backup » po ponownej instalacji.",
    "ru": "⚠️ При удалении экземпляр и настройки удаляются; резервная копия миров сохраняется — её можно вернуть через « Restore worlds backup » после переустановки.",
}


_VERSION = {
    "en": {"title": "Version",
           "desc": "Pick a fixed version, or keep 'Latest' to stay on "
                   "automatic daily updates. Your worlds are backed up "
                   "automatically before any version change (last 3 kept).",
           "latest": "Latest (auto-update)"},
    "fr": {"title": "Version",
           "desc": "Choisissez une version fixe, ou gardez « Latest » pour "
                   "conserver les mises à jour automatiques quotidiennes. "
                   "Vos mondes sont sauvegardés automatiquement avant tout "
                   "changement de version (3 derniers conservés).",
           "latest": "Dernière (màj auto)"},
    "de": {"title": "Version",
           "desc": "Wähle eine feste Version oder behalte „Latest“ für die "
                   "täglichen automatischen Updates. Deine Welten werden "
                   "vor jedem Versionswechsel automatisch gesichert (die "
                   "letzten 3 bleiben erhalten).",
           "latest": "Neueste (Auto-Update)"},
    "es": {"title": "Versión",
           "desc": "Elige una versión fija o mantén «Latest» para conservar "
                   "las actualizaciones automáticas diarias. Tus mundos se "
                   "copian automáticamente antes de cualquier cambio de "
                   "versión (se conservan las 3 últimas copias).",
           "latest": "Última (act. auto)"},
    "it": {"title": "Versione",
           "desc": "Scegli una versione fissa oppure mantieni «Latest» per "
                   "gli aggiornamenti automatici quotidiani. I tuoi mondi "
                   "vengono salvati automaticamente prima di ogni cambio di "
                   "versione (si conservano gli ultimi 3 backup).",
           "latest": "Ultima (agg. auto)"},
    "pt": {"title": "Versão",
           "desc": "Escolha uma versão fixa ou mantenha «Latest» para as "
                   "atualizações automáticas diárias. Os seus mundos são "
                   "copiados automaticamente antes de qualquer mudança de "
                   "versão (mantêm-se as 3 últimas cópias).",
           "latest": "Mais recente (atual. auto)"},
    "nl": {"title": "Versie",
           "desc": "Kies een vaste versie of houd 'Latest' aan voor de "
                   "dagelijkse automatische updates. Je werelden worden "
                   "vóór elke versiewissel automatisch geback-upt (laatste "
                   "3 bewaard).",
           "latest": "Nieuwste (auto-update)"},
    "pl": {"title": "Wersja",
           "desc": "Wybierz stałą wersję albo zostaw „Latest”, by zachować "
                   "codzienne automatyczne aktualizacje. Twoje światy są "
                   "automatycznie zapisywane przed każdą zmianą wersji "
                   "(ostatnie 3 kopie zostają).",
           "latest": "Najnowsza (auto-aktualizacja)"},
    "ru": {"title": "Версия",
           "desc": "Выберите фиксированную версию или оставьте «Latest», "
                   "чтобы сохранить ежедневные автообновления. Перед любой "
                   "сменой версии миры автоматически сохраняются "
                   "(хранятся 3 последние копии).",
           "latest": "Последняя (автообновление)"},
}


_RESTORE = {
    "en": {"none": "No worlds backup found for this game yet (backups are "
                   "made automatically on version changes and uninstalls).",
           "not_installed": "Install the game first, then restore.",
           "done": "{n} world(s) restored from backup « {label} ». The "
                   "previous worlds were snapshotted first."},
    "fr": {"none": "Aucune sauvegarde de mondes pour ce jeu (les backups "
                   "sont créés automatiquement aux changements de version "
                   "et à la désinstallation).",
           "not_installed": "Installez d'abord le jeu, puis restaurez.",
           "done": "{n} monde(s) restauré(s) depuis le backup « {label} ». "
                   "Les mondes précédents ont d'abord été sauvegardés."},
    "de": {"none": "Noch kein Welten-Backup für dieses Spiel (Backups "
                   "entstehen automatisch bei Versionswechseln und beim "
                   "Deinstallieren).",
           "not_installed": "Installiere zuerst das Spiel, dann "
                            "wiederherstellen.",
           "done": "{n} Welt(en) aus dem Backup „{label}“ "
                   "wiederhergestellt. Die bisherigen Welten wurden zuvor "
                   "gesichert."},
    "es": {"none": "Aún no hay copia de los mundos de este juego (las "
                   "copias se crean automáticamente al cambiar de versión "
                   "y al desinstalar).",
           "not_installed": "Instala primero el juego y luego restaura.",
           "done": "{n} mundo(s) restaurado(s) desde la copia «{label}». "
                   "Los mundos anteriores se guardaron antes."},
    "it": {"none": "Nessun backup dei mondi per questo gioco (i backup "
                   "vengono creati automaticamente ai cambi di versione e "
                   "alla disinstallazione).",
           "not_installed": "Installa prima il gioco, poi ripristina.",
           "done": "{n} mondo/i ripristinato/i dal backup «{label}». I "
                   "mondi precedenti sono stati prima salvati."},
    "pt": {"none": "Ainda não há backup dos mundos deste jogo (os backups "
                   "são criados automaticamente nas mudanças de versão e "
                   "na desinstalação).",
           "not_installed": "Instale primeiro o jogo e depois restaure.",
           "done": "{n} mundo(s) restaurado(s) do backup «{label}». Os "
                   "mundos anteriores foram guardados antes."},
    "nl": {"none": "Nog geen wereldenback-up voor dit spel (back-ups "
                   "worden automatisch gemaakt bij versiewissels en bij "
                   "verwijderen).",
           "not_installed": "Installeer eerst het spel en herstel daarna.",
           "done": "{n} wereld(en) hersteld uit back-up '{label}'. De "
                   "huidige werelden zijn eerst veiliggesteld."},
    "pl": {"none": "Brak jeszcze kopii światów tej gry (kopie powstają "
                   "automatycznie przy zmianach wersji i odinstalowaniu).",
           "not_installed": "Najpierw zainstaluj grę, potem przywróć.",
           "done": "Przywrócono {n} świat(y) z kopii „{label}”. "
                   "Dotychczasowe światy zostały wcześniej zapisane."},
    "ru": {"none": "Для этой игры ещё нет резервной копии миров (копии "
                   "создаются автоматически при смене версии и удалении).",
           "not_installed": "Сначала установите игру, затем "
                            "восстанавливайте.",
           "done": "Восстановлено миров: {n} (копия «{label}»). Текущие "
                   "миры предварительно сохранены."},
}


def version_texts():
    return _pick(_VERSION)


def restore_texts():
    return _pick(_RESTORE)


def desc_for(shortname):
    table = _DESC.get(shortname)
    if not table:
        return ""
    desc = _pick(table)
    if shortname == "java":
        desc += "<br><br>" + _pick(_UNINSTALL)
    return desc


def pack_desc(mc="", loader=""):
    ver = ""
    if mc:
        ver = _pick(_PACK_VER).format(
            mc=mc, loader=f" ({loader})" if loader else "")
    return _pick(_PACK).format(ver=ver)


def uninstall_note():
    return _pick(_UNINSTALL)
