# Zentrale HEO-Topologie

| Modul | Aufgabe |
| --- | --- |
| `definitions.py` | Energieträger, Farben, Geräteslots und Auswahlregeln. |
| `model.py` | Fachliche Knoten, Kanten, Komponentenports und Rasterdaten. |
| `sizing.py` | Responsive Größenregeln für Knoten und Gebäude. |
| `geometry.py` | Allgemeine Geometrie, Ports und Pfadgrundformen. |
| `building.py` | Gebäudeanschlüsse, Kandidaten, Ringplätze und dezentrale Badges. |
| `labels.py` | Vollnamen, Umbrüche und Kürzel der Topologieknoten. |
| `layout.py` | Raster, Slots, Gebäudeplätze, Pillengrenzen und Plus-Positionen. |
| `nodes.py` | Sichtbare Knoten und Pillen aus der aufgelösten Rastergeometrie. |
| `routing.py` | Korridore und konkrete Pfadformen für Kanten. |
| `edges.py` | Semantische Kanten mit Ports und fertigen SVG-Pfaden. |
| `core.py` | Setzt Gebäude, Layout, Knoten und Kanten zur gemeinsamen Szene zusammen. |
| `postprocessing.py` | Baut aus normalisierten Ergebnisdaten die HEO-Ergebnisszene. |
| `scene_storage.py` | PFC-Ergebnisszenen für den Dash-Store serialisieren und wiederherstellen. |
| `pfc_model.py` | PFC-Frames, Momentaufnahmen und Animationsskala beschreiben. |

`core.py` ist der Einstiegspunkt für Konfigurator und Ergebnisse. Seine
Abhängigkeiten verlaufen von Fachmodell und allgemeinen Geometrieregeln über
Gebäude, Layout und Knoten zu den Kanten. Tabs und UI importieren benötigte
Definitionen direkt aus ihrem jeweiligen Modul; sie berechnen keine eigene
HEO-Topologie.

`H2BOI` ist im DG ausschließlich ein Gebäudegerät. Die HEO-Szene zeigt es
am Gebäude beziehungsweise als Teil der hybriden Gebäudeheizung `H2HP`;
ein zentraler `H2BOI`-Knoten und eine Kante zum Wärmenetz werden nicht erzeugt.
Der externe Gasbezug heißt in der Szene einheitlich `GAS_IMPORT`. Der Knoten
`GAS_BUS` bezeichnet dagegen den Gasbus innerhalb des dargestellten Systems.
`dg_adapter/output/topology_results.py` normalisiert rohe DG-Ergebnisse für
`postprocessing.py`. `dg_adapter/output/scenes.py` verbindet diese Module
für rohe DG-Ergebnisse. `tabs/tab_3_ergebnisse/energiesystem_topologie.py`
rendert die Szene und ihre Dialoge in Dash.

Die bestätigte Gesamtansicht behält ihre Halbzeilenanordnung und die
SAB-/H2-BHKW-Kantenkreuzungen. Beim Hover über eine Kante graut die UI die
anderen Kanten aus. Der Modulzuschnitt verändert weder Szene noch Pfade:
fünf repräsentative Szenen wurden vor und nach dem Aufteilen vollständig
verglichen. Die visuelle Prüfung der Teilansichten ist noch offen.
