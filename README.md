# TTC-Gransee-Webseiten-Aktualisierung

Das Skript liest die festgelegten myTischtennis-Spielpläne, übernimmt die nächsten fünf Spiele des TTC Gransee und erzeugt aus neuen abgeschlossenen Begegnungen mit der DeepSeek-API bis zu fünf Spielberichte. Anschließend wird aus `template.html` eine neue `index.html` erzeugt.

## 1. Sicherheit

Der im Chat veröffentlichte API-Schlüssel muss im DeepSeek-Konto **sofort widerrufen und ersetzt** werden. Ein veröffentlichter Schlüssel gilt als kompromittiert. Den neuen Schlüssel ausschließlich in `.env` speichern; diese Datei wird durch `.gitignore` ausgeschlossen.

## 2. Installation unter Windows

1. Python 3.11 oder neuer installieren.
2. Diesen Ordner entpacken.
3. Eingabeaufforderung oder PowerShell in diesem Ordner öffnen.
4. Virtuelle Umgebung und Pakete installieren:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

5. `.env.example` nach `.env` kopieren und den **neuen** Schlüssel eintragen:

```env
OPENAI_API_KEY=NEUER_SCHLUESSEL
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
GENERATE_REPORTS_FROM_TEST_LEAGUE=true
```

6. Skript starten:

```powershell
python update_website.py
```

Danach liegt die fertige Datei als `index.html` im selben Ordner. Diese Datei kann auf GitHub hochgeladen werden. Bilder und sonstige Dateien der bisherigen Webseite bleiben unverändert erforderlich.

## Verhalten

- Unter „Vereinsnachrichten“ erscheinen maximal fünf Titel mit Datum.
- Ein Klick öffnet den vollständigen Artikel als eingebetteten Dialog.
- Es werden maximal fünf Artikel dauerhaft gespeichert; ältere werden aus `data/articles.json` entfernt.
- Unter „Nächste Termine“ erscheinen nur Spiele ab dem heutigen Datum, aufsteigend sortiert, maximal fünf.
- Beim ersten Test werden höchstens fünf historische Berichte erzeugt, um API-Kosten zu begrenzen.
- Bereits bekannte Spiele lösen keinen erneuten API-Aufruf aus.
- Nach dem Test `GENERATE_REPORTS_FROM_TEST_LEAGUE=false` setzen, damit nur noch die aktuelle Saison ausgewertet wird.

## Wichtige Hinweise

Die Struktur externer Webseiten kann sich ändern. Das Skript protokolliert dann einen Fehler, statt unbemerkt falsche Inhalte zu veröffentlichen. Vor jedem Hochladen sollte die erzeugte `index.html` kurz im Browser geprüft werden.
