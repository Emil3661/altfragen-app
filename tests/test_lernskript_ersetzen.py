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

    def test_geaendert_ohne_haken_geht_durch(self):
        # 1.Q02 trägt keine Kästchen; ihr Stamm ändert sich gewollt, die übrigen Haken bleiben
        neu_text, neu_daten = neue_fassung()
        neu_daten['themen'][0]['fragen'][1]['stamm'] = 'Was ist kein Obst, sondern Gemüse?'
        neu_text = neu_text.replace('Was ist kein Obst?', 'Was ist kein Obst, sondern Gemüse?', 1)
        with self.assertRaises(le.Fehler):
            le.uebertragen(MD, DATEN, neu_text, neu_daten)
        text, bericht = le.uebertragen(MD, DATEN, neu_text, neu_daten, ('1.Q02',))
        alt, _ = zustaende(MD, DATEN)
        neu, fehler = zustaende(text, neu_daten)
        self.assertEqual(fehler, [])
        for qid, k in alt.items():
            self.assertEqual(neu[qid], k, qid)
        self.assertEqual(bericht['haken'], 5)

    def test_geaendert_mit_haken_bricht_ab(self):
        neu_text, neu_daten = neue_fassung()
        neu_daten['themen'][0]['fragen'][0]['stamm'] = 'Was ist eckig?'
        neu_text = neu_text.replace('Was ist rund?', 'Was ist eckig?', 1)
        with self.assertRaisesRegex(le.Fehler, 'tragen Kästchen'):
            le.uebertragen(MD, DATEN, neu_text, neu_daten, ('1.Q01',))

    def test_geaendert_nur_falsch_kaestchen_bricht_ab(self):
        # 1.Q03 trägt nur das Kästchen falsch, auch das gehörte zur alten Frage
        neu_text, neu_daten = neue_fassung()
        neu_daten['themen'][0]['fragen'][2]['stamm'] = 'Nenne eine Steinfrucht.'
        neu_text = neu_text.replace('Nenne eine Zitrusfrucht.', 'Nenne eine Steinfrucht.', 1)
        with self.assertRaisesRegex(le.Fehler, 'tragen Kästchen'):
            le.uebertragen(MD, DATEN, neu_text, neu_daten, ('1.Q03',))

    def test_geaendert_ohne_abweichung_bricht_ab(self):
        neu_text, neu_daten = neue_fassung()
        with self.assertRaisesRegex(le.Fehler, 'gleich oder unbekannt'):
            le.uebertragen(MD, DATEN, neu_text, neu_daten, ('1.Q02',))

    def test_geaendert_mit_neuer_nummer_bricht_ab(self):
        # Stamm geändert und zugleich auf Nummer 3 gerückt: Die Nummer bleibt auch mit --geaendert streng
        neu_text, neu_daten = neue_fassung()
        f = neu_daten['themen'][0]['fragen']
        f[1]['stamm'] = 'Was ist kein Obst, sondern Gemüse?'
        f[1]['nr'], f[2]['nr'] = 3, 2
        neu_text = neu_text.replace('Was ist kein Obst?', 'Was ist kein Obst, sondern Gemüse?', 1)
        neu_text = neu_text.replace('**Frage 2** · 2× gefragt', '**Frage 9** · 2× gefragt', 1)
        neu_text = neu_text.replace('**Frage 3**\n\nNenne', '**Frage 2**\n\nNenne', 1)
        neu_text = neu_text.replace('**Frage 9** · 2× gefragt', '**Frage 3** · 2× gefragt', 1)
        with self.assertRaisesRegex(le.Fehler, 'andere Nummer'):
            le.uebertragen(MD, DATEN, neu_text, neu_daten, ('1.Q02', '1.Q03'))

    def test_fortschritt_belegt(self):
        fo = {'versuche': {'1.Q01': [{'wahl': ['Apfel']}], '1.Q02': []}, 'sterne': {'2.Q01': {'wert': True}},
              'md': {'basis': {'2.Q03': 'Lauch#u1f0'}, 'ueberschrieben': {'1.Q04': 'Zitrone#u0f0'}}}
        self.assertEqual(le.fortschritt_belegt(fo, ('1.Q01', '1.Q02', '2.Q01', '1.Q03', '2.Q03', '1.Q04')),
                         ['1.Q01', '1.Q04', '2.Q01', '2.Q03'])
        self.assertEqual(le.fortschritt_belegt({}, ('1.Q01',)), [])

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
