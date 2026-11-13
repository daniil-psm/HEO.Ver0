# HEO-Modell

| Modul | Aufgabe |
| --- | --- |
| `building_types.py` | Erlaubte Gebäude-, Heiz- und Ladearten; auch vom DG-Validator verwendet. |
| `buildings.py` | Gebäudezustand, Reihenfolge, Bearbeitung, zentral versorgte neue Gebäude und aktivierte Geräte. |
| `building_supply.py` | Zentrale und dezentrale Versorgungsregeln. |
| `devices.py` | Einmalige HEO-Geräteidentitäten und Eigenschaften. |
| `configuration.py` | HEO-Geräteauswahl, gemeinsame Geräteumschaltung, Entwurf, Formularwerte und vorübergehend deaktivierte Grenzwerte verwalten. |
| `site.py` | HEO-Standortmodus, Beschriftung, Zeitzone und wirksamen PV-Albedo-Wert bestimmen. |
| `annual_series.py` | Jahresreihen und Stützjahr-Eingabeart im HEO-Zustand bearbeiten und darstellen. |

Das Einlesen der DG-Standortdateien liegt in `dg_adapter/input/site_lookup.py`.
Die Wahl verfügbarer Ergebnisvarianten liegt in `result_selection.py`.
Die deutsche Gerätebezeichnung wird aus dem Katalog in `devices.py` über
`heo/display/device_labels.py` bereitgestellt.
Die abweichende native DG-Schreibweise wird in
`dg_adapter/shared/device_catalog.py` ergänzt.
HEO-Module verwenden `HEO_CENTRAL_DEVICE_CATALOG` und
`HEO_DECENTRAL_DEVICE_CATALOG`. Die `DG_`-Kataloge entstehen ausschließlich
an der Adaptergrenze.
