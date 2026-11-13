"""Canonical locations of scenario inputs, shared preparation and results."""

from __future__ import annotations

from pathlib import Path


OBJECTIVES = ("economic", "ecological")


def scenario_root(scenario_dir: Path) -> Path:
    return Path(scenario_dir)


def dg_input_dir(scenario_dir: Path) -> Path:
    return scenario_root(scenario_dir) / "common" / "dg_input"


def dg_profiles_dir(scenario_dir: Path) -> Path:
    return scenario_root(scenario_dir) / "common" / "dg_profiles"


def seed_control_dir(scenario_dir: Path) -> Path:
    return scenario_root(scenario_dir) / "common" / "heo_seed_control"


def results_dir(scenario_dir: Path) -> Path:
    return scenario_root(scenario_dir) / "results"


def objective_dir(scenario_dir: Path, objective: str) -> Path:
    if objective not in OBJECTIVES:
        raise ValueError(f"Unbekanntes Optimierungsziel: {objective!r}")
    return results_dir(scenario_dir) / objective


def dg_results_dir(scenario_dir: Path, objective: str) -> Path:
    return objective_dir(scenario_dir, objective) / "dg_results"


def heo_results_dir(scenario_dir: Path, objective: str) -> Path:
    return objective_dir(scenario_dir, objective) / "heo_postprocessing_results"


def scenario_dir_for_config(config_path: Path) -> Path:
    parent = Path(config_path).parent
    if parent.name == "dg_input" and parent.parent.name == "common":
        return parent.parent.parent
    return parent
