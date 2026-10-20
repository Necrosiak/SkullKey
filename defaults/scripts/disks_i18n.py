#!/usr/bin/env python3
"""Localized texts for the Discs & Installers tab (9 UI languages, like
ports_i18n.py)."""

from ports_i18n import LANGS, machine_lang_code

TEXT = {
    "tab_title": {
        "en": "Discs & Installers", "fr": "Disques & installeurs",
        "de": "Discs & Installer", "es": "Discos e instaladores",
        "it": "Dischi e installer", "pt": "Discos e instaladores",
        "nl": "Schijven & installers", "pl": "Płyty i instalatory",
        "ru": "Диски и установщики",
    },
}


def t(key):
    table = TEXT[key]
    return table.get(machine_lang_code(), table["en"])
