# Ergebnis-Tab

Dieser Ordner enthält Dash-Callbacks, Layouts und Renderer. Fachliche Daten
kommen aus `dg_adapter/output/`; HEO-Bezeichnungen und renderunabhängige
Darstellungsregeln liegen in `heo/display/` und `heo/topology/`.

| Modul | Aufgabe im Tab |
| --- | --- |
| `energiesystem_callbacks.py` | Dashboard-Ereignisse, Datenstores und Navigation mit den passenden Renderern verbinden. |
| `energiesystem_layout.py` | Aufbau und Startansicht des Dashboards. |
| `energiesystem_topologie.py` | Ergebnis-, Sankey- und PFC-Szenen samt Dialogen rendern. |
| `energiesystem_bedarfe.py` | Bedarfsreihen als Plotly-Diagramme rendern. |
| `energiesystem_umgebung.py` | Wetterreihen als Plotly-Diagramme rendern. |
| `energiesystem_vergleich.py` | Kennzahlenkarten und Vergleichsdiagramm rendern. |

Referenztopologie und Ergebnisberechnungen werden direkt aus `heo/topology/`
und `dg_adapter/output/` importiert. Im Tab liegen nur Dash-bezogene Module.
Die von Konfigurator und Ergebnissen verwendete Projektansicht liegt in
`ui/components/project_info.py`.
