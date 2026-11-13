"""Beschreibt HEO-Dialogfelder und ihre Darstellung unabhängig von Dash."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .number_format import NumberKind
from .units import parameter_unit_key


def checkbox_field_value(value: Any) -> Any:
    """Übersetzt die Werteliste einer Checkbox in einen einfachen Wahrheitswert."""

    if isinstance(value, list) and (value == ["enabled"] or value == []):
        return bool(value)
    return value


def range_counterpart_key(
    key: str, source: str, target: str,
) -> str | None:
    """Erkennt MIN-/MAX-Paare unabhängig von ihrer Position im Feldsuffix."""

    prefix, separator, suffix = str(key).rpartition("__")
    if suffix.startswith(f"{source}_"):
        counterpart = f"{target}_{suffix[len(source) + 1:]}"
    elif f"_{source}" in suffix:
        counterpart = suffix.replace(f"_{source}", f"_{target}", 1)
    else:
        return None
    return f"{prefix}{separator}{counterpart}" if separator else counterpart


def range_parameter_noun(field: dict[str, Any]) -> str:
    """Benennt die von einem MIN-/MAX-Paar gemeinsam begrenzte Größe."""

    key = str(field.get("env_key") or field.get("input_key") or "")
    suffix = key.split("__")[-1]
    if suffix.startswith("T_SET_"):
        return "Raumtemperatur nachts" if suffix.endswith("_NIGHT") else "Raumtemperatur"
    if suffix.startswith("SOC_"):
        return "Ladezustand"
    if "AREA" in suffix:
        return "Fläche"
    if "VOL" in suffix:
        return "Speichervolumen"
    unit = str(field.get("unit") or "").lower()
    return "Kapazität" if "wh" in unit else "Leistung"


def range_parameter_label(field: dict[str, Any]) -> str:
    """Leitet die Bezeichnung eines einzelnen Grenzwerts aus dem Paar ab."""

    key = str(field.get("env_key") or field.get("input_key") or "")
    suffix = key.split("__")[-1]
    minimum = suffix.startswith("MIN_") or "_MIN" in suffix
    if suffix.startswith("T_SET_"):
        return str(field.get("label") or (
            "Minimale Raumtemperatur" if minimum else "Maximale Raumtemperatur"
        ))
    if suffix.startswith("SOC_"):
        return "Minimaler Ladezustand" if minimum else "Maximaler Ladezustand"
    prefix = "Mindest" if minimum else "Maximal"
    noun = range_parameter_noun(field)
    return f"{prefix}{noun.lower()}"


FieldKind = Literal["number", "text", "choice", "full"]

FIELD_KINDS = {"number", "text", "choice", "full"}

@dataclass(frozen=True)
class FieldPresentation:
    """Renderunabhängige Feldbeschreibung mit Wert, Einheit, Bearbeitbarkeit und Rasterspanne."""

    label: str
    value: str
    unit: str | None = None
    editable: bool = False
    kind: FieldKind = "text"
    column_span: int = 1
    row_span: int = 1
    help_text: str = ""
    number_kind: NumberKind | None = None
    parameter_key: str = ""
    numeric_value: float | None = None

    def __post_init__(self) -> None:
        """Validiert Feldart, positive Rasterspannen und Zahlenformat; löst ValueError aus."""

        if self.kind not in FIELD_KINDS:
            raise ValueError(f"Unbekannte Feldart: {self.kind}")
        if self.column_span < 1 or self.row_span < 1:
            raise ValueError("Feldspannen müssen mindestens 1 betragen.")
        if self.number_kind not in {None, "integer", "decimal"}:
            raise ValueError(f"Unbekannte Zahlenart: {self.number_kind}")

OverlayField = FieldPresentation

@dataclass(frozen=True)
class OverlaySection:
    """Titel und anfänglicher Öffnungszustand eines aufklappbaren Dialogabschnitts."""

    title: str
    default_open: bool = False

def parameter_number_kind(field: dict[str, Any]) -> NumberKind:
    """Bestimmt das Zahlenformat der Anzeige unabhängig vom gespeicherten DG-Typ."""

    if field.get("display_number_kind") in {"integer", "decimal"}:
        return field["display_number_kind"]
    value_type = str(field.get("value_type") or "")
    if value_type in {"int", "optional-int"}:
        return "integer"
    default = field.get("default")
    if value_type == "list" and isinstance(default, list) and len(default) == 1:
        item = default[0]
        if isinstance(item, int) and not isinstance(item, bool):
            return "integer"
    return "decimal"

def parameter_field_presentation(
    field: dict[str, Any],
    *,
    label: str,
    value: Any,
    kind: str,
    editable: bool = True,
    column_span: int = 1,
    row_span: int = 1,
    help_text: str | None = None,
    number_kind: NumberKind | None = None,
    unit: str | None = None,
    numeric_value: float | None = None,
) -> FieldPresentation:
    """Erzeugt eine Feldbeschreibung aus Katalogmetadaten und den übergebenen Darstellungswerten."""

    ui = field.get("ui") if isinstance(field.get("ui"), dict) else {}
    effective_kind = str(ui.get("kind", kind))
    raw = value[0] if isinstance(value, list) and len(value) == 1 else value
    if numeric_value is None and kind == "number" and isinstance(raw, (int, float)) and not isinstance(raw, bool):
        numeric_value = (
            float(raw) * float(field.get("display_scale") or 1.0)
            / float(field.get("display_divisor") or 1.0)
        )
    # Katalogeinheiten gehören zum Zahlenwert, nicht zu seinem umgebenden
    # Schalter oder zu einem Editor, der seine eigene Einheit bereits rendert.
    visible_unit = unit if unit is not None else field.get("unit") if effective_kind == "number" else None
    if effective_kind == "full" or field.get("value_type") == "bool":
        visible_unit = None
    if visible_unit in {"", "–", "-"}:
        visible_unit = None
    return FieldPresentation(
        label=label,
        value=str(value if value is not None else ""),
        unit=visible_unit,
        parameter_key=parameter_unit_key(field),
        numeric_value=numeric_value,
        editable=bool(ui.get("editable", editable)),
        kind=effective_kind,
        column_span=int(ui.get("column_span", column_span)),
        row_span=int(ui.get("row_span", row_span)),
        number_kind=ui.get("number_kind", number_kind),
        help_text=str(
            ui.get(
                "help_text",
                help_text if help_text is not None
                else field.get("help_text_de") or "",
            )
        ),
    )


def overlay_section(title: str, *, default_open: bool = False) -> OverlaySection:
    """Erzeugt die gemeinsame Definition eines aufklappbaren Abschnitts."""

    return OverlaySection(title=title, default_open=default_open)

