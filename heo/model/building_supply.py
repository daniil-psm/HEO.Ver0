
"""Zentrale und dezentrale Gebäudeanschlüsse nach dem DG-Gebäudemodell.

Die Kälteversorgung folgt dem primären Heizsystem: Wärmenetz bedeutet zentrale
Kälte, andere Heizsysteme bedeuten lokale Kälteerzeugung. Gebäude besitzen
keinen eigenen Stromanschluss-Schalter im DG. Frühere HEO-Anschlussvorgaben
werden an der Import-/Exportgrenze auf Verträglichkeit geprüft.
"""
from __future__ import annotations

import math


def flag(value, default=False):
    """Liest einen Wahrheitswert; fehlende, leere oder NaN-Werte ergeben den übergebenen Standard."""

    if value is None or isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, str):
        if not value.strip():
            return default
        return value.strip().lower() in {"1", "true", "yes", "enabled"}
    return bool(value)


def cooling_supply(row):
    """Liefert none, central oder decentral aus Kühlbedarf und primärem Heizsystem."""

    if not flag(row.get("cooling")):
        return "none"
    return "central" if row.get("heater") in {None, "", "heat_grid"} else "decentral"


def central_connections(row):
    """Liefert die zentralen Strom-, Raumwärme-, TWW- und Kälteanschlüsse eines Gebäudes."""

    heat_grid = row.get("heater") in {None, "", "heat_grid"}
    separate_dhw = flag(row.get("dhw")) or str(row.get("dhw_heater", "")).upper() == "EH_DHW"
    return {
        "ac": True,
        "heat": heat_grid,
        "dhw": heat_grid and not separate_dhw,
        "cooling": cooling_supply(row) == "central",
    }


