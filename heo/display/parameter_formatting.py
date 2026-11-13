"""Bereitet HEO-Labels, Einheiten und Hilfetexte für Formularfelder auf."""

from __future__ import annotations

import re
from typing import Any, Mapping

from .parameter_catalog import (
    GROUP_LABELS, PARAMETER_HELP_TEXT_DE, PARAMETER_PRESENTATION,
    PARAMETER_SUFFIX_PRESENTATION, PERCENT_PARAMETER_SUFFIXES, SECTION_PRESENTATION,
)
from .parameter_dialog_layout import parameter_dialog_view


def _humanize(value: str) -> str:
    """Wandelt technische Schlüssel in lesbare Feldbezeichnungen um."""

    return value.replace("__", " · ").replace("_", " ").strip().title()


def _unit_for(field: dict[str, Any]) -> str:
    """Leitet die Anzeigeeinheit aus Parameterschlüssel und Hilfetext ab; unbekannte Einheiten ergeben –."""

    key = str(field["env_key"]).upper()
    text = str(field.get("help_text") or "").lower().replace("²", "^2").replace("³", "^3")
    # Explizite Einheiten im Hilfetext haben Vorrang vor allgemeineren Schlüsselworttreffern.
    explicit_units = (
        (r"€/kw(?:_?th)?/year", "€/kW·a"),
        (r"€/t_?co2", "€/tCO₂"),
        (r"€/mwh(?:_?th)?", "€/MWh"),
        (r"€/kwh", "€/kWh"),
        (r"€/kw(?:_?th)?", "€/kW"),
        (r"€/m\^?3|€/cubic meter", "€/m³"),
        (r"€/m\^?2", "€/m²"),
        (r"€/liter", "€/l"),
        (r"kg/kwh", "kg CO₂/kWh" if "CO2" in key else "kg/kWh"),
        (r"mwh/year", "MWh/a"),
        (r"watt per watthour", "W/Wh"),
        (r"watt per squaremeter|w/m\^?2", "W/m²"),
        (r"kw/m\^?2", "kW/m²"),
        (r"w/\(m\*k\)", "W/(m·K)"),
        (r"j/\(kg\*k\)", "J/(kg·K)"),
        (r"kg/m\^?3", "kg/m³"),
        (r"m\^?2/s", "m²/s"),
        (r"pa/m", "Pa/m"),
        (r"pascal|\(pa\)", "Pa"),
        (r"1/year|per year as a fraction", "1/a"),
        (r"1/h|per hour as a fraction", "1/h"),
    )
    for pattern, unit in explicit_units:
        if re.search(pattern, text):
            return unit
    # Bekannte Parameterschlüssel lösen mehrdeutige oder fehlende Einheitenangaben auf.
    if key == "DISTRICT_AREA":
        return "m²"
    if key == "TIMEZONE":
        return "h"
    if key in {"CLUSTERLENGTH", "DATALENGTH", "TIMERESOLUTION", "DATARESOLUTION"}:
        return "s"
    if key in {"T_SET_MIN_FREE_DAY", "T_HEATLIMIT"}:
        return "°C"
    if key in {"K_PUF", "K_PE"}:
        return "W/(m·K)"
    if "DELTA_T" in key or "T_DIFF" in key:
        return "K"
    if key in {
        "HEATING_PERIOD_START",
        "HEATING_PERIOD_END",
        "COOLING_PERIOD_START",
        "COOLING_PERIOD_END",
    }:
        return "Tag des Jahres"
    if key in {"INTERPOLATION_POINTS", "OBSERVATION_TIME"}:
        return "a"
    if key.startswith("FONTS__SIZES__") or key in {"SIZES__LABEL", "SIZES__LEGEND_TEXT"}:
        return "pt"
    if key.startswith("SIZES__"):
        return "px"
    # Für übrige Katalogfelder die Einheit aus der technischen Beschreibung ableiten.
    if "degree celsius" in text or "degrees celsius" in text or " in celsius" in text:
        return "°C"
    if "in kelvin" in text:
        return "K"
    if "in degrees" in text or "angle" in text and "degree" in text:
        return "°"
    if "square meter" in text or "squaremeter" in text:
        return "m²"
    if "cubic meter" in text:
        return "m³"
    if " in meters" in text or " in meter" in text or "height" in text and "meter" in text:
        return "m"
    if " in liters" in text or " in liter" in text:
        return "l"
    if " in seconds" in text or "resolution in seconds" in text:
        return "s"
    if " in hours" in text:
        return "h"
    if " in years" in text or "lifetime" in text or "life time" in text:
        return "a"
    if " in watt" in text or "(watt)" in text:
        return "W"
    if " in kwh" in text or "capacity in kwh" in text:
        return "kWh"
    if " in kw" in text or "capacity in kw" in text or "potential in kw" in text:
        return "kW"
    if " in %" in text or "percentage (%)" in text:
        return "%"
    return "–"


def _decorate_sections(
    sections: list[dict], help_text_de: dict[str, str] | None = None
) -> list[dict]:
    """Ergänzt Abschnitte und Felder in-place um HEO-Bezeichnungen, Einheiten und Dialogmetadaten."""

    if help_text_de is None:
        help_text_de = PARAMETER_HELP_TEXT_DE
    for section in sections:
        presentation = SECTION_PRESENTATION.get(section["key"], {})
        section["label"] = presentation.get("title", section["class_name"])
        section["description"] = presentation.get("description", "")
        for field in section["fields"]:
            key = str(field["env_key"])
            suffix = key.split("__")[-1]
            explicit = PARAMETER_PRESENTATION.get(key, {})
            suffix_presentation = PARAMETER_SUFFIX_PRESENTATION.get(suffix)
            label = explicit.get("label") or (
                suffix_presentation[0] if suffix_presentation else _humanize(suffix)
            )
            field["label"] = label
            if field.get("additional_model_field") and not explicit.get("label"):
                field["label"] = _humanize(key)
            field["group_label"] = GROUP_LABELS.get(
                field["group"], _humanize(field["group"])
            )
            field["unit"] = explicit["unit"] if "unit" in explicit else _unit_for(field)
            if field["unit"] == "a":
                field["unit_singular"] = "Jahr"
                field["unit_plural"] = "Jahre"
            if (suffix in PERCENT_PARAMETER_SUFFIXES or suffix.startswith("ETA_")
                    or key in {"INTEREST_RATE", "SOLVER_OPTIONS__MIP_GAP"}):
                field["unit"] = (
                    "% der Anfangsinvestition"
                    if suffix in {"COST_OM", "INV_SUBSIDY_RATE", "SUBSIDY_RATE"}
                    else "%"
                )
                field["display_scale"] = 100.0
            else:
                field["display_scale"] = 1.0
            # Anzeigeeinheiten ändern weder den DG-Wert noch dessen Datentyp.
            field["display_divisor"] = explicit.get("display_divisor", 1.0)
            if "display_number_kind" in explicit:
                field["display_number_kind"] = explicit["display_number_kind"]
            field["help_text_de"] = explicit.get("help_text_de") or help_text_de.get(key) or (
                suffix_presentation[1]
                if suffix_presentation
                else field.get("help_text") or "Für diesen Modellparameter ist noch keine technische Erläuterung hinterlegt."
            )
            try:
                field["konfigurator_view"] = parameter_dialog_view(key)
            except KeyError:
                # Neue DG-Modellfelder bleiben im erweiterten Bereich bearbeitbar.
                field["konfigurator_view"] = "more"
            field["option_labels_de"] = explicit.get("option_labels", {})
    return sections


def device_parameter_help_texts(
    central_catalog: Mapping[str, Mapping[str, Any]],
    decentral_catalog: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    """Baut deutsche Hilfetexte für die vom DG-Katalog gelieferten Gerätekennungen."""

    help_texts: dict[str, str] = {}
    for _prefix, _catalog, _scope in (
        ("C", central_catalog, "zentralen Anlagen des Quartiers"),
        ("D", decentral_catalog, "dezentralen Anlagen der Gebäude"),
    ):
        for _code, _metadata in _catalog.items():
            _device_help = (
                f"Zusammengefasster Datensatz für {_metadata['full_name']} bei den {_scope}. "
                "Enthält die technischen Kennwerte und wirtschaftlichen Annahmen, die bei Auslegung und Betrieb dieser Komponente verwendet werden."
            )
            help_texts[f"{_prefix}_{_code}"] = _device_help
            if _metadata.get("dg_code"):
                help_texts[f"{_prefix}_{_metadata['dg_code']}"] = _device_help
    return help_texts
