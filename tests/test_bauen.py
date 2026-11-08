"""Prüft die Kontrollen von werkzeug/bauen.py (Lernskript-Abgleich, Zuordnung der Probeklausuren) synthetisch.

Rein: tests/vektoren/fragen.json und lernskript.md, dazu eine kleine erfundene Probeklausur.
Raus: unittest-Ergebnis. Der Bau selbst braucht den Quellordner und wird hier nicht ausgeführt.
Aufruf: python -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HIER, 'vektoren')
sys.path.insert(0, os.path.join(os.path.dirname(HIER), 'werkzeug'))
import bauen

with open(os.path.join(V, 'fragen.json'), encoding='utf-8') as _d:
    DATEN = json.load(_d)
with open(os.path.join(V, 'lernskript.md'), encoding='utf-8', newline='') as _d:
    MD = _d.read()
# Quellstämme: in den Vektoren gibt es keine Kombinationsfragen, Stamm = Quelltext
ROH = {q['id']: {'stem': q['stamm']} for t in DATEN['themen'] for q in t['fragen']}

PROBE = '\n'.join([
    '**Probeklausur 1** · 2 Fragen', '', '---', '',
    '**Frage 1**', '', 'Was ist kein Obst?', '', '- [ ] Pflaume', '- [ ] Gurke', '- [ ] Kiwi', '', '---', '',
    '**Frage 2**', '', r'Was ist rund?', '', r'- [ ] Birne 3\. Klasse \= gut  ', '- [ ] Apfel  ', '- [ ] Banane',
    '', '---', '', '## Lösungen', '', '---', '',
    '**1 · Gurke** · Thema 1: Obst', '', '✗ **Gurke** — Gemüse', '', '---', '',
    '**2 · Apfel** · Thema 1: Obst', '', '✓ **Apfel**', '',
])


class Lernskript(unittest.TestCase):

    def test_vektor_passt(self):
        self.assertEqual(bauen.lernskript_pruefen(DATEN, MD), [])

    def test_abweichungen_werden_gefunden(self):
        faelle = {
            'Optionen vertauscht': MD.replace('- [ ] Kiwi\n- [ ] Gurke', '- [ ] Gurke\n- [ ] Kiwi', 1),
            'Lösung falsch': MD.replace('**Lösung:** Gurke', '**Lösung:** Kiwi', 1),
            'Frage fehlt': MD.replace('**Frage 2** · 2× gefragt', 'Frage zwei', 1),
            'Frage ohne Gegenstück': MD + '\n**Frage 7**\n\nNeu?\n',
            'Stamm anders': MD.replace('Was ist rund?', 'Was ist eckig?', 1),
            'Option zu viel': MD.replace('- [ ] Pflaume', '- [ ] Pflaume\n- [ ] Melone', 1),
        }
        for name, md in faelle.items():
            with self.subTest(name):
                self.assertTrue(bauen.lernskript_pruefen(DATEN, md))

    def test_angehaengter_absatz_bleibt_merkmal(self):
        # Google Docs zieht einen Absatz direkt nach dem Kästchen in dieselbe Zeile; das Kästchen bleibt ein Merkmal
        md = MD.replace('- [ ] *unsicher*\n\n---\n\n## 2', '- [ ] *unsicher* **Hinweis:** etwas\n\n---\n\n## 2', 1)
        self.assertNotEqual(md, MD)
        self.assertEqual(bauen.lernskript_pruefen(DATEN, md), [])


class Probeklausur(unittest.TestCase):

    def test_zuordnung_ueber_stamm_und_optionen(self):
        self.assertEqual(bauen.probe_zuordnen(DATEN, ROH, PROBE, 'P'), (['1.Q02', '1.Q01'], []))

    def test_crlf(self):
        self.assertEqual(bauen.probe_zuordnen(DATEN, ROH, PROBE.replace('\n', '\r\n'), 'P')[1], [])

    def test_nicht_zuordenbar(self):
        faelle = {
            'falsches Thema': PROBE.replace('**2 · Apfel** · Thema 1', '**2 · Apfel** · Thema 2', 1),
            'Option fehlt': PROBE.replace('- [ ] Banane', '', 1),
            'Lösung passt nicht': PROBE.replace('**2 · Apfel**', '**2 · Banane**', 1),
            'Lösung fehlt': PROBE.replace('**2 · Apfel** · Thema 1: Obst', '', 1),
            'Stamm anders': PROBE.replace('Was ist kein Obst?', 'Was ist Obst?', 1),
        }
        for name, text in faelle.items():
            with self.subTest(name):
                self.assertTrue(bauen.probe_zuordnen(DATEN, ROH, text, 'P')[1])

    def test_doppelte_frage_ist_mehrdeutig(self):
        # Zwei Fragen mit gleichem Stamm und gleicher Optionsmenge im selben Thema: nie raten
        daten = json.loads(json.dumps(DATEN))
        kopie = dict(daten['themen'][0]['fragen'][0], id='1.Q09', nr=9)
        daten['themen'][0]['fragen'].append(kopie)
        roh = dict(ROH, **{'1.Q09': {'stem': kopie['stamm']}})
        _, abw = bauen.probe_zuordnen(daten, roh, PROBE, 'P')
        self.assertEqual(len(abw), 1)
        self.assertIn('2 passende Fragen', abw[0])


if __name__ == '__main__':
    unittest.main()
