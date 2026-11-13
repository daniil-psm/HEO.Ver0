"""HEO-Standortzustand, Ortsbezeichnungen und Zeitzonenregeln."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

LOCATION_MODE_PIDULA = "pidula"
LOCATION_MODE_GERMANY = "germany"
LOCATION_MODE_OTHER = "other"
PIDULA_TIMEZONE = 2.0
GERMANY_TRY_TIMEZONE = 1.0
LOCATION_MODES = {
    LOCATION_MODE_PIDULA,
    LOCATION_MODE_GERMANY,
    LOCATION_MODE_OTHER,
}


def normalise_postal_code(value: Any) -> str:
    """Normalisiert eine deutsche PLZ auf fünf Ziffern."""

    text = str(value or "").strip()
    if not text.isdigit() or len(text) > 5:
        raise ValueError("Bitte eine gültige deutsche Postleitzahl eingeben.")
    return text.zfill(5)


def german_location_label(site: dict[str, Any]) -> str:
    """Formatiert die deutsche PLZ und gegebenenfalls die zugeordnete TRY-Referenzstadt."""

    city = site.get("reference_city")
    if city:
        return f"PLZ {site['zip']} · TRY-Referenzstadt {city}"
    return f"Deutschland · PLZ {site['zip']}"


def automatic_location_timezone(
    mode: str,
    weather_data: dict[str, Any] | None = None,
) -> float | None:
    """Liefert den vom Standort/Wetterdatensatz vorgegebenen GMT-Versatz."""

    if mode == LOCATION_MODE_PIDULA:
        return PIDULA_TIMEZONE
    if mode == LOCATION_MODE_GERMANY:
        # Die DWD-TRY-Dateien sind ganzjährig in MEZ angegeben.
        return GERMANY_TRY_TIMEZONE
    if mode == LOCATION_MODE_OTHER and weather_data:
        value = weather_data.get("time_zone")
        if value is not None:
            return float(value)
    return None


def location_mode_from_state(state: dict | None) -> str:
    """Ermittelt den Standortmodus aus expliziter Auswahl oder bisherigen Standortfeldern."""

    state = state or {}
    mode = state.get("location_mode")
    if mode in LOCATION_MODES:
        return mode
    values = state.get("values", {})
    if bool(values.get("USE_GERMAN_ZIP")):
        return LOCATION_MODE_GERMANY
    location_name = str(values.get("LOCATION_NAME") or "").lower()
    weather_file = str(values.get("WEATHER_FILE") or "").lower()
    if "pidula" in location_name or "vilsandi" in weather_file:
        return LOCATION_MODE_PIDULA
    return LOCATION_MODE_OTHER


def state_with_effective_albedo(state: dict, weather: dict | None) -> dict:
    """Setzt den wirksamen PV-Albedo-Wert nach manueller, Wetter- und Standardvorgabe."""

    updated = deepcopy(state)
    values = updated.setdefault("values", {})
    stored = values.get("ALBEDO", updated.get("defaults", {}).get("ALBEDO", 0.2))
    try:
        weather_value = float((weather or {}).get("albedo"))
    except (TypeError, ValueError):
        weather_value = None
    overrides = {str(key).upper() for key in updated.get("overrides", [])}
    try:
        stored_number = float(stored)
    except (TypeError, ValueError):
        stored_number = None
    manual = (
        "ALBEDO" in overrides
        and stored_number is not None
        and weather_value is not None
        and abs(stored_number - weather_value) > 1e-9
    )
    if not manual and weather_value is not None and 0.0 <= weather_value <= 1.0:
        values["ALBEDO"] = weather_value
    elif stored_number is None:
        values["ALBEDO"] = 0.2
    return updated
