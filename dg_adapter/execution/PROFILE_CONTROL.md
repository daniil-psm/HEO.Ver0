# Profil- und Seedsteuerung

Die Implementierung liegt in `execution/profile_service.py`; die Vorlage
liegt weiter unter `dg_adapter/.env.PROFILES`.

Die Szenarioeinstellungen liegen in `scenarios/<name>/common/heo_seed_control/.env.PROFILES`. Für neue Szenarien wird die Vorlage `dg_adapter/.env.PROFILES` kopiert. Die Datei gehört zum HEO-Adapter; die DG-Modellkonfiguration liegt getrennt in `common/dg_input/.env.CONFIG`.

Standardwerte: `PROFILE_SEED=20261013`, `PROFILE_SEED_MODE=fixed`, `PROFILE_WORKERS=1`, `PROFILE_MODE=generate`. Der Konfigurator bietet „Zufällig“ und „Vorgeben“ an. Bei „Zufällig“ wird bei jedem Optimierungsstart ein neuer ganzzahliger Seed in der szenariospezifischen `.env.PROFILES` gespeichert, bevor der Profil-Fingerprint und die gemeinsame Quartiersvorbereitung berechnet werden. So verwenden die ökonomische und ökologische Optimierung desselben Laufs dieselben Profile. Bei „Vorgeben“ bleibt `PROFILE_SEED` unverändert. Mit einem Profilworker kann ein vorgegebener Seed die erzeugten Profile reproduzieren. Mehrere Worker teilen Zufallszustände, sodass der Seed allein dafür nicht genügt.

Die einmal erzeugten Nachfrage- und Erzeugungsprofile liegen in `common/dg_profiles/`. `common/heo_seed_control/manifest.json` dokumentiert Fingerprint, Seed, Profiloptionen und die gemeinsame Generation; `prepared_scenario.p` hält die vorbereitete Modellinstanz. Ein späterer Lauf des anderen Optimierungsfokus nutzt diese Grundlage, sofern Fingerprint und Generation passen. Bei geänderten Eingaben oder Profiloptionen wird die gemeinsame Grundlage neu erzeugt. Alte Fokusergebnisse gelten dann als veraltet.

## Gespeicherte DG-Nachfrageprofile übernehmen

In `.env.PROFILES` können gesetzt werden:

```dotenv
PROFILE_SEED=20261013
PROFILE_WORKERS=1
PROFILE_MODE=saved
PROFILE_SOURCE=/absoluter/pfad/zum/DG/Ergebnisordner/demands
```

Relative `PROFILE_SOURCE`-Pfade beziehen sich auf den Szenarioordner. Der Adapter prüft die drei CSV-Dateien je Gebäude und die Zeitreihenlängen über die DG-Lader und kopiert gültige Profile nach `common/dg_profiles/demands`. Fehlende oder ungültige Dateien führen zum Abbruch. Hashes der Quelldateien gehen in den Fingerprint ein.

`reuse_common=False` erzwingt eine erneute Vorbereitung. Das Manifest erhält dann eine neue `generation_id`; vorherige Fokusergebnisse werden nicht mit den neuen Profilen verglichen. Pro Fokus wird nur das jeweils aktuelle Ergebnis unter `results/economic/` beziehungsweise `results/ecological/` gespeichert. Historische Runs werden nicht aufbewahrt.
