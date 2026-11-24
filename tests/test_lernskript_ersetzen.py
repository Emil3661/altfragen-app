"""Prüft werkzeug/lernskript_ersetzen.py ohne Drive: Kästchen übertragen, Abbrüche, Suche nach eigenen Notizen.

Rein: tests/vektoren/fragen.json und lernskript.md (mit Haken), daraus abgeleitete neue Fassungen.
Raus: unittest-Ergebnis.
Aufruf: python -m unittest discover -s tests -v
"""
import copy
import json
import os
import re
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HIER, 'vektoren')
sys.path.insert(0, os.path.join(os.path.dirname(HIER), 'werkzeug'))
import kern
import lernskript_ersetzen as le

with open(os.path.join(V, 'fragen.json'), encoding='utf-8') as _d:
    DATEN = json.load(_d)
with open(os.path.join(V, 'lernskript.md'), encoding='utf-8', newline='') as _d:
    MD = _d.read()

# Neue Frage 4 im Thema Obst, im Lernskript direkt vor dem Themenwechsel
FRAGE4_MD = '**Frage 4**\n\nWas ist gelb?\n\n- [ ] Zitrone\n- [ ] Traube\n\n**Lösung:** Zitrone\n\n- [ ] *unsicher*\n\n---\n\n'
FRAGE4 = {'id': '1.Q04', 'nr': 4, 'abschnitt': None, 'mal': 1, 'typ': 'positiv', 'stamm': 'Was ist gelb?',
          'aussagen': None, 'optionen': [{'t': 'Zitrone', 'w': '', 'richtig': True, 'erg': False, 'fest': False},
                                          {'t': 'Traube', 'w': '', 'richtig': False, 'erg': False, 'fest': False}],
          'loesung': None, 'neu': [], 'hinweis': [], 'ids': '2526-09'}
# Docs maskiert Satzzeichen mit Backslash; die frisch gesetzte Fassung hat das nicht
MASKIERT = r'Birne 3\. Klasse \= gut'


def leeren(text):
    # Alle Kästchen leeren, wie in einer frisch gesetzten Fassung
    return re.sub(r'(?m)^(\s*[-*+] \[)[xX](\] )', r'\1 \2', text)


def neue_fassung():
    """Frisch gesetztes Lernskript mit Frage 4 und ohne Docs-Maskierung, dazu die passenden Fragendaten."""
    text = leeren(MD).replace(MASKIERT, 'Birne 3. Klasse = gut')
    text = text.replace('## 2 · Gemüse', FRAGE4_MD + '## 2 · Gemüse', 1)
    daten = copy.deepcopy(DATEN)
    daten['themen'][0]['fragen'].append(copy.deepcopy(FRAGE4))
    return text, daten


def zustaende(text, daten):
    # Schlüssel je Frage-ID, so wie die App das Lernskript liest
    z, fehler = kern.lernskript_lesen(text, daten)
    return {qid: kern.schluessel(v) for qid, v in z.items()}, fehler


class Uebertragen(unittest.TestCase):

    def test_haken_bleiben_neue_frage_leer(self):
        neu_text, neu_daten = neue_fassung()
        text, bericht = le.uebertragen(MD, DATEN, neu_text, neu_daten)
        alt, _ = zustaende(MD, DATEN)
        neu, fehler = zustaende(text, neu_daten)
        self.assertEqual(fehler, [])
        for qid, k in alt.items():
            self.assertEqual(neu[qid], k, qid)
        self.assertEqual(neu['1.Q04'], kern.schluessel({}))
        self.assertEqual((bericht['fragen'], bericht['neu']), (3, ['1.Q04']))
        self.assertEqual(bericht['haken'], 5)

    def test_reihenfolge_im_text_egal(self):
        # Thema 2 steht im neuen Lernskript vor Thema 1; die Haken folgen Thema, Nummer und ID, nicht der Zeile
        neu_text, neu_daten = neue_fassung()
        kopf, rest = neu_text.split('## 1 · Obst', 1)
        obst, gemuese = rest.split('## 2 · Gemüse', 1)
        neu_text = kopf + '## 2 · Gemüse' + gemuese + '\n---\n\n## 1 · Obst' + obst
        text, _ = le.uebertragen(MD, DATEN, neu_text, neu_daten)
        neu, _ = zustaende(text, neu_daten)
        self.assertEqual((neu['1.Q01'], neu['2.Q01']), ('Apfel#u1f0', 'Erbse|Gurke#u0f0'))

    def test_nummer_geaendert_bricht_ab(self):
        # Eine neue offene Frage schiebt sich auf Nummer 3, die alte 1.Q03 rückt auf 4: Ihr falsch-Kästchen
        # würde sonst bei der neuen Frage landen, Optionen zum Vergleichen gibt es keine
        neu_text, neu_daten = neue_fassung()
        f = neu_daten['themen'][0]['fragen']
        f[2]['nr'], f[3]['nr'] = 4, 3
        with self.assertRaises(le.Fehler):
            le.uebertragen(MD, DATEN, neu_text, neu_daten)

    def test_andere_frage_unter_alter_id_bricht_ab(self):
        neu_text, neu_daten = neue_fassung()
        neu_daten['themen'][0]['fragen'][0]['stamm'] = 'Was ist eckig?'
        neu_text = neu_text.replace('Was ist rund?', 'Was ist eckig?', 1)
        with self.assertRaises(le.Fehler):
            le.uebertragen(MD, DATEN, neu_text, neu_daten)

    def test_frage_mit_haken_fehlt(self):
        neu_text, neu_daten = neue_fassung()
        neu_text = neu_text.replace('**Frage 1**\n', 'Frage eins\n', 1)
        with self.assertRaises(le.Fehler):
            le.uebertragen(MD, DATEN, neu_text, neu_daten)

    def test_neue_fassung_hat_schon_haken(self):
        neu_text, neu_daten = neue_fassung()
        neu_text = neu_text.replace('- [ ] Zitrone', '- [x] Zitrone', 1)
        with self.assertRaises(le.Fehler):
            le.uebertragen(MD, DATEN, neu_text, neu_daten)

    def test_unbekannte_option_im_alten_lernskript(self):
        neu_text, neu_daten = neue_fassung()
        alt = MD.replace('- [x] Apfel', '- [x] Apfelsine', 1)
        with self.assertRaises(le.Fehler):
            le.uebertragen(alt, DATEN, neu_text, neu_daten)


class Notizen(unittest.TestCase):

    def test_docs_umformatierung_ist_keine_notiz(self):
        # Docs maskiert Satzzeichen, schreibt Tabellentrenner anders und hängt Absätze an Kästchen
        alt = MD.replace('- [x] *unsicher*\n\n✗', '- [x] *unsicher* ✗', 1) + '\n| a | b |\n| :---- | :---- |\n'
        vorher = leeren(MD).replace(MASKIERT, 'Birne 3. Klasse = gut') + '\n| a | b |\n|---|---|\n'
        self.assertEqual(le.notizen(alt, vorher), [])

    def test_eigene_zeile_wird_gefunden(self):
        alt = MD.replace('Was ist rund?', 'Was ist rund?\n\nMerke: Zytokin ⭐', 1)
        self.assertEqual(le.notizen(alt, leeren(MD)), ['Merke', 'Zytokin', '⭐'])

    def test_woerter_der_neuen_fassung_verdecken_nichts(self):
        # Die Notiz besteht aus Wörtern, die eine neue Fassung auch haben könnte; verglichen wird nur mit der vorigen
        alt = MD.replace('Was ist rund?', 'Was ist rund?\n\nZitrone gelb', 1)
        self.assertEqual(le.notizen(alt, leeren(MD)), ['Zitrone', 'gelb'])


if __name__ == '__main__':
    unittest.main()
