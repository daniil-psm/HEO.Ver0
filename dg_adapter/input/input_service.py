# Lädt und speichert HEO-Szenarien über die envConfig und Gebäude-csv des DG

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .config_service import (
    load_dg_config_state,
    scenario_config_path,
)
from .input_mapper import (
    dg_state_to_heo_state,
    with_input_keys,
)
from ..execution.dg_run_service import save_scenario_run
from .scenario_service import (
    load_building_scenario,
)
from .site_lookup import LOCATION_MODE_OTHER
from heo.model.annual_series import numbers
from ..shared.dg_paths import scenario_dir_for_config
from ..execution.profile_service import (
    profile_seed_choice, save_profile_seed_choice, validate_profile_seed_choice,
)

from .input_builder import ANNUAL_EDITOR_METADATA
HEO_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / ".env.HEO_DEFAULTS"


# Laden der Default-Parameter und Übersetzung in das HEO-Eingabemodell
def load_heo_input_state(config_path: Path | None = None) -> tuple[list[dict], dict]:
    # HEO reset/preset defaults come from the env template. An imported
    # scenario's effective values still come exclusively from its DG config.
    if not HEO_DEFAULTS_PATH.is_file():
        raise FileNotFoundError(f"HEO-Vorgaben fehlen: {HEO_DEFAULTS_PATH}")
    default_sections, heo_defaults = load_dg_config_state(HEO_DEFAULTS_PATH)
    if config_path is None:
        sections, dg_state = default_sections, heo_defaults
        dg_state.update(config_path=None, config_exists=False)
    else:
        sections, dg_state = load_dg_config_state(config_path)
    for key in heo_defaults["overrides"]:
        dg_state["defaults"][key] = heo_defaults["values"][key]
    state = dg_state_to_heo_state(dg_state)
    if config_path is not None:
        try:
            metadata = json.loads((scenario_dir_for_config(Path(config_path)) / ANNUAL_EDITOR_METADATA).read_text(encoding="utf-8"))
            for key, spec in metadata.get("editors", {}).items():
                # Ignore stale editor metadata after an external DG config edit.
                if numbers(state["values"][key]) == numbers(metadata["values"][key]):
                    state.setdefault("annual_series", {})[key] = spec
        except (OSError, ValueError, TypeError, KeyError):
            pass
    sections = with_input_keys(sections)
    for section in sections:
        for field in section["fields"]:
            if field["env_key"] in heo_defaults["overrides"]:
                field["default"] = state["defaults"][field["input_key"]]
    return sections, state


# Lädt die gespeicherte Wetterdatei als HEO-Uploadzustand und prüft ihren Szenariobezug.
def _scenario_weather_upload(state: dict[str, Any]) -> dict[str, str] | None:
    if state.get("location_mode") != LOCATION_MODE_OTHER:
        return None
    weather_reference = str(state.get("values", {}).get("WEATHER_FILE") or "").strip()
    if not weather_reference:
        raise ValueError("Im Szenario ist keine EPW-Wetterdatei hinterlegt.")

    config_path = Path(str(state.get("config_path") or "")).resolve()
    scenario_dir = config_path.parent.resolve()
    weather_path = Path(weather_reference)
    if not weather_path.is_absolute():
        weather_path = scenario_dir / weather_path
    weather_path = weather_path.resolve()
    if not weather_path.is_relative_to(scenario_dir):
        raise ValueError("Die Wetterdatei muss innerhalb des Szenarioordners liegen.")
    if not weather_path.is_file():
        raise FileNotFoundError(f"Gespeicherte EPW-Datei nicht gefunden: {weather_path}")
    contents = (
        "data:application/octet-stream;base64,"
        + base64.b64encode(weather_path.read_bytes()).decode("ascii")
    )
    return {"filename": weather_path.name, "contents": contents}


# Lädt Config, Gebäude und ggf. Wetterdatei eines Szenarios
def load_heo_scenario(scenario_name: str) -> dict[str, Any]:
    _sections, state = load_heo_input_state(scenario_config_path(scenario_name))
    state["values"]["SCENARIO_NAME"] = scenario_name
    return {
        "state": state,
        "buildings": load_building_scenario(scenario_name),
        "weather_upload": _scenario_weather_upload(state),
        "profile_seed_choice": profile_seed_choice(scenario_dir_for_config(Path(state["config_path"]))),
    }


# Speichert die Eingabedateien über den Builder und ergänzt das bisherige Startskript.
# Der Rückgabevertrag mit Config-, Gebäude- und Startskriptergebnis bleibt erhalten.
def save_heo_scenario(
    state: dict[str, Any],
    buildings: list[dict[str, Any]],
    *,
    weather_upload: dict[str, Any] | None = None,
    weather_metadata: dict[str, Any] | None = None,
    config_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from .input_builder import build_inputs
    seed_mode = (config_state or {}).get("profile_seed_mode")
    seed = (config_state or {}).get("profile_seed")
    if seed_mode is not None:
        seed = validate_profile_seed_choice(seed_mode, seed)
    config_result, building_result = build_inputs(
        state, buildings, weather_upload=weather_upload,
        weather_metadata=weather_metadata, config_state=config_state,
    )
    if seed_mode is not None:
        scenario_dir = Path(config_result["scenario_dir"])
        previous_choice = profile_seed_choice(scenario_dir)
        config_result["profile_options_written"] = save_profile_seed_choice(
            scenario_dir, seed_mode, seed,
        )
        config_result["profile_options_changed"] = previous_choice != {
            "mode": seed_mode, "seed": seed,
        }
    else:
        config_result["profile_options_written"] = False
        config_result["profile_options_changed"] = False
    run_result = save_scenario_run(config_result["scenario_name"])
    return config_result, building_result, run_result
