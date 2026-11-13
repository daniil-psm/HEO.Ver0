# DG-Ausführung

| Modul | Aufgabe |
| --- | --- |
| `profile_service.py` | Profiloptionen, Seedwahl und Nachfrageprofile verwalten. |
| `run_template.py` | `run.py` aus der Vorlage mit geprüftem Szenarionamen rendern. |
| `dg_run_service.py` | Szenario-Startskripte atomar speichern und Vorgänger sichern. |
| `profile_fingerprint.py` | Cache-Schlüssel aus Eingaben, Wetter, DG-Quellen und Profiloptionen berechnen. |
| `dg_connector.py` | Szenariokontext und DG-Datenhandler herstellen. |
| `dg_model_preparation.py` | DG-Modell vorbereiten und finalisieren. |
| `dg_comparison_service.py` | Ökonomische und ökologische Varianten vorbereiten, ausführen und ihre Manifeste schreiben. |
| `dg_simulation_service.py` | Simulation starten, beobachten und stoppen. |
| `dg_progress_service.py` | Fortschritt aus Laufdaten ableiten. |
| `dg_project_snapshot.py` | Projektzustand beim Laufstart sichern. |

`PROFILE_CONTROL.md` beschreibt die Profilvorlage im Paketstamm und die
Seedsteuerung pro Szenario. Aufrufer verwenden die Module in diesem Ordner.
