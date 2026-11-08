"""Prüft werkzeug/kern.py gegen die gemeinsamen Testvektoren und eigene synthetische Fälle.

Rein: tests/vektoren/*.json und lernskript.md. Raus: unittest-Ergebnis. Braucht weder Drive noch Quellordner.
Aufruf: python -m unittest discover -s tests -v
Schreibweisen: [x for x in liste] baut eine Liste, {..} eine Menge oder ein Dictionary, {**a, **b} vereinigt
zwei Dictionaries (b überschreibt a).
"""
import copy
import json
import os
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HIER, 'vektoren')
sys.path.insert(0, os.path.join(os.path.dirname(HIER), 'werkzeug'))
import kern


def lade(name):
    with open(os.path.join(V, name), encoding='utf-8') as d:
        return json.load(d)


def text(name):
    # newline='' lässt Zeilenenden so, wie sie in der Datei stehen
    with open(os.path.join(V, name), encoding='utf-8', newline='') as d:
        return d.read()


def ersetzt(t, paare):
    # Jeweils die erste Fundstelle ersetzen, wie in abgleich.json beschrieben
    for alt, neu in paare:
        i = t.index(alt)
        t = t[:i] + neu + t[i + len(alt):]
    return t


DATEN = lade('fragen.json')
MD = text('lernskript.md')
IX = kern.erschliessen(DATEN)


def frage(qid):
    return IX['fragen'][qid]['frage']


def versuchs_schluessel(f):
    # Je Frage die Schlüssel der nicht gelöschten Versuche in Zeitfolge
    return {qid: [kern.schluessel(v) for v in kern.gueltige(vs)] for qid, vs in f['versuche'].items()}


class Vektoren(unittest.TestCase):

    def test_lesen(self):
        for fall in lade('lesen.json'):
            with self.subTest(fall['name']):
                t = text(fall['datei']) if fall.get('datei') else fall['text']
                zustaende, fehler = kern.lernskript_lesen(t, DATEN)
                # {id: schluessel} = Zustände in vergleichbarer Form
                self.assertEqual({k: kern.schluessel(z) for k, z in zustaende.items()}, fall['zustaende'])
                self.assertEqual(fehler, fall['fehler'])

    def test_wiederholung(self):
        for fall in lade('wiederholung.json'):
            with self.subTest(fall['name']):
                # Fehlende Felder der Vektoren mit den Vorgaben ergänzen; {**a, **v} = a, überschrieben durch v
                versuche = [{'id': f'v{i}', 'unsicher': False, 'falsch': False, 'geloescht': None, **v}
                            for i, v in enumerate(fall['versuche'])]
                status, faellig = kern.wiederholung(frage(fall['frage']), versuche, fall['heute'], DATEN['klausur'])
                self.assertEqual((status, faellig), (fall['status'], fall['faellig']))

    def test_abgleich(self):
        for fall in lade('abgleich.json'):
            with self.subTest(fall['name']):
                md = ersetzt(MD, fall['ersetze'])
                vorher = copy.deepcopy(fall['fortschritt'])
                r = kern.abgleichen(fall['fortschritt'], md, fall['mdZeit'], DATEN, fall['jetzt'])
                erw = fall['erwartet']
                self.assertIsNone(r['abbruch'])
                self.assertEqual(r['fehler'], [])
                self.assertEqual(fall['fortschritt'], vorher, 'Eingang verändert')
                ist = versuchs_schluessel(r['fortschritt'])
                for qid in set(ist) | set(erw['versuche']):
                    self.assertEqual(ist.get(qid, []), erw['versuche'].get(qid, []), qid)
                self.assertEqual(set(r['geaendert']), set(erw['geaendert']))
                self.assertEqual(r['md_neu'] is not None, bool(erw['geaendert']))
                # Zeilen exakt zählen, ohne Abschneiden von Leerraum
                zeilen = (r['md_neu'] if r['md_neu'] is not None else md).split('\n')
                for zeile, anzahl in (erw.get('zeilen') or {}).items():
                    self.assertEqual(zeilen.count(zeile), anzahl, zeile)
                self.assertEqual(r['fortschritt']['md']['basis'], erw['basis'])
                self.assertEqual(r['fortschritt']['md']['ueberschrieben'], erw['ueberschrieben'])
                self.assertEqual(r['fortschritt']['md']['zeit'], fall['jetzt'])


class Normal(unittest.TestCase):

    def test_beispiele(self):
        faelle = {
            r'3\. Klasse \= gut': '3. Klasse = gut',
            '*unsicher*': 'unsicher',
            '**_Apfel_**': 'Apfel',
            '  Apfel  rot  ': 'Apfel rot',
            '*E. coli* und *S. aureus*': 'E. coli* und *S. aureus',
            '*halb': '*halb',
            r'\*fett\*': 'fett',
            'Groß': 'Groß',
            '': '',
        }
        for roh, soll in faelle.items():
            with self.subTest(roh):
                self.assertEqual(kern.normal(roh), soll)
        self.assertEqual(kern.normal(None), '')

    def test_schluessel(self):
        self.assertEqual(kern.schluessel({'wahl': ['Gurke', 'Erbse'], 'unsicher': True}), 'Erbse|Gurke#u1f0')
        self.assertEqual(kern.schluessel({'wahl': [], 'unsicher': False, 'falsch': False}), kern.LEER)
        self.assertEqual(kern.schluessel({'wahl': [r'Birne 3\. Klasse']}), 'Birne 3. Klasse#u0f0')


class Ergebnis(unittest.TestCase):

    def test_ergebnisse(self):
        self.assertEqual(kern.ergebnis(frage('1.Q01'), {'wahl': ['Apfel']}), 'richtig')
        self.assertEqual(kern.ergebnis(frage('1.Q01'), {'wahl': ['Apfel'], 'unsicher': True}), 'unsicher')
        self.assertEqual(kern.ergebnis(frage('1.Q01'), {'wahl': ['Apfel', 'Banane']}), 'falsch')
        self.assertIsNone(kern.ergebnis(frage('1.Q01'), {'wahl': [], 'unsicher': True}))
        self.assertEqual(kern.ergebnis(frage('1.Q03'), {'wahl': [], 'unsicher': True}), 'unsicher')
        self.assertEqual(kern.ergebnis(frage('1.Q03'), {'wahl': [], 'unsicher': True, 'falsch': True}), 'falsch')
        self.assertIsNone(kern.ergebnis(frage('2.Q03'), {'wahl': ['x']}))

    def test_berliner_tag(self):
        # Sommerzeit endet am letzten Sonntag im Oktober um 01:00 UTC
        self.assertEqual(kern.tag_von('2026-10-24T22:30:00Z'), '2026-10-25')
        self.assertEqual(kern.tag_von('2026-10-25T22:30:00Z'), '2026-10-25')
        self.assertEqual(kern.tag_von('2026-03-28T22:59:00Z'), '2026-03-28')
        self.assertEqual(kern.tag_von('2026-03-29T22:30:00Z'), '2026-03-30')
        self.assertEqual(kern.tag_von('2026-11-08T23:30:00.000Z'), '2026-11-09')
        self.assertEqual(kern.tag_von('2026-11-09T00:30:00+01:00'), '2026-11-09')


def app_versuch(vid, zeit, wahl, **merkmale):
    v = {'id': vid, 'zeit': zeit, 'wahl': wahl, 'unsicher': False, 'falsch': False, 'quelle': 'app',
         'geaendert': zeit, 'geloescht': None}
    v.update(merkmale)
    return v


class Umschreiben(unittest.TestCase):

    def test_nur_das_zeichen_aendert_sich_auch_bei_crlf(self):
        # Windows-Zeilenenden, angehängte Leerzeichen und geschützte Leerzeichen bleiben byte-gleich
        md = MD.replace('\n', '\r\n').replace('Was ist rund?', 'Was ist rund?  ')
        f = {'versuche': {
            '1.Q02': [app_versuch('a1', '2026-11-08T21:08:00.000Z', ['Gurke'], unsicher=True)],
            '1.Q01': [app_versuch('a2', '2026-11-08T21:09:00.000Z', ['Banane'])],
        }, 'md': {'zeit': None, 'basis': {}, 'ueberschrieben': {}}}
        r = kern.abgleichen(f, md, '2026-11-08T17:25:00.000Z', DATEN, '2026-11-08T21:10:00.000Z')
        neu = r['md_neu']
        self.assertEqual(len(md.encode('utf-8')), len(neu.encode('utf-8')))
        self.assertEqual(len(md), len(neu))
        # Zeichenpositionen, an denen sich alter und neuer Text unterscheiden
        diff = [i for i in range(len(md)) if md[i] != neu[i]]
        geaendert = {md[:i].count('\n') for i in diff}
        zeilen = md.split('\n')
        # Jede geänderte Stelle ist das Zeichen zwischen [ und ] eines Kästchens
        for i in diff:
            self.assertEqual((md[i - 1], md[i + 1]), ('[', ']'))
            self.assertIn(neu[i], ' x')
            self.assertRegex(zeilen[md[:i].count('\n')], r'^- \[[ xX]\] ')
        self.assertEqual(r['md_neu'].count('\r\n'), md.count('\r\n'))
        self.assertIn('- [x] Gurke\r', r['md_neu'])
        self.assertIn('- [x] Banane  \r', r['md_neu'])
        self.assertIn('- [ ] Apfel  \r', r['md_neu'])
        # Frage 1: Banane an, Apfel und unsicher aus; Frage 2: Gurke und unsicher an
        self.assertEqual(len(geaendert), 5)
        self.assertEqual(set(r['geaendert']), {'1.Q01', '1.Q02'})

    def test_lesen_und_schreiben_stimmen_ueberein(self):
        # Nach dem Umschreiben liest sich die .md als Soll
        f = {'versuche': {'2.Q01': [app_versuch('a', '2026-11-08T21:00:00Z', ['Tomate'], unsicher=True)]},
             'md': {'zeit': None, 'basis': {'2.Q01': 'Erbse|Gurke#u0f0'}, 'ueberschrieben': {}}}
        r = kern.abgleichen(f, MD, '2026-11-08T17:25:00.000Z', DATEN, '2026-11-08T21:10:00.000Z')
        zustaende, _ = kern.lernskript_lesen(r['md_neu'], DATEN)
        self.assertEqual(kern.schluessel(zustaende['2.Q01']), 'Tomate#u1f0')
        self.assertEqual(r['fortschritt']['md']['ueberschrieben']['2.Q01'], ['Erbse|Gurke#u0f0'])

    def test_ueberschrieben_hoechstens_drei_ohne_doppelte(self):
        f = {'versuche': {'1.Q02': [app_versuch('a', '2026-11-08T21:00:00Z', ['Kiwi'])]},
             'md': {'zeit': None, 'basis': {'1.Q02': 'Kiwi#u0f0'},
                    'ueberschrieben': {'1.Q02': ['Gurke#u0f0', '#u0f0', 'Pflaume#u0f0']}}}
        r = kern.abgleichen(f, MD, '2026-11-08T17:25:00.000Z', DATEN, '2026-11-08T21:10:00.000Z')
        self.assertEqual(r['fortschritt']['md']['ueberschrieben']['1.Q02'], ['#u0f0', 'Gurke#u0f0', 'Pflaume#u0f0'])

    def test_frage_mit_lesefehler_bleibt_unberuehrt(self):
        md = MD.replace('- [x] Apfel  ', '- [x] Melone  ', 1)
        f = {'versuche': {'1.Q01': [app_versuch('a', '2026-11-08T21:00:00Z', ['Banane'])]},
             'md': {'zeit': None, 'basis': {'1.Q01': 'Apfel#u1f0'}, 'ueberschrieben': {}}}
        r = kern.abgleichen(f, md, '2026-11-08T17:25:00.000Z', DATEN, '2026-11-08T21:10:00.000Z')
        self.assertEqual(r['fehler'], ['1.Q01'])
        self.assertNotIn('1.Q01', r['geaendert'])
        self.assertEqual(r['fortschritt']['md']['basis']['1.Q01'], 'Apfel#u1f0')
        self.assertEqual(versuchs_schluessel(r['fortschritt'])['1.Q01'], ['Banane#u0f0'])
        self.assertIn('- [x] Melone  ', r['md_neu'] or md)


def viele_fragen(n):
    # Synthetisches Fach mit n gleichartigen Fragen, Option A richtig
    fragen = [{'id': f'1.Q{i:02d}', 'nr': i, 'abschnitt': None, 'mal': 1, 'typ': 'positiv', 'stamm': f'F{i}',
               'aussagen': None, 'optionen': [{'t': 'A', 'w': '', 'richtig': True, 'erg': False},
                                              {'t': 'B', 'w': '', 'richtig': False, 'erg': False}],
               'loesung': None, 'neu': [], 'hinweis': [], 'ids': 'x'} for i in range(1, n + 1)]
    daten = {'format': 1, 'fach': 'syn', 'klausur': '2027-02-12', 'plan': 'rang', 'bloecke': [],
             'themen': [{'rang': 1, 'titel': 'T', 'stufe': None, 'block': None, 'fragen': fragen}]}
    md = '## 1 · T\n' + ''.join(f'**Frage {i}**\n- [x] A\n- [ ] B\n- [ ] *unsicher*\n' for i in range(1, n + 1))
    # basis = alle angehakt, aber keine Versuche mehr: ein verlorener Fortschritt würde alles leeren
    f = {'versuche': {}, 'md': {'zeit': '2026-11-08T20:00:00Z', 'basis': {q['id']: 'A#u0f0' for q in fragen},
                                'ueberschrieben': {}}}
    return daten, md, f


class Schutz(unittest.TestCase):

    def test_mehr_als_fuenf_geleerte_fragen_brechen_ab(self):
        daten, md, f = viele_fragen(6)
        r = kern.abgleichen(f, md, '2026-11-08T21:00:00Z', daten, '2026-11-08T21:05:00Z')
        self.assertIsNotNone(r['abbruch'])
        self.assertIn('6', r['abbruch'])
        self.assertIsNone(r['md_neu'])
        self.assertEqual(r['geaendert'], [])
        self.assertEqual(r['fortschritt']['md'], f['md'])

    def test_fuenf_geleerte_fragen_sind_erlaubt(self):
        daten, md, f = viele_fragen(5)
        r = kern.abgleichen(f, md, '2026-11-08T21:00:00Z', daten, '2026-11-08T21:05:00Z')
        self.assertIsNone(r['abbruch'])
        self.assertEqual(len(r['geaendert']), 5)
        self.assertEqual(r['md_neu'].count('- [x]'), 0)
        self.assertEqual(r['fortschritt']['md']['basis'], {})


class Zusammenfuehren(unittest.TestCase):

    def test_grabstein_mit_spaeterem_geaendert_gewinnt(self):
        lebend = app_versuch('v1', '2026-11-08T10:00:00Z', ['Apfel'])
        grab = dict(lebend, geloescht='2026-11-08T12:00:00Z', geaendert='2026-11-08T12:00:00Z')
        for a, b in ((lebend, grab), (grab, lebend)):
            with self.subTest(erst=a['geloescht']):
                r = kern.zusammenfuehren({'fach': 'test', 'versuche': {'1.Q01': [a]}},
                                         {'fach': 'test', 'versuche': {'1.Q01': [b]}})
                self.assertEqual(len(r['versuche']['1.Q01']), 1)
                self.assertEqual(r['versuche']['1.Q01'][0]['geloescht'], '2026-11-08T12:00:00Z')

    def test_spaeteres_geaendert_gewinnt_und_vereinigung(self):
        alt = app_versuch('v1', '2026-11-08T10:00:00Z', ['Apfel'])
        neu = dict(alt, unsicher=True, geaendert='2026-11-08T11:00:00.000Z')
        nur_b = app_versuch('v2', '2026-11-08T09:00:00Z', ['Banane'])
        r = kern.zusammenfuehren({'versuche': {'1.Q01': [alt]}}, {'versuche': {'1.Q01': [neu, nur_b], '1.Q02': []}})
        self.assertEqual([v['id'] for v in r['versuche']['1.Q01']], ['v2', 'v1'])
        self.assertTrue(r['versuche']['1.Q01'][1]['unsicher'])
        self.assertEqual(r['versuche']['1.Q02'], [])

    def test_schritte_je_feld_und_md_als_ganzes(self):
        a = {'schritte': {'1': {'meditricks': {'wert': 'ja', 'zeit': '2026-11-08T12:00:00Z'},
                                'kern': {'wert': None, 'zeit': '2026-11-08T09:00:00Z'}}},
             'md': {'zeit': '2026-11-08T10:00:00Z', 'basis': {'1.Q01': 'Apfel#u0f0'}, 'ueberschrieben': {}}}
        b = {'schritte': {'1': {'meditricks': {'wert': 'keins', 'zeit': '2026-11-08T11:00:00Z'},
                                'kern': {'wert': 'ja', 'zeit': '2026-11-08T10:00:00Z'}},
                          '2': {'kern': {'wert': 'ja', 'zeit': '2026-11-08T08:00:00Z'}}},
             'md': {'zeit': '2026-11-08T11:00:00Z', 'basis': {}, 'ueberschrieben': {'1.Q01': ['#u0f0']}}}
        for x, y in ((a, b), (b, a)):
            r = kern.zusammenfuehren(x, y)
            self.assertEqual(r['schritte']['1']['meditricks']['wert'], 'ja')
            self.assertEqual(r['schritte']['1']['kern']['wert'], 'ja')
            self.assertEqual(r['schritte']['2']['kern']['wert'], 'ja')
            self.assertEqual(r['md'], b['md'])

    def test_eingaenge_bleiben_unveraendert(self):
        a = {'versuche': {'1.Q01': [app_versuch('v1', '2026-11-08T10:00:00Z', ['Apfel'])]}}
        b = copy.deepcopy(a)
        b['versuche']['1.Q01'][0]['geaendert'] = '2026-11-09T10:00:00Z'
        vorher = copy.deepcopy((a, b))
        r = kern.zusammenfuehren(a, b)
        r['versuche']['1.Q01'][0]['wahl'].append('x')
        self.assertEqual((a, b), vorher)


class Plan(unittest.TestCase):

    def test_block_stufe(self):
        themen = [{'rang': r, 'block': b, 'stufe': s, 'fragen': []}
                  for r, b, s in ((1, 2, 'A'), (2, 1, 'C'), (3, 1, 'B'), (4, 1, 'A'), (5, 2, 'C'))]
        daten = {'plan': 'block-stufe', 'bloecke': [{'nr': 1}, {'nr': 2}], 'themen': themen}
        self.assertEqual([(t['rang'], o) for t, o in kern.plan_liste(daten)],
                         [(4, False), (3, False), (1, False), (2, True), (5, True)])

    def test_tempo(self):
        tp = kern.tempo(DATEN, kern.leerer_fortschritt('test'), '2026-11-09')
        self.assertEqual((tp['ziel'], tp['tage'], tp['offen'], tp['pro_tag']), ('2027-02-05', 89, 4, 1))


if __name__ == '__main__':
    unittest.main()
