"""Serialisierbarer Eingabestand für Projektinfos eines Berechnungslaufs."""

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from ..input.scenario_service import load_building_scenario


# Fixiert Gebäude-IDs und Ergebnisindizes für die Zuordnung zum späteren Lauf.
def build_topology_snapshot(
    buildings: dict | Iterable[dict] | None,
) -> dict[str, Any]:
    if isinstance(buildings, dict):
        source_rows = buildings.get("rows") or []
    else:
        source_rows = buildings or []
    rows = [
        {**deepcopy(row), "result_index": index}
        for index, row in enumerate(source_rows)
        if isinstance(row, dict)
    ]
    return {"schema_version": 1, "buildings": rows}


def capture_project_snapshot(data: Any, config_path: Path, building_path: Path) -> dict:
    # Wird direkt nach der Initialisierung des Datahandlers aufgerufen, bevor
    # Zeitreihen und abgeleitete Geräteparameter dessen Eingaben erweitern.
    from ..input.config_bridge import build_schema

    sections = build_schema(config_path)["sections"]
    attributes = {
        "location": "site", "time": "time", "calendar": "calendar",
        "design_building": "design_building_data", "eco": "ecoData",
        "heatgrid": "heat_grid_data", "ehdo": "params_ehdo_model",
        "physics": "physics", "pyomo": "pyomo_config", "report": "report_config",
        "central": "central_device_data", "decentral": "decentral_device_data",
    }
    values, defaults = {}, {}
    for section in sections:
        source = getattr(data, attributes[section["key"]])
        for field in section["fields"]:
            key = field["env_key"]
            defaults[key] = deepcopy(field["default"])
            value = source
            # Pydantic fasst z.B. solver_options__time_limit zu einem Dict zusammen.
            if field["field_name"] in source:
                value = source[field["field_name"]]
            else:
                for part in field["field_name"].split("__"):
                    if not isinstance(value, dict) or part not in value:
                        value = field["value"]
                        break
                    value = value[part]
            values[key] = deepcopy(value)
    values["SCENARIO_NAME"] = data.scenario_name
    return {
        "schema_version": 1,
        "source": "run",
        "config": {"values": values, "defaults": defaults},
        "buildings": deepcopy(load_building_scenario(data.scenario_name, csv_path=building_path)),
        "weather": {"filename": str(values.get("WEATHER_FILE") or "")},
    }
