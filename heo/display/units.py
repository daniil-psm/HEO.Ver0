"""Einheitenfamilien und Darstellungsregeln ohne Änderung der Modellwerte."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
from typing import Any

from .number_format import format_german_number


# Nur gleiche physikalische Größen sind Kandidaten füreinander. Bei Kosten
# darf der Nenner skalieren; MW/h bleibt dagegen eine eigene Leistungsgröße.
SI_PREFIXES = (("", 1), ("k", 1e3), ("M", 1e6), ("G", 1e9), ("T", 1e12))
AREA_UNITS = (("m²", 1), ("ha", 1e4), ("km²", 1e6))
CURRENCY_UNITS = (("ct", .01), ("€", 1), ("k€", 1e3), ("M€", 1e6), ("G€", 1e9))
UNIT_FAMILIES = (
    (("ms", .001), ("s", 1), ("min", 60), ("h", 3600), ("d", 86400)),
    tuple((prefix + "W", scale) for prefix, scale in SI_PREFIXES),
    tuple((prefix + "Wh", scale) for prefix, scale in SI_PREFIXES),
    tuple((prefix + "Wp", scale) for prefix, scale in SI_PREFIXES[:-1]),
    AREA_UNITS,
    (("mm", .001), ("cm", .01), ("m", 1), ("km", 1000)),
    (("ml", 1e-6), ("l", .001), ("m³", 1)),
    (("g", .001), ("kg", 1), ("t", 1000)),
    CURRENCY_UNITS,
)
UNIT_ALIASES = {"Liter": "l", "L": "l", "Sekunden": "s", "Sekunde": "s"}
LEGACY_AREA_SCALES = {"mm²": 1e-6, "cm²": 1e-4}
AUTO_UPPER = 10_000
SIGNIFICANT_DIGITS = 5


def parameter_unit_key(field: dict[str, Any]) -> str:
    """Liefert dieselbe Identität unabhängig von Tab, Dialog und Renderer-ID."""

    return str(field.get("parameter_key") or (
        "parameter:" + str(field.get("input_key") or field.get("env_key") or "")
    ))


def building_unit_key(uid: Any, field: str) -> str:
    """Trennt Parameter verschiedener Gebäude anhand ihrer beständigen UID."""

    return f"building:{uid}:{field}"


def unit_choices(unit: str) -> list[dict[str, Any]]:
    """Liefert fachlich geordnete Kandidaten mit Faktor zur Ausgangseinheit."""

    unit = str(unit).strip()
    numerator, slash, denominator = unit.partition("/")
    # Jährliche Geldsummen bleiben Geldsummen (k€/a). Bei Stückkosten wie
    # €/kW oder €/m² wird dagegen die Bezugsgröße im Nenner skaliert.
    if slash and numerator in dict(CURRENCY_UNITS) and denominator not in {"a", "Jahr", "Jahre"}:
        return _cost_choices(numerator, denominator)
    # Emissionszusätze bleiben ebenso erhalten wie Nenner zusammengesetzter Einheiten.
    token, space, suffix = numerator.partition(" ")
    canonical = UNIT_ALIASES.get(token, token)
    for family in UNIT_FAMILIES:
        source = next((scale for name, scale in family if name == canonical), None)
        if source is None and family == AREA_UNITS:
            source = LEGACY_AREA_SCALES.get(canonical)
        if source is None:
            continue
        return [
            {"unit": (token if name == canonical else name) + (space + suffix if space else "")
             + (slash + denominator if slash else ""), "factor": scale / source}
            for name, scale in family
        ]
    return [{"unit": unit, "factor": 1.0}]


def _cost_choices(currency: str, denominator: str) -> list[dict[str, Any]]:
    """Skaliert Kosten über ct/€ und den Nenner, ohne künstliche k€-Preisreihen."""

    currency_scale = dict(CURRENCY_UNITS)[currency]
    token, separator, suffix = denominator.partition("·")
    canonical = UNIT_ALIASES.get(token, token)
    for family in UNIT_FAMILIES[:-1]:
        denominator_scale = dict(family).get(canonical)
        if denominator_scale is None:
            continue
        # W und Wh bleiben bei Bedarf lesbar, die Preisleiter beginnt sonst
        # wie die üblichen Eingaben bei kW/kWh und enthält genau eine Cent-Stufe.
        common = next((item for item in family if item[0] in {"kW", "kWh", "kWp"}), (canonical, denominator_scale))
        euro_units = [item for item in family if item[1] >= common[1] or item[0] == canonical]
        entries = [("ct", common[0], .01, common[1])] + [
            ("€", name, 1, scale) for name, scale in euro_units
        ]
        return [
            {"unit": f"{money}/{name}{separator}{suffix}",
             "factor": money_scale / currency_scale * denominator_scale / scale}
            for money, name, money_scale, scale in entries
        ]
    return [{"unit": f"{money}/{denominator}", "factor": scale / currency_scale}
            for money, scale in (("ct", .01), ("€", 1))]


def display_unit(value: float, unit: str, preferred: str | None = None) -> dict[str, Any]:
    """Wählt eine manuelle Einheit oder skaliert automatisch bei <1 bzw. >=10⁴."""

    unit = str(unit).strip()
    choices = unit_choices(unit)
    if preferred:
        selected = next((item for item in choices if item["unit"] == preferred), None)
        if selected:
            return selected
    magnitude = abs(float(value))
    source = next((item for item in choices if item["unit"] == unit), None)
    if source and (not math.isfinite(magnitude) or magnitude == 0 or 1 <= magnitude < AUTO_UPPER):
        return source
    # Bei €/MW ist der Faktor gegenüber €/kW kleiner. Deshalb entscheidet
    # der Umrechnungsfaktor über die Automatik, unabhängig von der Menüreihenfolge.
    suitable = [item for item in choices if 1 <= magnitude / item["factor"] < AUTO_UPPER]
    if suitable:
        return min(suitable, key=lambda item: abs(math.log10(item["factor"])))
    if magnitude == 0 or not math.isfinite(magnitude):
        return min(choices, key=lambda item: abs(math.log10(item["factor"])))
    if magnitude < 1:
        return min(choices, key=lambda item: item["factor"])
    return max(choices, key=lambda item: item["factor"])


def significant_number(value: float) -> str:
    """Formatiert höchstens fünf signifikante Stellen ohne angehängte Nullen."""

    number = Decimal(str(value))
    if not number.is_finite():
        return "—"
    if number == 0:
        return "0"
    with localcontext() as context:
        context.prec = max(32, abs(number.adjusted()) + SIGNIFICANT_DIGITS + 2)
        rounded = number.quantize(
            Decimal(1).scaleb(number.adjusted() - SIGNIFICANT_DIGITS + 1),
            rounding=ROUND_HALF_UP,
        )
    return format_german_number(rounded)


def unit_display(value: float, unit: str, preferred: str | None = None) -> tuple[str, str]:
    """Liefert gerundeten Anzeigetext und Einheit; der Ausgangswert bleibt exakt."""

    selected = display_unit(value, unit, preferred)
    return significant_number(float(value) / selected["factor"]), selected["unit"]
