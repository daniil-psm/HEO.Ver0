# Laden gespeicherter HEO-Szenarien mit dem DG

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..input.config_service import DG_ROOT, scenario_config_path
from ..shared.scenario_names import validate_scenario_name
from ..input.scenario_paths import scenario_building_csv_path


# Aufgelöste Pfade und Argumente eines gespeicherten HEO-Szenarios
@dataclass(frozen=True)
class DGScenarioContext:
    scenario_name: str
    scenario_dir: Path
    config_path: Path

    @property
    def datahandler_arguments(self) -> dict[str, str]:
        return {
            "scenario_name": self.scenario_name,
            "env_path": str(self.config_path),
            "scenario_file_path": str(self.scenario_dir),
        }

    @property
    def building_csv_path(self) -> Path:
        return scenario_building_csv_path(self.scenario_name).resolve()


def resolve_dg_scenario(scenario_name: Any) -> DGScenarioContext:
    """Löst ein gespeichertes Szenario auf und prüft seine Config-Datei."""

    name = validate_scenario_name(scenario_name)
    config_path = scenario_config_path(name).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Für das Szenario {name!r} wurde noch keine Config gespeichert: "
            f"{config_path}"
        )
    return DGScenarioContext(
        scenario_name=name,
        scenario_dir=config_path.parent,
        config_path=config_path,
    )


# Lädt die Szenario-Config über den offiziellen DG-Config-Loader
def load_global_config_for_scenario(scenario_name: Any):
    context = resolve_dg_scenario(scenario_name)
    if str(DG_ROOT) not in sys.path:
        sys.path.insert(0, str(DG_ROOT))

    from districtgenerator.data_handling.config import load_global_config

    return load_global_config(env_file=str(context.config_path))


# Erzeugt einen DG-Datahandler mit dem absoluten HEO-Szenariopfad
def create_datahandler_for_scenario(scenario_name: Any, **datahandler_options):
    context = resolve_dg_scenario(scenario_name)
    if not context.building_csv_path.is_file():
        raise FileNotFoundError(
            f"Für das Szenario {context.scenario_name!r} wurde noch keine Gebäude-CSV "
            f"gespeichert: {context.building_csv_path}"
        )
    if str(DG_ROOT) not in sys.path:
        sys.path.insert(0, str(DG_ROOT))

    from districtgenerator.classes.datahandler import Datahandler

    options = dict(datahandler_options)
    options.update(context.datahandler_arguments)
    return Datahandler(**options)
