"""Baut die Fragendatei der App aus den Quellen des Lernskripts und prüft sie gegen das echte Lernskript.

Rein: <QUELLE>/src/<fach>/index.json, out/<fach>/NN.txt, ergaenzt/<fach>/NN.txt (über fmt.lade),
      das Lernskript und die beiden Probeklausuren des Fachs (nur gelesen).
Raus: build/fragen-<fach>.json nach FORMAT.md. Weicht das Gebaute vom Lernskript oder einer Probeklausur ab,
      wird die Liste der Abweichungen ausgegeben, nichts geschrieben und mit Code 1 beendet.
Die Aufbereitung (Reihenfolge, Nummerierung, Mischen der Optionen) folgt render.py der Quelle.
Aufruf: python werkzeug/bauen.py mibi|innere
Schreibweisen: [x for x in liste if bedingung] baut eine Liste, {..} ebenso eine Menge oder ein Dictionary,
(..) einen Durchlauf ohne Zwischenliste; lambda v: ausdruck ist eine Funktion in einer Zeile, meist als
Sortierschlüssel; next(durchlauf, None) liefert den ersten Treffer oder None.
"""
import hashlib
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kern
from faecher import BUILD, FAECHER, QUELLE


def _fmt():
    # fmt aus dem Quellordner erst beim Bauen laden, damit die Prüffunktionen ohne Quelle testbar bleiben.
    # Hinten im Suchpfad, damit nichts Eigenes verdeckt wird. Raus: das Modul mit lade() und PIN
    if QUELLE not in sys.path:
        sys.path.append(QUELLE)
    import fmt
    return fmt


# ---------- Aufbereitung wie in render.py ----------

def meta_text(m):
    # `erwartet …` -> erwartet … (Backticks und Leerraum außen weg)
    return m.strip().strip('`').strip()


def gefragt_eintraege(g):
    # "- Text — 8×" -> "**8×** Text"; die Kopfzeile mit den Jahrgängen entfällt, Listenzeichen ebenso
    aus = []
    for zeile in g:
        if zeile.startswith('**So wurde gefragt**'):
            continue
        m = re.match(r'^- (.*?)\s+—\s+(\d+)×\s*$', zeile)
        eintrag = f'- **{m.group(2)}×** {m.group(1)}' if m else zeile
        aus.append(eintrag.removeprefix('- '))
    return aus


def optionen_mischen(schluessel, q):
    # Alle Optionen mischen, Sammeloptionen ("alle genannten" ...) ans Ende.
    # Jede Option ist ein Tupel (Text, Begründung, anzukreuzen?, ergänzt?); Startwert aus dem Schlüssel,
    # deshalb bei jedem Lauf dieselbe Reihenfolge wie im Lernskript
    opts = ([(o, w, True, False) for o, w in q['x']] + [(o, w, False, False) for o, w in q['o']]
            + [(o, w, False, True) for o, w in q['e']])
    rnd = random.Random(int(hashlib.md5(schluessel.encode('utf-8')).hexdigest(), 16))
    pin = _fmt().PIN
    frei = [x for x in opts if not pin.search(x[0])]
    fest = [x for x in opts if pin.search(x[0])]
    rnd.shuffle(frei)
    return frei + fest


def aussagen_trennen(stamm):
    # "Frage? 1 X, 2 Y, 3 Z." -> ("Frage?", ["X", "Y", "Z"]). Nur wenn die Nummern lückenlos ab 1 laufen
    m = re.search(r'([?:.])\s+(?=\(?1\)? )', stamm)
    if not m:
        return stamm, None
    kopf, rest = stamm[:m.start() + 1], stamm[m.end():].strip()
    teile = re.split(r'(?:^|,\s*)\(?(\d)\)?\s+', rest)
    # teile = [vorlauf, nummer1, text1, nummer2, text2, ...]; [1::2] = jede zweite ab Index 1
    nummern, texte = teile[1::2], teile[2::2]
    if len(nummern) < 3 or nummern != [str(i) for i in range(1, len(nummern) + 1)]:
        return stamm, None
    return kopf, [t.strip().rstrip('.').strip() for t in texte]


def ist_bruchstueck(q):
    return q['x'][0][0].lower().startswith('nicht rekonstruierbar')


def ist_leeres_bruchstueck(q):
    # Bruchstück ohne jede verwertbare Information -> nicht im Lernskript, nicht in der App
    return ist_bruchstueck(q) and not q['x'][0][1]


def gruppen_absetzen(md):
    # Fette Gruppenzeile direkt nach einem Stichpunkt würde als Fortsetzung gelesen -> Leerzeile davor
    aus = []
    for zeile in md.split('\n'):
        if zeile.startswith('**') and aus and aus[-1].lstrip().startswith('- '):
            aus.append('')
        aus.append(zeile)
    return '\n'.join(aus)


def titel_und_stufe(titel):
    # "Thema · A" -> ("Thema", "A"); ohne Suffix bleibt die Stufe leer
    m = re.match(r'^(.*) · ([ABC])$', titel)
    return (m.group(1), m.group(2)) if m else (titel, None)


def frage_bauen(fach, t, n, schl, nr, abschnitt, q):
    # Eine Frage nach FORMAT.md; Typ und Lösung wie in render.py
    ids = t['q_ids'][n]
    mal = len([i for i in ids.split(' · ') if i.strip()])
    stamm, aussagen = aussagen_trennen(q['stem'])
    optionen, loesung = [], None
    if ist_bruchstueck(q):
        typ = 'fragment'
        loesung = {'t': q['x'][0][0], 'w': q['x'][0][1]}
    elif q['typ'] == 'offen' or not (q['o'] or q['e']):
        typ = 'offen'
        loesung = {'t': q['x'][0][0], 'w': q['x'][0][1]}
    else:
        typ = 'negativ' if q['typ'] == 'negativ' else 'positiv'
        optionen = [{'t': o, 'w': w, 'richtig': c, 'erg': e, 'fest': bool(_fmt().PIN.search(o))}
                    for o, w, c, e in optionen_mischen(f'{fach}-{t["rank"]}-{schl}', q)]
    return {'id': f'{t["rank"]}.{schl}', 'nr': nr, 'abschnitt': abschnitt, 'mal': mal, 'typ': typ,
            'stamm': stamm, 'aussagen': aussagen, 'optionen': optionen, 'loesung': loesung,
            'neu': list(q['neu']), 'hinweis': list(q['hinweis']), 'ids': ids}


def bauen(fach, fehler):
    """Fragendaten ohne Probeklausuren; Fehler der Quelle landen in 'fehler'.

    Raus: (daten, roh {frageId: Quellfrage}, Anzahl weggelassener leerer Bruchstücke).
    """
    cfg = FAECHER[fach]
    with open(f'{QUELLE}/src/{fach}/index.json', encoding='utf-8') as d:
        idx = json.load(d)
    bloecke, block_nr = [], {}
    # Blöcke: "Block N · Titel" -> Nummer N und Titel ohne Vorsatz; Themen verweisen über die Zeilennummer
    for b in idx['blocks']:
        m = re.match(r'^Block (\d+) · (.*)$', b['title'])
        if not m:
            fehler.append(f'Blocktitel ohne Nummer: {b["title"]}')
            continue
        block_nr[b['line']] = int(m.group(1))
        bloecke.append({'nr': int(m.group(1)), 'titel': m.group(2), 'meta': meta_text(b['meta'])})
    themen, roh, leer = [], {}, 0
    for t in idx['topics']:
        if not os.path.exists(f'{QUELLE}/out/{fach}/{t["rank"]:02d}.txt'):
            fehler.append(f'Thema {t["rank"]}: out-Datei fehlt')
            continue
        o = _fmt().lade(QUELLE, fach, t['rank'])
        if o['errors']:
            fehler.append(f'Thema {t["rank"]}: {o["errors"]}')
        titel, stufe = titel_und_stufe(t['title'])
        # Schlüssel Q01, Q02 ... in Quellreihenfolge. Qnn ist per Definition die Position n in q_ids und q_sub
        # desselben Themas (so legt die Quelle sie an). Leere Bruchstücke fallen raus, die Nummer läuft weiter
        schluessel = [f'Q{n + 1:02d}' for n in range(t['n_q'])]
        fehlend = [s for s in schluessel if s not in o['qs']]
        if fehlend:
            fehler.append(f'Thema {t["rank"]}: Fragen fehlen in out: {fehlend}')
            continue
        fragen, abschnitte, akt, nr = [], [], None, 0
        for n, schl in enumerate(schluessel):
            q = o['qs'][schl]
            if ist_leeres_bruchstueck(q):
                leer += 1
                continue
            # Abschnitt wie im Lernskript: Ein neuer Titel beginnt einen Abschnitt, ohne Titel gilt der laufende weiter
            sub = t['q_sub'][n]
            if sub and sub != akt:
                akt = sub
                if sub not in [a['titel'] for a in abschnitte]:
                    abschnitte.append({'titel': sub, 'text': gruppen_absetzen(o['subs'][sub]) if sub in o['subs'] else ''})
            nr += 1
            frage = frage_bauen(fach, t, n, schl, nr, akt, q)
            fragen.append(frage)
            roh[frage['id']] = q
        themen.append({
            'rang': t['rank'], 'titel': titel, 'stufe': stufe,
            'block': block_nr[t['block']] if t['block'] is not None else None,
            'meta': meta_text(t['meta']), 'kern': gruppen_absetzen(o['kern']), 'falle': o['falle'] or None,
            'tabellen': '\n'.join(t['tables']).strip(), 'gefragt': gefragt_eintraege(t['gefragt']),
            'abschnitte': abschnitte, 'fragen': fragen,
        })
    daten = {'format': 1, 'fach': fach, 'name': cfg['name'], 'klausur': cfg['klausur'],
             'klausurInfo': cfg['klausurInfo'], 'stand': kern.jetzt_berlin(), 'plan': cfg['plan'],
             'bloecke': bloecke, 'themen': themen, 'probeklausuren': []}
    return daten, roh, leer


# ---------- Lernskript zerlegen (zum Prüfen) ----------

LOESUNG = re.compile(r'^\*\*Lösung:\*\*\s*(.*?)\s*$')
NICHT_UEBERLIEFERT = re.compile(r'^\*\*Lösung nicht überliefert\*\*')
# Merkmal-Kästchen, an das Google Docs den folgenden Absatz angehängt hat ("*unsicher* **Hinweis:** …")
ANGEHAENGT = re.compile(r'^\*(unsicher|falsch)\*\s+(.+)$')


def md_fragen(text):
    """Alle Fragen der .md mit Thema, Nummer, Stamm, Optionstexten, Merkmalen und Lösungszeile, in Dateireihenfolge.

    'angehaengt' sammelt Merkmal-Kästchen mit angehängtem Text: Die App kann solche Fragen nicht lesen.
    """
    aus, rang, akt = [], None, None
    for i, roh in enumerate(text.split('\n')):
        z = roh.removesuffix('\r')
        m = kern.THEMA.match(z)
        if m:
            rang, akt = int(m.group(1)), None
            continue
        if kern.UEBERSCHRIFT.match(z):
            akt = None
            continue
        m = kern.FRAGE.match(z)
        if m:
            akt = {'rang': rang, 'nr': int(m.group(1)), 'zeile': i + 1, 'stamm': None, 'optionen': [],
                   'merkmale': [], 'angehaengt': [], 'loesung': None, 'nicht_ueberliefert': False}
            aus.append(akt)
            continue
        if akt is None:
            continue
        m = kern.KASTEN.match(z)
        if m:
            inhalt = kern.normal(m.group(4))
            n = ANGEHAENGT.match(inhalt)
            if n:
                akt['merkmale'].append(n.group(1))
                akt['angehaengt'].append((i + 1, inhalt))
            else:
                (akt['merkmale'] if inhalt in ('unsicher', 'falsch') else akt['optionen']).append(inhalt)
            continue
        m = LOESUNG.match(z)
        if m and akt['loesung'] is None:
            akt['loesung'] = m.group(1)
            continue
        if NICHT_UEBERLIEFERT.match(z):
            akt['nicht_ueberliefert'] = True
            continue
        # Erste nichtleere Zeile nach dem Fragekopf ist der Stamm
        if akt['stamm'] is None and z.strip():
            akt['stamm'] = z
    return aus


def lernskript_pruefen(daten, text):
    """Vergleicht jede Frage mit dem Lernskript über (Thema, Nummer).

    Raus: (Abweichungen, Warnungen). Warnungen betreffen nur die Darstellung im Lernskript, nicht die Zuordnung.
    """
    abw, warn = [], []
    md = {}
    for f in md_fragen(text):
        if f['rang'] is None:
            abw.append(f'Zeile {f["zeile"]}: Frage {f["nr"]} vor dem ersten Thema')
        elif (f['rang'], f['nr']) in md:
            abw.append(f'Zeile {f["zeile"]}: Frage {f["rang"]}#{f["nr"]} doppelt')
        else:
            md[(f['rang'], f['nr'])] = f
    gebaut = set()
    for t in daten['themen']:
        for q in t['fragen']:
            ort = f'{q["id"]} (Thema {t["rang"]}, Frage {q["nr"]})'
            gebaut.add((t['rang'], q['nr']))
            f = md.get((t['rang'], q['nr']))
            if f is None:
                abw.append(f'{ort}: nicht im Lernskript')
                continue
            for zeile, inhalt in f['angehaengt']:
                warn.append(f'{ort}, Zeile {zeile}: Kästchen und Folgeabsatz in einer Zeile ({inhalt[:50]}…). '
                            'Die App meldet die Frage als Lesefehler, bis im Lernskript ein Zeilenumbruch dahinter steht')
            if kern.normal(f['stamm']) != kern.normal(q['stamm']):
                abw.append(f'{ort}: Stamm weicht ab: {f["stamm"]!r} / {q["stamm"]!r}')
            # Optionen nach normal() in gleicher Reihenfolge; [.. for o in ..] = Liste der normalisierten Texte
            soll = [kern.normal(o['t']) for o in q['optionen']]
            if f['optionen'] != soll:
                abw.append(f'{ort}: Optionen weichen ab: {f["optionen"]} / {soll}')
            if q['typ'] in ('positiv', 'negativ'):
                richtig = ' · '.join(o['t'] for o in q['optionen'] if o['richtig'])
                if f['loesung'] is None or kern.normal(f['loesung']) != kern.normal(richtig):
                    abw.append(f'{ort}: Lösung weicht ab: {f["loesung"]!r} / {richtig!r}')
                if f['merkmale'] != ['unsicher']:
                    abw.append(f'{ort}: Merkmal-Kästchen {f["merkmale"]}')
            elif q['typ'] == 'offen':
                l = q['loesung']
                richtig = l['t'] + (f' — {l["w"]}' if l['w'] else '')
                if f['loesung'] is None or kern.normal(f['loesung']) != kern.normal(richtig):
                    abw.append(f'{ort}: Lösung weicht ab: {f["loesung"]!r} / {richtig!r}')
                if sorted(f['merkmale']) != ['falsch', 'unsicher']:
                    abw.append(f'{ort}: Merkmal-Kästchen {f["merkmale"]}')
            else:
                if not f['nicht_ueberliefert'] or f['merkmale']:
                    abw.append(f'{ort}: Bruchstück im Lernskript anders dargestellt')
    for (rang, nr), f in md.items():
        if (rang, nr) not in gebaut:
            abw.append(f'Zeile {f["zeile"]}: Frage {rang}#{nr} im Lernskript ohne Gegenstück')
    return abw, warn


# ---------- Probeklausuren zuordnen ----------

PROBE_LOESUNG = re.compile(r'^\*\*([0-9]+) · (.*?)\*\* · Thema ([0-9]+)')


def probe_fragen(text):
    """Fragen einer Probeklausur: {nummer: {stamm, optionen}} und Lösungsteil {nummer: (lösung, thema)}."""
    fragen, loesungen, akt = {}, {}, None
    for roh in text.split('\n'):
        z = roh.removesuffix('\r')
        m = PROBE_LOESUNG.match(z)
        if m:
            akt = None
            loesungen.setdefault(int(m.group(1)), []).append((m.group(2), int(m.group(3))))
            continue
        if kern.UEBERSCHRIFT.match(z) or z.strip() == '---':
            akt = None
            continue
        m = kern.FRAGE.match(z)
        if m:
            akt = {'stamm': [], 'optionen': []}
            fragen.setdefault(int(m.group(1)), []).append(akt)
            continue
        if akt is None:
            continue
        m = kern.KASTEN.match(z)
        if m:
            akt['optionen'].append(m.group(4))
        elif z.strip() and not akt['optionen']:
            akt['stamm'].append(z.strip())
    return fragen, loesungen


def probe_zuordnen(daten, roh, text, name):
    """Ordnet jede Frage der Probeklausur über Thema, Stamm und Optionsmenge einer Frage-ID zu.

    Raus: (Frage-IDs in Klausurreihenfolge, Abweichungen). Nie über die Position.
    """
    abw = []
    fragen, loesungen = probe_fragen(text)
    nach_rang = {t['rang']: t for t in daten['themen']}
    ids = []
    for nr in sorted(set(fragen) | set(loesungen)):
        ort = f'{name}, Frage {nr}'
        if len(fragen.get(nr, [])) != 1 or len(loesungen.get(nr, [])) != 1:
            abw.append(f'{ort}: Frage oder Lösung fehlt oder ist doppelt')
            continue
        f, (loesung, rang) = fragen[nr][0], loesungen[nr][0]
        stamm = kern.normal(' '.join(f['stamm']))
        # Optionsmenge nach normal(); {.. for o in ..} = Menge der normalisierten Texte
        menge = {kern.normal(o) for o in f['optionen']}
        t = nach_rang.get(rang)
        # Alle Fragen des Themas mit Optionen, deren Quellstamm und Optionsmenge nach normal() gleich sind
        kandidaten = [q for q in (t['fragen'] if t else [])
                      if q['optionen'] and kern.normal(roh[q['id']]['stem']) == stamm
                      and {kern.normal(o['t']) for o in q['optionen']} == menge]
        if len(kandidaten) != 1:
            abw.append(f'{ort} (Thema {rang}): {len(kandidaten)} passende Fragen')
            continue
        q = kandidaten[0]
        # Lösungszeile: richtige Optionen in der Reihenfolge der Probeklausur
        reihenfolge = {kern.normal(o): i for i, o in enumerate(f['optionen'])}
        # Sortierschlüssel = Position der Option in der Probeklausur
        richtig = sorted((o['t'] for o in q['optionen'] if o['richtig']), key=lambda x: reihenfolge[kern.normal(x)])
        if kern.normal(loesung) != kern.normal(' · '.join(richtig)):
            abw.append(f'{ort}: Lösung {loesung!r} passt nicht zu {q["id"]}')
            continue
        ids.append(q['id'])
    if len(set(ids)) != len(ids):
        abw.append(f'{name}: eine Frage-ID kommt mehrfach vor')
    return ids, abw


# ---------- Ablauf ----------

def lesen(pfad):
    # Text unverändert lesen; newline='' lässt die Zeilenenden, wie sie sind
    with open(pfad, encoding='utf-8', newline='') as d:
        return d.read()


def main(argv):
    if len(argv) != 2 or argv[1] not in FAECHER:
        print(f'Aufruf: python werkzeug/bauen.py {"|".join(FAECHER)}')
        return 2
    fach = argv[1]
    cfg = FAECHER[fach]
    fehler, warnungen = [], []
    daten, roh, leer = bauen(fach, fehler)

    # Prüfung gegen das echte Lernskript (so, wie es zuletzt gespeichert wurde)
    if os.path.exists(cfg['lernskript']):
        abw, warnungen = lernskript_pruefen(daten, lesen(cfg['lernskript']))
        fehler += abw
    else:
        fehler.append(f'Lernskript fehlt: {cfg["lernskript"]}')

    # Probeklausuren: jede Frage muss eindeutig einer Frage-ID zugeordnet werden
    for i, pfad in enumerate(cfg['probeklausuren'], start=1):
        name = f'Probeklausur {i}'
        if not os.path.exists(pfad):
            fehler.append(f'{name} fehlt: {pfad}')
            continue
        ids, abw = probe_zuordnen(daten, roh, lesen(pfad), name)
        fehler += abw
        daten['probeklausuren'].append({'name': name, 'minuten': cfg['minuten'], 'fragen': ids})

    if warnungen:
        print(f'{len(warnungen)} Warnungen zum Lernskript:')
        for w in warnungen:
            print('  ' + w)
    if fehler:
        print(f'{len(fehler)} Abweichungen, nichts geschrieben:')
        for f in fehler:
            print('  ' + f)
        return 1

    os.makedirs(BUILD, exist_ok=True)
    ziel = f'{BUILD}/fragen-{fach}.json'
    with open(ziel, 'w', encoding='utf-8', newline='\n') as aus:
        json.dump(daten, aus, ensure_ascii=False, indent=1)
        aus.write('\n')

    # Zahlen zur Kontrolle
    alle = [q for t in daten['themen'] for q in t['fragen']]
    bruch = sum(1 for q in alle if q['typ'] == 'fragment')
    typen = {k: sum(1 for q in alle if q['typ'] == k) for k in ('positiv', 'negativ', 'offen', 'fragment')}
    print(f'{cfg["name"]}: {len(daten["themen"])} Themen, {len(alle)} Fragen, {len(alle) - bruch} beantwortbar, '
          f'{bruch} Bruchstücke, {leer} leere Bruchstücke weggelassen')
    print('Typen: ' + ', '.join(f'{k} {v}' for k, v in typen.items()))
    print('Probeklausuren: ' + ', '.join(f'{p["name"]} {len(p["fragen"])} Fragen' for p in daten['probeklausuren']))
    print(f'geschrieben: {ziel}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
