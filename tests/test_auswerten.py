"""Prüft die Zählung von werkzeug/auswerten.py mit den synthetischen Testvektoren.

Rein: tests/vektoren/fragen.json und lernskript.md. Raus: unittest-Ergebnis. Braucht weder Drive noch Quellordner.
Aufruf: python -m unittest discover -s tests -v
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HIER, 'vektoren')
sys.path.insert(0, os.path.join(os.path.dirname(HIER), 'werkzeug'))
import auswerten
import kern

with open(os.path.join(V, 'fragen.json'), encoding='utf-8') as _d:
    DATEN = json.load(_d)
with open(os.path.join(V, 'lernskript.md'), encoding='utf-8', newline='') as _d:
    MD = _d.read()
MD_ZEIT = '2026-11-08T17:25:00.000Z'
JETZT = '2026-11-08T21:00:00.000Z'


def inhalt(ordner):
    # Dateiname -> Bytes aller Dateien im Ordner
    aus = {}
    for n in os.listdir(ordner):
        with open(os.path.join(ordner, n), 'rb') as d:
            aus[n] = d.read()
    return aus


def zaehlen(heute, fortschritt=None, md=MD):
    return auswerten.auswertung(DATEN, fortschritt or kern.leerer_fortschritt('test'), md, MD_ZEIT, heute, JETZT)


class Zaehlung(unittest.TestCase):

    def test_haken_aus_dem_lernskript_zaehlen(self):
        # Lernskript: 1.1 Apfel mit unsicher (Stern), 1.2 leer, 1.3 falsch markiert, 2.1 Erbse und Gurke richtig,
        # 2.2 Bruchstück
        a = zaehlen('2026-11-09')
        self.assertEqual((a['gesamt'], a['bruchstuecke'], a['bearbeitet'], a['richtig']), (4, 1, 3, 2))
        self.assertEqual(a['stand'], (2, 1))
        # [(..) for t in ..] = je Thema Rang, Anzahl, richtig, falsch, Stern
        self.assertEqual([(t['rang'], t['n'], t['richtig'], t['falsch'], t['stern']) for t in a['themen']],
                         [(1, 2, 1, ['1.3'], ['1.1']), (2, 1, 1, [], [])])
        self.assertEqual((a['tempo']['offen'], a['tempo']['tage'], a['tempo']['pro_tag']), (1, 89, 1))
        self.assertEqual((a['fehler'], a['abbruch']), ([], None))
        self.assertEqual((a['falsch'], a['markiert']), (['1.3'], ['1.1']))

    def test_letzter_versuch_zaehlt(self):
        # App: 1.2 richtig, 2.1 später falsch beantwortet; die Docs-Haken von 2.1 sind älter
        f = kern.leerer_fortschritt('test')
        f['versuche'] = {
            '1.Q02': [{'id': 'a1', 'zeit': '2026-11-08T20:00:00Z', 'wahl': ['Gurke'], 'unsicher': False,
                       'falsch': False, 'quelle': 'app', 'geaendert': '2026-11-08T20:00:00Z', 'geloescht': None}],
            '2.Q01': [{'id': 'a2', 'zeit': '2026-11-08T20:30:00Z', 'wahl': ['Tomate'], 'unsicher': False,
                       'falsch': False, 'quelle': 'app', 'geaendert': '2026-11-08T20:30:00Z', 'geloescht': None}],
        }
        f['md'] = {'zeit': '2026-11-08T20:40:00Z', 'basis': {'2.Q01': 'Tomate#u0f0'},
                   'ueberschrieben': {'2.Q01': ['Erbse|Gurke#u0f0']}}
        a = zaehlen('2026-11-09', f)
        self.assertEqual((a['bearbeitet'], a['richtig']), (4, 2))
        self.assertEqual([(t['rang'], t['falsch'], t['stern']) for t in a['themen']],
                         [(1, ['1.3'], ['1.1']), (2, ['2.1'], [])])
        self.assertEqual(a['tempo']['offen'], 0)

    def test_ohne_lernskript_und_ohne_fortschritt(self):
        a = zaehlen('2026-11-09', md=None)
        self.assertEqual((a['bearbeitet'], a['stand'], a['themen'], a['falsch'], a['markiert']), (0, None, [], [], []))
        self.assertEqual(a['tempo']['offen'], 4)

    def test_lesefehler_werden_gemeldet(self):
        md = MD.replace('- [ ] Banane  ', '- [x] Melone  ', 1).replace('**Frage 3**', '**Frage 9**', 1)
        a = zaehlen('2026-11-09', md=md)
        self.assertEqual(a['fehler'], ['1.1', '1.9 (gibt es nicht)'])
        self.assertEqual(a['bearbeitet'], 1)

    def test_bericht(self):
        t = auswerten.bericht(zaehlen('2026-11-10'), DATEN)
        self.assertIn('Bearbeitet 3 von 4 Fragen (1 Bruchstück ohne Antwort nicht gezählt)', t)
        self.assertIn('Stand: Thema 2, Frage 1', t)
        self.assertIn('Zuletzt richtig: 2 (66 %)', t)
        self.assertIn('Thema 1 Obst: 1 von 2 zuletzt richtig\n   falsch:   1.3\n   Stern:    1.1', t)
        self.assertIn('Sammlungen: ✗ 1 je falsch · ☆ 1 markiert', t)
        self.assertNotIn('fällig', t)


class Aufruf(unittest.TestCase):

    def test_schreibt_nichts(self):
        # Kopie der Vektoren in einen leeren Ordner; nach dem Lauf müssen Inhalt und Dateiliste gleich sein
        with tempfile.TemporaryDirectory() as tmp:
            md = os.path.join(tmp, 'lernskript.md')
            fragen = os.path.join(tmp, 'fragen.json')
            shutil.copyfile(os.path.join(V, 'lernskript.md'), md)
            shutil.copyfile(os.path.join(V, 'fragen.json'), fragen)
            vorher = inhalt(tmp)
            aus = io.StringIO()
            with contextlib.redirect_stdout(aus):
                rc = auswerten.main(['mibi', '--fragen', fragen, '--md', md, '--heute', '2026-11-09',
                                     '--fortschritt', os.path.join(tmp, 'fehlt.json')])
            nachher = inhalt(tmp)
            self.assertEqual(rc, 0)
            self.assertEqual(vorher, nachher)
            self.assertIn('Bearbeitet 3 von 4 Fragen', aus.getvalue())
            self.assertIn('Fortschritt fehlt, leerer Stand', aus.getvalue())


if __name__ == '__main__':
    unittest.main()
