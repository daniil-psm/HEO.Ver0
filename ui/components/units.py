"""Gemeinsame Anzeigeadapter für Einheiten in Formularen und Ergebnissen."""

from __future__ import annotations

import json
import math
from typing import Any

from dash import dcc, html

from heo.display.number_format import parse_german_number
from heo.display.units import unit_choices, unit_display


def unit_attributes(key: str, unit: str | None, value: float | None = None) -> dict:
    """Beschreibt die Anzeige unabhängig von Tab, Raster und Fensterposition."""

    if not key:
        return {}
    unit = unit or ""
    data = {"key": key, "unit": unit, "choices": unit_choices(unit)}
    if value is not None and math.isfinite(value):
        data["value"] = value
    return {"data-unit-field": json.dumps(data, ensure_ascii=False)}


def selectable_unit(unit: str, *, class_name: str = "konfig-unit") -> Any:
    """Rendert das aktive Feld als Anker einer frei schwebenden Kandidatenauswahl."""

    selectable = len(unit_choices(unit)) > 1
    if not selectable:
        return html.Span(unit, className=class_name)
    return html.Button(
        unit, type="button", className=f"{class_name} heo-unit-button",
        title="Einheit ändern", **{
            "aria-label": f"Einheit ändern: {unit}",
            "aria-haspopup": "listbox", "aria-expanded": "false",
        },
    )


def unit_editor_inputs(control: Any, unit: str) -> Any:
    """Ergänzt Anzeigeeingaben; bestehende Callback-IDs behalten ihre Basiseinheit.

    Erst eine bestätigte Bearbeitung schreibt über den Browseradapter zurück.
    Dadurch können Rundung und reine Einheitenwechsel keine Modellwerte ändern.
    """

    if isinstance(control, dcc.Input):
        props = dict(control.to_plotly_json()["props"])
        if not props.get("id") or props.get("type") not in {None, "text", "number"}:
            return control
        try:
            number = parse_german_number(props.get("value"), kind="decimal")
        except (TypeError, ValueError):
            number = None
        displayed = unit_display(number, unit)[0] if number is not None else str(props.get("value") or "")
        if "heo-number-input--ungrouped" in str(props.get("className") or "").split():
            displayed = displayed.replace(".", "")
        source_id = props["id"]
        editor_props = {**props, "id": {
            "type": "heo-unit-editor", "source": json.dumps(source_id, sort_keys=True),
        }, "value": displayed, "type": "text", "debounce": False, "inputMode": "decimal"}
        # Umgerechnete ganzzahlige Modellwerte können eine Dezimalanzeige benötigen.
        editor_props["className"] = str(props.get("className") or "").replace(
            "heo-number-input--integer", "heo-number-input--decimal",
        ) + " heo-unit-editor"
        control.type = "hidden"
        control.className = "heo-unit-source"
        return html.Span(
            [control, dcc.Input(**editor_props)], className="heo-unit-number",
            **{"data-unit-source": json.dumps(source_id, sort_keys=True),
               "data-unit-base-value": number},
        )
    children = getattr(control, "children", None)
    if children is not None:
        control.children = (
            [unit_editor_inputs(item, unit) for item in children]
            if isinstance(children, (list, tuple)) else unit_editor_inputs(children, unit)
        )
    return control


def readonly_unit_value(key: str, value: float, unit: str, *, class_name: str = "") -> html.Span:
    """Rendert einen Zahlenwert samt synchronisierter, wählbarer Einheit."""

    displayed, selected = unit_display(value, unit)
    return html.Span(
        [html.Span(displayed, className="heo-unit-value"), " ",
         selectable_unit(selected)],
        className=f"heo-unit-readonly {class_name}",
        **unit_attributes(key, unit, value),
    )
