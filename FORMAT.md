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
          "institut": ["Institut wertet „…“ (Klausureinsicht 21/22)"],
          "hinweis": ["<Text>"],
          "ids": "1920-02 · 2223-21",
          "herkunft": "22/23, 19/20"
        }
      ]
    }
  ],
  "probeklausuren": [{"name": "Probeklausur 1", "minuten": 45, "fragen": ["1.Q05", "…"]}]
}
```

- `durchgang`: optional, Datum, bis zu dem der erste Durchgang fertig sein soll (Tempo). Fehlt es, gilt sieben Tage vor der Klausur. Für Testate, die erst in der Woche davor gelernt werden
- `plan`: `rang` = Themen nach Rang. `block-stufe` = Blöcke in Reihenfolge, darin Stufe A, dann B; alle C-Themen danach als „nur bei Zeit“
- `id` = `<rang>.<Qnn>` aus der Quelle, bleibt über Neubauten stabil. `nr` = Nummer im Lernskript (`**Frage nr**`), leere Bruchstücke zählen nicht mit
- `optionen` in der Reihenfolge des Lernskripts. `richtig` = anzukreuzen (bei negativ gestellten Fragen die falsche Aussage). `erg` = nicht überliefert, ergänzt. `fest` = Sammeloption („alle genannten“), bleibt beim Neumischen am Ende. Leer bei `offen` und `fragment`
- `loesung` nur bei `offen` und `fragment`, sonst `null`
- `aussagen` nur bei Kombinationsfragen, sonst `null`
- `abschnitte[].text` leer = Unterthema ohne eigene Notiz, gliedert im Lernskript nur die Fragen. Die App zeigt im Kern nur Unterthemen mit Text als Klappfeld
- `abschnitt` = Titel aus `abschnitte`, unter dem die Frage im Lernskript steht, sonst `null`
- Texte sind Markdown-Teilmenge: `**fett**`, `*kursiv*`, Listen mit `- ` (Einrückung zwei Leerzeichen je Ebene), nummerierte Listen, Tabellen mit `|`. Kein HTML
- `optionen[].w` = Begründung, die App zeigt sie nach dem Lösen direkt unter der Option, mit ✓ trifft zu / ✗ trifft nicht zu. `neu` = Extra-Fakten
- Lösung ist die fachlich richtige Antwort. `institut` = belegte Wertung des Instituts (Klausureinsicht, Lösungsschlüssel), wenn sie davon abweicht oder die Klausur eine zweite vertretbare Option hatte; die App zeigt sie deutlich. `bauen.py` nimmt dafür die Hinweise der Quelle, die mit „Institut wertet“ beginnen. `hinweis` = alles Übrige (Protokollabweichung, Varianten, Quellen), klein

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
  "sterne": {"1.Q05": {"wert": true, "zeit": "<ISO>"}},
  "md": {"zeit": "<ISO>", "basis": {"1.Q05": "<Schlüssel>"}, "ueberschrieben": {"1.Q05": ["<Schlüssel>"]}}
}
```

- `wahl` enthält **Optionstexte**, nie Positionen. Verglichen wird über `normal()`
- `falsch` nur bei offenen Fragen (Selbsteinschätzung). `unsicher` nur noch aus früheren Fassungen, siehe Stern
- `geloescht` = Zeitpunkt des Zurücknehmens. Gelöschte Versuche bleiben als Grabstein stehen, damit das Zusammenführen sie nicht zurückholt
- Versuche aus Docs: `id` = `docs:<frageId>:<Schlüssel der Antwort, immer u0>:<Zahl der nicht gelöschten Versuche davor>`, damit zwei Geräte denselben Haken nicht doppelt anlegen, auch wenn sie die .md zu verschiedenen Zeiten lesen
- Unbrauchbare Versuche (ohne `id`, ohne lesbare `zeit`, `wahl` keine Liste) und Sterne (`wert` nicht `true`/`false`, ohne lesbare `zeit`) werden beim Laden verworfen

### Stern
- Je Frage höchstens ein Eintrag in `sterne`, auch für Bruchstücke. Ausschalten schreibt `wert: false` mit neuer `zeit`, der Eintrag bleibt. Schlüssel nach Frage-ID sortiert
- Der Stern ist ein Merker: Er bestimmt die Sammlung Markiert und das Kästchen `unsicher` im Lernskript, sonst nichts
- `unsicher` in Versuchen stammt aus früheren Fassungen der App; neue Versuche tragen immer `false`, im Ergebnis zählt das Merkmal nicht. **Übernahme**: Eine Frage ohne eigenen Eintrag mit einem nicht gelöschten Versuch mit `unsicher` bekommt `{wert: true, zeit: <zeit des letzten solchen Versuchs>, alt: true}`. Solche Einträge werden bei jedem Laden und Zusammenführen neu aus den Versuchen abgeleitet, damit ein veralteter Stand sie nicht festhält. Umschalten in App oder Docs ersetzt sie durch einen eigenen Eintrag
- Fassungen der App vor dem Stern verwerfen `sterne` beim Zusammenführen. Die nächste neue Fassung, die sie noch gespeichert hat, schreibt sie zurück; übernommene leitet sie ohnehin neu ab

### Zusammenführen zweier Stände
- `versuche`: Vereinigung über `id`. Gleiche `id` → der mit späterem `geaendert`. Trägt eine der beiden Fassungen `geloescht`, bleibt der Versuch gelöscht
- `schritte`: je Feld der mit späterer `zeit`
- `sterne`: eigene Einträge je Frage der mit späterer `zeit`, bei gleicher `zeit` der mit `wert: true`. Übernommene (`alt`) danach neu aus den vereinigten Versuchen. Ein Stand ohne `sterne` (ältere Fassung der App) löscht keinen
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

**Zustand** einer Frage in der .md: `{wahl: [Texte], unsicher, falsch}`. Das Kästchen `unsicher` ist der Stern. **Schlüssel**: `normal()` jeder gewählten Option (Groß- und Kleinschreibung bleibt), nach Unicode sortiert, mit `|` verbunden, dann `#` und `u0|u1`, `f0|f1`. Beispiel `Penicilline#u1f0`. **LEER** = `#u0f0`.

## Ergebnis eines Versuchs

- Mit Optionen: Menge `normal(wahl)` = Menge `normal(richtige Optionen)` → `richtig`, sonst `falsch`. Leere Wahl → kein Versuch
- Offen: `falsch` markiert → `falsch`, sonst `richtig` (gewusst)
- Bruchstücke werden nicht beantwortet
- Eine Frage gilt als beantwortet, sobald sie einen nicht gelöschten Versuch mit Ergebnis hat (für Plan, Tempo, „Weiter mit Frage“). Im Thema zählt das Ergebnis des letzten solchen Versuchs (Anteil richtig)
- Keine Wiederholung nach Zeitplan: Was erneut geübt wird, wählt man über die Sammlungen
- Tempo des ersten Durchgangs: offene Pflichtfragen bis `durchgang`, ohne diese Angabe bis sieben Tage vor der Klausur, Tage = Kalendertage in Europe/Berlin

## Sammlungen

Je Frage: Zahl der nicht gelöschten Versuche mit Ergebnis `falsch`, ob der letzte Versuch mit Ergebnis `falsch` war, `zuletzt` = Zeit des letzten Versuchs mit Ergebnis (keiner: nie geübt).

- **Falsch**: jede Frage außer Bruchstücken mit mindestens einem falschen Versuch. Bleibt, auch wenn spätere Versuche richtig sind. Reihenfolge: zuerst die, deren letzter Versuch falsch war; darin und danach `zuletzt` aufsteigend (am längsten nicht geübte zuerst), bei Gleichstand Plan-Reihenfolge
- **Markiert**: genau die Fragen mit Stern. Reihenfolge: nie geübte zuerst, dann `zuletzt` aufsteigend, bei Gleichstand Plan-Reihenfolge
- Eine Frage kann in beiden stehen. Die App zeigt beide als Zahl (✗ N, ☆ N); antippen startet eine Runde mit den ersten Einträgen. Im Thema dieselben Sammlungen, beschränkt auf das Thema, in Reihenfolge des Themas

## Abgleich App ↔ Lernskript

Für jede beantwortbare Frage, mit `basis` und `ueberschrieben` aus `md`:

1. `m` = Zustand in der .md (fehlt die Frage oder hat sie keine Haken: LEER)
2. `schluessel(m)` = `basis` (fehlt: LEER) → keine Änderung in Docs
3. Sonst:
   - `m` ist LEER → ignorieren. Haken entfernen geht nur in der App, weil Docs beim Speichern einer alten Fassung Haken der App löschen kann
   - `schluessel(m)` steht in `ueberschrieben` → alte Fassung aus Docs, ignorieren
   - sonst Änderung in Docs übernehmen, Stern und Antwort getrennt, jeweils nur, was sich gegenüber `basis` geändert hat:
     - **Stern**: `unsicher` in `m` angehakt, in `basis` nicht → Stern an, `zeit` = `modifiedTime` der .md. Ist der Eintrag in `sterne` jünger, bleibt er. Abgehakt wird ignoriert wie jeder entfernte Haken: Stern entfernen nur in der App
     - **Antwort**: Optionen oder `falsch` anders als in `basis`. Mit Optionen, aber keine angehakt: nichts. Offene Frage ohne `falsch` und ohne Versuch: nichts. Hat der letzte Versuch dieselbe Wahl, nur `falsch` anpassen (`geaendert` neu). Sonst neuer Versuch, `quelle: docs`, `unsicher: false`, `zeit` = `modifiedTime` der .md
4. Soll = Optionen und `falsch` des letzten Versuchs, `unsicher` = Stern (nichts davon: LEER)
5. Weicht `m` vom Soll ab → Kästchen der Frage in der .md umschreiben, nur das Zeichen in `[ ]`. `schluessel(m)` vorn in `ueberschrieben`, ohne Doppelte, höchstens 3
6. `basis` = `schluessel(Soll)`, LEER wird nicht gespeichert
7. Fragen mit Fehler beim Lesen (unbekannte Option) bleiben unberührt: kein Import, kein Umschreiben, `basis` bleibt
8. Ebenso Fragen mit Optionen, bei denen in der .md keine Option angehakt ist, aber `falsch`, oder `unsicher`, während `basis` eine Option enthält: Docs ist mitten in einer Antwort. Sonst ist ein angehaktes `unsicher` allein der Stern
9. Neuer md-Text nur, wenn er sich vom gelesenen unterscheidet

**Schutz**
- Reihenfolge je Fach: Fortschritt holen und zusammenführen → Fortschritt hochladen → .md lesen und abgleichen → `modifiedTime` der .md erneut prüfen, bei Abweichung von vorn (höchstens dreimal) → .md hochladen → Fortschritt mit neuem md-Block hochladen
- `basis` und `ueberschrieben` gelten erst, wenn die .md erfolgreich hochgeladen ist
- Abgeglichen wird nur ein Stand, der vorher mit dem Fortschritt auf Drive zusammengeführt wurde. Ist der nicht lesbar oder leer, unterbleibt der Abgleich
- Würde ein Abgleich bei mehr als 5 Fragen, zu denen die App keinen Versuch kennt (auch keinen zurückgenommenen), eine Antwort aus der .md entfernen oder sie ganz leeren, ohne dass es einen Eintrag in `sterne` gibt, bricht er ab und nennt sie. Die .md bleibt dann unverändert

**Bekannte Grenze:** Ob ein Stand aus Docs eine alte Fassung ist, erkennt der Abgleich nur an Ständen, die die App selbst überschrieben hat. Wählt man in Docs bewusst genau die Antwort wieder, die eine spätere Antwort in der App ersetzt hat, setzt die App ihre zurück. Speichert eine veraltete Docs-Sitzung einen früheren Docs-Stand, wird er als neuer Versuch übernommen. Für den Stern heißt das: Hat die App ihn bei unveränderter Antwort ausgeschaltet, wird `unsicher` in Docs erst wieder übernommen, wenn sich die Antwort ändert
