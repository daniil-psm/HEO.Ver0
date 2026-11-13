# Zentrale Prüfung der DG-Eingaben; liefert Fehler ohne Abhängigkeit von Dash oder Tabs.
from __future__ import annotations
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from ..shared.building_supply import cooling_supply, supply_validation_errors
from ..shared.device_catalog import DG_CENTRAL_DEVICE_CATALOG, HEATER_SYSTEM_PARTS, normalize_building_heater, building_heater_parts

SCENARIO_COLUMNS = (
    "id",
    "building",
    "year",
    "retrofit",
    "construction_type",
    "night_setback",
    "area",
    "heater",
    "dhw_heater",
    "cooling",
    "EV",
    "f_TES",
    "f_BAT",
    "f_PV1",
    "f_PV2",
    "f_STC",
    "beta_PV",
    "gamma_PV",
    "ev_charging",
)

from heo.model.building_types import BUILDING_TYPES, HEATER_TYPES, EV_CHARGING_TYPES
from heo.model.buildings import normalize_building_row as normalize_heo_building_row

# Prüft den E-Auto-Anteil zwischen 0 und 1 und unterstützt alte Boolean-Werte.
def _ev_fraction(value):
    if isinstance(value, str) and value.strip().lower() in {"true", "false", ""}:
        value = 1.0 if value.strip().lower() == "true" else 0.0
    result = float(value or 0.0)
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError("E-Auto-Anteil muss zwischen 0 und 100 % liegen.")
    return result


# Liest eine ganze Zahl und ergänzt bei ungültigen Werten den Feldnamen.
def _integer(value: Any, label: str) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: ganze Zahl erwartet.") from exc
    if not number.is_integer():
        raise ValueError(f"{label}: ganze Zahl erwartet.")
    return int(number)


# Liest einen Zahlenwert und ergänzt bei ungültigen Werten den Feldnamen.
def _number(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: Zahl erwartet.") from exc


# Normalisiert Schalterwerte aus Formularen oder Dateien auf 0 oder 1.
def _flag(value: Any) -> int:
    if isinstance(value, list):
        return int(bool(value))
    if isinstance(value, str):
        return int(value.strip().lower() in {"1", "true", "yes", "ja", "enabled"})
    return int(bool(value))


# Validiert UI-Zeilen und überführt sie in das exakte DG-CSV-Schema.
def validate_building_rows(rows: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:

    source_rows = list(rows or [])
    if not source_rows:
        raise ValueError("Bitte mindestens ein Gebäude anlegen.")

    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows, start=1):
        building_id = index
        errors = supply_validation_errors(row)
        if errors:
            raise ValueError(f"Gebäude {building_id}: {errors[0]}")

        building_type = str(row.get("building") or "").strip()
        if building_type not in BUILDING_TYPES:
            raise ValueError(f"Gebäude {building_id}: gültigen Gebäudetyp auswählen.")

        year = _integer(row.get("year"), f"Gebäude {building_id} · Baujahr")
        if year < 1860:
            raise ValueError(f"Gebäude {building_id}: Das Baujahr muss mindestens 1860 sein.")

        retrofit = _integer(row.get("retrofit"), f"Gebäude {building_id} · Sanierung")
        if retrofit not in {0, 1, 2}:
            raise ValueError(f"Gebäude {building_id}: Sanierungsstufe 0, 1 oder 2 wählen.")

        construction_type = _integer(
            row.get("construction_type"),
            f"Gebäude {building_id} · Bauweise",
        )
        if construction_type not in {0, 1, 2}:
            raise ValueError(f"Gebäude {building_id}: Bauweise 0, 1 oder 2 wählen.")

        area = _number(row.get("area"), f"Gebäude {building_id} · Fläche")
        if area <= 0:
            raise ValueError(f"Gebäude {building_id}: Die Fläche muss größer als 0 m² sein.")

        heater = str(row.get("heater") or "").strip()
        if heater not in HEATER_TYPES:
            raise ValueError(f"Gebäude {building_id}: gültiges Heizsystem auswählen.")

        ev_charging = str(row.get("ev_charging") or "on_demand").strip()
        if ev_charging not in EV_CHARGING_TYPES:
            raise ValueError(f"Gebäude {building_id}: gültigen EV-Lademodus auswählen.")

        f_tes = _number(row.get("f_TES"), f"Gebäude {building_id} · f_TES")
        if f_tes < 0:
            raise ValueError(f"Gebäude {building_id}: f_TES darf nicht negativ sein.")

        fraction_fields: dict[str, float] = {}
        battery_factor = _number(row.get("f_BAT"), f"Gebäude {building_id} · f_BAT")
        if battery_factor < 0:
            raise ValueError(f"Gebäude {building_id}: f_BAT darf nicht negativ sein.")
        fraction_fields["f_BAT"] = battery_factor
        for field in ("f_PV1", "f_PV2", "f_STC"):
            value = _number(row.get(field), f"Gebäude {building_id} · {field}")
            if value < 0 or value > 1:
                raise ValueError(f"Gebäude {building_id}: {field} muss zwischen 0 und 1 liegen.")
            fraction_fields[field] = value

        beta_pv = _number(row.get("beta_PV", 35.0), f"Gebäude {building_id} · beta_PV")
        if beta_pv < 0 or beta_pv > 90:
            raise ValueError(
                f"Gebäude {building_id}: beta_PV muss zwischen 0° und 90° liegen."
            )

        normalized.append(
            {
                "id": building_id,
                "building": building_type,
                "year": year,
                "retrofit": retrofit,
                "construction_type": construction_type,
                "night_setback": _flag(row.get("night_setback")),
                "area": area,
                "heater": heater,
                "dhw_heater": "EH_DHW" if _flag(row.get("dhw")) else 0,
                "cooling": _flag(row.get("cooling")),
                "EV": _ev_fraction(row.get("EV")),
                "f_TES": f_tes,
                **fraction_fields,
                "beta_PV": beta_pv,
                "gamma_PV": _number(
                    row.get("gamma_PV"),
                    f"Gebäude {building_id} · gamma_PV",
                ),
                "ev_charging": ev_charging,
            }
        )

    return normalized


# Prüft einen Config-Entwurf über eine temporäre Datei mit der DG-Bridge.
# Die temporäre Datei wird auch bei Validierungsfehlern entfernt; Szenarioeingaben bleiben unverändert.
def validate_dg_config_values(
    values: dict[str, Any],
    *,
    weather_upload: dict[str, Any] | None = None,
) -> dict[str, Any]:

    from . import config_service as config_service
    from .env_config_builder import _render_config
    from .weather_input import _decode_weather_upload

    scenario_name = config_service.scenario_name_from_values(values)
    config_path = config_service.scenario_config_path(scenario_name)
    effective_values = dict(values)
    if weather_upload and not bool(effective_values.get("USE_GERMAN_ZIP")):
        decoded_weather = _decode_weather_upload(weather_upload, config_path.parent)
        if decoded_weather is not None:
            effective_values["WEATHER_FILE"] = decoded_weather[2]

    sections, _ = config_service.load_dg_config_state(config_path)
    content, changed_count = _render_config(sections, effective_values)
    config_service.DG_SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".heo-config-check-",
            suffix=".tmp",
            dir=config_service.DG_SCENARIOS_DIR,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)
        config_service._run_bridge("validate", temporary_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return {
        "valid": True,
        "scenario_name": scenario_name,
        "changed_count": changed_count,
    }


# Beschreibt einen Eingabefehler unabhängig von seiner Darstellung im Konfigurator.
@dataclass(frozen=True)
class ValidationIssue:
    message: str
    field: str | None = None
    building_id: int | None = None


# Vereinheitlicht Heizsystembezeichnungen vor der Prüfung und CSV-Ausgabe.
def normalize_building_row(row: dict[str, Any]) -> dict[str, Any]:
    return normalize_heo_building_row(row)


# Prüft jede Gebäudezeile und erhält ihre Position für die spätere Fehlermarkierung.
def validate_buildings(buildings) -> list[ValidationIssue]:
    rows = buildings.get("rows", []) if isinstance(buildings, dict) else list(buildings or [])
    if not rows:
        return [ValidationIssue("Mindestens ein Gebäude muss hinzugefügt werden.", "buildings")]
    errors = []
    for index, row in enumerate(rows, start=1):
        try:
            validate_building_rows([normalize_building_row(row)])
        except (ValueError, TypeError, OverflowError) as exc:
            errors.append(ValidationIssue(str(exc).replace("Gebäude 1", f"Gebäude {index}", 1),
                                          "buildings", index))
    return errors


# Prüft die Versorgung des Entwurfs anhand fachlicher Gerätemetadaten.
# Verwendet keine UI-Komponenten; dieselben Regeln gelten beim Prüfen und Speichern.
def validate_supply(config_state, buildings) -> list[ValidationIssue]:
    state = config_state or {}
    selected = list(state.get("central_devices") or [])
    rows = buildings.get("rows", []) if isinstance(buildings, dict) else list(buildings or [])
    if not rows:
        return [ValidationIssue("Mindestens ein Gebäude muss hinzugefügt werden.", "buildings")]
    errors = []
    has_power = bool(state.get("grid_enabled")) or any(
        code in {"PV", "WT", "WAT", "FC", "CHP", "BCHP", "WCHP"} for code in selected)
    has_local_power = any(float(row.get("f_PV1") or 0) + float(row.get("f_PV2") or 0) > 0
                          or bool(set(building_heater_parts(row.get("heater"))) & {"CHP", "FC"}) for row in rows)
    heat = any(code != "TES" and "heat" in DG_CENTRAL_DEVICE_CATALOG.get(code, {}).get("outputs", ())
               for code in selected)
    cooling = any("cool" in DG_CENTRAL_DEVICE_CATALOG.get(code, {}).get("outputs", ()) for code in selected)
    if not has_power and not has_local_power:
        errors.append(ValidationIssue("Mindestens eine elektrische Versorgung muss hinzugefügt werden.", "supply"))
    if any(normalize_building_row(row)["heater"] == "heat_grid" for row in rows) and not heat:
        errors.append(ValidationIssue("Mindestens ein Wärmeerzeuger muss hinzugefügt werden.", "supply"))
    for index, row in enumerate(rows, start=1):
        building_id = row.get("id") or index
        errors.extend(ValidationIssue(f"Gebäude {building_id}: {message}", "supply", building_id)
                      for message in supply_validation_errors(row))
        heater = normalize_building_row(row)["heater"]
        if heater != "heat_grid" and heater not in HEATER_SYSTEM_PARTS:
            errors.append(ValidationIssue(f"Gebäude {building_id}: Unbekannte Heizkombination "
                f"{row.get('heater')!r}. Zulässig sind die im Konfigurator "
                "angebotenen Heizsysteme und ihre bekannten x+y-Kombinationen.", "heater", building_id))
        if cooling_supply(row) == "central" and not cooling:
            errors.append(ValidationIssue(f"Gebäude {building_id}: Zentrale Kälteversorgung wurde gewählt, "
                "aber es ist keine zentrale Kälteerzeugung vorhanden.", "cooling", building_id))
        if heater == "heat_grid" and float(row.get("f_TES") or 0) > 0:
            errors.append(ValidationIssue(f"Gebäude {building_id}: Ein dezentraler Wärmespeicher ist bei "
                "zentraler Wärmeversorgung nicht zulässig.", "f_TES", building_id))
    return errors


# Prüft einen vollständigen HEO-Entwurf vor dem Schreiben von Szenariodateien.
# Gebäude werden zuerst geprüft, anschließend Versorgung, Wetter und das originale DG-Schema.
# Ohne Konfiguratorzustand werden die Versorgungsfreigaben aus den DG-Eingabewerten abgeleitet.
def validate_inputs(state, buildings, *, weather_upload=None, weather_metadata=None,
                    config_state=None) -> list[ValidationIssue]:
    from ..input.config_service import DGConfigError
    from .input_mapper import heo_state_to_dg_values
    from .weather_input import parse_weather_upload

    errors = validate_buildings(buildings)
    if errors:
        return errors
    try:
        values = heo_state_to_dg_values(state, weather_metadata=weather_metadata,
            require_complete_location=True, has_weather_upload=bool(weather_upload))
        if config_state is None:
            effective = {**(state or {}).get("defaults", {}), **values}
            config_state = {
                "central_devices": [code for code, spec in DG_CENTRAL_DEVICE_CATALOG.items()
                    if _flag(effective.get(f"C_{spec['dg_code']}__FEASIBLE"))],
                "grid_enabled": bool(_flag(effective.get("ENABLE_SUPPLY_EL", True))),
            }
        errors.extend(validate_supply(config_state, buildings))
        if weather_upload:
            parse_weather_upload(weather_upload.get("contents"), weather_upload.get("filename") or "weather.epw")
        validate_dg_config_values(values, weather_upload=weather_upload)
    except (DGConfigError, ValueError, TypeError, OSError, OverflowError) as exc:
        errors.append(ValidationIssue(str(exc)))
    return list(dict.fromkeys(errors))
