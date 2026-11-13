# Serialisiert DG-Optimierungsergebnisse als dauerhaftes HEO-Ergebnisbundle.

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .component_results import network_design_from_grid, building_thermal_imports_from_solutions

OPTIMIZATION_BUNDLE_FILENAME = "optimization_results.json"
CAPACITY_PATTERN = re.compile(r"^cap\[([^\]]+)\]\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$")
AREA_PATTERN = re.compile(r"^area\[([^\]]+)\]\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$")
ENERGY_STORAGE_DEVICE_CODES = {"BAT", "H2S", "GS", "TES", "CTES"}


# Wandelt DG- und NumPy-Werte in JSON-fähige Werte um.
def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


# Liest optimierte Kapazitäten aus der EHDO-Lösungsdatei.
def _optimized_capacities(result_path: Path) -> dict[str, Any]:
    solution_path = result_path / "optimization_results" / "solution_file_ehdo_model.txt"
    if not solution_path.is_file():
        return {"source_file": None, "devices": {}}

    capacities: dict[str, float] = {}
    areas: dict[str, float] = {}
    with solution_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            capacity_match = CAPACITY_PATTERN.match(line)
            if capacity_match:
                capacities[capacity_match.group(1)] = float(capacity_match.group(2))
                continue
            area_match = AREA_PATTERN.match(line)
            if area_match:
                areas[area_match.group(1)] = float(area_match.group(2))

    devices = {
        code: {
            "value": value,
            "unit": (
                "kWh"
                if code in ENERGY_STORAGE_DEVICE_CODES
                else "kW"
            ),
            **({"area_m2": areas[code]} if code in areas else {}),
        }
        for code, value in capacities.items()
    }
    return {
        "source_file": str(solution_path.resolve()),
        "devices": devices,
    }


# Schreibt das vollständige Ergebnisbundle atomar als JSON.
def save_optimization_results(
    data: Any,
    *,
    objective: str | None = None,
    optimization_focus: int | None = None,
    profile_hash: str | None = None,
    comparison_run_id: str | None = None,
    summary: dict[str, Any] | None = None,
    _capacity_reader=None,
) -> Path:
    result_path = Path(data.resultPath).resolve() / "optimization_results"
    result_path.mkdir(parents=True, exist_ok=True)
    target = result_path / OPTIMIZATION_BUNDLE_FILENAME
    payload = {
        "schema_version": 1,
        "source": "district_generator",
        "scenario_name": str(data.scenario_name),
        "objective": objective,
        "optimization_focus": optimization_focus,
        "profile_hash": profile_hash,
        "comparison_run_id": comparison_run_id,
        "project_snapshot": _json_value(getattr(data, "project_snapshot", None)),
        "units": {
            "time_series_power": "W",
            "energy_totals": "kWh",
            "costs": "EUR",
            "emissions": "kg_CO2eq",
        },
        "time": _json_value(data.time),
        "clusters": _json_value(getattr(data, "clusters", [])),
        "cluster_assignments": _json_value(
            getattr(data, "clusterAssignments", [])
        ),
        "cluster_weights": _json_value(getattr(data, "clusterWeights", [])),
        "simulated_years": _json_value(
            getattr(data, "ecoData", {}).get("interpolation_points", [])
        ),
        "capacities": (_capacity_reader or _optimized_capacities)(Path(data.resultPath).resolve()),
        "network_design": network_design_from_grid(getattr(data, "heat_grid_data", None)),
        "summary": _json_value(summary or {}),
        "results": _json_value(data.resultsOptimization),
    }
    payload["building_thermal_imports"] = building_thermal_imports_from_solutions(
        result_path, payload
    )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".heo-optimization-results-",
            suffix=".tmp",
            dir=result_path,
            delete=False,
        ) as temporary_file:
            json.dump(payload, temporary_file, ensure_ascii=False, separators=(",", ":"))
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return target
