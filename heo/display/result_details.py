"""Zerlegt Ergebniszeilen in HEO-Feldbeschreibungen mit Wert und Einheit."""

from __future__ import annotations

from .field_presentation import FieldPresentation
from .number_format import parse_german_number

def overlay_field_from_line(line: str, *, parameter_scope: str = "result") -> FieldPresentation:
    """Erkennt die Einheit einer Ergebniszeile für den zentralen Dialogrenderer."""

    label, separator, value = str(line).partition(":")
    if not separator:
        return FieldPresentation(label="Information", value=label)
    value = value.strip()
    for unit in ("kg CO₂eq/a", "€/a", "MWh/a", "MWh", "kWh", "kWp", "kW", "m³", "m²", "Liter", "°C", "K", "%", "€", "m"):
        suffix = f" {unit}"
        if value.endswith(suffix):
            numeric_text = value[: -len(suffix)].strip()
            try:
                numeric_value = parse_german_number(numeric_text)
            except (TypeError, ValueError):
                numeric_value = None
            return FieldPresentation(
                label=label.strip(),
                value=numeric_text,
                unit=unit,
                kind="number",
                parameter_key=f"{parameter_scope}:{label.strip()}",
                numeric_value=numeric_value,
            )
    return FieldPresentation(label=label.strip(), value=value)
