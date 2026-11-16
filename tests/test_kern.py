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
                status, faellig = kern.wiederholung(frage(fall['frage']), versuche, fall['heute'], DATEN['klausur'],
                                                    {'wert': True, 'zeit': fall['stern']} if fall.get('stern') else None)
                self.assertEqual((status, faellig), (fall['status'], fall['faellig']))

    def test_sammlungen(self):
        for fall in lade('sammlung.json'):
            with self.subTest(fall['name']):
                # Fehlende Felder wie in der App ergänzen; {**a, **b} = b überschreibt a. Danach vervollstaendigen,
                # wie in der App, damit das alte Merkmal unsicher zum Stern wird
                versuche = {qid: [{'id': f'{qid}:{i}', 'unsicher': False, 'falsch': False, 'geloescht': None, **v}
                                  for i, v in enumerate(vs)] for qid, vs in fall['versuche'].items()}
                f = kern.vervollstaendigen({'versuche': versuche, 'sterne': fall.get('sterne') or {}}, 'test')
                self.assertEqual([{'frage': x['frage']['id'], 'falsch': x['falsch']} for x in kern.falsch_sammlung(DATEN, f)],
                                 fall['erwartet']['falsch'])
                self.assertEqual([x['frage']['id'] for x in kern.markiert_sammlung(DATEN, f)], fall['erwartet']['markiert'])

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
                # Sterne: alle Fragen, deren Stern nach dem Abgleich an ist
                self.assertEqual(sorted(q for q in IX['fragen'] if kern.stern_an(r['fortschritt'], q)), erw['sterne'])


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
        # Das alte Merkmal unsicher zählt im Ergebnis nicht mehr, es wirkt nur noch als Stern
        self.assertEqual(kern.ergebnis(frage('1.Q01'), {'wahl': ['Apfel'], 'unsicher': True}), 'richtig')
        self.assertEqual(kern.ergebnis(frage('1.Q01'), {'wahl': ['Apfel', 'Banane']}), 'falsch')
        self.assertIsNone(kern.ergebnis(frage('1.Q01'), {'wahl': [], 'unsicher': True}))
        self.assertEqual(kern.ergebnis(frage('1.Q03'), {'wahl': [], 'unsicher': True}), 'richtig')
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
        # Frage 1: Banane an, Apfel aus, unsicher bleibt als Stern aus Docs; Frage 2: Gurke und unsicher (Stern) an
        self.assertEqual(len(geaendert), 4)
        self.assertEqual(r['md_neu'].count('- [x] *unsicher*\r'), 2)
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

    def test_sechs_zurueckgenommene_antworten_halten_nicht_an(self):
        # Jede Antwort steht als Grabstein im Fortschritt: Die App kennt sie und hat sie bewusst zurückgenommen
        daten, md, f = viele_fragen(6)
        f['versuche'] = {f'1.Q{i:02d}': [app_versuch(f'a{i}', '2026-11-08T19:00:00Z', ['A'],
                                                     geloescht='2026-11-08T20:30:00Z')] for i in range(1, 7)}
        r = kern.abgleichen(f, md, '2026-11-08T21:00:00Z', daten, '2026-11-08T21:05:00Z')
        self.assertIsNone(r['abbruch'])
        self.assertEqual(len(r['geaendert']), 6)
        self.assertEqual(r['md_neu'].count('- [x]'), 0)

    def test_meldung_nennt_bis_zu_acht_fragen(self):
        daten, md, f = viele_fragen(9)
        r = kern.abgleichen(f, md, '2026-11-08T21:00:00Z', daten, '2026-11-08T21:05:00Z')
        self.assertEqual(r['abbruch'], 'Abgleich angehalten: 9 Fragen würden in der .md geleert '
                                       '(1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8 …)')

    def test_nur_unsicher_ohne_option_wartet(self):
        # Docs mitten in einer Antwort, die App kennt schon eine: kein Import, kein Stern, kein Umschreiben, basis bleibt
        md = MD.replace('- [ ] *unsicher*\n\n*2425-03', '- [x] *unsicher*\n\n*2425-03', 1)
        self.assertNotEqual(md, MD)
        f = {'versuche': {'1.Q02': [app_versuch('a', '2026-11-08T17:00:00Z', ['Gurke'])]},
             'md': {'zeit': None, 'basis': {'1.Q02': 'Gurke#u0f0'}, 'ueberschrieben': {}}}
        r = kern.abgleichen(f, md, '2026-11-08T17:25:00.000Z', DATEN, '2026-11-08T21:10:00.000Z')
        self.assertNotIn('1.Q02', r['geaendert'])
        self.assertEqual(len(r['fortschritt']['versuche']['1.Q02']), 1)
        self.assertFalse(kern.stern_an(r['fortschritt'], '1.Q02'))
        self.assertEqual(r['fortschritt']['md']['basis']['1.Q02'], 'Gurke#u0f0')

    def test_nur_unsicher_ohne_antwort_ist_der_stern(self):
        # Unbeantwortete Frage, in Docs nur unsicher angehakt: Stern an, kein Versuch, nichts umzuschreiben
        md = MD.replace('- [ ] *unsicher*\n\n*2425-03', '- [x] *unsicher*\n\n*2425-03', 1)
        r = kern.abgleichen(kern.leerer_fortschritt('test'), md, '2026-11-08T17:25:00.000Z', DATEN,
                            '2026-11-08T21:10:00.000Z')
        self.assertTrue(kern.stern_an(r['fortschritt'], '1.Q02'))
        self.assertNotIn('1.Q02', r['fortschritt']['versuche'])
        self.assertNotIn('1.Q02', r['geaendert'])
        self.assertEqual(r['fortschritt']['md']['basis']['1.Q02'], '#u1f0')

    def test_kein_neuer_text_ohne_unterschied(self):
        # Soll mit falsch-Merkmal bei einer Frage ohne falsch-Kästchen: abweichend, aber nichts zu schreiben
        f = {'versuche': {'1.Q01': [app_versuch('a', '2026-11-08T21:00:00Z', ['Apfel'], unsicher=True, falsch=True)]},
             'md': {'zeit': None, 'basis': {'1.Q01': 'Apfel#u1f0'}, 'ueberschrieben': {}}}
        r = kern.abgleichen(f, MD, '2026-11-08T17:25:00.000Z', DATEN, '2026-11-08T21:10:00.000Z')
        self.assertIn('1.Q01', r['geaendert'])
        self.assertIsNone(r['md_neu'])


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

    def test_grabstein_bleibt_auch_bei_spaeterer_aenderung(self):
        # Gerät A nimmt zurück, Gerät B ändert danach noch das Merkmal: gelöscht bleibt gelöscht
        grab = app_versuch('v1', '2026-11-08T10:00:00Z', ['Apfel'], geloescht='2026-11-08T11:00:00Z',
                           geaendert='2026-11-08T11:00:00Z')
        spaeter = app_versuch('v1', '2026-11-08T10:00:00Z', ['Apfel'], unsicher=True, geaendert='2026-11-08T12:00:00Z')
        for a, b in ((grab, spaeter), (spaeter, grab)):
            with self.subTest(erst=a['geaendert']):
                r = kern.zusammenfuehren({'versuche': {'1.Q01': [a]}}, {'versuche': {'1.Q01': [b]}})
                v, = r['versuche']['1.Q01']
                self.assertEqual(v['geloescht'], '2026-11-08T11:00:00Z')
                self.assertTrue(v['unsicher'])
                self.assertEqual(kern.gueltige(r['versuche']['1.Q01']), [])

    def test_zwei_geraete_lesen_denselben_haken_zu_verschiedenen_zeiten(self):
        # Beide Geräte übernehmen dieselbe .md mit verschiedener modifiedTime; danach je Frage ein Versuch
        leer = kern.leerer_fortschritt('test')
        a = kern.abgleichen(leer, MD, '2026-11-08T17:25:00.000Z', DATEN, '2026-11-08T21:00:00.000Z')
        b = kern.abgleichen(leer, MD, '2026-11-08T18:40:00.000Z', DATEN, '2026-11-08T22:00:00.000Z')
        r = kern.zusammenfuehren(a['fortschritt'], b['fortschritt'])
        # {qid: [..]} = je Frage die IDs der Versuche
        self.assertEqual({qid: [v['id'] for v in vs] for qid, vs in r['versuche'].items()},
                         {'1.Q01': ['docs:1.Q01:Apfel#u0f0:0'], '1.Q03': ['docs:1.Q03:#u0f1:0'],
                          '2.Q01': ['docs:2.Q01:Erbse|Gurke#u0f0:0']})
        self.assertEqual(sorted(q for q in r['sterne'] if kern.stern_an(r, q)), ['1.Q01'])

    def test_docs_id_zaehlt_die_gueltigen_versuche_davor(self):
        f = {'versuche': {'1.Q01': [app_versuch('a1', '2026-11-08T20:00:00Z', ['Apfel']),
                                    app_versuch('a2', '2026-11-08T20:10:00Z', ['Kiwi'], geloescht='2026-11-08T20:11:00Z')]},
             'md': {'zeit': None, 'basis': {}, 'ueberschrieben': {}}}
        md = MD.replace('- [ ] Banane  ', '- [x] Banane  ', 1).replace('- [x] Apfel  ', '- [ ] Apfel  ', 1)
        r = kern.abgleichen(f, md, '2026-11-08T21:20:00.000Z', DATEN, '2026-11-08T21:25:00.000Z')
        # Die ID trägt nur die Antwort; unsicher in Docs ist der Stern und gehört nicht zum Versuch
        self.assertEqual(r['fortschritt']['versuche']['1.Q01'][-1]['id'], 'docs:1.Q01:Banane#u0f0:1')

    def test_unbrauchbare_versuche_werden_verworfen(self):
        gut = app_versuch('v1', '2026-11-08T10:00:00Z', ['Apfel'])
        kaputt = [dict(gut, id=5), dict(gut, zeit='gestern'), dict(gut, zeit=None), dict(gut, wahl='Apfel'), None, 'x']
        r = kern.zusammenfuehren({'versuche': {'1.Q01': [gut] + kaputt, '1.Q02': 'keine Liste'}}, {})
        self.assertEqual(r['versuche'], {'1.Q01': [gut], '1.Q02': []})

    def test_eingaenge_bleiben_unveraendert(self):
        a = {'versuche': {'1.Q01': [app_versuch('v1', '2026-11-08T10:00:00Z', ['Apfel'])]}}
        b = copy.deepcopy(a)
        b['versuche']['1.Q01'][0]['geaendert'] = '2026-11-09T10:00:00Z'
        vorher = copy.deepcopy((a, b))
        r = kern.zusammenfuehren(a, b)
        r['versuche']['1.Q01'][0]['wahl'].append('x')
        self.assertEqual((a, b), vorher)


def stern(wert, zeit):
    return {'wert': wert, 'zeit': zeit}


class Stern(unittest.TestCase):

    def test_uebernahme_des_alten_merkmals(self):
        # Letzter nicht zurückgenommener Versuch mit unsicher gibt Stern und Zeit; vorhandener Eintrag bleibt
        f = kern.vervollstaendigen({'versuche': {
            '1.Q01': [app_versuch('a', '2026-11-08T10:00:00Z', ['Apfel'], unsicher=True),
                      app_versuch('b', '2026-11-09T10:00:00Z', ['Apfel'], unsicher=True),
                      app_versuch('c', '2026-11-10T10:00:00Z', ['Apfel'])],
            '1.Q02': [app_versuch('d', '2026-11-08T10:00:00Z', ['Gurke'], unsicher=True, geloescht='2026-11-08T11:00:00Z')],
            '1.Q03': [app_versuch('e', '2026-11-08T10:00:00Z', [], unsicher=True)],
            '2.Q01': [app_versuch('g', '2026-11-08T10:00:00Z', ['Erbse'], unsicher=True)],
        }, 'sterne': {'1.Q03': stern(False, '2026-11-09T10:00:00Z')}}, 'test')
        self.assertEqual(f['sterne'], {'1.Q01': {**stern(True, '2026-11-09T10:00:00Z'), 'alt': True},
                                       '1.Q03': stern(False, '2026-11-09T10:00:00Z'),
                                       '2.Q01': {**stern(True, '2026-11-08T10:00:00Z'), 'alt': True}})
        # Wiederholt angewendet ändert sich nichts
        self.assertEqual(kern.vervollstaendigen(copy.deepcopy(f), 'test'), f)

    def test_veralteter_stand_haelt_uebernommenen_stern_nicht_fest(self):
        # Auf Drive ist unsicher am Versuch y später abgehakt bzw. y zurückgenommen; ein Gerät hat noch die alte Fassung
        q = frage('1.Q01')
        x = app_versuch('x', '2026-11-01T10:00:00Z', ['Apfel'])
        y = app_versuch('y', '2026-11-08T10:00:00Z', ['Apfel'], unsicher=True)
        for drive in (dict(y, unsicher=False, geaendert='2026-11-08T12:00:00Z'),
                      dict(y, geloescht='2026-11-08T12:00:00Z', geaendert='2026-11-08T12:00:00Z')):
            with self.subTest(drive=drive):
                veraltet = kern.vervollstaendigen({'versuche': {'1.Q01': [x, y]}}, 'test')
                for a, b in ((veraltet, {'versuche': {'1.Q01': [x, drive]}}), ({'versuche': {'1.Q01': [x, drive]}}, veraltet)):
                    g = kern.zusammenfuehren(a, b)
                    self.assertFalse(kern.stern_an(g, '1.Q01'))
                    self.assertEqual(kern.wiederholung(q, g['versuche']['1.Q01'], '2026-11-12', DATEN['klausur'],
                                                       g['sterne'].get('1.Q01')), ('sicher', None))

    def test_uebernommener_stern_wirkt_wie_das_alte_merkmal(self):
        # Gleiche Zeit (falsch mit unsicher, dann richtig) und unsicher an einem Versuch ohne Ergebnis: wie vorher
        q = frage('1.Q01')
        faelle = [([app_versuch('a', '2026-11-08T10:00:00Z', ['Banane'], unsicher=True),
                    app_versuch('b', '2026-11-08T10:00:00Z', ['Apfel'])], ('wartet', '2026-11-10')),
                  ([app_versuch('a', '2026-11-08T10:00:00Z', ['Apfel']),
                    app_versuch('b', '2026-11-08T11:00:00Z', [], unsicher=True)], ('sicher', None))]
        for versuche, soll in faelle:
            g = kern.vervollstaendigen({'versuche': {'1.Q01': versuche}}, 'test')
            self.assertEqual(kern.wiederholung(q, versuche, '2026-11-09', DATEN['klausur'], g['sterne'].get('1.Q01')), soll)

    def test_stern_aus_nimmt_auch_das_alte_merkmal(self):
        q = frage('1.Q01')
        f = kern.vervollstaendigen({'versuche': {'1.Q01': [app_versuch('a', '2026-11-08T10:00:00Z', ['Apfel'], unsicher=True)]}},
                                   'test')
        self.assertEqual(kern.wiederholung(q, f['versuche']['1.Q01'], '2026-11-09', DATEN['klausur'], f['sterne']['1.Q01']),
                         ('wartet', '2026-11-11'))
        kern.stern_setzen(f, '1.Q01', False, '2026-11-09T08:00:00Z')
        f = kern.vervollstaendigen(f, 'test')
        self.assertEqual(kern.wiederholung(q, f['versuche']['1.Q01'], '2026-11-09', DATEN['klausur'], f['sterne']['1.Q01']),
                         ('sicher', None))

    def test_schutz_auch_wenn_nur_sterne_uebrig_sind(self):
        # Versuche verloren, eigene Sterne noch da: Die Antworten würden aus der .md entfernt, das hält an
        daten, md, f = viele_fragen(6)
        md = md.replace('- [ ] *unsicher*', '- [x] *unsicher*')
        f['md']['basis'] = {k: 'A#u1f0' for k in f['md']['basis']}
        f['sterne'] = {k: stern(True, '2026-11-08T19:00:00Z') for k in f['md']['basis']}
        r = kern.abgleichen(f, md, '2026-11-08T21:00:00Z', daten, '2026-11-08T21:05:00Z')
        self.assertIsNotNone(r['abbruch'])
        self.assertIsNone(r['md_neu'])

    def test_unbrauchbare_sterne_werden_verworfen(self):
        f = kern.vervollstaendigen({'sterne': {'a': stern('ja', '2026-11-08T10:00:00Z'), 'b': stern(True, 'gestern'),
                                               'c': None, 'd': stern(False, '2026-11-08T10:00:00Z')}}, 'test')
        self.assertEqual(f['sterne'], {'d': stern(False, '2026-11-08T10:00:00Z')})
        self.assertEqual(kern.vervollstaendigen({'sterne': ['kein Dictionary']}, 'test')['sterne'], {})

    def test_zusammenfuehren_spaeterer_gewinnt_bei_gleicher_zeit_der_gesetzte(self):
        a = {'sterne': {'1.Q01': stern(True, '2026-11-08T10:00:00Z'), '1.Q02': stern(False, '2026-11-08T12:00:00Z'),
                        '1.Q03': stern(False, '2026-11-08T10:00:00Z')}}
        b = {'sterne': {'1.Q01': stern(False, '2026-11-08T11:00:00Z'), '1.Q02': stern(True, '2026-11-08T11:00:00Z'),
                        '1.Q03': stern(True, '2026-11-08T10:00:00Z'), '2.Q01': stern(True, '2026-11-08T09:00:00Z')}}
        for x, y in ((a, b), (b, a)):
            r = kern.zusammenfuehren(x, y)
            self.assertEqual({q: s['wert'] for q, s in r['sterne'].items()},
                             {'1.Q01': False, '1.Q02': False, '1.Q03': True, '2.Q01': True})

    def test_stand_ohne_sterne_loescht_keinen_stern(self):
        # Ein Stand aus einer älteren Fassung der App kennt keine Sterne; die Vereinigung behält sie
        mit = {'versuche': {'1.Q01': [app_versuch('a', '2026-11-08T10:00:00Z', ['Apfel'])]},
               'sterne': {'1.Q01': stern(True, '2026-11-08T10:01:00Z'), '1.Q02': stern(False, '2026-11-08T10:02:00Z')}}
        ohne = {'versuche': {'1.Q01': [app_versuch('a', '2026-11-08T10:00:00Z', ['Apfel'])]}}
        for x, y in ((mit, ohne), (ohne, mit)):
            self.assertEqual(kern.zusammenfuehren(x, y)['sterne'], mit['sterne'])

    def test_ausgeschalteter_stern_kommt_durch_alte_merkmale_nicht_zurueck(self):
        # Gerät A schaltet den übernommenen Stern aus, Gerät B kennt nur das alte Merkmal: aus bleibt aus
        alt = {'versuche': {'1.Q01': [app_versuch('a', '2026-11-08T10:00:00Z', ['Apfel'], unsicher=True)]}}
        a = kern.vervollstaendigen(copy.deepcopy(alt), 'test')
        kern.stern_setzen(a, '1.Q01', False, '2026-11-16T18:00:00Z')
        for x, y in ((a, alt), (alt, a)):
            self.assertFalse(kern.stern_an(kern.zusammenfuehren(x, y), '1.Q01'))

    def test_stern_zaehlt_im_tempo_nicht_als_antwort(self):
        f = kern.leerer_fortschritt('test')
        kern.stern_setzen(f, '1.Q01', True, '2026-11-08T10:00:00Z')
        self.assertEqual(kern.tempo(DATEN, f, '2026-11-09')['offen'], 4)
        self.assertEqual(kern.wiederholung(frage('1.Q01'), [], '2026-11-09', DATEN['klausur'], stern(True, '2026-11-08T10:00:00Z')),
                         ('neu', None))

    def test_neuer_versuch_aus_docs_traegt_kein_unsicher(self):
        r = kern.abgleichen(kern.leerer_fortschritt('test'), MD, '2026-11-08T17:25:00.000Z', DATEN,
                            '2026-11-08T21:00:00.000Z')
        self.assertFalse(any(v['unsicher'] for vs in r['fortschritt']['versuche'].values() for v in vs))

    def test_falsch_zahl(self):
        vs = [app_versuch('a', '2026-11-08T10:00:00Z', ['Banane']), app_versuch('b', '2026-11-09T10:00:00Z', ['Apfel']),
              app_versuch('c', '2026-11-10T10:00:00Z', ['Banane']),
              app_versuch('d', '2026-11-11T10:00:00Z', ['Banane'], geloescht='2026-11-11T10:01:00Z')]
        self.assertEqual(kern.falsch_zahl(frage('1.Q01'), vs), 2)

    def test_abgleich_mit_alter_basis_ohne_aenderung_in_docs(self):
        # Basis einer älteren Fassung (unsicher am letzten Versuch) und dieselbe .md: Stern übernommen, nichts zu tun
        f = {'versuche': {'1.Q01': [app_versuch('a', '2026-11-08T17:00:00Z', ['Apfel'], unsicher=True)],
                          '1.Q03': [app_versuch('b', '2026-11-08T17:00:00Z', [], falsch=True)],
                          '2.Q01': [app_versuch('c', '2026-11-08T17:00:00Z', ['Erbse', 'Gurke'])]},
             'md': {'zeit': '2026-11-08T17:30:00Z', 'basis': {'1.Q01': 'Apfel#u1f0', '1.Q03': '#u0f1',
                                                             '2.Q01': 'Erbse|Gurke#u0f0'}, 'ueberschrieben': {}}}
        r = kern.abgleichen(f, MD, '2026-11-08T17:25:00.000Z', DATEN, '2026-11-08T21:00:00.000Z')
        self.assertEqual((r['geaendert'], r['md_neu']), ([], None))
        self.assertTrue(kern.stern_an(r['fortschritt'], '1.Q01'))
        self.assertEqual(r['fortschritt']['versuche'], kern.vervollstaendigen(f, 'test')['versuche'])


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
        # Ein Versuch ohne Ergebnis (nur unsicher, keine Option) macht die Frage nicht beantwortet
        f = kern.leerer_fortschritt('test')
        f['versuche'] = {'1.Q01': [app_versuch('a', '2026-11-08T10:00:00Z', [], unsicher=True)],
                         '1.Q02': [app_versuch('b', '2026-11-08T10:00:00Z', ['Gurke'])]}
        self.assertEqual(kern.tempo(DATEN, f, '2026-11-09')['offen'], 3)


if __name__ == '__main__':
    unittest.main()
