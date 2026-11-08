# Altfragen-App

Lern-App für Altfragen-Lernskripte, am Handy und am Laptop. Antwort antippen, Lösung danach, falsche und unsichere Fragen kommen nach zwei bis drei Tagen wieder, Plan je Thema bis zur Klausur.

Das Repo enthält nur Code. Fragen und Lernstand liegen auf Google Drive und werden erst nach der Anmeldung geladen.

## Aufbau

| Teil | Inhalt |
|---|---|
| `web/` | Die App, ohne Build-Schritt: `kern.js` (Logik), `markdown.js`, `drive.js` (Anmeldung, Drive), `app.js` (Bildschirme), `sw.js` (offline) |
| `werkzeug/` | Python: `bauen.py` erzeugt die Fragendatei aus den Rohdaten und prüft sie gegen das Lernskript, `veroeffentlichen.py` legt die App-Dateien auf Drive an, `auswerten.py` wertet den Lernstand aus |
| `tests/` | `node --test tests/*.test.js` und `python -m unittest discover -s tests`, beide gegen dieselben Testvektoren in `tests/vektoren/` |
| `FORMAT.md` | Datenformate und Regeln für Abgleich und Wiederholung |

## Zugriff

Anmeldung mit Google, Berechtigung `drive.file`: Die App sieht nur Dateien, die das Projekt selbst angelegt hat. Der Zugang gilt eine Stunde und liegt nur im Tab. Ohne Netz läuft die App mit dem zuletzt geladenen Stand weiter.

## Abgleich mit dem Lernskript

Das Lernskript (.md) wird in Google Docs angehakt. Die App liest die Haken beim Abgleich und schreibt eigene Antworten zurück, nur das Zeichen im Kästchen. Regeln in `FORMAT.md`, Abschnitt „Abgleich“.
