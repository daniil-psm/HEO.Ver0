# Bidirektionale Übersetzung von Werten und Einheiten zwischen der HEO-Parametern und envConfig des DG

from __future__ import annotations

from copy import deepcopy
from typing import Any
from heo.model.annual_series import reconcile_series, support_years

from ..input.site_lookup import (
    LOCATION_MODE_GERMANY,
    LOCATION_MODE_OTHER,
    LOCATION_MODE_PIDULA,
    automatic_location_timezone,
    german_location_label,
    location_mode_from_state,
    lookup_german_site,
)


DISTRICT_AREA_INPUT_KEY = "DISTRICT_AREA_M2"
CLIMATE_PERIOD_INPUT_KEY = "CLIMATE_PERIOD"
OPTIMIZATION_FOCUS_INPUT_KEY = "OPTIMIZATION_FOCUS_MODE"

CLIMATE_PERIOD_MEASURED = "measured_1995_2012"
CLIMATE_PERIOD_FORECAST = "forecast_2031_2060"
OPTIMIZATION_FOCUS_ECONOMIC = "economic"
OPTIMIZATION_FOCUS_ECOLOGICAL = "ecological"


DG_TO_HEO_KEYS = {
    "DISTRICT_AREA": DISTRICT_AREA_INPUT_KEY,
    "TRYYEAR": CLIMATE_PERIOD_INPUT_KEY,
    "OPTIMIZATION_FOCUS": OPTIMIZATION_FOCUS_INPUT_KEY,
}
HEO_TO_DG_KEYS = {heo_key: dg_key for dg_key, heo_key in DG_TO_HEO_KEYS.items()}
ANGLE_INPUT_KEYS = {
    "C_PV__BETA", "C_PV__GAMMA", "C_STC__BETA", "C_STC__GAMMA",
}


# Liefert den stabilen Schlüssel des HEO-Eingabemodells.
def input_key_for_env(env_key: str) -> str:

    key = str(env_key).upper()
    return DG_TO_HEO_KEYS.get(key, key)


# Ergänzt das technische DG-Schema um HEO-Schlüssel, ohne es zu verändern.
def with_input_keys(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:

    result = deepcopy(sections)
    for section in result:
        for field in section.get("fields", []):
            field["input_key"] = input_key_for_env(field["env_key"])
            field["dg_default"] = field.get("default")
            field["dg_value"] = field.get("value")
            field["default"] = _from_dg_value(field["env_key"], field.get("default"))
            field["value"] = _from_dg_value(field["env_key"], field.get("value"))
    return result


# Übersetzt einen DG-Wert samt Einheit in das HEO-Eingabemodell.
def _from_dg_value(env_key: str, value: Any) -> Any:
    key = str(env_key).upper()
    if key in ANGLE_INPUT_KEYS:
        return None if value is None else float(value)
    if key == "DISTRICT_AREA":
        return None if value is None else float(value) * 10_000.0
    if key == "TRYYEAR":
        return (
            CLIMATE_PERIOD_FORECAST
            if str(value).upper() == "TRY2045"
            else CLIMATE_PERIOD_MEASURED
        )
    if key == "OPTIMIZATION_FOCUS":
        try:
            return (
                OPTIMIZATION_FOCUS_ECOLOGICAL
                if int(value) == 1
                else OPTIMIZATION_FOCUS_ECONOMIC
            )
        except (TypeError, ValueError):
            return OPTIMIZATION_FOCUS_ECONOMIC
    return value


# Übersetzt einen HEO-Schlüssel samt Wert und Einheit in das DG-Konfigurationsmodell.
def _to_dg_value(input_key: str, value: Any) -> tuple[str, Any]:
    key = str(input_key).upper()
    env_key = HEO_TO_DG_KEYS.get(key, key)
    if key in ANGLE_INPUT_KEYS:
        return env_key, None if value is None else float(value)
    if key == DISTRICT_AREA_INPUT_KEY:
        return env_key, None if value is None else float(value) / 10_000.0
    if key == CLIMATE_PERIOD_INPUT_KEY:
        return (
            env_key,
            "TRY2045" if value == CLIMATE_PERIOD_FORECAST else "TRY2015",
        )
    if key == OPTIMIZATION_FOCUS_INPUT_KEY:
        return (
            env_key,
            1 if value == OPTIMIZATION_FOCUS_ECOLOGICAL else 0,
        )
    return env_key, value


# Übersetzt alle Parameter eines Wörterbuchs in die angegebene Richtung.
def _map_value_dict(values: dict[str, Any] | None, *, to_heo: bool) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for key, value in (values or {}).items():
        if to_heo:
            mapped[input_key_for_env(key)] = _from_dg_value(key, value)
        else:
            env_key, converted = _to_dg_value(key, value)
            mapped[env_key] = converted
    return mapped


# Übersetzt einen geladenen DG-Zustand in editierbare HEO-Werte
def dg_state_to_heo_state(state: dict[str, Any] | None) -> dict[str, Any]:
    source = deepcopy(state or {})
    result = {
        "values": _map_value_dict(source.get("values"), to_heo=True),
        "defaults": _map_value_dict(source.get("defaults"), to_heo=True),
        "saved_values": _map_value_dict(source.get("saved_values"), to_heo=True),
        "overrides": [input_key_for_env(key) for key in source.get("overrides", [])],
        "config_path": source.get("config_path"),
        "config_exists": bool(source.get("config_exists")),
        "load_error": source.get("load_error"),
        "model": "heo-input-v1",
    }
    # Ältere HEO-Versionen speicherten den dezentralen H2-Kessel als
    # unbekanntes DG-Zentralgerät. Dieser Schalter hat keine DG-Bedeutung.
    for field in ("values", "defaults", "saved_values"):
        result[field].pop("C_H2BOI__FEASIBLE", None)
    result["location_mode"] = location_mode_from_state(source)
    result["custom_location_name"] = (
        str(result["values"].get("LOCATION_NAME") or "").strip()
        if result["location_mode"] == LOCATION_MODE_OTHER
        else ""
    )
    return result


# Übersetzt HEO-Werte und -Einheiten in die von DG erwarteten Env-Werte.
def heo_state_to_dg_values(
    state: dict[str, Any] | None,
    *,
    weather_metadata: dict[str, Any] | None = None,
    require_complete_location: bool = False,
    has_weather_upload: bool = False,
) -> dict[str, Any]:

    source = state or {}
    if require_complete_location:
        if source.get("annual_errors"):
            raise ValueError("Jahresreihen korrigieren: " + "; ".join(source["annual_errors"].values()))
        support_years({**source.get("defaults", {}), **source.get("values", {})})
        source = reconcile_series(source)
    values = _map_value_dict(source.get("values"), to_heo=False)
    values.pop("C_H2BOI__FEASIBLE", None)
    defaults = _map_value_dict(source.get("defaults"), to_heo=False)
    mode = source.get("location_mode") or LOCATION_MODE_PIDULA

    if mode == LOCATION_MODE_PIDULA:
        values["LOCATION_NAME"] = defaults.get("LOCATION_NAME", "Pidula, Estland")
        values["USE_GERMAN_ZIP"] = False
        values["WEATHER_FILE"] = defaults.get("WEATHER_FILE", values.get("WEATHER_FILE"))
    elif mode == LOCATION_MODE_GERMANY:
        values["USE_GERMAN_ZIP"] = True
        try:
            site = lookup_german_site(values.get("ZIP"))
        except (ValueError, OSError):
            if require_complete_location:
                raise
            values["LOCATION_NAME"] = f"Deutschland · PLZ {values.get('ZIP') or ''}"
        else:
            values["ZIP"] = site["zip"]
            values["LOCATION_NAME"] = german_location_label(site)
        values["WEATHER_FILE"] = defaults.get("WEATHER_FILE", values.get("WEATHER_FILE"))
    elif mode == LOCATION_MODE_OTHER:
        values["USE_GERMAN_ZIP"] = False
        location_name = str(values.get("LOCATION_NAME") or "").strip()
        if require_complete_location and not location_name:
            raise ValueError("Bitte einen Namen für den sonstigen Standort eingeben.")
        if require_complete_location and not has_weather_upload:
            raise ValueError("Bitte für den sonstigen Standort eine EPW-Wetterdatei hochladen.")
        values["LOCATION_NAME"] = location_name
    else:
        raise ValueError(f"Unbekannter HEO-Standortmodus: {mode}")

    timezone = automatic_location_timezone(mode, weather_metadata)
    if timezone is not None:
        values["TIMEZONE"] = timezone
    # EPW-Dateien enthalten stündliche Albedowerte. Der Parser legt daraus
    # einen globalstrahlungsgewichteten Jahreswert in den Wettermetadaten ab;
    # dieser ersetzt den historischen manuellen Standardwert.
    weather_albedo = (weather_metadata or {}).get("albedo")
    try:
        weather_albedo = float(weather_albedo)
    except (TypeError, ValueError):
        weather_albedo = None
    stored_albedo = values.get("ALBEDO")
    try:
        stored_albedo = float(stored_albedo)
    except (TypeError, ValueError):
        stored_albedo = None
    overrides = {str(key).upper() for key in source.get("overrides", [])}
    manual_albedo = (
        "ALBEDO" in overrides
        and stored_albedo is not None
        and weather_albedo is not None
        and abs(stored_albedo - weather_albedo) > 1e-9
    )
    if (
        not manual_albedo
        and weather_albedo is not None
        and 0.0 <= weather_albedo <= 1.0
    ):
        values["ALBEDO"] = weather_albedo
    values["TRYTYPE"] = "Jahr"
    return values


# Erzeugt den technischen DG-Zustand für bestehende, lesende HEO-Tabs.
def heo_state_to_dg_state(
    state: dict[str, Any] | None,
    *,
    weather_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:

    source = state or {}
    return {
        "values": heo_state_to_dg_values(source, weather_metadata=weather_metadata),
        "defaults": _map_value_dict(source.get("defaults"), to_heo=False),
        "saved_values": _map_value_dict(source.get("saved_values"), to_heo=False),
        "overrides": [HEO_TO_DG_KEYS.get(str(key).upper(), key) for key in source.get("overrides", [])],
        "config_path": source.get("config_path"),
        "config_exists": bool(source.get("config_exists")),
        "load_error": source.get("load_error"),
    }


# Übersetzt die Freigabe eines zentralen Geräts in den zugehörigen DG-Parameter.
def set_device_feasible(
    heo_state: dict[str, Any],
    code: str,
    enabled: bool,
) -> dict[str, Any]:
    updated = deepcopy(heo_state)
    updated.setdefault("values", {})[f"C_{code}__FEASIBLE"] = bool(enabled)
    return updated

