# Verbindet das DG-Eingabeschema mit den zentralen HEO-Darstellungsregeln.

from __future__ import annotations

from dg_adapter.shared.device_catalog import DG_CENTRAL_DEVICE_CATALOG, DG_DECENTRAL_DEVICE_CATALOG
from dg_adapter.input.config_service import DGConfigError
from dg_adapter.input.input_service import load_heo_input_state
from heo.display.parameter_catalog import (
    PROJECT_SECTION_PRESENTATION,
    BUILDING_SECTION_PRESENTATION,
    MICROGRID_SECTION_PRESENTATION,
    SIMULATION_SECTION_PRESENTATION,
    MICROGRID_CONFIG_SECTION_KEYS,
    SIMULATION_CONFIG_SECTION_KEYS,
    ADVANCED_CONFIG_SECTION_KEYS,
    ECO_SIMULATION_FIELD_KEYS,
    ECO_MICROGRID_FIELD_KEYS,
    BUILDING_CONFIG_SECTION_KEYS,
    ECO_PROJECT_FIELD_KEYS,
    BUILDING_CSV_SECTION,
    PROJECT_LOAD_SECTION,
    SIMULATION_CONFIG_SECTION,
    BUILDING_GROUP_SECTION,
    MICROGRID_GROUP_SECTION,
    ADVANCED_CONFIG_SECTION,
    GROUP_LABELS,
    PARAMETER_PRESENTATION,
    PARAMETER_SUFFIX_PRESENTATION,
    PERCENT_PARAMETER_SUFFIXES,
    SECTION_PRESENTATION,
    PARAMETER_HELP_TEXT_DE as _BASE_PARAMETER_HELP_TEXT_DE,
    _config_navigation_sections,
)
from heo.display.parameter_formatting import (
    _humanize, _unit_for, _decorate_sections as _format_sections,
    device_parameter_help_texts,
)
from heo.display.parameter_dialog_layout import parameter_dialog_view


# Ergänzt die HEO-Hilfetexte um Gerätekennungen des aktuellen DG-Katalogs.
PARAMETER_HELP_TEXT_DE = {
    **_BASE_PARAMETER_HELP_TEXT_DE,
    **device_parameter_help_texts(DG_CENTRAL_DEVICE_CATALOG, DG_DECENTRAL_DEVICE_CATALOG),
}


# Verknüpft geladene DG-Felder mit HEO-Namen, Einheiten und Dialogbereichen.
def _decorate_sections(sections: list[dict]) -> list[dict]:
    return _format_sections(sections, help_text_de=PARAMETER_HELP_TEXT_DE)

try:
    HEO_INPUT_SECTIONS, DEFAULT_HEO_INPUT_STATE = load_heo_input_state()
    HEO_INPUT_SECTIONS = _decorate_sections(HEO_INPUT_SECTIONS)
    HEO_INPUT_LOAD_ERROR = None
except DGConfigError as exc:
    HEO_INPUT_SECTIONS = []
    HEO_INPUT_LOAD_ERROR = str(exc)
    DEFAULT_HEO_INPUT_STATE = {
        "values": {},
        "defaults": {},
        "saved_values": {},
        "overrides": [],
        "config_path": None,
        "config_exists": False,
        "load_error": HEO_INPUT_LOAD_ERROR,
        "location_mode": "pidula",
        "custom_location_name": "",
        "model": "heo-input-v1",
    }

HEO_INPUT_SECTION_BY_KEY = {
    section["key"]: section for section in HEO_INPUT_SECTIONS
}


HEO_INPUT_NAVIGATION_SECTIONS = _config_navigation_sections()
DEFAULT_HEO_INPUT_SECTION = (
    HEO_INPUT_SECTIONS[0]["key"] if HEO_INPUT_SECTIONS else "location"
)
DEFAULT_HEO_INPUT_VIEW_SECTION = PROJECT_LOAD_SECTION

# Findet die mit HEO-Anzeigenamen dekorierten Metadaten eines Eingabefelds.
def field_spec(env_key: str) -> dict | None:
    for section in HEO_INPUT_SECTION_BY_KEY.values():
        for field in section.get("fields", []):
            if field.get("env_key") == env_key or field.get("input_key") == env_key:
                return field
    return None


# Liefert die Felder eines DG-Eingabeabschnitts in Katalogreihenfolge.
def fields_for_section(section_key: str) -> list[dict]:
    return list(HEO_INPUT_SECTION_BY_KEY.get(section_key, {}).get("fields", []))


# Liefert die Parameter eines Zentralgeräts ohne seinen Aktivierungsschalter.
def fields_for_device(code: str) -> list[dict]:
    prefix = f"C_{code}__"
    return [
        field for field in fields_for_section("central")
        if str(field.get("env_key", "")).startswith(prefix)
        and not str(field.get("env_key", "")).endswith("__FEASIBLE")
    ]


# Löst eine geordnete Folge von Feldschlüsseln in vorhandene Feldmetadaten auf.
def fields_by_keys(keys: tuple[str, ...] | list[str]) -> list[dict]:
    result = []
    for key in keys:
        spec = field_spec(key)
        if spec is not None:
            result.append(spec)
    return result
