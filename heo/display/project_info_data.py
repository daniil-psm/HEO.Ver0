"""Bereitet HEO-Projekt-, Gebäude- und Geräteinformationen für Ergebnisansichten auf."""

from __future__ import annotations

from typing import Any, TypedDict

from heo.model.devices import HEO_DECENTRAL_DEVICE_CATALOG, decentral_device_components
from heo.display.device_labels import central_device_abbreviation, central_device_name
from heo.display.building_fields import BUILDING_PARAMETER_FIELDS, BUILDING_PARAMETER_FIELD_BY_KEY
from heo.display.parameter_dialog_layout import split_parameter_dialog_fields
from heo.display.units import building_unit_key
from heo.model.buildings import active_decentral_devices
from heo.model.site import location_mode_from_state
from heo.display.parameter_catalog import (
    ECO_MICROGRID_FIELD_KEYS, ECO_PROJECT_FIELD_KEYS, ECO_SIMULATION_FIELD_KEYS,
    MICROGRID_CONFIG_SECTION_KEYS, SECTION_TITLES,
)

class ProjectInfoContext(TypedDict):
    """Vorbereitete Konfiguration, Parameterabschnitte, Gebäude und optionale TRY-Referenzstadt."""

    weather_data: dict | None
    buildings: list[dict]
    sections: dict[str, Any]
    source_label: str
    source_note: str


# Ökonomische Felder je dezentraler Komponente; Konfigurator und Ergebnisansicht teilen diese Zuordnung.
DECENTRAL_ECO_FIELDS = {
    "BOI": ("PRICE_SUPPLY_GAS", "CO2_GAS", "CO2_TAX"),
    "GHP": ("PRICE_SUPPLY_GAS", "CO2_GAS", "CO2_TAX"),
    "CHP": ("PRICE_SUPPLY_GAS", "CO2_GAS", "CO2_TAX"),
    "BHP": ("PRICE_BIOMASS", "CO2_BIOM", "CO2_TAX"),
    "BBOI": ("PRICE_BIOMASS", "CO2_BIOM", "CO2_TAX"),
    "OHP": ("PRICE_OIL", "CO2_OIL", "CO2_TAX"),
    "OBOI": ("PRICE_OIL", "CO2_OIL", "CO2_TAX"),
    "H2BOI": ("PRICE_HYDROGEN", "CO2_HYDROGEN", "CO2_TAX"),
    "H2HP": ("PRICE_HYDROGEN", "CO2_HYDROGEN", "CO2_TAX"),
    "FC": ("PRICE_HYDROGEN", "CO2_HYDROGEN", "CO2_TAX"),
    "DH": ("PRICE_DISTRICT_HEAT", "CO2_DISTRICT_HEAT", "CO2_TAX"),
    "EV": ("PRICE_GASOLINE_LITER",),
}

def format_project_number(value: int | float | None) -> str:
    """Formatiert einen Projektwert mit deutschem Dezimalkomma."""

    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = str(int(number)) if number.is_integer() else f"{number:.6g}"
    return text.replace(".", ",")

def config_changed(section: dict, values: dict, defaults: dict) -> bool:
    """Prüft, ob ein Konfigurationsabschnitt vom DG-Standard abweicht."""

    return any(
        values.get(field.get("input_key") or field["env_key"], field.get("default"))
        != defaults.get(field.get("input_key") or field["env_key"], field.get("default"))
        for field in section.get("fields", [])
    )

def selected_key(items: list[dict], requested: Any) -> str | None:
    """Wählt einen vorhandenen Detaildatensatz oder den ersten Eintrag."""

    keys = [str(item["key"]) for item in items]
    requested_key = str(requested) if requested is not None else None
    return requested_key if requested_key in keys else (keys[0] if keys else None)

def central_device_items(
    section: dict, values: dict, defaults: dict, weather_data: dict | None,
) -> list[dict]:
    """Stellt aktive zentrale Anlagen mit ihren Parameterfeldern zusammen."""

    groups: list[str] = []
    for field in section["fields"]:
        group = str(field.get("group") or "")
        if group and group not in groups:
            groups.append(group)
    items = []
    for group in groups:
        fields = [field for field in section["fields"] if field.get("group") == group]
        enabled = next(
            (field for field in fields if field["env_key"].endswith("__FEASIBLE")),
            None,
        )
        if enabled is None:
            continue
        enabled_key = enabled.get("input_key") or enabled["env_key"]
        if not bool(values.get(enabled_key, defaults.get(enabled_key, enabled.get("default")))):
            continue
        parameter_fields = [field for field in fields if field is not enabled]
        main_fields, more_fields = split_parameter_dialog_fields(parameter_fields)
        name = central_device_name(group)
        items.append({
            "key": group,
            "label": name,
            "subtitle": central_device_abbreviation(group),
            "title": name,
            "description": "Zentral im Microgrid aktivierte Anlage.",
            "main_fields": main_fields,
            "more_fields": more_fields,
            "values": values,
            "defaults": defaults,
            "weather_data": weather_data,
        })
    return items

def _local_device_fields(slot: str, code: str) -> list[dict]:
    """Liefert Gebäudeparameter für eine dezentrale Komponente."""

    keys = {
        "pv": ("f_PV1", "f_PV2", "beta_PV", "gamma_PV"),
        "stc": ("f_STC", "beta_PV", "gamma_PV"),
        "battery": ("f_BAT",),
        "heat_storage": ("f_TES",),
        "ev": ("ev_charging",),
    }.get(slot, ())
    return [BUILDING_PARAMETER_FIELD_BY_KEY[key] for key in keys]

def decentral_device_items(
    section: dict,
    buildings: list[dict],
    values: dict,
    defaults: dict,
    weather_data: dict | None,
    eco_fields: dict[str, dict],
) -> list[dict]:
    """Stellt aktive dezentrale Anlagen und ihre Parameter zusammen."""

    items = []
    for row in buildings:
        uid = int(row.get("uid", row.get("id", 0)))
        building_label = str(row.get("name") or f"Gebäude {row.get('id', uid)}")
        for slot, code in active_decentral_devices(row):
            config_codes = decentral_device_components(code)
            prefixes = tuple(f"D_{item}__" for item in config_codes)
            config_fields = [
                field for field in section["fields"]
                if str(field.get("env_key") or "").startswith(prefixes)
            ]
            economic_fields = [
                eco_fields[key] for key in DECENTRAL_ECO_FIELDS.get(code, ())
                if key in eco_fields
            ]
            seen: set[str] = set()
            advanced_fields = []
            for field in (*config_fields, *economic_fields):
                key = str(field.get("input_key") or field["env_key"])
                if key not in seen:
                    seen.add(key)
                    advanced_fields.append(field)
            metadata = HEO_DECENTRAL_DEVICE_CATALOG.get(code, {})
            items.append({
                "key": f"{uid}:{slot}:{code}",
                "label": (
                    f"Gebäude {row.get('id', uid)} · {building_label}"
                    if row.get("name") else building_label
                ),
                "subtitle": metadata.get("full_name") or code,
                "title": metadata.get("full_name") or code,
                "description": f"{building_label} · dezentrale Komponente",
                "main_fields": _local_device_fields(slot, code),
                "more_fields": advanced_fields,
                "values": {**values, **row},
                "defaults": defaults,
                "weather_data": weather_data,
            })
    return items

def building_items(buildings: list[dict]) -> list[dict]:
    """Stellt alle Gebäude als auswählbare Projektdetails zusammen."""

    items = []
    for row in buildings:
        uid = int(row.get("uid", row.get("id", 0)))
        category = row.get("category")
        applicable = [
            {**field, "parameter_key": building_unit_key(uid, field['input_key'])}
            for field in BUILDING_PARAMETER_FIELDS
            if not (
                field["input_key"] == "retrofit"
                and category not in {"residential", "non_residential", "mixed"}
            ) and not (
                field["input_key"] == "construction_type"
                and category not in {"non_residential", "mixed"}
            )
        ]
        title = str(row.get("name") or f"Gebäude {row.get('id', uid)}")
        main_fields, more_fields = split_parameter_dialog_fields(applicable)
        items.append({
            "key": str(uid),
            "label": title,
            "subtitle": str(row.get("building") or "Gebäudetyp offen"),
            "title": title,
            "description": f"Gebäude {row.get('id', uid)} · Gebäude-CSV",
            "status": "Vollständig" if category and row.get("building") else "Auswahl offen",
            "main_fields": main_fields,
            "more_fields": more_fields,
            "values": row,
            "defaults": {},
            "weather_data": None,
        })
    return items

def _merged_section(
    section: dict,
    extra_fields: list[dict],
    *,
    key: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> dict:
    """Ergänzt einen Parameterabschnitt um weitere Felder und HEO-Texte."""

    merged = dict(section)
    merged["fields"] = [*section.get("fields", []), *extra_fields]
    if key is not None:
        merged["key"] = key
    if title is not None:
        merged["class_name"] = title
    if description is not None:
        merged["description"] = description
    return merged


def build_project_sections(
    config_state: dict,
    sections: list[dict],
    *,
    reference_city: str | None = None,
) -> dict:
    """Liefert Projekt-, Gebäude-, Microgrid- und Simulationsabschnitte für die Projektinformation.

    reference_city ergänzt bei deutschen Standorten die bereits aufgelöste TRY-Referenzstadt.
    """

    values = config_state.get("values", {})
    defaults = config_state.get("defaults", {})
    section_by_key = {section["key"]: section for section in sections}
    eco_section = section_by_key["eco"]
    eco_fields = {field["env_key"]: field for field in eco_section["fields"]}
    location_section = section_by_key["location"]
    location_fields = {
        field["env_key"]: field for field in location_section["fields"]
    }
    # Simulations- und Anschlussfelder werden in eigene Abschnitte übernommen.
    simulation_location_fields = [location_fields["TRYYEAR"]]
    building_connection_fields = [
        location_fields["ENABLE_BUILDINGMAX_W"],
        location_fields["BUILDINGMAX_W"],
    ]
    microgrid_frame_fields = [
        location_fields["ENABLE_TRAFOMAX_W"],
        location_fields["TRAFOMAX_W"],
    ]
    delegated_location_keys = {
        field["env_key"]
        for field in (
            simulation_location_fields
            + building_connection_fields
            + microgrid_frame_fields
        )
    }
    # Standortfelder und ihre Beschriftung folgen dem gewählten Wetter-/Standortmodus.
    mode = location_mode_from_state(config_state)
    mode_labels = {"pidula": "Pidula (Saaremaa)", "germany": "Deutschland (PLZ)",
                   "other": "Sonstiger Standort (EPW-Upload)"}
    display_values = {**values, "WEATHER_MODE": mode_labels[mode]}
    display_defaults = {**defaults, "WEATHER_MODE": mode_labels[mode]}
    mode_field = {
        **location_fields["LOCATION_NAME"], "env_key": "WEATHER_MODE",
        "input_key": "WEATHER_MODE", "label": "Wettermodus",
        "default": mode_labels[mode], "konfigurator_view": "main", "help_text_de": "",
    }
    selected_location_keys = {
        "pidula": {"LOCATION_NAME", "WEATHER_FILE"},
        "germany": {"ZIP"},
        "other": {"LOCATION_NAME", "WEATHER_FILE"},
    }[mode]
    selected_location_labels = {
        "LOCATION_NAME": "Standort" if mode == "pidula" else "Standortname",
        "ZIP": "Postleitzahl", "WEATHER_FILE": "Wetterdatei",
    }
    reference_field = None
    if mode == "germany":
        city = reference_city
        if city:
            display_values["TRY_REFERENCE_CITY"] = city
            display_defaults["TRY_REFERENCE_CITY"] = city
            reference_field = {
                **location_fields["LOCATION_NAME"], "env_key": "TRY_REFERENCE_CITY",
                "input_key": "TRY_REFERENCE_CITY", "label": "TRY-Referenzstadt",
                "default": city, "konfigurator_view": "main", "help_text_de": "",
            }
    project_location_fields = []
    for field in location_section["fields"]:
        if field["env_key"] in delegated_location_keys:
            continue
        if field["env_key"] == "SCENARIO_NAME":
            project_location_fields.append(field)
            project_location_fields.append(mode_field)
            continue
        if field["env_key"] in {"USE_GERMAN_ZIP", "TRYTYPE"}:
            project_location_fields.append({
                **field,
                "label": "Deutsche PLZ verwenden" if field["env_key"] == "USE_GERMAN_ZIP"
                else "TRY-Typ",
            })
            continue
        if field["env_key"] in {"LOCATION_NAME", "ZIP", "WEATHER_FILE"}:
            if field["env_key"] not in selected_location_keys:
                continue
            field = {
                **field,
                "label": selected_location_labels[field["env_key"]],
                "konfigurator_view": "main",
            }
            if field["env_key"] == "LOCATION_NAME":
                field["help_text_de"] = (
                    "Ausgewählter Projektstandort."
                    if mode == "pidula" else "Name des Standorts der hochgeladenen EPW-Datei."
                )
        project_location_fields.append(field)
        if field["env_key"] == "ZIP" and reference_field is not None:
            project_location_fields.append(reference_field)
    project_location_fields.append(location_fields["DISTRICT_AREA"])
    # Die verbleibenden Standortfelder und wirtschaftlichen Rahmendaten bilden den Projektabschnitt.
    project_section = _merged_section(
        {**location_section, "fields": project_location_fields},
        [eco_fields[key] for key in ECO_PROJECT_FIELD_KEYS],
        title=SECTION_TITLES["location"],
        description="Standort-, Klima- und wirtschaftliche Projektrahmendaten.",
    )
    # Die Fachabschnitte teilen dieselben Katalogfelder und behalten ihre ursprünglichen Werte.
    simulation_sections = [
        _merged_section(
            section_by_key["time"],
            simulation_location_fields + [
                eco_fields[key]
                for key in ECO_SIMULATION_FIELD_KEYS
                if key != "OPTIMIZATION_FOCUS"
            ],
        ),
        section_by_key["ehdo"],
        section_by_key["pyomo"],
    ]
    building_connection = _merged_section(
        {"fields": [], "key": "building_connection"},
        building_connection_fields,
        key="building_connection",
        title=SECTION_TITLES["building_connection"],
        description="Leistungsgrenze am Anschlusspunkt jedes Gebäudes.",
    )
    building_sections = [
        section_by_key["calendar"],
        section_by_key["design_building"],
        building_connection,
    ]
    # Microgrid-Kosten und Netzgrenze werden getrennt von den Gebäudeanschlüssen angeboten.
    microgrid_economics = _merged_section(
        {"fields": [], "key": "microgrid_economics"},
        [eco_fields[key] for key in ECO_MICROGRID_FIELD_KEYS],
        key="microgrid_economics",
        title=SECTION_TITLES["microgrid_economics"],
        description=(
            "Bezugs- und Einspeisepreise sowie ökologische Kennwerte des Microgrids."
        ),
    )
    heatgrid, central = (
        section_by_key[key] for key in MICROGRID_CONFIG_SECTION_KEYS
    )
    microgrid_frame = _merged_section(
        {"fields": [], "key": "microgrid_frame"},
        microgrid_frame_fields,
        key="microgrid_frame",
        title=SECTION_TITLES["microgrid_frame"],
        description="Leistungsgrenze des Netzanschlusspunkts.",
    )
    return {
        "values": values,
        "defaults": defaults,
        "display_values": display_values,
        "display_defaults": display_defaults,
        "project_section": project_section,
        "simulation_sections": simulation_sections,
        "building_sections": building_sections,
        "microgrid_frame": microgrid_frame,
        "heatgrid": heatgrid,
        "central": central,
        "microgrid_economics": microgrid_economics,
        "section_by_key": section_by_key,
        "eco_fields": eco_fields,
    }
