"""Ersetzt den Inhalt eines App-Lernskripts auf Drive durch eine neu gesetzte Fassung und nimmt jedes Kästchen mit.

Antwort-Haken, Stern (Kästchen unsicher) und Kästchen falsch hängen an der Frage-ID, nie an der Position. Das alte
Lernskript wird mit den Fragendaten gelesen, die die App gerade kennt (fragen-<fach>.json auf Drive), das neue mit
der frisch gebauten Datei build/fragen-<fach>.json. Die Datei-ID auf Drive bleibt, die App behält den Zugriff.

Reihenfolge: 1. neu setzen (render) 2. python werkzeug/bauen.py <fach> --lernskript <neu.md> 3. dieses Werkzeug
4. python werkzeug/veroeffentlichen.py fragen <fach>. Erst danach die Fragen hochladen, denn das alte Lernskript
wird gegen die Fragen gelesen, die noch auf Drive liegen. Bestehende Fragen behalten Thema und Nummer, neue kommen
hinten dazu; so liest die App in der Zeit zwischen 3 und 4 jede Frage richtig und überspringt nur die neuen.

Rein: Fach, neu gesetztes Lernskript (ohne Haken), Sicherungsordner, die zuletzt hochgeladene Fassung (--vorher,
ohne Angabe build/lernskript-<fach>-hochgeladen.md, die dieses Werkzeug nach jedem Hochladen ablegt).
Raus: Sicherung des alten Lernskripts im Sicherungsordner, das neue mit allen Kästchen auf Drive.
Abbruch ohne Hochladen, wenn
- eines der beiden Lernskripte nicht Frage für Frage zu seinen Fragendaten passt (Stamm, Optionen, Lösung),
- eine Frage-ID in alten und neuen Fragendaten etwas anderes meint (Stamm, Optionen, Thema oder Nummer), außer sie
  ist mit --geaendert angegeben und trägt weder Kästchen im Lernskript noch Versuche oder Stern in der App,
- ein Kästchen keiner Frage oder Option zugeordnet werden kann oder eine Frage mit Haken im neuen fehlt,
- das alte Lernskript Wörter oder Zeichen enthält, die in der zuletzt hochgeladenen Fassung fehlen (Notizen in Docs),
- sich die Datei auf Drive während des Laufs ändert.

Aufruf: python werkzeug/lernskript_ersetzen.py <fach> <neu.md> <sicherungsordner> [--vorher <datei.md>]
        [--geaendert <ID,ID>] [--probe]
  --geaendert  Frage-IDs, deren Stamm oder Optionen gewollt geändert sind (etwa ein ergänzter Aussagenpool).
               Geprüft wird der Fortschritt auf Drive: vorher jedes Gerät mit der App abgleichen und die App bis
               nach veroeffentlichen.py nicht benutzen, sonst bringt ein Gerät alte Versuche zu der ID mit
  --probe      alles prüfen, das Ergebnis in den Sicherungsordner schreiben, nichts hochladen
Vorher offene Docs-Tabs dieses Lernskripts schließen: Ein offener Tab kann seine alte Fassung zurückspeichern.
Schreibweisen: Counter zählt, wie oft jedes Wort vorkommt; a - b bei zwei Countern lässt nur den Überschuss von a.
"""
import datetime
import hashlib
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bauen
import kern
from faecher import BUILD, FAECHER

# Kästchen am Zeilenanfang, angehakt oder nicht; für den Wortvergleich wird es entfernt
_KASTEN = re.compile(r'^\s*[-*+] \[[ xX]\] ')
# Trennzeile einer Tabelle (|---|, bei Docs |:----|); enthält keine Wörter, Docs schreibt sie anders
_TABELLENTRENNER = re.compile(r'^\|[\s:|-]+\|$')
# Wort = Folge aus Buchstaben und Ziffern ([^\W_] schließt den Unterstrich aus, den \w sonst mitnimmt),
# dazu jedes einzelne Zeichen außerhalb von ASCII, das weder Buchstabe noch Leerraum ist (⭐, ❗, →)
_WORT = re.compile(r'[^\W_]+|[^\x00-\x7f\w\s]')


class Fehler(Exception):
    """Erwarteter Abbruch mit Meldung für die Konsole."""


def woerter(text):
    """Wörter und Sonderzeichen eines Lernskripts ohne Kästchen, Markdown-Zeichen und Docs-Maskierung, gezählt."""
    zaehler = Counter()
    for zeile in str(text).split('\n'):
        zeile = zeile.rstrip('\r')
        if _TABELLENTRENNER.match(zeile.strip()):
            continue
        zaehler.update(_WORT.findall(kern.normal(_KASTEN.sub('', zeile))))
    return zaehler


def notizen(alt_text, vorher_text):
    """Was das alte Lernskript häufiger enthält als die zuletzt hochgeladene Fassung. Raus: sortierte Liste."""
    return sorted((woerter(alt_text) - woerter(vorher_text)).elements())


def kennung(rang, q):
    # Was eine Frage ausmacht: Thema, Nummer, Stamm und Menge der Optionstexte, verglichen über normal()
    return rang, q['nr'], kern.normal(q['stamm']), frozenset(kern.normal(o['t']) for o in q['optionen'])


def andere_fragen(alt_daten, neu_daten):
    """Frage-IDs, die es in beiden Fassungen gibt, aber mit anderem Inhalt oder an anderer Stelle."""
    def je_id(daten):
        # {Frage-ID: Kennung} über alle Themen
        return {q['id']: kennung(t['rang'], q) for t in daten['themen'] for q in t['fragen']}
    alt, neu = je_id(alt_daten), je_id(neu_daten)
    return sorted(i for i in alt.keys() & neu.keys() if alt[i] != neu[i])


def fortschritt_belegt(fortschritt, ids):
    """Frage-IDs aus ids, zu denen die App etwas gespeichert hat: Versuche, Stern oder einen Lernskript-Stand
    (md.basis, md.ueberschrieben). Raus: sortierte Liste."""
    fortschritt = fortschritt or {}
    md = fortschritt.get('md') or {}
    orte = [fortschritt.get('sterne') or {}, md.get('basis') or {}, md.get('ueberschrieben') or {}]
    return sorted(i for i in ids if (fortschritt.get('versuche') or {}).get(i) or any(i in o for o in orte))


def uebertragen(alt_text, alt_daten, neu_text, neu_daten, geaendert=()):
    """Kästchen des alten Lernskripts in das neue übernehmen, Frage für Frage über die ID.

    geaendert: Frage-IDs, die im Neubau gewollt etwas anderes meinen dürfen, solange sie keine Kästchen tragen.
    Raus: (neuer Text, {'fragen': Zahl übernommener Zustände, 'haken': Zahl angehakter Kästchen,
    'neu': IDs, die nur im neuen Lernskript stehen}). Unlösbares löst Fehler aus, nichts wird geraten.
    """
    # Beide Lernskripte müssen Frage für Frage zu ihren Daten passen, sonst zeigt eine Nummer auf die falsche Frage
    for name, daten, text in (('Altes', alt_daten, alt_text), ('Neues', neu_daten, neu_text)):
        abw = bauen.lernskript_pruefen(daten, text)
        if abw:
            raise Fehler(f'{name} Lernskript passt nicht zu seinen Fragendaten ({len(abw)}): ' + ' | '.join(abw[:5]))
    anders = andere_fragen(alt_daten, neu_daten)
    # Eine angegebene ID, die gar nicht abweicht, ist ein Tippfehler oder eine veraltete Angabe
    unnoetig = sorted(set(geaendert) - set(anders))
    if unnoetig:
        raise Fehler('Mit --geaendert angegeben, aber in beiden Fassungen gleich oder unbekannt: ' + ', '.join(unnoetig))
    # Thema und Nummer bleiben auch bei geänderten Fragen: Die App liest die neue Fassung bis zum Hochladen der
    # Fragen über (Thema, Nummer) mit den alten Fragendaten
    def stelle(daten):
        # {Frage-ID: (Rang, Nummer)}
        return {q['id']: (t['rang'], q['nr']) for t in daten['themen'] for q in t['fragen']}
    alt_stelle, neu_stelle = stelle(alt_daten), stelle(neu_daten)
    verschoben = sorted(i for i in geaendert if alt_stelle[i] != neu_stelle[i])
    if verschoben:
        raise Fehler('Geänderte Fragen haben ein anderes Thema oder eine andere Nummer: ' + ', '.join(verschoben))
    anders = [i for i in anders if i not in geaendert]
    if anders:
        raise Fehler(f'{len(anders)} Frage-IDs meinen im Neubau eine andere Frage oder Stelle: ' + ', '.join(anders[:20]))

    alt_ix, neu_ix = kern.erschliessen(alt_daten), kern.erschliessen(neu_daten)
    alt_z, _, alt_fehler, _ = kern._lesen(alt_text, alt_ix)
    if alt_fehler:
        raise Fehler(f'Altes Lernskript: {len(alt_fehler)} Fragen nicht lesbar, ihre Haken gingen verloren: '
                     + ', '.join(alt_fehler[:20]))
    neu_z, neu_orte, neu_fehler, _ = kern._lesen(neu_text, neu_ix)
    if neu_fehler:
        raise Fehler(f'Neues Lernskript passt nicht zu den Fragendaten: {", ".join(neu_fehler[:20])}')
    if any(z['wahl'] or z['unsicher'] or z['falsch'] for z in neu_z.values()):
        raise Fehler('Das neue Lernskript enthält schon Haken, erwartet ist eine frisch gesetzte Fassung')

    # Jede Frage mit Kästchen-Inhalt muss im neuen Lernskript wieder vorkommen
    mit_inhalt = {qid: z for qid, z in alt_z.items() if z['wahl'] or z['unsicher'] or z['falsch']}
    # Ein Kästchen einer geänderten Frage gehörte zur alten Fassung und landete sonst bei der neuen
    belegt = sorted(qid for qid in geaendert if qid in mit_inhalt)
    if belegt:
        raise Fehler('Geänderte Fragen tragen Kästchen im alten Lernskript: ' + ', '.join(belegt))
    fehlend = sorted(qid for qid in mit_inhalt if qid not in neu_orte)
    if fehlend:
        raise Fehler(f'{len(fehlend)} Fragen mit Haken fehlen im neuen Lernskript: {", ".join(fehlend[:20])}')

    text = kern.lernskript_schreiben(neu_text, neu_orte, mit_inhalt)

    # Gegenprobe: das Ergebnis neu lesen, jeder Zustand muss über den Schlüssel gleich sein, auch die leeren
    # (neue Fragen und Fragen ohne Haken stehen nur auf einer Seite und gelten dort als LEER)
    kontrolle, _, k_fehler, _ = kern._lesen(text, neu_ix)
    abw = sorted(qid for qid in set(alt_z) | set(kontrolle)
                 if kern.schluessel(alt_z.get(qid, {})) != kern.schluessel(kontrolle.get(qid, {})))
    if k_fehler or abw:
        raise Fehler(f'Gegenprobe weicht ab bei {", ".join((k_fehler + abw)[:20])}')
    haken = sum(len(z['wahl']) + z['unsicher'] + z['falsch'] for z in mit_inhalt.values())
    neu_ids = sorted(set(neu_ix['fragen']) - set(alt_ix['fragen']))
    return text, {'fragen': len(mit_inhalt), 'haken': haken, 'neu': neu_ids}


def lesen(pfad):
    # Text unverändert lesen; newline='' lässt die Zeilenenden, wie sie sind
    with open(pfad, encoding='utf-8', newline='') as d:
        return d.read()


def drive_stand(vo, datei_id):
    """Änderungszeit und Prüfsumme der Datei auf Drive."""
    return vo.anfrage('GET', f'{vo.API}/files/{datei_id}?fields=modifiedTime,md5Checksum')


def main(argv):
    args = argv[1:]
    probe = '--probe' in args
    args = [a for a in args if a != '--probe']
    vorher = ''
    if '--vorher' in args:
        i = args.index('--vorher')
        vorher = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    geaendert = ()
    if '--geaendert' in args:
        i = args.index('--geaendert')
        # Liste mit Kommas, Leerstellen um die IDs fallen weg; fehlt der Wert, gilt der Aufruf als falsch
        geaendert = tuple(x.strip() for x in args[i + 1].split(',') if x.strip()) if i + 1 < len(args) else None
        del args[i:i + 2]
    if len(args) != 3 or args[0] not in FAECHER or vorher is None or geaendert is None:
        print(__doc__)
        return 2
    fach, neu_pfad, sicherung = args
    vorher = vorher or f'{BUILD}/lernskript-{fach}-hochgeladen.md'
    if not os.path.exists(vorher):
        print(f'Zuletzt hochgeladene Fassung fehlt: {vorher}. Mit --vorher angeben.', file=sys.stderr)
        return 2
    # Drive-Zugang erst hier laden, damit die Funktionen oben ohne Zugang testbar bleiben
    import veroeffentlichen as vo

    try:
        datei = vo.einzeln(vo.finden('lernskript', fach), f'Lernskript {fach}')
        fragen = vo.einzeln(vo.finden('fragen', fach), f'Fragen {fach}')
        if not datei or not fragen:
            raise Fehler(f'{fach}: Lernskript oder Fragendatei fehlt auf Drive')
        stand = drive_stand(vo, datei['id'])
        alt_text = vo.anfrage('GET', f'{vo.API}/files/{datei["id"]}?alt=media').decode('utf-8')
        roh = vo.anfrage('GET', f'{vo.API}/files/{fragen["id"]}?alt=media')
        # Drive liefert JSON-Dateien schon als dict, sonst Bytes
        alt_daten = roh if isinstance(roh, dict) else json.loads(roh)
        with open(f'{BUILD}/fragen-{fach}.json', encoding='utf-8') as d:
            neu_daten = json.load(d)
        neu_text = lesen(neu_pfad)
        if geaendert:
            # Versuche und Sterne der App hängen ebenfalls an der ID und gehörten zur alten Frage
            fo = vo.einzeln(vo.finden('fortschritt', fach), f'Fortschritt {fach}')
            fo_roh = vo.anfrage('GET', f'{vo.API}/files/{fo["id"]}?alt=media') if fo else {}
            fo_daten = fo_roh if isinstance(fo_roh, dict) else json.loads(fo_roh)
            beantwortet = fortschritt_belegt(fo_daten, geaendert)
            if beantwortet:
                raise Fehler('Geänderte Fragen haben in der App Versuche, Stern oder Lernskript-Stand: '
                             + ', '.join(beantwortet))

        # Sicherung zuerst, eigener Dateiname mit Zeitstempel, wird danach nicht mehr angefasst
        os.makedirs(sicherung, exist_ok=True)
        zeit = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
        with open(os.path.join(sicherung, f'Lernskript {fach} vor Ersetzen {zeit}.md'), 'w', encoding='utf-8',
                  newline='') as d:
            d.write(alt_text)

        fremd = notizen(alt_text, lesen(vorher))
        if fremd:
            raise Fehler(f'{len(fremd)} Wörter stehen nur im Lernskript auf Drive (eigene Notizen?): '
                         + ' '.join(fremd[:40]))
        text, bericht = uebertragen(alt_text, alt_daten, neu_text, neu_daten, geaendert)
        inhalt = text.encode('utf-8')

        if probe:
            ziel = os.path.join(sicherung, f'Lernskript {fach} neu {zeit}.md')
            with open(ziel, 'wb') as d:
                d.write(inhalt)
            print(f'Probe, nichts hochgeladen: {ziel}')
        else:
            # Hat jemand die Datei seit dem Herunterladen geändert (Docs, App), wäre ein Haken verloren
            if drive_stand(vo, datei['id']) != stand:
                raise Fehler('Lernskript auf Drive hat sich während des Laufs geändert, neu starten')
            neu = vo.ersetzen(datei['id'], inhalt, 'text/markdown')
            if neu.get('md5Checksum') != hashlib.md5(inhalt).hexdigest():
                raise Fehler(f'Prüfsumme nach dem Hochladen weicht ab, Datei {datei["id"]} prüfen')
            # Neue Fassung ohne Haken als Maßstab für die Notizsuche beim nächsten Lauf
            with open(f'{BUILD}/lernskript-{fach}-hochgeladen.md', 'w', encoding='utf-8', newline='') as d:
                d.write(neu_text)
            print(f'{fach}: Lernskript ersetzt, {len(inhalt)} Bytes, Prüfsumme gleich. '
                  f'Jetzt veroeffentlichen.py fragen {fach}')
        print(f'Übernommen: {bericht["fragen"]} Fragen mit {bericht["haken"]} angehakten Kästchen. '
              f'Neu ohne Haken: {len(bericht["neu"])} Fragen {" ".join(bericht["neu"][:30])}')
        return 0
    except (Fehler, vo.Fehler) as e:
        print('Fehler:', e, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
