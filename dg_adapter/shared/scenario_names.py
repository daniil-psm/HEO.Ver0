# Prüft Szenarionamen für DG-Konfigurationen und Dateisystempfade.

from __future__ import annotations

import re
from typing import Any

INVALID_SCENARIO_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


# Validiert einen Szenarionamen für DG und Dateisystem.
def validate_scenario_name(scenario_name: Any) -> str:
    name = str(scenario_name or "").strip()
    if not name:
        raise ValueError("Bitte einen Szenarionamen angeben.")
    if len(name) > 100:
        raise ValueError("Der Szenarioname darf höchstens 100 Zeichen lang sein.")
    if name in {".", ".."} or INVALID_SCENARIO_NAME.search(name):
        raise ValueError(
            "Der Szenarioname enthält unzulässige Zeichen. "
            "Nicht erlaubt sind < > : \" / \\ | ? *."
        )
    if name.endswith((".", " ")):
        raise ValueError("Der Szenarioname darf nicht mit Punkt oder Leerzeichen enden.")
    if name.upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError(f"Der Szenarioname {name!r} ist unter Windows reserviert.")
    return name
