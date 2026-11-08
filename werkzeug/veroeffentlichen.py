"""Legt die Dateien der Altfragen-App auf Drive an und hält sie aktuell, über den Zugang JARVIS (drive.file).

Die App sieht nur Dateien, die JARVIS angelegt hat. Deshalb entstehen alle App-Dateien hier, nie über Drive for Desktop.
Erkannt werden sie an appProperties (altfragenApp = Rolle, fach = Kürzel), nicht am Namen.

Aufruf:
  python veroeffentlichen.py fragen mibi innere     build/fragen-<fach>.json hochladen, Fortschritt leer anlegen falls neu, Konfiguration schreiben.
                                                    Bricht ab, wenn eine Frage-ID neuen Inhalt hätte (--erzwingen übergeht das)
  python veroeffentlichen.py lernskript <fach> <datei.md> <ordner-id>
                                                    Lernskript als neue JARVIS-Datei in den Ordner legen (einmalig je Fach)
  python veroeffentlichen.py liste                  alle App-Dateien mit ID und Änderungszeit

Erwartet: Zugang JARVIS wie im Skill aufgaben (~/.config/jarvis). Raus: Text auf der Konsole, bei Fehler Code 1.
"""

import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = REPO / "build"
API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3"
# Ordner "01 Studium/Organisation" auf Drive; darin entsteht der App-Ordner
ORGANISATION = "1CyEGvc5L0Y5QJOWtN4rSdZIVZmqL6HQM"
ORDNER_NAME = "Altfragen-App"
FAECHER = {"mibi": "MiBi Teil 1", "innere": "Innere Teil 1"}

# Zugang aus dem Skill aufgaben übernehmen: dieselbe Client-Datei, derselbe erneuerbare Schlüssel
sys.path.insert(0, str(Path(r"G:/Meine Ablage/2nd Brain/.claude/skills/aufgaben/skripte")))
import aufgaben


class Fehler(Exception):
    """Erwarteter Fehler mit Meldung für die Konsole."""


def anfrage(methode: str, url: str, daten: bytes | None = None, art: str | None = None) -> dict | bytes:
    """Eine Anfrage an Drive mit dem JARVIS-Schlüssel. JSON-Antworten kommen als dict, sonst als Bytes."""
    kopf = {"Authorization": "Bearer " + aufgaben.zugriffsschluessel()}
    if art:
        kopf["Content-Type"] = art
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=daten, method=methode, headers=kopf)) as antwort:
            inhalt = antwort.read()
            if "json" in antwort.headers.get("Content-Type", ""):
                return json.loads(inhalt) if inhalt else {}
            return inhalt
    except urllib.error.HTTPError as e:
        raise Fehler(f"Drive {e.code}: {e.read().decode('utf-8', 'replace')[:400]}") from e


def finden(rolle: str, fach: str | None = None) -> list[dict]:
    """App-Dateien mit dieser Rolle (und diesem Fach), die nicht im Papierkorb liegen."""
    q = f"appProperties has {{ key='altfragenApp' and value='{rolle}' }} and trashed = false"
    if fach:
        q += f" and appProperties has {{ key='fach' and value='{fach}' }}"
    felder = "files(id,name,modifiedTime,md5Checksum,parents,appProperties)"
    url = f"{API}/files?spaces=drive&pageSize=100&fields={felder}&q={urllib.parse.quote(q)}"
    return anfrage("GET", url).get("files", [])


def anlegen(name: str, inhalt: bytes, mime: str, eltern: list[str], eigenschaften: dict) -> dict:
    """Neue Datei mit Metadaten und Inhalt in einem Schritt (multipart). Raus: id, name, modifiedTime."""
    grenze = uuid.uuid4().hex
    meta = {"name": name, "mimeType": mime, "parents": eltern, "appProperties": eigenschaften}
    koerper = (
        f"--{grenze}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n"
        f"--{grenze}\r\nContent-Type: {mime}\r\n\r\n"
    ).encode() + inhalt + f"\r\n--{grenze}--\r\n".encode()
    url = f"{UPLOAD}/files?uploadType=multipart&fields=id,name,modifiedTime,md5Checksum"
    return anfrage("POST", url, koerper, f"multipart/related; boundary={grenze}")


def ersetzen(datei_id: str, inhalt: bytes, mime: str) -> dict:
    """Inhalt einer bestehenden Datei ersetzen; die ID bleibt, die App behält den Zugriff."""
    url = f"{UPLOAD}/files/{datei_id}?uploadType=media&fields=id,name,modifiedTime,md5Checksum"
    return anfrage("PATCH", url, inhalt, mime)


def einzeln(liste: list[dict], was: str) -> dict | None:
    """Höchstens eine Datei je Rolle und Fach; mehrere sind ein Fehler, den jemand von Hand lösen muss."""
    if len(liste) > 1:
        raise Fehler(f"{was}: {len(liste)} Dateien gefunden, erwartet eine: " + ", ".join(d["id"] for d in liste))
    return liste[0] if liste else None


def app_ordner() -> str:
    """ID des App-Ordners, beim ersten Mal anlegen."""
    da = einzeln(finden("ordner"), "Ordner")
    if da:
        return da["id"]
    meta = {"name": ORDNER_NAME, "mimeType": "application/vnd.google-apps.folder", "parents": [ORGANISATION],
            "appProperties": {"altfragenApp": "ordner"}}
    neu = anfrage("POST", f"{API}/files?fields=id", json.dumps(meta).encode("utf-8"), "application/json")
    print("Ordner angelegt:", neu["id"])
    return neu["id"]


def kennung(frage: dict) -> tuple:
    """Was eine Frage ausmacht: Stamm und Menge der Optionstexte, ohne Leerraum-Unterschiede."""
    def rein(t):
        return " ".join(str(t or "").split())
    return rein(frage.get("stamm")), frozenset(rein(o["t"]) for o in frage.get("optionen") or [])


def ids_pruefen(alt: dict, neu: dict) -> list[str]:
    """Frage-IDs, die es in beiden Fassungen gibt, aber mit anderem Inhalt. Der Lernstand hängt an der ID,
    eine verschobene ID würde Antworten einer anderen Frage zuordnen."""
    # {id: Frage} je Fassung, über alle Themen
    alte = {q["id"]: q for t in alt.get("themen", []) for q in t["fragen"]}
    neue = {q["id"]: q for t in neu.get("themen", []) for q in t["fragen"]}
    return sorted(i for i in alte.keys() & neue.keys() if kennung(alte[i]) != kennung(neue[i]))


def fragen_veroeffentlichen(faecher: list[str], erzwingen: bool = False) -> None:
    """Fragen hochladen, leeren Fortschritt nur anlegen, wenn es noch keinen gibt, dann die Konfiguration.
    Hat eine bestehende Frage-ID neuen Inhalt, bricht es ab, außer mit --erzwingen."""
    ordner = app_ordner()
    for fach in faecher:
        quelle = BUILD / f"fragen-{fach}.json"
        if not quelle.exists():
            raise Fehler(f"{quelle} fehlt, zuerst bauen.py {fach}")
        inhalt = quelle.read_bytes()
        neu = json.loads(inhalt)
        da = einzeln(finden("fragen", fach), f"Fragen {fach}")
        if da and da.get("md5Checksum") != hashlib.md5(inhalt).hexdigest():
            # Drive liefert JSON-Dateien schon als dict, andere Inhalte als Bytes
            roh = anfrage("GET", f"{API}/files/{da['id']}?alt=media")
            alt = roh if isinstance(roh, dict) else json.loads(roh)
            anders = ids_pruefen(alt, neu)
            if anders and not erzwingen:
                raise Fehler(f"{fach}: {len(anders)} Frage-IDs mit anderem Inhalt, der Lernstand würde verrutschen: "
                             + ", ".join(anders[:20]) + (" …" if len(anders) > 20 else ""))
        if da and da.get("md5Checksum") == hashlib.md5(inhalt).hexdigest():
            print(f"{fach}: Fragen unverändert")
        elif da:
            ersetzen(da["id"], inhalt, "application/json")
            print(f"{fach}: Fragen ersetzt ({len(inhalt) // 1024} KB)")
        else:
            anlegen(f"fragen-{fach}.json", inhalt, "application/json", [ordner], {"altfragenApp": "fragen", "fach": fach})
            print(f"{fach}: Fragen angelegt ({len(inhalt) // 1024} KB)")
        if not finden("fortschritt", fach):
            leer = {"format": 1, "fach": fach, "versuche": {}, "schritte": {},
                    "md": {"zeit": None, "basis": {}, "ueberschrieben": {}}}
            anlegen(f"fortschritt-{fach}.json", json.dumps(leer).encode("utf-8"), "application/json", [ordner],
                    {"altfragenApp": "fortschritt", "fach": fach})
            print(f"{fach}: Fortschritt leer angelegt")
    konfig_schreiben(ordner)


def konfig_schreiben(ordner: str) -> None:
    """altfragen-app.json: welche Fächer es gibt und welche Datei-IDs dazugehören."""
    eintraege = []
    for fach, name in FAECHER.items():
        fr = einzeln(finden("fragen", fach), f"Fragen {fach}")
        if not fr:
            continue
        fo = einzeln(finden("fortschritt", fach), f"Fortschritt {fach}")
        ls = einzeln(finden("lernskript", fach), f"Lernskript {fach}")
        eintraege.append({"id": fach, "name": name, "fragen": fr["id"], "fortschritt": fo["id"] if fo else None,
                          "lernskript": ls["id"] if ls else None})
    inhalt = json.dumps({"format": 1, "faecher": eintraege}, ensure_ascii=False, indent=1).encode("utf-8")
    da = einzeln(finden("config"), "Konfiguration")
    if da:
        ersetzen(da["id"], inhalt, "application/json")
    else:
        anlegen("altfragen-app.json", inhalt, "application/json", [ordner], {"altfragenApp": "config"})
    for e in eintraege:
        print(f"Konfiguration {e['id']}: Lernskript {'verbunden' if e['lernskript'] else 'fehlt'}")


def lernskript_anlegen(fach: str, pfad: str, ordner_id: str) -> None:
    """Lernskript als JARVIS-Datei anlegen, Inhalt byte-gleich zur lokalen Datei. Nur einmal je Fach."""
    if finden("lernskript", fach):
        raise Fehler(f"{fach}: Lernskript gibt es schon als App-Datei")
    datei = Path(pfad)
    inhalt = datei.read_bytes()
    neu = anlegen(datei.name, inhalt, "text/markdown", [ordner_id], {"altfragenApp": "lernskript", "fach": fach})
    if neu.get("md5Checksum") != hashlib.md5(inhalt).hexdigest():
        raise Fehler(f"{fach}: Prüfsumme weicht ab, Datei {neu['id']} prüfen")
    print(f"{fach}: Lernskript angelegt {neu['id']}, {len(inhalt)} Bytes, Prüfsumme gleich")
    konfig_schreiben(app_ordner())


def liste() -> None:
    for rolle in ("ordner", "config", "fragen", "fortschritt", "lernskript"):
        for d in finden(rolle):
            fach = (d.get("appProperties") or {}).get("fach", "")
            print(f"{rolle:12} {fach:7} {d['id']}  {d['modifiedTime']}  {d['name']}")


def main() -> None:
    befehl = sys.argv[1:2]
    try:
        if befehl == ["fragen"]:
            erzwingen = "--erzwingen" in sys.argv
            faecher = [a for a in sys.argv[2:] if a != "--erzwingen"] or list(FAECHER)
            unbekannt = [f for f in faecher if f not in FAECHER]
            if unbekannt:
                raise Fehler("unbekanntes Fach: " + ", ".join(unbekannt))
            fragen_veroeffentlichen(faecher, erzwingen)
        elif befehl == ["lernskript"] and len(sys.argv) == 5:
            lernskript_anlegen(sys.argv[2], sys.argv[3], sys.argv[4])
        elif befehl == ["liste"]:
            liste()
        else:
            print(__doc__)
            sys.exit(1)
    except (Fehler, aufgaben.AufgabenFehler) as e:
        print("Fehler:", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
