"""Gemeinsame deutsche Darstellung und Auswertung numerischer Eingaben."""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Literal


NumberKind = Literal["integer", "decimal"]

_GERMAN_GROUPED_INTEGER = re.compile(r"\d{1,3}(?:\.\d{3})+")


# Editierbare Felder müssen auch während einer noch unvollständigen Eingabe darstellbar bleiben.
def format_german_number(
    value: Any, *, kind: NumberKind = "decimal", scale: float = 1.0,
    group_thousands: bool = True, divisor: float = 1.0,
) -> Any:
    """Formatiert skalierte Zahlen deutsch; nichtnumerische Zwischenwerte bleiben erhalten."""

    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if value is None:
        return ""
    if not isinstance(value, (int, float, Decimal)) or isinstance(value, bool):
        return value
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)

    # Dezimalrechnung vermeidet Rundungsreste bei der Skalierung ganzer Stunden und Minuten.
    try:
        scaled = Decimal(str(value)) * Decimal(str(scale)) / Decimal(str(divisor))
    except (InvalidOperation, ValueError):
        return value

    if kind == "integer":
        plain = format(scaled.quantize(Decimal("1")), "f")
    else:
        plain = format(scaled, "f")
        if "." in plain:
            plain = plain.rstrip("0").rstrip(".")

    sign = ""
    if plain.startswith(("-", "+")):
        sign, plain = plain[0], plain[1:]
    integer, separator, fraction = plain.partition(".")
    grouped = (
        _group_digits(integer or "0")
        if group_thousands else integer or "0"
    )
    return f"{sign}{grouped}{',' + fraction if separator and fraction else ''}"


def parse_german_number(
    value: Any, *, kind: NumberKind | None = None,
) -> float:
    """Liest deutsche Zahlen oder ungruppierte Punktdezimalen; ungültige Werte lösen ValueError aus.

    Bei gesetztem kind gelten Punkte ausschließlich als Tausendertrennzeichen.
    """

    if isinstance(value, bool):
        raise ValueError("Boolesche Werte sind keine numerische Eingabe.")
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Die Zahl muss endlich sein.")
        return number
    if not isinstance(value, str):
        raise ValueError("Die numerische Eingabe muss Text oder Zahl sein.")

    text = value.strip().replace(" ", "").replace("\u00a0", "")
    if not text:
        raise ValueError("Die numerische Eingabe ist leer.")
    if text.count(",") > 1:
        raise ValueError("Die numerische Eingabe enthält mehrere Dezimalkommas.")

    sign = ""
    if text.startswith(("-", "+")):
        sign, text = text[0], text[1:]
    if not text:
        raise ValueError("Die numerische Eingabe enthält keine Ziffern.")

    # Ohne explizite Feldart wird ein Punkt nur bei gültiger deutscher Gruppierung als Trenner gelesen.
    if "," in text:
        integer, fraction = text.split(",", 1)
        if "." in fraction or (fraction and not fraction.isdigit()):
            raise ValueError("Ungültige Nachkommastellen.")
        if not re.fullmatch(r"[0-9.]*", integer):
            raise ValueError("Ungültiger Ganzzahlteil.")
        if (
            kind is None and "." in integer
            and not _GERMAN_GROUPED_INTEGER.fullmatch(integer)
        ):
            raise ValueError("Ungültige Tausendergruppierung.")
        integer = integer.replace(".", "") or "0"
        normalized = f"{sign}{integer}.{fraction}"
    elif kind is not None:
        if not re.fullmatch(r"[0-9.]+", text):
            raise ValueError("Ungültiger Ganzzahlteil.")
        # In explizit deutschen Eingabefeldern bezeichnet ausschließlich das
        # Komma Nachkommastellen. Punkte bleiben auch während einer durch
        # Löschen unvollständigen Gruppierung Tausendertrennzeichen:
        # ``1.30`` wird deshalb korrekt zu ``130``.
        normalized = f"{sign}{text.replace('.', '')}"
    elif _GERMAN_GROUPED_INTEGER.fullmatch(text):
        normalized = f"{sign}{text.replace('.', '')}"
    else:
        normalized = f"{sign}{text}"

    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", normalized):
        raise ValueError("Ungültige numerische Eingabe.")
    number = float(normalized)
    if not math.isfinite(number):
        raise ValueError("Die Zahl muss endlich sein.")
    return number


def _group_digits(digits: str) -> str:
    """Gruppiert eine ausschließlich aus Ziffern bestehende Ganzzahl."""

    remainder = len(digits) % 3
    groups = ([digits[:remainder]] if remainder else []) + [
        digits[index:index + 3] for index in range(remainder, len(digits), 3)
    ]
    return ".".join(groups)
