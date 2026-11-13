# Kanonische Pfade für Gebäude-CSV und lokale Gebäudemetadaten eines Szenarios.

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import config_service
from ..shared.scenario_names import validate_scenario_name
from ..shared.dg_paths import dg_input_dir


BUILDING_METADATA_FILENAME = "heo_buildings.json"


# Liefert den Gebäude-CSV-Pfad im gemeinsamen HEO-/DG-Szenarioordner.
def scenario_building_csv_path(scenario_name: Any) -> Path:
    name = validate_scenario_name(scenario_name)
    return dg_input_dir(config_service.DG_SCENARIOS_DIR / name) / f"{name}.csv"


# Liefert den Pfad der rein lokalen HEO-Gebäudenamen.
def scenario_building_metadata_path(scenario_name: Any) -> Path:
    name = validate_scenario_name(scenario_name)
    return config_service.DG_SCENARIOS_DIR / name / BUILDING_METADATA_FILENAME
