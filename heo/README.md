# HEO-Anwendung und Fachlogik

Dieser Bereich enthält die Anwendungsintegration und die davon getrennte
HEO-Fachlogik. Die Startdateien für Anwender liegen im Projektstamm.

| Bereich | Aufgabe | Stand |
| --- | --- | --- |
| `application/` | Dash-Anwendung, Start, Python-Einrichtung, Paketliste und Asset-Manifest | umgesetzt |
| `display/` | Bezeichnungen, Formatierungen und Dialogfeld-Zuordnungen | umgesetzt |
| `model/` | Gebäude, Versorgung, Standort und Jahresreihen | umgesetzt |
| `topology/` | Geräteslots, gemeinsames Topologiemodell, Szenengeometrie und Postprocessing | umgesetzt |

`model/`, `display/` und `topology/` importieren keine Module aus
`application/`, `dg_adapter/`, `tabs/` oder `ui/`. `application/` verbindet
diese Bereiche; der Launcher selbst benötigt vor der Paketeinrichtung nur die
Python-Standardbibliothek. Die DG-spezifische Übersetzung bleibt in
`dg_adapter/`; Dash-Komponenten und fensterspezifische Callbacks bleiben in
`ui/` und `tabs/`.

Aufrufer importieren Fachlogik direkt aus `heo/` und die Übersetzung roher
DG-Daten aus `dg_adapter/output/`.

## Kommentare und Docstrings

Python-Module, Klassen und Funktionen beschreiben ihre Aufgabe in einem
Docstring (`"""…"""`). Bei Funktionen gehören relevante Rückgabewerte,
Seiteneffekte und Fehlerbedingungen dazu; kurze Funktionen benötigen meist
nur einen Satz.

`#`-Kommentare erklären Entscheidungen, fachliche Randbedingungen und
wichtige Abschnitte längerer Abläufe. Eine Begründung kann direkt vor der
Funktion stehen, eine Abschnittserklärung am zugehörigen Code. Sie wiederholen
den Docstring nicht. In Shell- und PowerShell-Skripten dienen `#`-Kommentare
auch zur Beschreibung der Ablaufschritte.
