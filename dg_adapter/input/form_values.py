# Übersetzt HEO-Formularwerte mithilfe des DG-Feldschemas in Eingabewerte.

from __future__ import annotations

from datetime import date
import re
from typing import Any

from dg_adapter.input.parameter_catalog import field_spec
from heo.display.field_presentation import checkbox_field_value, parameter_number_kind
from heo.display.number_format import parse_german_number
from heo.display.parameter_dialog_layout import CENTRAL_INCLINATION_FIELD_KEYS
from heo.model.annual_series import ANNUAL_KEYS, numbers


# Liest angezeigte Werte in den vom DG-Schema erwarteten Typen und Einheiten.
def parse_dg_field_value(key: str, raw_value: Any, default: Any = None) -> Any:
    value = checkbox_field_value(raw_value)
    if key == "INTERPOLATION_POINTS" and isinstance(value, str) and value.strip():
        try:
            years = numbers(value)
        except (TypeError, ValueError):
            return value  # support_years reports the invalid list in the form.
        return [int(year) for year in years] if all(year.is_integer() for year in years) else value
    if key in ANNUAL_KEYS:
        return numbers(value) if isinstance(value, list) or isinstance(value, str) and value.strip().startswith("[") else [parse_german_number(value, kind="decimal")]
    if key in {
        "HEATING_PERIOD_START", "HEATING_PERIOD_END",
        "COOLING_PERIOD_START", "COOLING_PERIOD_END",
    } and isinstance(value, str):
        try:
            selected_date = date.fromisoformat(value)
        except ValueError:
            match = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.?\s*", value)
            if match is None:
                return default
            try:
                selected_date = date(2021, int(match.group(2)), int(match.group(1)))
            except ValueError:
                return default
        return selected_date.timetuple().tm_yday
    spec = field_spec(key) or {}
    value_type = str(spec.get("value_type") or "")
    default_value = spec.get("default", default)
    scalar_list = value_type == "list" and isinstance(default_value, list) and len(default_value) == 1
    numeric = value_type in {"int", "float", "optional-int", "optional-float"} or scalar_list
    if not numeric:
        return value
    if isinstance(value, str):
        if not value.strip():
            return default
        try:
            parsed = parse_german_number(
                value, kind=parameter_number_kind(spec),
            ) / float(spec.get("display_scale") or 1.0)
        except (TypeError, ValueError, ZeroDivisionError):
            return default
    else:
        try:
            parsed = float(value) / float(spec.get("display_scale") or 1.0)
        except (TypeError, ValueError, ZeroDivisionError):
            return default
    # Übersetzt die Anzeigeeinheit zurück, bevor der DG-Datentyp hergestellt wird.
    parsed *= float(spec.get("display_divisor") or 1.0)
    if key in CENTRAL_INCLINATION_FIELD_KEYS:
        parsed = max(0.0, min(90.0, parsed))
    elif key in {"C_PV__GAMMA", "C_STC__GAMMA"}:
        parsed = max(-180.0, min(180.0, parsed))
    if value_type in {"int", "optional-int"}:
        result = int(round(parsed))
    else:
        result = parsed
    return [result] if scalar_list else result
