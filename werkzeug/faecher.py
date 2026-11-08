"""Angaben je Fach und gemeinsame Pfade für bauen.py und auswerten.py.

Rein: nichts. Raus: FAECHER (Name, Klausur, Plan, Lernskript, Probeklausuren je Fach) und Ordnerpfade.
Aufruf: from faecher import FAECHER, REPO, BUILD, DRIVE_APP, QUELLE
"""
import os

# Repo-Wurzel und Ausgabeordner für Dateien mit echten Fragen (per .gitignore ausgeschlossen)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\', '/')
BUILD = f'{REPO}/build'

# Quellordner der Altfragen (wird nur gelesen) und der App-Ordner auf Drive
QUELLE = 'C:/Users/joong/altfragen_work'
DRIVE_APP = 'G:/Meine Ablage/01 Studium/Organisation/Altfragen-App'

_MIBI = 'G:/Meine Ablage/01 Studium/Fächer/Mikrobiologie/Teil 1 Klausur 2027'
_INNERE = 'G:/Meine Ablage/01 Studium/Fächer/Innere/Teil 1 Klausur 2027'

FAECHER = {
    'mibi': {
        'name': 'MiBi Teil 1',
        'klausur': '2027-02-12',
        'klausurInfo': '30 Fragen in 45 Minuten',
        'plan': 'rang',
        'lernskript': f'{_MIBI}/MiBi Teil 1 — Lernskript.md',
        'probeklausuren': [f'{_MIBI}/MiBi Teil 1 — Probeklausur 1.md', f'{_MIBI}/MiBi Teil 1 — Probeklausur 2.md'],
        'minuten': 45,
    },
    'innere': {
        'name': 'Innere Teil 1',
        'klausur': '2027-02-15',
        'klausurInfo': '60 Fragen in 90 Minuten',
        'plan': 'block-stufe',
        'lernskript': f'{_INNERE}/Innere Teil 1 — Lernskript.md',
        'probeklausuren': [f'{_INNERE}/Innere Teil 1 — Probeklausur 1.md',
                           f'{_INNERE}/Innere Teil 1 — Probeklausur 2.md'],
        'minuten': 90,
    },
}
