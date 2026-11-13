"""Berechnet Monatsmarken und lesbare Achsenticks für HEO-Zeitreihendiagramme."""

from __future__ import annotations

import math
import pandas as pd

MONTH_LABELS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

def month_tick_data_from_daily(df: pd.DataFrame) -> tuple[list[float], list[str], list[int]]:
    """Berechnet Monatsmitten und Grenzen aus täglichen Bedarfsreihen."""

    if df is None or df.empty:
        return [], [], []

    month_centers = []
    month_labels = []
    month_boundaries = []

    for month in range(1, 13):
        month_df = df[df["month"].astype(int) == month]
        if month_df.empty:
            continue

        first_day = int(month_df["day_index"].iloc[0])
        last_day = int(month_df["day_index"].iloc[-1])
        center = (first_day + last_day) / 2

        month_centers.append(center)
        month_labels.append(MONTH_LABELS[month - 1])
        month_boundaries.append(first_day)

    if not df.empty:
        month_boundaries.append(int(df["day_index"].max()) + 1)

    return month_centers, month_labels, month_boundaries

def nice_axis_step(vmin: float, vmax: float, target_intervals: int = 6) -> float:
    """Liefert eine gut lesbare 1/2/2,5/5/10-Schrittweite."""

    span = max(0.0, float(vmax) - float(vmin))
    if span <= 1e-12:
        reference = max(abs(float(vmax)), 1.0)
        return 10 ** math.floor(math.log10(reference))

    raw_step = span / max(1, target_intervals)
    magnitude = 10 ** math.floor(math.log10(raw_step))
    normalized = raw_step / magnitude
    for candidate in (1.0, 2.0, 2.5, 5.0, 10.0):
        if normalized <= candidate:
            return candidate * magnitude
    return 10.0 * magnitude

def demand_axis_ticks(
    vmin: float,
    vavg: float,
    vmax: float,
    step: float,
) -> tuple[list[float], list[str]]:
    """Erzeugt reguläre Ticks und hervorgehobene Min-/Mittel-/Maxwerte."""

    start = math.floor(vmin / step) * step
    end = math.ceil(vmax / step) * step
    regular_values = []
    current = start
    while current <= end + 1e-9:
        regular_values.append(round(current, 10))
        current += step

    span = max(vmax - vmin, step)
    equality_tolerance = max(span * 1e-8, 1e-9)
    collision_tolerance = max(step * 0.15, span * 0.025)
    # Identische Extrem-/Mittelwerte teilen sich ein Label, damit ihre Texte nicht kollidieren.
    special_groups: list[dict] = []
    for role, value in (("min", vmin), ("Ø", vavg), ("max", vmax)):
        group = next(
            (
                item
                for item in special_groups
                if abs(item["value"] - value) <= equality_tolerance
            ),
            None,
        )
        if group is None:
            special_groups.append({"value": float(value), "roles": [role]})
        else:
            group["roles"].append(role)

    entries = [
        (group["value"], f"{'/'.join(group['roles'])} {group['value']:.1f}")
        for group in special_groups
    ]
    # Reguläre Marken in der Nähe besonderer Werte auslassen, damit deren Beschriftung lesbar bleibt.
    special_values = [group["value"] for group in special_groups]
    for value in regular_values:
        if any(
            abs(value - special) < collision_tolerance
            for special in special_values
        ):
            continue
        entries.append((float(value), f"{value:g}"))

    entries.sort(key=lambda entry: entry[0])
    return [entry[0] for entry in entries], [entry[1] for entry in entries]

def month_tick_data(weather: dict) -> tuple[list[float], list[str], list[int]]:
    """Berechnet Monatsmarken aus den Wetter-Tageswerten."""

    months = weather.get("daily_month", [])
    days = weather.get("daily_day_index", [])

    if not months or not days:
        return [], [], []

    month_centers = []
    month_labels = []
    month_boundaries = []

    for month in range(1, 13):
        indices = [i for i, m in enumerate(months) if int(m) == month]

        if not indices:
            continue

        first_i = indices[0]
        last_i = indices[-1]

        first_day = days[first_i]
        last_day = days[last_i]

        center = (first_day + last_day) / 2

        month_centers.append(center)
        month_labels.append(MONTH_LABELS[month - 1])
        month_boundaries.append(first_day)

    month_boundaries.append(max(days) + 1)

    return month_centers, month_labels, month_boundaries

def build_axis_ticks(
    vmin: float,
    vavg: float,
    vmax: float,
    step: float,
    suffix: str = "",
    special_decimals: int = 1,
    regular_decimals: int = 0,
) -> tuple[list[float], list[str]]:
    """Baut reguläre Achsenticks sowie kollisionsfreie Min-/Mittel-/Max-Ticks."""

    start = math.floor(vmin / step) * step
    end = math.ceil(vmax / step) * step

    regular_vals = []
    current = start
    while current <= end + 1e-9:
        regular_vals.append(round(current, 10))
        current += step

    span = max(vmax - vmin, step)
    equality_tol = max(span * 1e-8, 1e-9)
    collision_tol = max(step * 0.15, span * 0.025)
    # Numerisch gleiche Sonderwerte zu einer gemeinsamen Beschriftung zusammenführen.

    special_groups: list[dict] = []
    for role, value in (("min", vmin), ("Ø", vavg), ("max", vmax)):
        group = next(
            (item for item in special_groups if abs(item["value"] - value) <= equality_tol),
            None,
        )
        if group is None:
            special_groups.append({"value": float(value), "roles": [role]})
        else:
            group["roles"].append(role)

    entries = [
        (
            group["value"],
            f"{'/'.join(group['roles'])} {group['value']:.{special_decimals}f}{suffix}",
        )
        for group in special_groups
    ]

    # Sonderbeschriftungen erhalten Platz gegenüber den regulären Achsenticks.
    special_vals = [group["value"] for group in special_groups]
    for value in regular_vals:
        if any(abs(value - special) < collision_tol for special in special_vals):
            continue
        entries.append((float(value), f"{value:.{regular_decimals}f}{suffix}"))

    entries.sort(key=lambda entry: entry[0])
    return [entry[0] for entry in entries], [entry[1] for entry in entries]

