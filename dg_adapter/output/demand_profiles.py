# Prüft, liest und aggregiert DG-Bedarfsprofile für die HEO-Ausgabe.

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..input.config_service import DG_SCENARIOS_DIR, scenario_config_path
from ..shared.scenario_names import validate_scenario_name
from ..input.scenario_paths import scenario_building_csv_path
from ..shared.dg_paths import dg_profiles_dir
from . import DGResultError, DGResultMissingError, DGResultStaleError

POWER_COLUMNS = {
    "elec": "electricity_load_kw",
    "EV_carcharging_ondemand": "ev_load_kw",
    "dhw": "dhw_load_kw",
    "heating": "heat_load_kw",
    "cooling": "cooling_load_kw",
}


# Bestimmt die erwarteten Profildateien aus der Gebäude-CSV.
def expected_demand_profile_paths(
    scenario_name: Any,
    *,
    demand_root: Path | None = None,
    building_rows: list[dict] | None = None,
) -> list[Path]:
    name = validate_scenario_name(scenario_name)
    if building_rows is None:
        building_path = scenario_building_csv_path(name)
        if not building_path.is_file():
            raise DGResultMissingError(
                f"Für das Szenario {name!r} fehlt die Gebäude-CSV: {building_path}"
            )
        buildings = pd.read_csv(building_path, sep=";", dtype={"building": "string"})
        if buildings.empty or not {"id", "building"}.issubset(buildings.columns):
            raise DGResultMissingError(
                f"Die Gebäude-CSV des Szenarios {name!r} enthält keine gültigen Gebäude."
            )
        rows = buildings.to_dict(orient="records")
    else:
        rows = building_rows

    demands_path = (
        Path(demand_root).resolve()
        if demand_root is not None
        else dg_profiles_dir(DG_SCENARIOS_DIR / name) / "demands"
    )
    paths: list[Path] = []
    for row in rows:
        try:
            building_id = int(float(row["id"]))
        except (TypeError, ValueError) as exc:
            raise DGResultError("Ungültige Gebäude-ID in den gespeicherten Eingaben.") from exc
        paths.append(
            demands_path
            / f"{name}_{building_id}_{str(row['building'])}_timeseries.csv"
        )
    return paths


# Prüft Vollständigkeit und Zeitstempel der Profile.
def _validate_profile_files(scenario_name: str, profile_paths: list[Path]) -> None:
    missing = [path for path in profile_paths if not path.is_file()]
    if missing:
        raise DGResultMissingError(
            "Noch keine vollständigen DG-Bedarfsprofile vorhanden. Es fehlen: "
            + ", ".join(path.name for path in missing)
        )

    input_paths = [
        scenario_building_csv_path(scenario_name),
        scenario_config_path(scenario_name),
    ]
    newest_input = max(
        (path.stat().st_mtime_ns for path in input_paths if path.is_file()),
        default=0,
    )
    stale = [path for path in profile_paths if path.stat().st_mtime_ns < newest_input]
    if stale:
        raise DGResultStaleError(
            "Die DG-Bedarfsprofile sind älter als die aktuelle Konfiguration oder "
            "Gebäude-CSV. Bitte die szenariospezifische run.py erneut ausführen."
        )


# Addiert die Leistungen aller Gebäude je Zeitschritt.
def _read_and_sum_profiles(profile_paths: list[Path]) -> pd.DataFrame:
    reference_timestep: np.ndarray | None = None
    summed: dict[str, np.ndarray] = {}

    for path in profile_paths:
        profile = pd.read_csv(path, sep=";")
        if "timestep" not in profile:
            raise DGResultError(f"DG-Profil ohne Spalte 'timestep': {path}")

        timestep = pd.to_numeric(profile["timestep"], errors="coerce").to_numpy(float)
        if np.isnan(timestep).any():
            raise DGResultError(f"Ungültige Zeitschritte im DG-Profil: {path}")

        if reference_timestep is None:
            reference_timestep = timestep
            summed = {
                target: np.zeros(len(timestep), dtype=float)
                for target in POWER_COLUMNS.values()
            }
        elif len(timestep) != len(reference_timestep) or not np.allclose(
            timestep,
            reference_timestep,
            rtol=0,
            atol=1e-9,
        ):
            raise DGResultError(
                f"Die Zeitschritte der DG-Profile stimmen nicht überein: {path.name}"
            )

        for source, target in POWER_COLUMNS.items():
            if source not in profile:
                continue
            values = pd.to_numeric(profile[source], errors="coerce").fillna(0.0)
            summed[target] += values.to_numpy(float) / 1000.0

    if reference_timestep is None or not len(reference_timestep):
        raise DGResultMissingError("Die DG-Bedarfsprofile enthalten keine Zeitschritte.")

    result = pd.DataFrame({"timestep_h": reference_timestep, **summed})
    result["electricity_total_kw"] = (
        result["electricity_load_kw"] + result["ev_load_kw"]
    )
    return result


# Ermittelt die Schrittweite aus den Profilzeitpunkten.
def _time_step_hours(timestep: pd.Series) -> float:
    differences = np.diff(timestep.to_numpy(float))
    positive = differences[differences > 0]
    return float(np.median(positive)) if positive.size else 1.0


# Ergänzt Zeitangaben und Energiemengen zu den Leistungswerten.
def _add_time_and_energy_columns(profile: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    result = profile.copy()
    step_hours = _time_step_hours(result["timestep_h"])
    result["datetime"] = pd.Timestamp("2015-01-01") + pd.to_timedelta(
        result["timestep_h"],
        unit="h",
    )
    result["date"] = result["datetime"].dt.date
    result["month"] = result["datetime"].dt.month
    result["day"] = result["datetime"].dt.day
    result["hour"] = result["datetime"].dt.hour
    result["day_of_year"] = result["datetime"].dt.dayofyear
    result["date_label"] = result["datetime"].dt.strftime("%d.%m.")
    result["step_hours"] = step_hours

    for power_column in (*POWER_COLUMNS.values(), "electricity_total_kw"):
        energy_column = power_column.removesuffix("_kw") + "_kwh"
        result[energy_column] = result[power_column] * step_hours

    # Kompatibilitätszuordnung für die bestehende PFC: DG-Nutzerstrom und EV
    # werden derzeit AC-seitig zusammengefasst; eine busgenaue Trennung liefert
    # erst die Optimierungsschnittstelle.
    result["ac_load_kw"] = result["electricity_total_kw"]
    result["dc_load_kw"] = 0.0
    return result, step_hours


# Verdichtet Stundenwerte zu Tagesbedarfen.
def _daily_profiles(profile: pd.DataFrame) -> pd.DataFrame:
    return (
        profile.groupby("day_of_year", sort=True)
        .agg(
            month=("month", "first"),
            day=("day", "first"),
            date_label=("date_label", "first"),
            electricity_kwh_day=("electricity_load_kwh", "sum"),
            ev_kwh_day=("ev_load_kwh", "sum"),
            electricity_total_kwh_day=("electricity_total_kwh", "sum"),
            dhw_kwh_day=("dhw_load_kwh", "sum"),
            heat_kwh_day=("heat_load_kwh", "sum"),
            cooling_kwh_day=("cooling_load_kwh", "sum"),
        )
        .reset_index()
        .rename(columns={"day_of_year": "day_index"})
    )


# Wandelt einen DataFrame in serialisierbare Spalten um.
def _frame_to_store(frame: pd.DataFrame) -> dict[str, list]:
    serializable = frame.copy()
    for column in serializable.select_dtypes(include=["datetime", "datetimetz"]):
        serializable[column] = serializable[column].astype(str)
    if "date" in serializable:
        serializable["date"] = serializable["date"].astype(str)
    return serializable.to_dict(orient="list")


# Lädt, prüft und aggregiert die Bedarfsprofile eines Szenarios.
def load_demand_results(
    scenario_name: Any,
    *,
    demand_root: Path | None = None,
    validate_timestamps: bool = True,
    building_rows: list[dict] | None = None,
) -> dict[str, Any]:
    name = validate_scenario_name(scenario_name)
    profile_paths = expected_demand_profile_paths(
        name, demand_root=demand_root, building_rows=building_rows,
    )
    if validate_timestamps:
        _validate_profile_files(name, profile_paths)
    elif missing := [path for path in profile_paths if not path.is_file()]:
        raise DGResultMissingError(
            "Noch keine vollständigen DG-Bedarfsprofile vorhanden. Es fehlen: "
            + ", ".join(path.name for path in missing)
        )
    profile, step_hours = _add_time_and_energy_columns(
        _read_and_sum_profiles(profile_paths)
    )
    daily = _daily_profiles(profile)

    return {
        "status": "ready",
        "source": "district_generator",
        "scenario_name": name,
        "results_path": str(
            (Path(demand_root).resolve().parent if demand_root else dg_profiles_dir(DG_SCENARIOS_DIR / name).resolve())
        ),
        "profile_files": [str(path.resolve()) for path in profile_paths],
        "building_count": len(profile_paths),
        "time_step_hours": step_hours,
        "message": (
            f"{len(profile_paths)} DG-Gebäudeprofile aus Szenario „{name}“ geladen."
        ),
        "hourly": _frame_to_store(profile),
        "daily": _frame_to_store(daily),
    }


# Formt Profilfehler in einen darstellbaren Status um.
def demand_result_error_store(
    scenario_name: Any,
    error: Exception,
) -> dict[str, Any]:
    name = str(scenario_name or "").strip()
    status = "stale" if isinstance(error, DGResultStaleError) else "missing"
    return {
        "status": status,
        "source": "district_generator",
        "scenario_name": name,
        "message": str(error),
        "hourly": {},
        "daily": {},
    }
