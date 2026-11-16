"""Auswertung eines Fachs: Stand, Quote je Thema, falsche Fragen und Sterne, Sammlungen, Schritte, Tempo.

Rein: fragen-<fach>.json (zuerst im App-Ordner auf Drive, sonst build/), fortschritt-<fach>.json aus dem App-Ordner
      (fehlt sie: leerer Stand) und das Lernskript. Der Abgleich mit dem Lernskript läuft nur im Speicher, damit
      Haken aus Google Docs mitzählen, die die App noch nicht übernommen hat. Es wird nichts geschrieben.
Raus: knapper Bericht auf der Konsole. Fragen als Thema.Nr (Nummer im Lernskript), es zählt der letzte Versuch.
Aufruf: python werkzeug/auswerten.py mibi|innere [--md PFAD] [--fortschritt PFAD] [--fragen PFAD] [--heute JJJJ-MM-TT]
Schreibweisen: [x for x in liste if bedingung] baut eine Liste, {..} ebenso eine Menge oder ein Dictionary,
(..) einen Durchlauf ohne Zwischenliste; lambda v: ausdruck ist eine Funktion in einer Zeile, meist als
Sortierschlüssel; next(durchlauf, None) liefert den ersten Treffer oder None.
"""
import argparse
import json
import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kern
from faecher import BUILD, DRIVE_APP, FAECHER

WOCHENTAG = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']


def iso_utc(d):
    """Zeitpunkt als ISO in UTC mit Millisekunden, wie Drive modifiedTime liefert."""
    return d.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S.') + f'{d.microsecond // 1000:03d}Z'


def datum(tag):
    """'2026-11-10' -> 'Di 10.11.2026'."""
    d = datetime.strptime(tag, '%Y-%m-%d')
    return f'{WOCHENTAG[d.weekday()]} {d:%d.%m.%Y}'


def auswertung(daten, fortschritt, md_text=None, md_zeit=None, heute=None, jetzt=None):
    """Zählt den Stand eines Fachs. Rein: Fragendaten, Fortschritt, optional Text und Zeit des Lernskripts.

    Raus: Dictionary mit heute, gesamt, bruchstuecke, bearbeitet, richtig, stand, themen, tempo, falsch, markiert,
    fehler, abbruch. Der Fortschritt wird nicht verändert.
    """
    jetzt = jetzt or iso_utc(datetime.now(UTC))
    heute = heute or kern.tag_von(jetzt)
    f = kern.vervollstaendigen(fortschritt, daten['fach'])
    fehler, abbruch = [], None
    # Haken aus dem Lernskript wie beim Abgleich der App übernehmen, nur im Speicher
    if md_text is not None:
        ab = kern.abgleichen(f, md_text, md_zeit, daten, jetzt)
        f, fehler, abbruch = ab['fortschritt'], ab['fehler'], ab['abbruch']

    # Je beantwortbare Frage in Lernskript-Reihenfolge: letztes Ergebnis und Stern
    marke, themen, stand = {}, [], None
    for t in daten['themen']:
        eintrag = {'rang': t['rang'], 'titel': t['titel'], 'n': 0, 'richtig': 0, 'falsch': [], 'stern': [],
                   'meditricks': ((f['schritte'].get(str(t['rang'])) or {}).get('meditricks') or {}).get('wert'),
                   'kern': ((f['schritte'].get(str(t['rang'])) or {}).get('kern') or {}).get('wert')}
        for q in t['fragen']:
            marke[q['id']] = f'{t["rang"]}.{q["nr"]}'
            if q['typ'] == 'fragment':
                continue
            e = kern.letztes_ergebnis(q, f['versuche'].get(q['id']))
            if e is None:
                continue
            stand = (t['rang'], q['nr'])
            eintrag['n'] += 1
            if e == 'richtig':
                eintrag['richtig'] += 1
            else:
                eintrag['falsch'].append(marke[q['id']])
            if kern.stern_an(f, q['id']):
                eintrag['stern'].append(marke[q['id']])
        if eintrag['n']:
            themen.append(eintrag)

    alle = [q for t in daten['themen'] for q in t['fragen']]
    # Lesefehler lesbar machen: Frage-ID -> Thema.Nr, "<rang>#<nr>" -> unbekannte Frage
    lesefehler = [marke.get(x, x.replace('#', '.') + ' (gibt es nicht)') for x in fehler]
    return {
        'heute': heute,
        'gesamt': sum(1 for q in alle if q['typ'] != 'fragment'),
        'bruchstuecke': sum(1 for q in alle if q['typ'] == 'fragment'),
        'bearbeitet': sum(t['n'] for t in themen),
        'richtig': sum(t['richtig'] for t in themen),
        'stand': stand,
        'themen': sorted(themen, key=lambda t: t['rang']),
        'tempo': kern.tempo(daten, f, heute),
        # Sammlungen wie in der App, als Thema.Nr: Falsch (je falsch) und Markiert (Stern, auch unbeantwortete)
        'falsch': [marke[x['frage']['id']] for x in kern.falsch_sammlung(daten, f)],
        'markiert': [marke[x['frage']['id']] for x in kern.markiert_sammlung(daten, f)],
        'fehler': lesefehler,
        'abbruch': abbruch,
    }


def bericht(a, daten):
    """Bericht als Text, eine Aussage je Zeile."""
    z = []
    n = a['bruchstuecke']
    z.append(f'Bearbeitet {a["bearbeitet"]} von {a["gesamt"]} Fragen'
             + (f' ({n} {"Bruchstück" if n == 1 else "Bruchstücke"} ohne Antwort nicht gezählt)' if n else ''))
    if a['bearbeitet']:
        z.append(f'Stand: Thema {a["stand"][0]}, Frage {a["stand"][1]}')
        z.append(f'Zuletzt richtig: {a["richtig"]} ({100 * a["richtig"] // a["bearbeitet"]} %)')
    z.append('')
    for t in a['themen']:
        z.append(f'Thema {t["rang"]} {t["titel"]}: {t["richtig"]} von {t["n"]} zuletzt richtig')
        if t['falsch']:
            z.append('   falsch:   ' + ', '.join(t['falsch']))
        if t['stern']:
            z.append('   Stern:    ' + ', '.join(t['stern']))
    if a['themen']:
        z.append('')
    z.append(f'Sammlungen: ✗ {len(a["falsch"])} je falsch · ☆ {len(a["markiert"])} markiert')
    if a['themen']:
        # Schritte je bearbeitetem Thema; None = noch nicht abgehakt
        anzeige = {'ja': 'ja', 'keins': 'keins', None: 'offen'}
        z.append('Schritte: ' + ' · '.join(
            f'Thema {t["rang"]} Meditricks {anzeige.get(t["meditricks"], t["meditricks"])}, '
            f'Kern {anzeige.get(t["kern"], t["kern"])}' for t in a['themen']))
    tp = a['tempo']
    ohne_c = ' ohne C-Themen' if daten.get('plan') == 'block-stufe' else ''
    z.append(f'Tempo: {tp["offen"]} offene Fragen{ohne_c} bis {datum(tp["ziel"])} ({tp["tage"]} Tage) '
             f'→ {tp["pro_tag"]} pro Tag · Klausur in {tp["bis_klausur"]} Tagen')
    if a['fehler']:
        z.append('Lesefehler im Lernskript (übersprungen): ' + ', '.join(a['fehler']))
    if a['abbruch']:
        z.append('Abgleich: ' + a['abbruch'])
    return '\n'.join(z)


def json_lesen(pfad):
    with open(pfad, encoding='utf-8') as d:
        return json.load(d)


def main(argv=None):
    p = argparse.ArgumentParser(description='Auswertung eines Fachs der Altfragen-App')
    p.add_argument('fach', choices=sorted(FAECHER))
    p.add_argument('--md', help='Lernskript (.md)')
    p.add_argument('--fortschritt', help='fortschritt-<fach>.json')
    p.add_argument('--fragen', help='fragen-<fach>.json')
    p.add_argument('--heute', help='Tag der Auswertung, JJJJ-MM-TT')
    arg = p.parse_args(argv)
    cfg = FAECHER[arg.fach]

    # Fragendaten: angegeben, sonst die erste vorhandene von Drive und build/
    pfad_fragen = arg.fragen or next((x for x in (f'{DRIVE_APP}/fragen-{arg.fach}.json',
                                                  f'{BUILD}/fragen-{arg.fach}.json') if os.path.exists(x)), None)
    if not pfad_fragen or not os.path.exists(pfad_fragen):
        print(f'Keine Fragendatei gefunden. Erst: python werkzeug/bauen.py {arg.fach}')
        return 1
    daten = json_lesen(pfad_fragen)

    # Fortschritt: fehlt er, gilt ein leerer Stand
    pfad_f = arg.fortschritt or f'{DRIVE_APP}/fortschritt-{arg.fach}.json'
    fortschritt = json_lesen(pfad_f) if os.path.exists(pfad_f) else kern.leerer_fortschritt(arg.fach)

    # Lernskript mit Änderungszeit als modifiedTime; newline='' lässt Zeilenenden unverändert
    pfad_md = arg.md or cfg['lernskript']
    md_text = md_zeit = None
    if os.path.exists(pfad_md):
        with open(pfad_md, encoding='utf-8', newline='') as d:
            md_text = d.read()
        md_zeit = iso_utc(datetime.fromtimestamp(os.path.getmtime(pfad_md), UTC))

    a = auswertung(daten, fortschritt, md_text, md_zeit, arg.heute)
    quellen = [f'Fortschritt {"vorhanden" if os.path.exists(pfad_f) else "fehlt, leerer Stand"}',
               f'Lernskript {"vom " + datum(kern.tag_von(md_zeit)) if md_text is not None else "fehlt"}']
    print(f'{daten["name"]} · Auswertung {datum(a["heute"])} · ' + ' · '.join(quellen))
    print(bericht(a, daten))
    return 0


if __name__ == '__main__':
    # Umlaute auch in Konsolen mit anderer Codepage
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
