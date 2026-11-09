# Datenformate und Regeln

Verbindlich für die App (`web/kern.js`) und die Werkzeuge (`werkzeug/*.py`). Beide Seiten prüfen sich gegen dieselben Testvektoren in `tests/vektoren/`.

## Dateien auf Drive

Alle im Ordner `Altfragen-App`, angelegt vom Werkzeug `veroeffentlichen.py` über den Zugang JARVIS (`drive.file`). Erkannt werden sie an `appProperties.altfragenApp`, nicht am Namen.

| Datei | `appProperties.altfragenApp` | Schreibt |
|---|---|---|
| `altfragen-app.json` | `config` | Werkzeug |
| `fragen-<fach>.json` | `fragen` | Werkzeug |
| `fortschritt-<fach>.json` | `fortschritt` | App, Werkzeug legt leer an |
| Lernskript `.md` | `lernskript` | App und Google Docs |

### altfragen-app.json

```json
{
  "format": 1,
  "faecher": [
    {"id": "mibi", "name": "MiBi Teil 1", "fragen": "<fileId>", "fortschritt": "<fileId>", "lernskript": "<fileId>|null"}
  ]
}
```

### fragen-&lt;fach&gt;.json

```json
{
  "format": 1,
  "fach": "mibi",
  "name": "MiBi Teil 1",
  "klausur": "2027-02-12",
  "klausurInfo": "30 Fragen in 45 Minuten",
  "stand": "2026-11-08T21:30:00+01:00",
  "plan": "rang",
  "bloecke": [{"nr": 1, "titel": "Leber, Gallenwege, Pankreas", "meta": "erwartet 9,4 von 60 Fragen · 7 Themen"}],
  "themen": [
    {
      "rang": 1,
      "titel": "Erstes Thema",
      "stufe": null,
      "block": null,
      "meta": "erwartet 1,90 von 30 Fragen · …",
      "kern": "<Markdown>",
      "falle": "<Text>|null",
      "tabellen": "<Markdown-Tabelle>|''",
      "gefragt": ["**9×** Substanz einer Klasse zuordnen"],
      "abschnitte": [{"titel": "<Unterthema>", "text": "<Markdown>"}],
      "fragen": [
        {
          "id": "1.Q05",
          "nr": 5,
          "abschnitt": null,
          "mal": 2,
          "typ": "positiv|negativ|offen|fragment",
          "stamm": "<Text>",
          "aussagen": ["<Text>"],
          "optionen": [{"t": "<Text>", "w": "<Begründung>", "richtig": true, "erg": false, "fest": false}],
          "loesung": {"t": "<Text>", "w": "<Begründung>"},
          "neu": ["<Text>"],
          "hinweis": ["<Text>"],
          "ids": "1920-02 · 2223-21"
        }
      ]
    }
  ],
  "probeklausuren": [{"name": "Probeklausur 1", "minuten": 45, "fragen": ["1.Q05", "…"]}]
}
```

- `plan`: `rang` = Themen nach Rang. `block-stufe` = Blöcke in Reihenfolge, darin Stufe A, dann B; alle C-Themen danach als „nur bei Zeit“
- `id` = `<rang>.<Qnn>` aus der Quelle, bleibt über Neubauten stabil. `nr` = Nummer im Lernskript (`**Frage nr**`), leere Bruchstücke zählen nicht mit
- `optionen` in der Reihenfolge des Lernskripts. `richtig` = anzukreuzen (bei negativ gestellten Fragen die falsche Aussage). `erg` = nicht überliefert, ergänzt. `fest` = Sammeloption („alle genannten“), bleibt beim Neumischen am Ende. Leer bei `offen` und `fragment`
- `loesung` nur bei `offen` und `fragment`, sonst `null`
- `aussagen` nur bei Kombinationsfragen, sonst `null`
- `abschnitt` = Titel aus `abschnitte`, unter dem die Frage im Lernskript steht, sonst `null`
- Texte sind Markdown-Teilmenge: `**fett**`, `*kursiv*`, Listen mit `- ` (Einrückung zwei Leerzeichen je Ebene), nummerierte Listen, Tabellen mit `|`. Kein HTML
- `optionen[].w` = Begründung, die App zeigt sie nach dem Lösen direkt unter der Option, mit ✓ trifft zu / ✗ trifft nicht zu. `neu` = Extra-Fakten

### Ausgebaute Erklärungen (Quelle)

`<QUELLE>/erklaert/<fach>/NN.txt` je Thema, optional. `bauen.py` setzt sie über die Lernskript-Begründungen:

```
@@Q Q15
W: <Optionstext> || <Begründung>
EXTRA: <Fakt>
```

- `W` ersetzt `w` der Option, zugeordnet über `normal(Optionstext)`, nie über die Position. Unbekannte Option oder Frage = Fehler, der Bau bricht ab
- `EXTRA` ersetzt `neu` der Frage, wenn mindestens eine Zeile da ist
- Stichworte mit echtem Grund, keine Wiederholung des Optionstexts. Das Zeichen ✓/✗ setzt die App, im Text steht kein „trifft zu“
- Das Lernskript behält seine Begründungen. Der Abgleich prüft nur Stamm, Optionen und Lösung

## Fortschritt

```json
{
  "format": 1,
  "fach": "mibi",
  "versuche": {
    "1.Q05": [
      {"id": "<eindeutig>", "zeit": "2026-11-08T17:25:00.000Z", "wahl": ["Streptococcus pyogenes"], "unsicher": false, "falsch": false,
       "quelle": "app|docs|probe", "geaendert": "<ISO>", "geloescht": null}
    ]
  },
  "schritte": {"1": {"meditricks": {"wert": "ja|keins|null", "zeit": "<ISO>"}, "kern": {"wert": "ja|null", "zeit": "<ISO>"}}},
  "md": {"zeit": "<ISO>", "basis": {"1.Q05": "<Schlüssel>"}, "ueberschrieben": {"1.Q05": ["<Schlüssel>"]}}
}
```

- `wahl` enthält **Optionstexte**, nie Positionen. Verglichen wird über `normal()`
- `falsch` nur bei offenen Fragen (Selbsteinschätzung). `unsicher` bei allen
- `geloescht` = Zeitpunkt des Zurücknehmens. Gelöschte Versuche bleiben als Grabstein stehen, damit das Zusammenführen sie nicht zurückholt
- Versuche aus Docs: `id` = `docs:<frageId>:<Schlüssel>:<Zahl der nicht gelöschten Versuche davor>`, damit zwei Geräte denselben Haken nicht doppelt anlegen, auch wenn sie die .md zu verschiedenen Zeiten lesen
- Unbrauchbare Versuche (ohne `id`, ohne lesbare `zeit`, `wahl` keine Liste) werden beim Laden verworfen

### Zusammenführen zweier Stände
- `versuche`: Vereinigung über `id`. Gleiche `id` → der mit späterem `geaendert`. Trägt eine der beiden Fassungen `geloescht`, bleibt der Versuch gelöscht
- `schritte`: je Feld der mit späterer `zeit`
- `md`: der ganze Block mit späterer `zeit`

## Text vergleichbar machen: `normal(text)`

1. Backslash vor ASCII-Satzzeichen entfernen (`3\.` → `3.`, `\=` → `=`). Google Docs setzt diese Escapes beim Speichern
2. Geschütztes Leerzeichen → Leerzeichen
3. Umschließende `*` und `_` entfernen (wiederholt)
4. Leerraum zusammenfassen, außen abschneiden

## Lernskript lesen

Zeilenweise, `\r` am Zeilenende ignorieren:

- `## <rang> · <titel>` (optional ` · Stufe X`) → aktuelles Thema
- `**Frage <nr>**` am Zeilenanfang, danach beliebig (` · 2× gefragt`) → aktuelle Frage = Thema `rang`, Nummer `nr`
- Kästchen: `^\s*[-*+] \[([ xX])\] (.*?)\s*$`
  - Text nach `normal()` = `unsicher` → Merkmal unsicher, = `falsch` → Merkmal falsch
  - Ebenso, wenn der Text mit `*unsicher*` oder `*falsch*` beginnt und danach mehr kommt: Google Docs hängt beim Speichern manchmal die Folgezeile an (`*unsicher* **Hinweis:** …`)
  - sonst Option. Angehakt → in `wahl`
- `## `, `# ` oder `**Frage ` beendet die laufende Frage
- Optionstext, der zu keiner Option der Frage passt → Fehler für diese Frage, sie wird beim Abgleich übersprungen und gemeldet. Nie über die Position zuordnen

**Zustand** einer Frage in der .md: `{wahl: [Texte], unsicher, falsch}`. **Schlüssel**: `normal()` jeder gewählten Option (Groß- und Kleinschreibung bleibt), nach Unicode sortiert, mit `|` verbunden, dann `#` und `u0|u1`, `f0|f1`. Beispiel `Penicilline#u1f0`. **LEER** = `#u0f0`.

## Ergebnis eines Versuchs

- Mit Optionen: Menge `normal(wahl)` = Menge `normal(richtige Optionen)` → `unsicher` wenn markiert, sonst `richtig`. Sonst `falsch`. Leere Wahl → kein Versuch
- Offen: `falsch` markiert → `falsch`, sonst `unsicher` markiert → `unsicher`, sonst `richtig` (gewusst)
- Bruchstücke werden nicht beantwortet

## Wiederholung

Aus den nicht gelöschten Versuchen einer Frage, nach `zeit` aufsteigend. Tage = Kalendertage in Europe/Berlin.

| Ergebnis | Folge |
|---|---|
| falsch | Leiter an, Stufe 0, fällig nach **2** Tagen |
| unsicher | Leiter an, Stufe 0, fällig nach **3** Tagen |
| richtig, Leiter aus | nichts fällig |
| richtig, Leiter an | Stufe +1: Stufe 1 → **7** Tage, Stufe 2 → **21** Tage, Stufe 3 → Leiter aus |
| richtig, Leiter an, vor dem Fälligkeitstag | nichts ändert sich, sofortiges Üben rückt die Leiter nicht vor |

- Fälligkeit höchstens zwei Tage vor der Klausur, mindestens einen Tag nach dem Versuch
- Eine Frage gilt als beantwortet, sobald sie einen Versuch mit Ergebnis hat (für Plan, Tempo, „Weiter mit Frage“)
- **Status**: `neu` (kein Versuch) · `sicher` (nichts fällig) · `faellig` (Fälligkeit ≤ heute) · `wartet`

**Fehlersammlung**: jede Frage außer Bruchstücken mit mindestens einem nicht gelöschten Versuch, dessen Ergebnis `falsch` oder `unsicher` ist. Bleibt, auch wenn spätere Versuche richtig sind. Je Frage die Zahl der falschen und unsicheren Versuche und `zuletzt` = Zeit des letzten Versuchs mit Ergebnis. Reihenfolge: `zuletzt` aufsteigend (am längsten nicht geübte zuerst), bei Gleichstand Plan-Reihenfolge

## Abgleich App ↔ Lernskript

Für jede beantwortbare Frage, mit `basis` und `ueberschrieben` aus `md`:

1. `m` = Zustand in der .md (fehlt die Frage oder hat sie keine Haken: LEER)
2. `schluessel(m)` = `basis` (fehlt: LEER) → keine Änderung in Docs
3. Sonst:
   - `m` ist LEER → ignorieren. Haken entfernen geht nur in der App, weil Docs beim Speichern einer alten Fassung Haken der App löschen kann
   - `schluessel(m)` steht in `ueberschrieben` → alte Fassung aus Docs, ignorieren
   - sonst Änderung in Docs übernehmen: Hat der letzte Versuch dieselbe Wahl, nur `unsicher`/`falsch` anpassen (`geaendert` neu). Sonst neuer Versuch, `quelle: docs`, `zeit` = `modifiedTime` der .md
4. Soll = Zustand des letzten Versuchs (keiner: LEER)
5. Weicht `m` vom Soll ab → Kästchen der Frage in der .md umschreiben, nur das Zeichen in `[ ]`. `schluessel(m)` vorn in `ueberschrieben`, ohne Doppelte, höchstens 3
6. `basis` = `schluessel(Soll)`, LEER wird nicht gespeichert
7. Fragen mit Fehler beim Lesen (unbekannte Option) bleiben unberührt: kein Import, kein Umschreiben, `basis` bleibt
8. Ebenso Fragen mit Optionen, bei denen in der .md nur `unsicher` oder `falsch` angehakt ist, aber keine Option: Docs ist mitten in einer Antwort
9. Neuer md-Text nur, wenn er sich vom gelesenen unterscheidet

**Schutz**
- Reihenfolge je Fach: Fortschritt holen und zusammenführen → Fortschritt hochladen → .md lesen und abgleichen → `modifiedTime` der .md erneut prüfen, bei Abweichung von vorn (höchstens dreimal) → .md hochladen → Fortschritt mit neuem md-Block hochladen
- `basis` und `ueberschrieben` gelten erst, wenn die .md erfolgreich hochgeladen ist
- Abgeglichen wird nur ein Stand, der vorher mit dem Fortschritt auf Drive zusammengeführt wurde. Ist der nicht lesbar oder leer, unterbleibt der Abgleich
- Würde ein Abgleich bei mehr als 5 Fragen alle Haken entfernen, für die es in der App keinen Versuch gibt (auch keinen zurückgenommenen), bricht er ab und nennt sie. Die .md bleibt dann unverändert

**Bekannte Grenze:** Ob ein Stand aus Docs eine alte Fassung ist, erkennt der Abgleich nur an Ständen, die die App selbst überschrieben hat. Wählt man in Docs bewusst genau die Antwort wieder, die eine Wiederholung in der App ersetzt hat, setzt die App ihre zurück. Speichert eine veraltete Docs-Sitzung einen früheren Docs-Stand, wird er als neuer Versuch übernommen
