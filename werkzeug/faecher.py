"""Angaben je Fach und gemeinsame Pfade für bauen.py, auswerten.py und veroeffentlichen.py.

Rein: nichts. Raus: FAECHER (Name, Klausur, Plan, Lernskript, Probeklausuren je Fach) und Ordnerpfade.
Optional je Fach: 'ordner' = Fachordner im Aufbau des Skills altfragen (src/index.json, out/NN.txt,
ergaenzt/NN.txt), sonst gilt QUELLE mit Unterordnern je Fach. 'durchgang' = Zieldatum des ersten Durchgangs,
sonst sieben Tage vor der Klausur.
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
_GYN = 'G:/Meine Ablage/01 Studium/Fächer/Frauenheilkunde'
_UMWELT = 'G:/Meine Ablage/01 Studium/Fächer/Umweltmedizin'
_HUMGEN = 'G:/Meine Ablage/01 Studium/Fächer/Humangenetik'
_NEURO = 'G:/Meine Ablage/01 Studium/Fächer/Neurologie'
_PAED = 'G:/Meine Ablage/01 Studium/Fächer/Kinderheilkunde'

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
    'gyn': {
        'name': 'Gyn Testat',
        'klausur': '2027-01-08',
        'klausurInfo': 'Testat, 10 Fragen: 8 MC, 2 offen',
        'plan': 'block-stufe',
        'lernskript': f'{_GYN}/Gyn Testat — Lernskript.md',
        'probeklausuren': [],
        'minuten': None,
        'ordner': 'C:/Users/joong/altfragen/gyn',
        'durchgang': '2027-01-07',
    },
    'umwelt': {
        'name': 'Umweltmedizin',
        'klausur': '2027-02-08',
        'klausurInfo': '40 Fragen in 60 Minuten',
        'plan': 'rang',
        'lernskript': f'{_UMWELT}/Umweltmedizin — Lernskript.md',
        'probeklausuren': [f'{_UMWELT}/Umweltmedizin — Probeklausur 1.md', f'{_UMWELT}/Umweltmedizin — Probeklausur 2.md'],
        'minuten': 60,
        'ordner': 'C:/Users/joong/altfragen/umwelt',
        'durchgang': '2027-01-23',
    },
    'humgen': {
        'name': 'Humangenetik',
        'klausur': '2027-02-12',
        'klausurInfo': '40 Fragen in 60 Minuten',
        'plan': 'rang',
        'lernskript': f'{_HUMGEN}/Humangenetik — Lernskript.md',
        'probeklausuren': [f'{_HUMGEN}/Humangenetik — Probeklausur 1.md', f'{_HUMGEN}/Humangenetik — Probeklausur 2.md'],
        'minuten': 60,
        'ordner': 'C:/Users/joong/altfragen/humgen',
        'durchgang': '2027-01-21',
    },
    'neuro': {
        'name': 'Neurologie',
        'klausur': '2027-06-30',
        'klausurInfo': '40 Fragen in 60 Minuten · Termin vorläufig',
        'plan': 'rang',
        'lernskript': f'{_NEURO}/Neurologie — Lernskript.md',
        'probeklausuren': [f'{_NEURO}/Neurologie — Probeklausur 1.md', f'{_NEURO}/Neurologie — Probeklausur 2.md'],
        'minuten': 60,
        'ordner': 'C:/Users/joong/altfragen/neuro',
        'durchgang': '2027-06-12',
    },
    'paed': {
        'name': 'Kinderheilkunde',
        'klausur': '2027-07-02',
        'klausurInfo': '40 Fragen in 60 Minuten · Termin vorläufig',
        'plan': 'rang',
        'lernskript': f'{_PAED}/Kinderheilkunde — Lernskript.md',
        'probeklausuren': [f'{_PAED}/Kinderheilkunde — Probeklausur 1.md',
                           f'{_PAED}/Kinderheilkunde — Probeklausur 2.md'],
        'minuten': 60,
        'ordner': 'C:/Users/joong/altfragen/paed',
        'durchgang': '2027-06-12',
    },
}
