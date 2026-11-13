# Konfigurator-Tab

Der Tab enthält den Dash-Bedienzustand, Layouts, Formulare, Callbacks und den
interaktiven Topologie-Renderer. Fachliche HEO-Regeln und Bezeichnungen liegen
in `heo/model/`, `heo/topology/` und `heo/display/`. Geladene DG-Eingabefelder
kommen aus `dg_adapter/input/parameter_catalog.py`. Die Projektansicht wird
gemeinsam mit dem Ergebnisfenster aus `ui/components/project_info.py` genutzt.

| Modul | Aufgabe |
| --- | --- |
| `konfigurator_config.py` | Dash-Bedienzustand anlegen, ergänzen und aus einem Szenario rekonstruieren. |
| `konfigurator_callbacks.py` | Topologie, Auswahl und Navigation steuern. |
| `konfigurator_szenarien_callbacks.py` | Szenarien verwalten sowie Projekt-, Standort- und Wetterdaten bearbeiten. |
| `konfigurator_eingaben_callbacks.py` | Parameter, Jahresreihen, Grenzen und Gebäudefelder bearbeiten. |
| `konfigurator_simulation_callbacks.py` | Eingaben prüfen, Szenarien speichern und Optimierungen ausführen. |
| `konfigurator_projektformular.py` | Projektstart, Standortauswahl und Szenarioladen darstellen. |
| `konfigurator_parameterdialoge.py` | Geräte-, Netz- und Gebäudeparameterdialoge zusammensetzen. |
| `konfigurator_simulationsdialoge.py` | Simulationseinstellungen, Fortschritt und Fehler darstellen. |
| `konfigurator_formfelder.py` | Wiederverwendbare Feld-, Winkel-, Zeitraum- und Gebäudeeingaben rendern. |
| `konfigurator_layout.py` | Fensteraufbau und Startbereich. |
| `konfigurator_parameteruebersicht.py` | Gemeinsame Projektansicht im Konfigurator einbinden. |
| `konfigurator_topologie.py` | Zentrale HEO-Szene als anklickbare Dash-Ansicht rendern. |

`__init__.py` importiert die vier Callback-Module einmal zur Dash-Registrierung.
Funktionsaufrufer importieren direkt aus dem zuständigen Modul. Die
Dialogmodule erzeugen Dash-Komponenten; Feld- und Zustandsregeln liegen in
`heo/model/`, `heo/display/` beziehungsweise `dg_adapter/input/`.
