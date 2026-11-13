"""Metadaten für HEO-Gebäudeformulare und statische Gebäudeansichten."""

from __future__ import annotations

from typing import Any
from heo.model.buildings import BUILDING_CATEGORIES
from heo.model.building_types import BUILDING_TYPES, EV_CHARGING_TYPES
from heo.model.devices import decentral_device_codes
from heo.display.device_labels import (
    building_category_label, building_heater_label, building_type_label, ev_charging_label,
)
from heo.display.parameter_dialog_layout import parameter_dialog_view

def _building_field(
    key: str,
    label: str,
    value_type: str,
    *,
    unit: str = "",
    options: tuple[Any, ...] = (),
    labels: dict[Any, str] | None = None,
    display_scale: float = 1.0,
    angle_kind: str | None = None,
) -> dict[str, Any]:
    """Erzeugt Metadaten für Gebäudeformulare und statische Detailansichten."""

    field = {
        "env_key": key,
        "input_key": key,
        "label": label,
        "value_type": value_type,
        "unit": unit,
        "options": list(options),
        "option_labels_de": dict(labels or {}),
        "konfigurator_view": parameter_dialog_view(key),
        "display_scale": display_scale,
        "help_text_de": "",
    }
    if angle_kind:
        field["angle_kind"] = angle_kind
    return field


BUILDING_PARAMETER_FIELDS = (
    _building_field("category", "Nutzungsart", "str", options=BUILDING_CATEGORIES, labels={category: building_category_label(category) for category in BUILDING_CATEGORIES},),
    _building_field("building", "Gebäudetyp", "str", options=BUILDING_TYPES, labels={code: building_type_label(code) for code in BUILDING_TYPES},),
    _building_field("year", "Baujahr", "int"),
    _building_field("area", "Wohn-/Nutzfläche", "float", unit="m²"),
    _building_field("heater", "Heizsystem", "str", options=("heat_grid", *decentral_device_codes("heater")), labels={code: building_heater_label(code) for code in ("heat_grid", *decentral_device_codes("heater"))},),
    _building_field("retrofit", "Sanierungszustand", "int", options=(0, 1, 2), labels={0: "0 · Bestand", 1: "1 · Teilsaniert", 2: "2 · Saniert"},),
    _building_field("construction_type", "Bauweise", "int", options=(0, 1, 2), labels={0: "Leicht", 1: "Mittel", 2: "Schwer"},),
    _building_field("night_setback", "Nachtabsenkung", "bool"),
    _building_field("cooling", "Kühlung", "bool"),
    _building_field("dhw", "Dezentrale Warmwasserbereitung", "bool"),
    _building_field("EV", "E-Auto-Anteil", "float", unit="%", display_scale=100.0),
)

DECENTRAL_BUILDING_PARAMETER_FIELDS = (
    _building_field("beta_PV", "PV-/ST-Neigungswinkel β", "float", unit="°", angle_kind="inclination",),
    _building_field("gamma_PV", "PV-/ST-Ausrichtung γ", "float", unit="°", angle_kind="orientation",),
    _building_field("f_PV1", "PV-Dachanteil 1", "float", unit="%", display_scale=100.0),
    _building_field("f_PV2", "PV-Dachanteil 2", "float", unit="%", display_scale=100.0),
    _building_field("f_STC", "Solarthermie-Dachanteil", "float", unit="%", display_scale=100.0),
    _building_field("f_BAT", "Batteriefaktor", "float", unit="Wh/WPV"),
    _building_field("f_TES", "Speicherfaktor", "float", unit="l/kW"),
    _building_field("ev_charging", "Ladeverhalten", "str", options=EV_CHARGING_TYPES, labels={mode: ev_charging_label(mode) for mode in EV_CHARGING_TYPES},),
)
BUILDING_PARAMETER_FIELD_BY_KEY = {
    field["input_key"]: field
    for field in (*BUILDING_PARAMETER_FIELDS, *DECENTRAL_BUILDING_PARAMETER_FIELDS)
}

# Felder, deren freie Texteingaben im Gebäudedialog als Zahlen gelesen werden.
# Dropdowns wie `retrofit` und `construction_type` werden separat verarbeitet.
BUILDING_INTEGER_INPUT_FIELDS = {"year"}
BUILDING_DECIMAL_INPUT_FIELDS = {
    "area", "f_PV1", "f_PV2", "f_STC", "f_BAT", "f_TES", "EV", "beta_PV", "gamma_PV",
}


