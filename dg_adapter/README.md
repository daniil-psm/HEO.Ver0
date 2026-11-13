# Struktur des DG-Adapters

| Ort | Aufgabe |
| --- | --- |
| `input/` | HEO-Eingaben prüfen, DG-Konfiguration und Gebäude-CSV bauen sowie gespeicherte Eingaben lesen. |
| `execution/` | DG-Läufe, Profile, Vergleiche und Fortschritt steuern. |
| `output/` | DG-Ergebnisse lesen, prüfen und für HEO aufbereiten. |
| `shared/` | Szenarionamen, Pfade und den Vergleichsdatenvertrag verwalten. |
| `maintenance/` | Einmalige Wartungs- und Migrationsskripte. |
| `scenarios/` | Gespeicherte Szenarien und Ergebnisdateien. |

Im Paketstamm liegen die Vorlagen `.env.HEO_DEFAULTS` und `.env.PROFILES`.
Aufrufer importieren die jeweils zuständigen Module direkt; `__init__.py`
lädt keine Adapterdienste. Gespeicherte `run.py`-Dateien rufen den
Vergleichslauf über `execution/dg_comparison_service.py` auf.

Die von mehreren Bereichen genutzten Regeln liegen in `shared/`.
`execution/` schreibt Ergebnisbundles über `results_writer.py` und erzeugt
Energieausweise über `certificates.py`. Das Lesen von Variantenmanifesten,
alten Ergebnisbundles und vollständigen Paketen liegt in `results_reader.py`.
Vergleichslauf und Ergebnisleser nutzen denselben Datenvertrag in
`shared/comparison_contract.py`; sie importieren sich nicht gegenseitig.
Szenariovalidierung und das Rendern von `run.py` liegen in
`shared/scenario_names.py` beziehungsweise `execution/run_template.py`.
So können die Szenarioverwaltung und der Laufdienst dieselbe Vorlage nutzen,
ohne sich gegenseitig zu importieren. Aufrufer dieser Funktionen verwenden
ihre zuständigen Module direkt.

Gebäudelogik liegt in `heo/model/buildings.py`, Feldbeschreibungen in
`heo/display/building_fields.py`.

Die beiden Vorlagen und `scenarios/` bleiben am bisherigen Ort, weil
Szenariopfade und gespeicherte Einstellungen darauf verweisen. Die
Profilsteuerung ist unter `execution/PROFILE_CONTROL.md` beschrieben.
