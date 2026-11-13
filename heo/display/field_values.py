"""Bereitet Feldwerte, Einheiten, Auswahlmöglichkeiten und Winkel ohne Dash auf."""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from typing import Any

from heo.display.field_presentation import (
    FieldPresentation, parameter_field_presentation, parameter_number_kind,
)
from heo.display.number_format import format_german_number

NUMERIC_VALUE_TYPES = {"int", "float", "optional-int", "optional-float"}
PERIOD_REFERENCE_YEAR = 2021


def readonly_parameter_presentation(
    field: dict[str, Any], value: Any, *, missing: str = "—",
) -> FieldPresentation:
    """Formatiert einen Katalogparameter für statische Formularansichten.

    Zahlen, Prozent-Skalierung, Auswahlwerte, Einheiten und Feldart folgen
    damit denselben Katalogmetadaten wie die editierbaren Parameterdialoge.
    """

    single_value_list = isinstance(value, list) and len(value) == 1
    if single_value_list:
        value = value[0]
    structured_value = isinstance(value, (list, dict))
    value_type = str(field.get("value_type") or "str")
    options = field.get("options") or []
    labels = field.get("option_labels_de") or {}
    # Den sichtbaren Wert mit denselben Zahlen- und Auswahlmetadaten wie im Eingabedialog bilden.
    if value is None or value == "":
        displayed = missing
    elif isinstance(value, bool):
        displayed = "Ja" if value else "Nein"
    elif (
        value_type in NUMERIC_VALUE_TYPES or single_value_list
    ) and isinstance(value, (int, float)):
        displayed = format_german_number(
            value,
            kind=parameter_number_kind(field),
            scale=float(field.get("display_scale") or 1.0),
            divisor=float(field.get("display_divisor") or 1.0),
        )
    elif structured_value:
        displayed = json.dumps(value, ensure_ascii=False)
    else:
        displayed = labels.get(value, labels.get(str(value), str(value)))

    # Listen und Objekte bleiben Textfelder; ihre innere Struktur ist keine einzelne Zahl.
    if structured_value:
        kind = "text"
    elif value_type == "bool" or options or labels:
        kind = "choice"
    elif value_type in NUMERIC_VALUE_TYPES or single_value_list:
        kind = "number"
    else:
        kind = "text"

    return parameter_field_presentation(
        field,
        label=str(field.get("label") or field.get("env_key") or "Parameter"),
        value=displayed,
        kind=kind,
        editable=False,
        help_text=str(field.get("help_text_de") or ""),
        number_kind=parameter_number_kind(field) if kind == "number" else None,
        unit=parameter_unit(field, value),
        numeric_value=(
            float(value) * float(field.get("display_scale") or 1.0)
            / float(field.get("display_divisor") or 1.0)
            if kind == "number" and isinstance(value, (int, float))
            and not isinstance(value, bool) else None
        ),
    )



def parameter_unit(field: dict[str, Any], value: Any = None) -> str | None:
    """Bestimmt die sichtbare Einheit eines Katalogparameters."""

    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if field.get("unit_singular") and field.get("unit_plural"):
        try:
            singular = float(value) == 1.0
        except (TypeError, ValueError):
            singular = False
        unit = str(field["unit_singular"] if singular else field["unit_plural"])
    else:
        unit = str(field.get("unit") or "")
    return None if unit in {"", "–", "-"} else unit



def numeric_angle(value: Any, minimum: float, maximum: float) -> float:
    """Normalisiert einen Winkel für Eingabe und grafische Darstellung."""

    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        number = 0.0
    if not math.isfinite(number):
        number = 0.0
    return max(minimum, min(maximum, number))



def parameter_angle_kind(field: dict[str, Any]) -> str | None:
    """Erkennt Neigung und Ausrichtung anhand der gemeinsamen Feldmetadaten."""

    ui = field.get("ui") if isinstance(field.get("ui"), dict) else {}
    configured = ui.get("angle_kind") or field.get("angle_kind")
    if configured in {"inclination", "orientation"}:
        return str(configured)
    key = str(field.get("input_key") or field.get("env_key") or "").upper()
    if key.endswith("BETA") or key.endswith("BETA_PV"):
        return "inclination"
    if key.endswith("GAMMA") or key.endswith("GAMMA_PV"):
        return "orientation"
    return None



def month_day_from_day_of_year(value: Any) -> str:
    """Formatiert einen DG-Jahrestag als fachliches Datum ohne Jahr."""

    try:
        day = max(1, min(365, int(value)))
    except (TypeError, ValueError):
        day = 1
    selected = date(PERIOD_REFERENCE_YEAR, 1, 1) + timedelta(days=day - 1)
    return selected.strftime("%d.%m.")



def parameter_choice_options(
    field: dict[str, Any], current_value: Any = None,
) -> list[dict[str, Any]]:
    """Löst technische Auswahlwerte und deutsche Labels zentral auf."""

    key = str(field.get("input_key") or field.get("env_key") or "")
    labels = field.get("option_labels_de") or {}
    if key == "CLIMATE_PERIOD":
        values = ["measured_1995_2012", "forecast_2031_2060"]
    elif key == "OPTIMIZATION_FOCUS_MODE":
        values = ["economic", "ecological"]
    else:
        values = list(field.get("options") or [])
        if not values and labels:
            values = [current_value]
    if current_value is not None and current_value not in values:
        values.append(current_value)
    return [
        {"label": str(labels.get(item, labels.get(str(item), item))), "value": item}
        for item in values
    ]



def dependent_panel_hidden(selected_value: Any, required_value: Any) -> bool:
    """Einheitliche Sichtbarkeitsregel für abhängige Formularbereiche."""

    return selected_value != required_value

