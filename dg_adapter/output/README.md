# DG-Ergebnisse für HEO

Dieser Ordner enthält die Verarbeitung der DG-Optimierungsergebnisse bis zu
darstellbaren HEO-Daten. Zentrale HEO-Darstellungsregeln liegen in
`heo/display/`; die Oberfläche bleibt in `tabs/` und `ui/`.

| Modul | Aufgabe |
| --- | --- |
| `results_writer.py` | Optimierungsergebnis als JSON-Bundle speichern |
| `results_reader.py` | Varianten, Manifeste und vollständige Ergebnispakete prüfen und laden |
| `demand_profiles.py` | Gebäude-Bedarfsprofile lesen und aggregieren |
| `result_flows.py` | Ergebniscluster und deren Gewichte bereitstellen |
| `component_results.py` | Gebäude- und Wärmenetzwerte berechnen |
| `topology_results.py` | DG-Ergebnisse auf HEO-Topologiedaten abbilden |
| `result_series.py` | Ergebnisreihen und Clustergewichte für Topologie, Sankey und PFC lesen |
| `topology_details.py` | DG-Kennwerte und Ergebniszeilen für Topologieknoten berechnen |
| `sankey_results.py` | Jahresflüsse für HEO-Topologiekanten aggregieren |
| `scenes.py` | DG-Ergebnisse normalisieren und HEO-Ergebnisszene oder Topologiemodell aufbauen |
| `pfc_results.py` | Cluster, Kantenreihen und Frames der Powerflow Card vorbereiten |
| `heo/topology/pfc_model.py` | PFC-Datenmodelle und globale Animationsskala bereitstellen |
| `pfc_profiles.py` | Optimierungs-, Wetter- und Bedarfsprofile für die PFC lesen |
| `pfc_flows.py` | Momentaufnahmen der Energieflüsse berechnen |
| `demand_data.py` | Gespeicherte Bedarfsreihen für Ergebnisdiagramme öffnen |
| `project_info.py` | Projektkontext einschließlich Standort, Laufstandvergleich und Quellhinweis vor dem Rendern aufbereiten |
| `kpi_results.py` | DG-Berichte und Kennzahlen aufbereiten |
| `certificates.py` | Energieausweise finden, erstellen und Seiten rendern |
| `render_pdf_page.ps1` | PDF-Seiten für `certificates.py` unter Windows rendern |

Die Gebäudezuordnung wird beim Laufstart in `execution/dg_project_snapshot.py`
festgehalten und beim Lesen der Ergebnisse verwendet.

`execution/dg_comparison_service.py` steuert Optimierungsläufe. Leser,
Schreiber und Ergebnisberechnungen werden direkt aus `output/` importiert.

Die Topologieszene und das Postprocessing liegen in `heo/topology/`. Der
Ergebnisse-Tab rendert Szenen, Diagramme und Dash-Dialoge.

Die beiden Tab-Aufrufer erzeugen den Projektkontext ausdrücklich mit
`project_info_context(..., run_metadata=...)`. Die gemeinsame UI-Funktion
`project_info_view(context, ...)` erhält den fertigen `ProjectInfoContext`
und führt selbst keine Adapteraufrufe aus.
