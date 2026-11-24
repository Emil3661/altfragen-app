"""Lernlogik der Altfragen-App für die Werkzeuge, Gegenstück zu web/kern.js.

Rein: Fragendaten (fragen-<fach>.json als Dictionary), Fortschritt, Text des Lernskripts.
Raus: Zustände, Ergebnisse, Sammlungen, zusammengeführte und abgeglichene Stände.
Regeln und Formate stehen in FORMAT.md, beide Seiten prüfen sich gegen tests/vektoren/.
Nur Standardbibliothek. Aufruf als Modul: import kern (Ordner werkzeug im Suchpfad).
Schreibweisen: [x for x in liste if bedingung] baut eine Liste, {..} ebenso eine Menge oder ein Dictionary,
(..) einen Durchlauf ohne Zwischenliste; lambda v: ausdruck ist eine Funktion in einer Zeile, meist als
Sortierschlüssel; next(durchlauf, None) liefert den ersten Treffer oder None.
"""
import copy
import math
import re
from datetime import UTC, date, datetime, timedelta, timezone

LEER = '#u0f0'
SCHUTZ_GELEERT = 5


# ---------- Text vergleichbar machen ----------

# Backslash vor einem ASCII-Satzzeichen, so wie Google Docs beim Speichern maskiert
_ESCAPE = re.compile(r'\\([!-/:-@\[-`{-~])')
# Gleiche Folge aus * und _ am Anfang und am Ende (Kursiv- und Fettdruck); \1 = dieselbe Folge wie vorn
_UMSCHLIESSEND = re.compile(r'^([*_]+)(.*?)\1\Z', re.DOTALL)


def normal(text):
    """Macht Docs-Fassung und Original vergleichbar, Groß- und Kleinschreibung bleibt."""
    s = '' if text is None else str(text)
    s = _ESCAPE.sub(r'\1', s).replace('\u00a0', ' ').strip()
    # Umschließende Sternchen und Unterstriche entfernen, bis sich nichts mehr ändert
    while True:
        neu = _UMSCHLIESSEND.sub(r'\2', s, count=1).strip()
        if neu == s:
            break
        s = neu
    return re.sub(r'\s+', ' ', s)


# Merkmal-Kästchen: Text ist "unsicher" oder "falsch", auch wenn Google Docs die nächste Zeile angehängt hat
# ("*unsicher* **Hinweis:** …"). Raus: 'unsicher', 'falsch' oder None
MERKMAL = re.compile(r'^([*_]+)(unsicher|falsch)\1(\s|$)')


def merkmal(roh):
    n = normal(roh)
    if n in ('unsicher', 'falsch'):
        return n
    m = MERKMAL.match(str(roh).strip())
    return m.group(2) if m else None


def schluessel(z):
    """Schlüssel eines Zustands: gewählte Optionen sortiert, dann unsicher und falsch. LEER = nichts angehakt."""
    wahl = sorted(normal(t) for t in (z.get('wahl') or []))
    return '|'.join(wahl) + '#u' + ('1' if z.get('unsicher') else '0') + 'f' + ('1' if z.get('falsch') else '0')


def zustand_aus(v):
    """Zustand (wahl, unsicher, falsch) aus einem Versuch."""
    return {'wahl': list(v.get('wahl') or []), 'unsicher': bool(v.get('unsicher')), 'falsch': bool(v.get('falsch'))}


def _leerer_zustand():
    return {'wahl': [], 'unsicher': False, 'falsch': False}


def teile(k):
    """Schlüssel zerlegen in Optionen, unsicher und falsch. Die letzten fünf Zeichen haben die Form '#u0f0'."""
    return {'wahl': k[:-5], 'unsicher': k[-3] == '1', 'falsch': k[-1] == '1'}


# ---------- Fragendaten erschließen ----------

def erschliessen(daten):
    """Nachschlagen nach Frage-ID und nach (Thema, Nummer im Lernskript), dazu die beantwortbaren Fragen."""
    fragen, nach_rang_nr, themen, beantwortbar = {}, {}, {}, []
    for t in daten['themen']:
        themen[t['rang']] = t
        for q in t['fragen']:
            fragen[q['id']] = {'frage': q, 'thema': t}
            nach_rang_nr[f"{t['rang']}#{q['nr']}"] = q
            if q['typ'] != 'fragment':
                beantwortbar.append(q)
    return {'daten': daten, 'fragen': fragen, 'nach_rang_nr': nach_rang_nr, 'themen': themen,
            'beantwortbar': beantwortbar}


def _ix(fragen):
    # Akzeptiert die Fragendaten selbst oder ein schon erschlossenes Verzeichnis
    return fragen if 'nach_rang_nr' in fragen else erschliessen(fragen)


# ---------- Lernskript lesen ----------

THEMA = re.compile(r'^## ([0-9]+) · ')
UEBERSCHRIFT = re.compile(r'^#{1,2} ')
FRAGE = re.compile(r'^\*\*Frage ([0-9]+)\*\*')
KASTEN = re.compile(r'^(\s*[-*+] \[)([ xX])(\] )(.*?)\s*$')


def _lesen(text, ix):
    """Zerlegt die .md zeilenweise in Zustände je Frage.

    Raus: zustaende {frageId: zustand}, orte {frageId: [Kästchen mit Zeilennummer und Rolle]},
    fehler (unbekannte Frage "<rang>#<nr>", unbekannte Option = Frage-ID), kaputt (Menge der unlesbaren Fragen).
    """
    zeilen = str(text).split('\n')
    zustaende, orte, fehler, kaputt = {}, {}, [], set()
    rang, akt = None, None
    for i, roh in enumerate(zeilen):
        z = roh.removesuffix('\r')
        # Themenkopf setzt das Thema; jede andere Überschrift erster oder zweiter Ebene beendet nur die Frage
        m = THEMA.match(z)
        if m:
            rang, akt = int(m.group(1)), None
            continue
        if UEBERSCHRIFT.match(z):
            akt = None
            continue
        # Fragekopf: Frage über (Thema, Nummer) nachschlagen, nie über die Position
        m = FRAGE.match(z)
        if m:
            akt = None
            if rang is None:
                continue
            q = ix['nach_rang_nr'].get(f'{rang}#{int(m.group(1))}')
            if q is None:
                fehler.append(f'{rang}#{int(m.group(1))}')
                continue
            if q['typ'] == 'fragment':
                continue
            akt = {'q': q, 'z': _leerer_zustand()}
            zustaende[q['id']] = akt['z']
            orte[q['id']] = []
            continue
        if akt is None:
            continue
        m = KASTEN.match(z)
        if not m:
            continue
        # Kästchen: Merkmal unsicher/falsch oder eine Option der Frage, verglichen über normal()
        an = m.group(2) != ' '
        inhalt = normal(m.group(4))
        qid = akt['q']['id']
        rolle = merkmal(m.group(4))
        if rolle:
            if an:
                akt['z'][rolle] = True
            orte[qid].append({'zeile': i, 'rolle': rolle})
            continue
        # Erste Option der Frage mit gleichem Text nach normal(), sonst None
        opt = next((o for o in akt['q']['optionen'] if normal(o['t']) == inhalt), None)
        if opt is None:
            if qid not in kaputt:
                fehler.append(qid)
            kaputt.add(qid)
            continue
        if an:
            akt['z']['wahl'].append(opt['t'])
        orte[qid].append({'zeile': i, 'rolle': 'option', 't': opt['t']})
    # Fragen mit unbekannter Option fallen ganz heraus, damit nichts falsch zugeordnet wird
    for qid in kaputt:
        zustaende.pop(qid, None)
        orte.pop(qid, None)
    return zustaende, orte, fehler, kaputt


def lernskript_lesen(text, fragen):
    """Zustand je Frage aus dem Lernskript. Raus: (zustaende {frageId: zustand}, fehler [..])."""
    zustaende, _, fehler, _ = _lesen(text, _ix(fragen))
    return zustaende, fehler


# ---------- Lernskript umschreiben ----------

_KASTEN_ANFANG = re.compile(r'^(\s*[-*+] \[)[ xX](\] )')


def lernskript_schreiben(text, orte, soll):
    """Setzt nur das Zeichen zwischen den eckigen Klammern; alle anderen Zeichen und Zeilenenden bleiben."""
    zeilen = str(text).split('\n')
    for qid, z in soll.items():
        # {.. for t in ..} = Menge der normalisierten Optionstexte, die angehakt sein sollen
        wahl = {normal(t) for t in z['wahl']}
        for o in orte.get(qid, []):
            an = normal(o['t']) in wahl if o['rolle'] == 'option' else bool(z.get(o['rolle']))
            # \g<1> und \g<2> = die beiden Klammerteile unverändert, dazwischen das neue Zeichen
            zeilen[o['zeile']] = _KASTEN_ANFANG.sub(r'\g<1>' + ('x' if an else ' ') + r'\g<2>', zeilen[o['zeile']],
                                                    count=1)
    return '\n'.join(zeilen)


# ---------- Ergebnis eines Versuchs ----------

def ergebnis(frage, versuch):
    """'richtig', 'falsch' oder None, wenn der Versuch nichts aussagt (leere Wahl, Bruchstück).

    Das Merkmal unsicher älterer Versuche zählt hier nicht, es ist beim Laden zum Stern geworden.
    """
    if frage['typ'] == 'fragment':
        return None
    if frage['typ'] == 'offen' or not frage['optionen']:
        return 'falsch' if versuch.get('falsch') else 'richtig'
    wahl = {normal(t) for t in (versuch.get('wahl') or [])}
    if not wahl:
        return None
    soll = {normal(o['t']) for o in frage['optionen'] if o['richtig']}
    return 'richtig' if wahl == soll else 'falsch'


# ---------- Zeit und Kalendertage in Berliner Zeit ----------

def zeitpunkt(s):
    """ISO-Zeit als Zeitpunkt in UTC, None bei fehlender oder unlesbarer Angabe. Ohne Zone gilt UTC."""
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC)


def _ms(s):
    # Millisekunden seit 1970 wie Date.parse in JS; fehlt die Zeit, zählt 0
    d = zeitpunkt(s)
    return d.timestamp() * 1000 if d else 0


def _letzter_sonntag(jahr, monat):
    # Letzter Sonntag im März oder Oktober (beide Monate haben 31 Tage); weekday(): Montag 0, Sonntag 6
    d = date(jahr, monat, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def berlin_versatz(d):
    """Abstand Berliner Zeit zu UTC für einen Zeitpunkt in UTC: Sommerzeit nach EU-Regel, Wechsel um 01:00 UTC."""
    beginn = datetime.combine(_letzter_sonntag(d.year, 3), datetime.min.time(), UTC) + timedelta(hours=1)
    ende = datetime.combine(_letzter_sonntag(d.year, 10), datetime.min.time(), UTC) + timedelta(hours=1)
    return timedelta(hours=2 if beginn <= d < ende else 1)


def tag_von(zeit):
    """Kalendertag in Europe/Berlin als 'JJJJ-MM-TT'."""
    d = zeitpunkt(zeit)
    return (d + berlin_versatz(d)).date().isoformat()


def jetzt_berlin():
    """Aktuelle Zeit in Berliner Zeit mit Versatz, sekundengenau, etwa 2026-11-08T21:30:00+01:00."""
    jetzt = datetime.now(UTC).replace(microsecond=0)
    versatz = berlin_versatz(jetzt)
    return (jetzt + versatz).replace(tzinfo=timezone(versatz)).isoformat()


def plus_tage(tag, n):
    """Kalendertag plus n Tage, beides als 'JJJJ-MM-TT'."""
    return (date.fromisoformat(tag) + timedelta(days=n)).isoformat()


def tage_zwischen(von, bis):
    """Anzahl Kalendertage von 'von' bis 'bis'."""
    return (date.fromisoformat(bis) - date.fromisoformat(von)).days


# ---------- Versuche ----------

def gueltige(versuche):
    """Nicht gelöschte Versuche nach Zeit; bei gleicher Zeit bleibt die Reihenfolge der Liste (sorted ist stabil)."""
    return sorted((v for v in (versuche or []) if not v.get('geloescht')), key=lambda v: _ms(v.get('zeit')))


def letzter_versuch(f, qid):
    vs = gueltige(f['versuche'].get(qid))
    return vs[-1] if vs else None


# ---------- Stern ----------

def stern_an(f, qid):
    """Hat die Frage einen Stern? Einträge {wert, zeit} in f['sterne']; wert False = ausgeschaltet."""
    s = (f.get('sterne') or {}).get(qid)
    return bool(s and s.get('wert'))


def stern_setzen(f, qid, wert, jetzt):
    f.setdefault('sterne', {})[qid] = {'wert': bool(wert), 'zeit': jetzt}


def ergebnisse(frage, versuche):
    """Versuche mit Ergebnis nach Zeit als [(versuch, ergebnis)]; zurückgenommene und solche ohne Aussage fallen weg."""
    vs = [(v, ergebnis(frage, v)) for v in gueltige(versuche)]
    return [(v, e) for v, e in vs if e]


def beantwortet(frage, versuche):
    """Mindestens ein Versuch mit Ergebnis (für Plan, Tempo, „Weiter mit Frage“)."""
    return bool(ergebnisse(frage, versuche))


def falsch_zahl(frage, versuche):
    """Wie oft eine Frage falsch beantwortet wurde, zurückgenommene Versuche ausgenommen."""
    return sum(1 for v in gueltige(versuche) if ergebnis(frage, v) == 'falsch')


def letztes_ergebnis(frage, versuche):
    """Ergebnis des letzten aussagekräftigen Versuchs oder None."""
    vs = ergebnisse(frage, versuche)
    return vs[-1][1] if vs else None


# ---------- Fortschritt ----------

def leerer_fortschritt(fach):
    return {'format': 1, 'fach': fach, 'versuche': {}, 'schritte': {}, 'sterne': {},
            'md': {'zeit': None, 'basis': {}, 'ueberschrieben': {}}}


def brauchbar(v):
    """Versuch mit ID als Text, lesbarer Zeit und Wahl als Liste; alles andere wird beim Laden verworfen."""
    return (isinstance(v, dict) and isinstance(v.get('id'), str) and zeitpunkt(v.get('zeit')) is not None
            and isinstance(v.get('wahl'), list))


def stern_brauchbar(s):
    """Stern-Eintrag mit wert True oder False und lesbarer Zeit; alles andere wird beim Laden verworfen."""
    return isinstance(s, dict) and isinstance(s.get('wert'), bool) and zeitpunkt(s.get('zeit')) is not None


def _sterne_ableiten(g):
    # Übernahme des alten Merkmals: Eine Frage ohne eigenen Stern-Eintrag, die einen nicht zurückgenommenen Versuch
    # mit unsicher hat, bekommt {wert: True, zeit, alt: True}. Jedes Mal neu aus den Versuchen abgeleitet, damit
    # ein veralteter Stand ihn nach dem Zusammenführen nicht festhält. Schlüssel sortiert wie in der App
    neu = {}
    for qid in sorted(set(g['sterne']) | set(g['versuche'])):
        s = g['sterne'].get(qid)
        if s and not s.get('alt'):
            neu[qid] = s
            continue
        alt = [v for v in gueltige(g['versuche'].get(qid)) if v.get('unsicher')]
        if alt:
            neu[qid] = {'wert': True, 'zeit': alt[-1]['zeit'], 'alt': True}
    g['sterne'] = neu
    return g


def vervollstaendigen(f, fach=None):
    """Fehlende Teile eines Fortschritts ergänzen, unbrauchbare Versuche und Sterne verwerfen.

    So legt eine beschädigte Datei die Auswertung nicht lahm. Vorhandene brauchbare Teile bleiben unverändert.
    Sterne aus dem alten Merkmal unsicher werden neu abgeleitet (_sterne_ableiten); ein Umschalten in der App oder
    in Docs schreibt einen eigenen Eintrag ohne alt, der von da an gilt.
    """
    leer = leerer_fortschritt(fach)
    g = {**leer, **(f or {})}
    # Je Frage nur die brauchbaren Versuche; ist der Eintrag keine Liste, bleibt eine leere
    g['versuche'] = {qid: [v for v in liste if brauchbar(v)] if isinstance(liste, list) else []
                     for qid, liste in (g.get('versuche') or {}).items()}
    g['schritte'] = dict(g.get('schritte') or {})
    sterne = g.get('sterne') if isinstance(g.get('sterne'), dict) else {}
    g['sterne'] = {qid: s for qid, s in sterne.items() if stern_brauchbar(s)}
    g['md'] = {**leer['md'], **(g.get('md') or {})}
    return _sterne_ableiten(g)


def _spaeter(a, b):
    return _ms(a) > _ms(b)


def zusammenfuehren(a, b):
    """Zwei Stände vereinigen.

    Versuche über ihre ID, bei gleicher ID gewinnt das spätere 'geaendert', bei Gleichstand der aus a.
    Trägt eine der Fassungen 'geloescht', bleibt der Versuch gelöscht, auch wenn die andere später geändert wurde.
    Schritte je Feld nach 'zeit', Sterne je Frage nach 'zeit' (bei gleicher Zeit gewinnt der gesetzte),
    md-Block als Ganzes.
    """
    fach = (a or {}).get('fach') or (b or {}).get('fach')
    a = vervollstaendigen(copy.deepcopy(a or {}), fach)
    b = vervollstaendigen(copy.deepcopy(b or {}), fach)
    aus = leerer_fortschritt(fach)
    # dict.fromkeys(a + b) = Vereinigung der Schlüssel in fester Reihenfolge
    for qid in dict.fromkeys(list(a['versuche']) + list(b['versuche'])):
        nach_id = {}
        for v in (a['versuche'].get(qid) or []) + (b['versuche'].get(qid) or []):
            da = nach_id.get(v['id'])
            if da is None:
                nach_id[v['id']] = v
                continue
            sieger = v if _spaeter(v.get('geaendert'), da.get('geaendert')) else da
            tod = da.get('geloescht') or v.get('geloescht')
            if tod and not sieger.get('geloescht'):
                # {**sieger, ...} = Kopie des Siegers mit gesetztem Löschzeitpunkt
                sieger = {**sieger, 'geloescht': tod}
            nach_id[v['id']] = sieger
        aus['versuche'][qid] = sorted(nach_id.values(), key=lambda v: _ms(v.get('zeit')))
    for rang in dict.fromkeys(list(a['schritte']) + list(b['schritte'])):
        sa, sb = a['schritte'].get(rang) or {}, b['schritte'].get(rang) or {}
        aus['schritte'][rang] = {}
        for feld in dict.fromkeys(list(sa) + list(sb)):
            x, y = sa.get(feld), sb.get(feld)
            aus['schritte'][rang][feld] = y if not x else x if not y else (y if _spaeter(y.get('zeit'), x.get('zeit')) else x)
    # Eigene Stern-Einträge nach Zeit, übernommene (alt) danach neu aus den vereinigten Versuchen
    for qid in dict.fromkeys(list(a['sterne']) + list(b['sterne'])):
        x, y = a['sterne'].get(qid), b['sterne'].get(qid)
        x = None if x and x.get('alt') else x
        y = None if y and y.get('alt') else y
        if not x or not y:
            if x or y:
                aus['sterne'][qid] = x or y
        elif _spaeter(y['zeit'], x['zeit']):
            aus['sterne'][qid] = y
        elif _spaeter(x['zeit'], y['zeit']):
            aus['sterne'][qid] = x
        else:
            aus['sterne'][qid] = x if x['wert'] else y
    aus['md'] = b['md'] if _spaeter(b['md'].get('zeit'), a['md'].get('zeit')) else a['md']
    return _sterne_ableiten(aus)


# ---------- Abgleich mit dem Lernskript ----------

def _gleiche_wahl(a, b):
    return sorted(normal(t) for t in (a or [])) == sorted(normal(t) for t in (b or []))


def _uebernehmen(f, q, m, kb, md_zeit, jetzt):
    # Änderung aus Docs übernehmen, getrennt nach Stern und Antwort, jeweils nur, was sich gegenüber basis geändert
    # hat. So löscht eine neue Antwort in Docs keinen Stern aus der App und umgekehrt.
    b = teile(kb)
    zeit = md_zeit or jetzt
    # Stern: Kästchen unsicher neu angehakt setzt ihn, Zeit = modifiedTime der .md; ist der Eintrag in der App jünger,
    # bleibt er. Abgehakt wird ignoriert wie jeder entfernte Haken: Eine veraltete Docs-Fassung soll keinen Stern
    # still löschen, entfernt wird er nur in der App
    if m['unsicher'] and not b['unsicher']:
        s = f['sterne'].get(q['id'])
        if not s or (not s['wert'] and not _spaeter(s['zeit'], zeit)):
            f['sterne'][q['id']] = {'wert': True, 'zeit': zeit}
    antwort = {'wahl': list(m['wahl']), 'unsicher': False, 'falsch': m['falsch']}
    if teile(schluessel(antwort))['wahl'] == b['wahl'] and m['falsch'] == b['falsch']:
        return
    # Frage mit Optionen ohne angehakte Option, offene Frage ohne falsch und ohne Versuch: Docs sagt nichts über eine
    # Antwort. a if b else c = a, wenn b gilt, sonst c
    ohne_antwort = not m['wahl'] if q['optionen'] else (not m['falsch'] and not letzter_versuch(f, q['id']))
    if ohne_antwort:
        return
    # Gleiche Wahl wie zuletzt: nur falsch anpassen. Sonst neuer Versuch; die ID aus Frage, Antwort und Zahl der
    # bisherigen Versuche ist auf jedem Gerät gleich, so legen zwei Geräte denselben Haken nicht doppelt an,
    # auch wenn sie die .md zu verschiedenen Zeiten lesen
    letzter = letzter_versuch(f, q['id'])
    if letzter and _gleiche_wahl(letzter.get('wahl'), m['wahl']):
        if bool(letzter.get('falsch')) != m['falsch']:
            letzter['falsch'] = m['falsch']
            letzter['geaendert'] = jetzt
        return
    liste = f['versuche'].setdefault(q['id'], [])
    vid = f"docs:{q['id']}:{schluessel(antwort)}:{len(gueltige(liste))}"
    if any(v.get('id') == vid for v in liste):
        return
    liste.append({'id': vid, 'zeit': zeit, **antwort, 'quelle': 'docs', 'geaendert': jetzt, 'geloescht': None})


def soll_zustand(f, qid):
    """Zustand der App, wie er in der .md stehen soll: Optionen und falsch aus dem letzten Versuch, unsicher = Stern."""
    letzter = letzter_versuch(f, qid)
    return {'wahl': list(letzter.get('wahl') or []) if letzter else [], 'unsicher': stern_an(f, qid),
            'falsch': bool(letzter and letzter.get('falsch'))}


def abgleichen(fortschritt, md_text, md_zeit, fragen, jetzt):
    """Drei-Wege-Abgleich je Frage zwischen basis (letzter gemeinsamer Stand), .md und App (soll_zustand).

    Rein: Fortschritt (schon mit Drive zusammengeführt), md-Text, modifiedTime der .md, Fragendaten, jetzt (ISO).
    Raus: {fortschritt, md_neu (neuer Text oder None), geaendert [ids], fehler, abbruch (Text oder None), md_alt}.
    Bei Abbruch bleibt der alte md-Block stehen und die .md unverändert. Der Eingang wird nicht verändert.
    """
    ix = _ix(fragen)
    f = vervollstaendigen(copy.deepcopy(fortschritt), ix['daten'].get('fach'))
    md_alt = copy.deepcopy(f['md'])
    zustaende, orte, fehler, kaputt = _lesen(md_text, ix)
    basis = f['md'].get('basis') or {}
    ueb = f['md'].get('ueberschrieben') or {}
    neue_basis, neue_ueb = {}, copy.deepcopy(ueb)
    soll, geaendert, geleert = {}, [], []
    for q in ix['beantwortbar']:
        qid = q['id']
        # Unlesbar oder nicht im Lernskript: nichts übernehmen, nichts schreiben, basis bleibt
        if qid in kaputt or qid not in zustaende:
            if basis.get(qid):
                neue_basis[qid] = basis[qid]
            continue
        m = zustaende[qid]
        km, kb = schluessel(m), basis.get(qid) or LEER
        # Merkmal angehakt, aber keine Option, obwohl im letzten gemeinsamen Stand eine angehakt war: Docs ist mitten
        # in einer Antwort, abwarten. Sonst ist ein angehaktes unsicher allein der Stern
        if q['optionen'] and not m['wahl'] and (m['falsch'] or (m['unsicher'] and teile(kb)['wahl'] != '')):
            if basis.get(qid):
                neue_basis[qid] = basis[qid]
            continue
        # Neu in Docs angehakt und keine alte, von der App überschriebene Fassung: übernehmen
        if km != kb and km != LEER and km not in (ueb.get(qid) or []):
            _uebernehmen(f, q, m, kb, md_zeit, jetzt)
        # Weicht die .md vom Soll ab, wird sie umgeschrieben und ihr Stand als überschrieben gemerkt
        s = soll_zustand(f, qid)
        ks = schluessel(s)
        if ks != km:
            geaendert.append(qid)
            soll[qid] = s
            # [km] + alte ohne km, höchstens drei
            neue_ueb[qid] = ([km] + [k for k in (neue_ueb.get(qid) or []) if k != km])[:3]
            # Haken entfernt, die die App gar nicht kennt: kein Versuch, auch kein Grabstein, und dabei geht eine
            # Antwort aus der .md verloren oder die Frage wird ganz geleert, ohne dass es einen Stern-Eintrag gibt
            in_md = teile(km)
            unbekannt = not f['versuche'].get(qid)
            if unbekannt and (in_md['wahl'] != '' or in_md['falsch'] or (ks == LEER and qid not in f['sterne'])):
                geleert.append(q)
        if ks != LEER:
            neue_basis[qid] = ks
    # Schutz: Würden zu viele unbekannte Antworten geleert, ist eher der Fortschritt verloren als die Haken falsch.
    # Die Meldung nennt bis zu acht Fragen als Thema.Nr
    if len(geleert) > SCHUTZ_GELEERT:
        f['md'] = md_alt
        liste = ', '.join(f"{ix['fragen'][q['id']]['thema']['rang']}.{q['nr']}" for q in geleert[:8])
        rest = ' …' if len(geleert) > 8 else ''
        return {'fortschritt': f, 'md_neu': None, 'geaendert': [], 'fehler': fehler,
                'abbruch': f'Abgleich angehalten: {len(geleert)} Fragen würden in der .md geleert ({liste}{rest})',
                'md_alt': md_alt}
    f['md'] = {'zeit': jetzt, 'basis': neue_basis, 'ueberschrieben': neue_ueb}
    # Neuer Text nur, wenn er sich vom gelesenen unterscheidet
    neu = lernskript_schreiben(md_text, orte, soll) if geaendert else md_text
    return {'fortschritt': f, 'md_neu': neu if neu != md_text else None, 'geaendert': geaendert, 'fehler': fehler,
            'abbruch': None, 'md_alt': md_alt}


# ---------- Plan ----------

def plan_liste(daten):
    """Reihenfolge der Themen als [(thema, optional)]: nach Rang, oder Blöcke mit Stufe A, dann B, C am Ende optional."""
    themen = list(daten['themen'])
    if daten.get('plan') != 'block-stufe':
        return [(t, False) for t in sorted(themen, key=lambda t: t['rang'])]
    bloecke = [b['nr'] for b in daten.get('bloecke') or []]

    def im_block(nr):
        return sorted((t for t in themen if t['block'] == nr), key=lambda t: t['rang'])

    liste = []
    for nr in bloecke:
        im = im_block(nr)
        liste += [(t, False) for t in im if t['stufe'] == 'A']
        liste += [(t, False) for t in im if t['stufe'] not in ('A', 'C')]
    for nr in bloecke:
        liste += [(t, True) for t in im_block(nr) if t['stufe'] == 'C']
    drin = {t['rang'] for t, _ in liste}
    liste += [(t, False) for t in themen if t['rang'] not in drin]
    return liste


def tempo(daten, f, heute):
    """Erster Durchgang: offene Pflichtfragen bis zum Zieldatum des Fachs (durchgang), ohne eigenes Ziel bis
    sieben Tage vor der Klausur, daraus Fragen pro Tag."""
    ziel = daten.get('durchgang') or plus_tage(daten['klausur'], -7)
    tage = max(1, tage_zwischen(heute, ziel) + 1)
    # Zählt je Pflichtthema die Fragen ohne Bruchstücke, die noch nicht beantwortet sind
    offen = sum(1 for t, optional in plan_liste(daten) if not optional for q in t['fragen']
                if q['typ'] != 'fragment' and not beantwortet(q, f['versuche'].get(q['id'])))
    return {'ziel': ziel, 'tage': tage, 'offen': offen, 'pro_tag': math.ceil(offen / tage),
            'bis_klausur': tage_zwischen(heute, daten['klausur'])}


def _sammel_eintrag(q, t, f, pos):
    # Je Frage: Zahl der falschen Versuche, ob der letzte falsch war, Zeit des letzten Versuchs (None = nie geübt)
    # und Position des Themas im Plan. Zurückgenommene Versuche zählen nicht
    vs = ergebnisse(q, f['versuche'].get(q['id']))
    return {'frage': q, 'thema': t, 'falsch': sum(1 for _, e in vs if e == 'falsch'),
            'zuletzt_falsch': bool(vs) and vs[-1][1] == 'falsch', 'zuletzt': vs[-1][0]['zeit'] if vs else None,
            'pos': pos}


def _nach_uebung(x):
    # Sortierschlüssel: nie geübte zuerst (-inf), dann am längsten nicht geübte, bei Gleichstand nach Plan
    return (_ms(x['zuletzt']) if x['zuletzt'] else float('-inf'), x['pos'])


def falsch_sammlung(daten, f):
    """Jede Frage, die je falsch beantwortet wurde, auch wenn sie inzwischen sitzt.

    Zuerst die, deren letzte Antwort falsch war, darin und danach am längsten nicht geübte zuerst, dann nach Plan.
    Raus: [{'frage', 'thema', 'falsch': Anzahl, 'zuletzt_falsch', 'zuletzt': Zeit des letzten Versuchs, 'pos'}]
    """
    aus = []
    for pos, (t, _) in enumerate(plan_liste(daten)):
        for q in t['fragen']:
            if q['typ'] == 'fragment':
                continue
            x = _sammel_eintrag(q, t, f, pos)
            if x['falsch']:
                aus.append(x)
    # (not zuletzt_falsch, ...) sortiert die zuletzt falschen (False) vor die übrigen (True)
    return sorted(aus, key=lambda x: (not x['zuletzt_falsch'], *_nach_uebung(x)))


def markiert_sammlung(daten, f):
    """Genau die Fragen mit Stern, am längsten nicht geübte zuerst. Gleiche Felder wie falsch_sammlung."""
    aus = [_sammel_eintrag(q, t, f, pos) for pos, (t, _) in enumerate(plan_liste(daten)) for q in t['fragen']
           if stern_an(f, q['id'])]
    return sorted(aus, key=_nach_uebung)
