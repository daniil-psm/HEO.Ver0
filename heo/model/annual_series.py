"""Wirtschaftliche HEO-Jahresreihen mit Stützwerten bis zum jeweils nächsten Stützjahr."""
from __future__ import annotations

import json
import math
from copy import deepcopy

ANNUAL_KEYS = (
    "PRICE_SUPPLY_EL", "REVENUE_FEED_IN_EL", "PRICE_SUPPLY_EL_EH", "REVENUE_FEED_IN_EL_EH",
    "PRICE_SUPPLY_GAS", "PRICE_SUPPLY_GAS_EH", "REVENUE_FEED_IN_GAS", "PRICE_GASOLINE_LITER",
    "PRICE_HYDROGEN", "PRICE_WASTE", "PRICE_BIOMASS", "PRICE_OIL", "PRICE_DISTRICT_HEAT",
    "CO2_EL_GRID", "CO2_GAS", "CO2_BIOM", "CO2_HYDROGEN", "CO2_OIL", "CO2_WASTE",
    "CO2_DISTRICT_HEAT", "CO2_TAX",
)


def numbers(value):
    """Konvertiert eine Zahl, Liste oder Textliste in eine nichtleere Liste endlicher Float-Werte."""

    if isinstance(value, str):
        value = json.loads(value) if value.strip().startswith("[") else value.split(",")
    values = value if isinstance(value, (list, tuple)) else [value]
    result = [float(v) for v in values]
    if not result or not all(math.isfinite(v) for v in result):
        raise ValueError("Eine Zahlenliste mit endlichen Werten ist erforderlich.")
    return result


def support_years(values):
    """Ermittelt und validiert Stützjahre aus Anzahl oder expliziter Liste im Betrachtungszeitraum."""

    horizon = int(values.get("OBSERVATION_TIME", 20))
    if horizon < 1:
        raise ValueError("Der Betrachtungszeitraum muss mindestens ein Jahr betragen.")
    count = values.get("NUM_INTERPOLATION_POINTS")
    if count not in (None, "", "None", "null"):
        count = int(count)
        if not 1 <= count <= horizon:
            raise ValueError("Die Anzahl der Stützjahre muss zwischen 1 und dem Betrachtungszeitraum liegen.")
        return [round(i * horizon / count) for i in range(count)]
    raw = numbers(values.get("INTERPOLATION_POINTS", [0, 5, 10, 15]))
    points = [int(v) for v in raw]
    if raw != points or points[0] != 0 or points != sorted(set(points)) or points[-1] >= horizon:
        raise ValueError("Stützjahre müssen eindeutig und aufsteigend sein, mit 0 beginnen und im Betrachtungszeitraum liegen.")
    return points


def expand_support(points, values, horizon):
    """Überträgt jeden Stützwert bis zum nächsten Stützjahr auf die Jahresreihe."""

    if len(points) != len(values):
        raise ValueError("Für jedes Stützjahr ist ein Wert erforderlich.")
    return [values[max(i for i, point in enumerate(points) if point <= year)] for year in range(horizon)]


def series_view(state, key):
    """Liefert Eingabeart, Stützjahre und wirksame Anzeigewerte einer wirtschaftlichen Jahresreihe."""

    values = {**state.get("defaults", {}), **state.get("values", {})}
    points = support_years(values)
    annual = numbers(values.get(key, [0]))
    horizon = int(values.get("OBSERVATION_TIME", 20))
    annual = (annual + [annual[-1]] * horizon)[:horizon]
    mode = state.get("annual_series", {}).get(key, {}).get("mode")
    mode = mode or ("constant" if len(set(annual)) == 1 else "support")
    # Effektive DG-Segmentwerte anzeigen, damit importierte Jahresdaten unverändert bleiben.
    q = 1 + float(values.get("INTEREST_RATE", 0.05))
    displayed = []
    for start, stop in zip(points, points[1:] + [horizon]):
        segment = annual[start:stop]
        if len(set(segment)) == 1:
            displayed.append(segment[0])
            continue
        weights = [1 if key.startswith("CO2_") else q ** -i for i in range(stop-start)]
        displayed.append(sum(v*w for v, w in zip(segment, weights)) / sum(weights))
    return mode, points, ([annual[0]] if mode == "constant" else displayed)


def edit_series(state, key, mode, entries):
    """Übernimmt konstante Werte oder Stützwerte in eine Kopie des Zustands; validiert die Eingaben."""

    if key not in ANNUAL_KEYS or mode not in {"constant", "support"}:
        raise ValueError("Unbekannte Jahresreihe oder Eingabeart.")
    updated = deepcopy(state)
    values = {**updated.get("defaults", {}), **updated.get("values", {})}
    points = support_years(values)
    entries = numbers(entries)
    if mode == "constant" and len(entries) != 1:
        raise ValueError("Für konstant ist genau ein Wert erforderlich.")
    annual = entries if mode == "constant" else expand_support(points, entries, int(values.get("OBSERVATION_TIME", 20)))
    updated.setdefault("values", {})[key] = annual
    updated.setdefault("annual_series", {})[key] = {"mode": mode, "points": points, "values": entries}
    return updated


def reconcile_series(state):
    """Passt bearbeitete Stützjahrreihen an die aktuellen Stützjahre und den Betrachtungszeitraum an."""
    updated = deepcopy(state)
    values = {**updated.get("defaults", {}), **updated.get("values", {})}
    points = support_years(values)
    # Nur ausdrücklich bearbeitete Stützreihen neu aufteilen; importierte Jahreslisten erhalten.
    for key, spec in updated.get("annual_series", {}).items():
        if spec["mode"] == "support":
            annual = expand_support(spec["points"], spec["values"], int(values.get("OBSERVATION_TIME", 20)))
            entries = [annual[year] for year in points]
            updated = edit_series(updated, key, "support", entries)
    return updated


def support_year_mode(state: dict) -> str:
    """Leitet die aktive Stützjahr-Eingabeart aus dem HEO-Entwurf ab."""

    values = state.get("values", {})
    defaults = state.get("defaults", {})
    count = values.get("NUM_INTERPOLATION_POINTS", defaults.get("NUM_INTERPOLATION_POINTS"))
    return "count" if count not in (None, "", "None", "null") else "years"


def set_support_year_mode(state: dict, mode: str) -> dict:
    """Wechselt in einer Zustandskopie die Stützjahr-Eingabeart und hält Eingabefehler im Zustand fest."""

    if mode not in {"count", "years"}:
        raise ValueError("Unbekannte Stützjahr-Eingabeart.")
    updated = deepcopy(state)
    values = updated.setdefault("values", {})
    defaults = updated.setdefault("defaults", {})
    if mode == "count":
        effective = {**defaults, **values}
        try:
            point_count = len(support_years(effective))
        except (TypeError, ValueError):
            point_count = len(defaults.get("INTERPOLATION_POINTS") or [0, 5, 10, 15])
        values["NUM_INTERPOLATION_POINTS"] = min(
            point_count, max(1, int(effective.get("OBSERVATION_TIME") or 20)),
        )
    else:
        values["NUM_INTERPOLATION_POINTS"] = None
    try:
        updated = reconcile_series(updated)
        updated.pop("support_year_error", None)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        updated["support_year_error"] = str(exc)
    return updated
