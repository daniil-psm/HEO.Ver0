# Baut aus einem HEO-Entwurf geprüfte DG-Eingabedateien.
# Prüft zuerst den vollständigen Entwurf, schreibt dann Config, Wetter, CSV und Editor-Metadaten.
# Der Aufrufer übernimmt Startskripte und die Ausführung des DG.
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ..shared.dg_paths import scenario_dir_for_config
from ..input.site_lookup import LOCATION_MODE_OTHER
from .input_mapper import heo_state_to_dg_values
from .config_service import validate_new_scenario_name
from .env_config_builder import save_dg_config
from .building_csv_builder import save_building_scenario
from .validation import validate_inputs, normalize_building_row

ANNUAL_EDITOR_METADATA = "heo_annual_series.json"


# Prüft den vollständigen HEO-Entwurf vor dem Schreiben.
# Erzeugt anschließend Config, Wetter und Gebäude-CSV und sichert die Metadaten des Jahresreiheneditors.
def build_inputs(
    state: dict[str, Any],
    buildings: list[dict[str, Any]],
    *,
    weather_upload: dict[str, Any] | None = None,
    weather_metadata: dict[str, Any] | None = None,
    config_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors = validate_inputs(
        state, buildings,
        weather_upload=weather_upload,
        weather_metadata=weather_metadata,
        config_state=config_state,
    )
    if errors:
        raise ValueError("\n".join(error.message for error in errors))
    buildings = [normalize_building_row(row) for row in buildings]
    values = heo_state_to_dg_values(
        state,
        weather_metadata=weather_metadata,
        require_complete_location=True,
        has_weather_upload=bool(weather_upload),
    )
    if (config_state or {}).get("create_token") and not config_state.get("source_scenario"):
        validate_new_scenario_name(values["SCENARIO_NAME"])
    weather_to_save = weather_upload if state.get("location_mode") == LOCATION_MODE_OTHER else None
    config_result = save_dg_config(values, weather_upload=weather_to_save)
    building_result = save_building_scenario(config_result["scenario_name"], buildings)
    metadata_path = (
        scenario_dir_for_config(Path(config_result["config_path"]))
        / ANNUAL_EDITOR_METADATA
    )
    editors = state.get("annual_series", {})
    content = json.dumps(
        {"editors": editors, "values": {key: values[key] for key in editors}},
        ensure_ascii=False,
        indent=2,
    )
    if not metadata_path.exists() or metadata_path.read_text(encoding="utf-8") != content:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=metadata_path.parent, delete=False,
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        try:
            os.replace(temporary, metadata_path)
        finally:
            temporary.unlink(missing_ok=True)
    return config_result, building_result

