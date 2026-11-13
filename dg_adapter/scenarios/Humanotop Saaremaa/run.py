# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from pathlib import Path


SCENARIO_NAME = 'Humanotop Saaremaa'
SCENARIO_DIR = Path(__file__).resolve().parent
DG_INPUT_DIR = SCENARIO_DIR / "common" / "dg_input"
CONFIG_PATH = DG_INPUT_DIR / ".env.CONFIG"
BUILDING_CSV_PATH = DG_INPUT_DIR / f"{SCENARIO_NAME}.csv"
RESULTS_DIR = SCENARIO_DIR / "results"


# Sucht den HEO-Projektordner unabhängig vom aktuellen Arbeitsverzeichnis.
def _find_heo_root() -> Path:
    for candidate in SCENARIO_DIR.parents:
        if (
            (candidate / "dg_backend" / "districtgenerator").is_dir()
            and (candidate / "dg_adapter").is_dir()
        ):
            return candidate
    raise FileNotFoundError(
        "Der HEO-Projektordner mit dg_backend und dg_adapter wurde nicht gefunden."
    )


# Ergänzt die Projektordner für die verzögert geladenen HEO- und DG-Module.
def _configure_import_paths() -> None:
    heo_root = _find_heo_root()
    for project_path in (heo_root / "dg_backend", heo_root):
        path_entry = str(project_path)
        if path_entry not in sys.path:
            sys.path.insert(0, path_entry)


# Modelliert, optimiert und bewertet das gespeicherte Einzelszenario.
def run_scenario():
    _configure_import_paths()
    from dotenv import dotenv_values
    from dg_adapter.execution.dg_comparison_service import run_scenario_comparison
    focus = int(dotenv_values(CONFIG_PATH).get("OPTIMIZATION_FOCUS") or 0)
    if focus not in (0, 1):
        raise ValueError(f"Ungültiger OPTIMIZATION_FOCUS: {focus}")
    return run_scenario_comparison(
        SCENARIO_NAME, scenario_dir=SCENARIO_DIR,
        objectives=(("economic", "ecological")[focus],),
    )


# Berechnet die gewählten Optimierungsziele mit gemeinsamer Vorverarbeitung.
def run_comparison():
    _configure_import_paths()

    from dg_adapter.execution.dg_comparison_service import run_scenario_comparison

    return run_scenario_comparison(
        SCENARIO_NAME,
        scenario_dir=SCENARIO_DIR,
        objectives=tuple(
            os.environ.get("HEO_OPTIMIZATION_OBJECTIVES", "economic,ecological").split(",")
        ),
    )


if __name__ == "__main__":
    comparison = run_comparison()
