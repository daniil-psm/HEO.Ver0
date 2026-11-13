# HEO → DG: Eingabedaten

Dieser Ordner übersetzt einen HEO-Entwurf in geprüfte DG-Eingabedateien.
Die Module importieren weder Dash noch `tabs` oder `ui`.

| Modul | Verantwortung |
| --- | --- |
| `input_builder.py` | Öffentlicher Einstieg `build_inputs`: vollständigen Entwurf prüfen, Config/Wetter/CSV schreiben, Jahresreihen-Metadaten sichern. |
| `env_config_builder.py` | DG-Werte serialisieren und `.env.CONFIG` samt Wetterdatei speichern. |
| `building_csv_builder.py` | Gebäude als Semikolon-CSV und HEO-Namensmetadaten speichern. |
| `weather_input.py` | TRY/EPW lesen, Wettermetadaten bestimmen und Uploads für DG vorbereiten. |
| `input_mapper.py` | HEO-Schlüssel und Einheiten auf DG abbilden; unterstützt auch das Zurückladen gespeicherter Eingaben. |
| `config_bridge.py` | Originales DG-Schema und DG-Validierung im DG-Interpreter aufrufen. |
| `validation.py` | Gebäude, Versorgung und Konfiguration zentral prüfen. |
| `config_service.py` | DG-Schema laden, Szenarien auflisten und gespeicherte Szenarioordner verwalten. |
| `scenario_service.py` | Gebäude-CSV und HEO-Gebäudemetadaten eines Szenarios lesen. |
| `scenario_paths.py` | Pfade für Gebäude-CSV und lokale Gebäudemetadaten bestimmen. |
| `input_service.py` | HEO-Eingabezustand und ganze Szenarien laden beziehungsweise speichern. |
| `site_lookup.py` | Postleitzahlen in den DG-Standortdateien nachschlagen. |
| `parameter_catalog.py` | DG-Schema und HEO-Darstellungsregeln zum Konfigurator-Katalog verbinden. |
| `form_values.py` | Angezeigte Formularwerte anhand der DG-Feldmetadaten in DG-Typen und -Einheiten zurückübersetzen. |

`validate_inputs(state, buildings, ...)` liefert `ValidationIssue`-Objekte mit
Meldung, Feld und gegebenenfalls Gebäude-ID. Sowohl die Konfiguratorvorschau als
auch `build_inputs` verwenden diese Prüfung. Ohne Konfiguratorzustand werden
Gerätefreigaben und Netzbezug aus den Eingabewerten abgeleitet.

`build_inputs(state, buildings, ...)` liefert die Speicherergebnisse für Config
und Gebäude als Tupel. Bei ungültigen Eingaben wird vor dem Schreiben der
Szenariodateien ein `ValueError` ausgelöst. Die DG-Schemaprüfung verwendet eine
vorübergehende Datei, die anschließend gelöscht wird. Die einzelnen Dateien
werden atomar ersetzt; es gibt keine Transaktion über alle Dateien zusammen.

`input_service.save_heo_scenario` ruft den Builder auf und ergänzt anschließend
die `run.py` über `execution/dg_run_service.py`. Die Vorlage wird in
`execution/run_template.py` gerendert. Die Verwaltung gespeicherter
Szenarioordner liegt zurzeit ebenfalls in `config_service.py`.

Die Konfigurator-Callbacks lesen Dash-Feld-IDs und rufen `form_values.py` auf.
Das Zusammenführen der konvertierten Werte und der Abgleich bearbeiteter
Jahresreihen liegen in `heo/model/configuration.py`. Die Callbacks stellen
Validierungsfehler dar und steuern die Oberfläche.

Die deutschen Feldnamen, Einheiten und Hilfetexte liegen in `heo/display/`.
`parameter_catalog.py` führt sie mit dem geladenen DG-Schema
und den HEO-Standardwerten zusammen.
