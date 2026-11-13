# Humanotop Energiesystem-Optimierer (HEO)

Zum Start die passende Datei im Hauptordner öffnen: **HEO (Windows).bat**
unter Windows oder **HEO (Linux).sh** unter Linux. Die technischen App- und
Startdateien sind unter `heo/application/` zusammengefasst.

## Start unter Windows und Linux

Für die erste Einrichtung wird eine Internetverbindung benötigt. Der
Projektordner muss beschreibbar sein. Ist ein geeignetes **Python 3.12 mit
64 Bit** einschließlich venv-Unterstützung vorhanden, wird es verwendet.
Andernfalls laden die Starter eine eigene Python-Laufzeit in den HEO-Ordner.
Eine vorherige manuelle Python-Installation ist damit nicht mehr nötig.

- **Windows:** `HEO (Windows).bat` per Doppelklick öffnen.
- **Linux:** `HEO (Linux).sh` als Programm ausführen. Je nach Dateimanager muss
  das Ausführen zunächst erlaubt werden. Alternativ im Terminal:
  `bash "HEO (Linux).sh"`.

Die Starter ermitteln den Projektordner selbst; Leerzeichen im Pfad sind
zulässig. Sie stellen bei Bedarf Python bereit, erstellen einmalig
`.venv-windows/` beziehungsweise
`.venv-linux/`, installieren die Pakete aus
`heo/application/requirements.txt` und starten anschließend die Dash-Anwendung
aus `heo/application/heo_dash.py`. Die App öffnet den Browser unter
`http://127.0.0.1:8050/`. Unter Linux öffnet der Doppelklick kein Terminal.
Beim ersten Start kann die Einrichtung etwas dauern. Startprotokolle liegen
unter `.heo-runtime/logs/`; Fehler werden als Desktopdialog angezeigt
(je nach Desktop über Zenity, KDialog oder Xmessage, andernfalls über eine
Benachrichtigung und den geöffneten Protokollordner).

Alle offenen HEO-Tabs senden alle fünf Sekunden ein Lebenszeichen. Fehlen
30 Sekunden lang Lebenszeichen, beendet sich der lokale Server und gibt den
Port frei. Laufende Requests und Optimierungen verlängern diese Frist.
Beim ersten Start gelten bis zu 120 Sekunden Wartezeit für das Browserfenster.
Pausierte Hintergrund-Tabs oder ein schlafender Rechner können als geschlossene
Tabs gelten. Nicht gespeicherte Browsereingaben werden dabei nicht automatisch
gesichert.

Ein erneuter Doppelklick öffnet eine noch laufende eigene Instanz und erneuert
deren Frist. Nach der Abschaltung startet HEO frisch mit aktuellem Python-Code.
Für Codeänderungen daher alle HEO-Tabs schließen und etwa 35 Sekunden warten;
während einer Optimierung entsprechend bis nach deren Ende warten.

Unter Linux kann der Starter eine nicht antwortende eigene Instanz kontrolliert
ersetzen. Dazu prüft er Prozessidentität, Startkennung, Benutzer und Projektpfad;
laufende Kindprozesse verhindern das Ersetzen. Auch alte Launcher-Instanzen
ohne Lebenszeichen werden anhand ihres Port-Sockets erkannt. Fremde Prozesse
werden nicht beendet. Ein echter Portkonflikt wird grafisch gemeldet.
Unter Windows erfolgt diese erzwungene Prozesswiederherstellung nicht.

Die Dateimanager-Auswahl „Ausführen“ startet die App; „Anzeigen“ öffnet
das Skript im Editor.

Der automatische Python-Download unterstützt Windows x64 und Linux x86_64.
Unter Windows wird die mitgelieferte Windows PowerShell verwendet. Unter
Linux werden Bash, `tar`, `sha256sum` und `curl` oder `wget` benötigt; eine
separate Installation von `python3.12-venv` ist beim Download nicht nötig.
Für verwaltete Unternehmensrechner können Download- oder Ausführungsregeln
gelten, die eine automatische Einrichtung verhindern.

Die zusätzliche Laufzeit liegt ausschließlich unter `.heo-runtime/`. Das
Downloadwerkzeug uv ist auf eine Version mit SHA-256-Prüfsummen in
`heo/application/uv.env` festgelegt. Es kommt aus dem offiziellen
[uv-Release](https://github.com/astral-sh/uv/releases/tag/0.13.7); die
Python-Laufzeiten stammen aus Astrals `python-build-standalone`. Die
Einrichtung verwendet weder eine systemweite Installation noch Änderungen
am globalen PATH oder an der Windows-Registry. Details zur Python-Verwaltung:
[uv-Dokumentation](https://docs.astral.sh/uv/guides/install-python/).

Bei weiteren Starts werden die Pakete nicht erneut installiert. Ändert sich
`heo/application/requirements.txt`, wird die Installation vor dem nächsten App-Start
aktualisiert und auf widersprüchliche Abhängigkeiten geprüft. Ein
fehlgeschlagener Versuch gilt nicht als abgeschlossen und kann durch einen
erneuten Start wiederholt werden. Das Windows-Fenster bleibt bei Fehlern
offen, damit die Meldung gelesen werden kann.

Die bestehenden Umgebungen `.venv-linux~/`, `.venv/` und `dg_backend/.venv/`
werden nicht verändert. Für Starts über die neuen Starter verwenden Oberfläche
und Berechnungen denselben neuen Interpreter. Für die Entwicklung kann eine
bestehende Umgebung die Anwendung ohne automatische Einrichtung aus dem
Projektstamm starten:

```bash
'.venv-linux~/bin/python' -m heo.application.launcher --run-app
```

`heo_dash.py` definiert die Anwendung und startet beim Import weder Server
noch Browser. `launcher.py` delegiert Browseraufruf und Serverstart an `server_runtime.py`;
`browser_lifecycle.py` verwaltet Lebenszeichen und Abschaltfristen.

Nur die Einrichtung ausführen, ohne die App zu öffnen:

```powershell
& '.\HEO (Windows).bat' --setup-only
```

```bash
bash "HEO (Linux).sh" --setup-only
```

Mit `--check` statt `--setup-only` lässt sich der gespeicherte Einrichtungsstand
prüfen, ohne Python herunterzuladen, Pakete zu installieren oder die App zu
starten. Das ersetzt keinen Funktionstest der Berechnung.

## Codeänderungen, Updates und Übertragung

`heo/application/launcher.py` verwendet für die Einrichtung nur die
Python-Standardbibliothek. Erst beim App-Start wird `heo_dash.py` importiert.
Interne Änderungen an `heo/model/`, `heo/display/`, `heo/topology/`, `tabs/`,
`ui/` oder `dg_adapter/` benötigen keine Anpassung der Startdateien.

Neue oder geänderte Laufzeitpakete werden zentral in
`heo/application/requirements.txt`
eingetragen. Diese Liste enthält die direkten Abhängigkeiten der Oberfläche
und des Backends mit Versionen aus der vorhandenen Linux-Umgebung. Sie ist
kein vollständiger Lock aller transitiven Abhängigkeiten und ersetzt keinen
Windows-Funktionstest. Die Paketliste des Backends unter
`dg_backend/requirements.txt` bleibt für dessen separate Installation bestehen;
der HEO-Starter verwendet die Liste unter `heo/application/`.

Beim Übertragen oder Hochladen werden keine venv-Ordner, `.heo-runtime/`,
Caches oder Einrichtungsmarker mitgenommen. Nach Codeupdates bleiben die lokalen
Umgebungen erhalten. Nach einem Verschieben des Projektordners oder einem
Wechsel der Python-Basisinstallation muss die Umgebung gegebenenfalls neu
erstellt werden. Der Starter überschreibt keine fremden oder verschobenen
Umgebungen: In diesem Fall den betroffenen `.venv-linux/`- oder
`.venv-windows/`-Ordner zunächst umbenennen und erneut starten.

Die beiden Startdateien und der vollständige Ordner `heo/application/` gehören
zur übertragbaren App. Lokale Tests, Vergleichsläufe und Archive sind nicht
Teil des veröffentlichten Git-Stands.

## Projektstruktur

| Bereich | Inhalt |
| --- | --- |
| `HEO (Linux).sh`, `HEO (Windows).bat` | Sichtbare Einstiegspunkte |
| `heo/application/` | Dash-Anwendung, Asset-Manifest, Paketliste und automatische Einrichtung |
| `assets/`, `tabs/`, `ui/` | Oberfläche und ausgelieferte Dateien |
| `heo/model/`, `heo/topology/`, `heo/display/` | Fachmodell, zentrale Topologie und HEO-Bezeichnungen |
| `dg_adapter/`, `dg_backend/` | Szenarioverwaltung, Berechnung und DistrictGenerator |
| `data/` | Wetterdaten und Vorlagen für die Anwendung |
| `dg_adapter/scenarios/Humanotop Saaremaa/` | Mitgeliefertes Beispielszenario |

Setup-Sperrdateien werden unter `.heo-runtime/locks/` angelegt.

Die neue Linux-Umgebung `.venv-linux/`, die bisherige Entwicklungsumgebung
`.venv-linux~/` und das Git-Verzeichnis `.git/` bleiben im Projektstamm.
Diese lokalen Umgebungen werden nicht mit Git übertragen.
