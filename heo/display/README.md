# Zentrale HEO-Darstellungsregeln

Dieser Ordner enthält die fachlichen Zuordnungen für HEO-Dialoge. Die Module
erzeugen keine Dash-Komponenten und lesen keine DG-Ergebnisdateien.

| Modul | Aufgabe |
| --- | --- |
| `parameter_dialog_layout.py` | Ordnet Parameter den Haupt- und Zusatzbereichen sowie fachlichen Feldgruppen zu und prüft die Sichtbarkeit von Gebäudefeldern. |
| `parameter_catalog.py` | Definiert HEO-Abschnittstitel, Feldnamen, Hilfetexte und Gruppierungen. `SECTION_TITLES` ist die Quelle für Formulare, Navigation und Projektansicht. |
| `parameter_formatting.py` | Ergänzt geladene Felder um HEO-Labels, Einheiten, Anzeigeskalen und Dialogbereiche. |
| `device_labels.py` | Zentrale deutsche Geräte-, Gebäude-, Lade- und Topologie-Schaltflächenbezeichnungen. |
| `building_fields.py` | Feldmetadaten und numerische Eingabefelder für Gebäudedialoge und statische Gebäudeansichten. |
| `result_dialog_layout.py` | Ordnet Ergebnisgrößen den Dialogbereichen zu. |
| `kpi_dialog_layout.py` | Ordnet HEO- und DG-Berichtskennzahlen den Dialogbereichen zu. |
| `comparison.py` | Deutsche Vergleichskennzahlen, Berichtsbeschreibungen und vorbereitete Kartenwerte. |
| `project_info_data.py` | Abschnitte und Geräte-/Gebäudeinformationen der Projektansicht. |
| `field_presentation.py` | Renderunabhängige Feld- und Dialogbeschreibungen einschließlich MIN-/MAX-Bezeichnungen. |
| `form_content.py` | Sichtbare Felder, Reihenfolge und verschachtelte Aktivierungs-, Zeitraum- und Grenzwertgruppen vor dem Rendern planen. |
| `field_values.py` | Bereitet Feldwerte, Einheiten, Auswahlmöglichkeiten, Datumsanzeigen und Winkel renderunabhängig auf. |
| `chart_theme.py` | Gemeinsame Hintergrund-, Schrift-, Raster- und Achsenfarben für HEO-Zeitreihendiagramme. |
| `result_details.py` | Ergebniszeilen in beschriftete Werte mit Einheit zerlegen. |
| `chart_axes.py` | Monatsmarken und Achsenticks für Ergebniszeitreihen. |
| `chart_series.py` | Beschriftungen, Datenfelder und Farben von Wetter- und Bedarfsreihen. |
| `result_views.py` | Bezeichnungen und Informationstexte der Ergebnisansichten. |
| `number_format.py` | Deutsche Zahlen formatieren und einlesen. |

Die Module importieren weder `dg_adapter` noch `tabs` oder `ui`. Der Adapter
liefert die DG-Schemafelder an `parameter_formatting.py` und ergänzt die
Geräte-Hilfetexte aus dem zentralen Katalog in `heo/model/devices.py`.
Die vollständigen geladenen
Abschnitte und Standardwerte bleiben über `dg_adapter.input.parameter_catalog`
erreichbar.

Dialog-Zuordnungen und Zahlenformate werden direkt aus `heo.display`
importiert.

## Formularraster

`form_content.py` bestimmt den Inhalt. `ui/components/form_grid.py` übergibt
Feldspannen und Gruppen als Metadaten an den Browser. Unter `assets/shared/`
misst `form_measure.js` den Platzbedarf, `form_layout.js` plant Zeilen und
Spalten und `form_viewports.js` aktualisiert die betroffenen Raster.
`form_state.js` erhält dabei Bedienanker, Eingabeentwürfe, Fokus und Scrollstand.

Die äußeren Fensterfunktionen bestimmen weiterhin Lage und verfügbare Größe
von Dialogen und Ansichten. Automatische Raster verwenden dieselbe Planung
für editierbare Parameter, Ergebniswerte, Abschnittskarten und KPIs. Die
benannten Profile `microgrid_start` und `scenario_load` behalten ihre feste
Anordnung. CSS beschreibt die Gestaltung und eine anfängliche Einzelspalte;
die automatische Belegung wird ausschließlich vom gemeinsamen Planer gesetzt.

Text- und Gruppenbedarfe werden innerhalb eines Planungsdurchlaufs geteilt.
Bei Breitenvarianten werden die tatsächlichen Höhen nach dem Umbrechen gelesen;
gelöste innere Raster derselben Breite werden wiederverwendet. Jeder neue
Durchlauf misst Inhalte und Schriften erneut.

Bedingte Gruppen berücksichtigen schon eingeklappt die Mindestbreite ihrer
abhängigen Controls. Deren Höhe bleibt bis zum Einblenden unbesetzt. Rahmen
und Innenabstand der Schalterbox bleiben beim Öffnen konstant, damit eine
gebundene Gruppe ihre Eingaben lesbar und den Schalter am Mausort halten kann.
