# Übersetzt HEO-Gerätemetadaten in native DG-Codes an der Adaptergrenze.

from __future__ import annotations

from heo.model.devices import (
    HEATER_SYSTEM_PARTS, HEO_CENTRAL_DEVICE_CATALOG, HEO_DECENTRAL_DEVICE_CATALOG,
    building_heater_parts, decentral_device_components,
    normalize_building_heater, normalize_central_device_code,
)
from heo.display.device_labels import (
    catalog_display_name, central_device_abbreviation, decentral_device_abbreviation,
)

# DG verwendet für die Erdsonden-Wärmepumpe eine abweichende Schreibweise.
DG_NATIVE_CENTRAL_CODES = {"GROUNDHP": "GroundHP"}
DG_CENTRAL_DEVICE_CATALOG = {
    code: {**metadata, "dg_code": DG_NATIVE_CENTRAL_CODES.get(code, code)}
    for code, metadata in HEO_CENTRAL_DEVICE_CATALOG.items()
}
DG_DECENTRAL_DEVICE_CATALOG = {
    code: dict(metadata) for code, metadata in HEO_DECENTRAL_DEVICE_CATALOG.items()
}


# Liefert DG-Metadaten einschließlich des nativen Codes.
def central_device_metadata(code: str):
    return DG_CENTRAL_DEVICE_CATALOG.get(normalize_central_device_code(code))
