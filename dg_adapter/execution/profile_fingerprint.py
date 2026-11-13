# Berechnet den Cache-Schlüssel für die gemeinsame DG-Modellvorbereitung.

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..input.config_service import APP_ROOT, DG_ROOT
from ..shared.dg_paths import scenario_dir_for_config
from .profile_service import load_profile_options

PREPARED_SCENARIO_SCHEMA_VERSION = 5
_OBJECTIVE_LINE = re.compile(r"^\s*OPTIMIZATION_FOCUS\s*=", re.IGNORECASE)


# Entfernt nur den Variantenfokus aus der Basiskonfiguration.
def without_objective(config_text: str) -> str:
    lines = [line for line in config_text.splitlines() if not _OBJECTIVE_LINE.match(line)]
    return "\n".join(lines).rstrip() + "\n"


# Fügt eine Datei samt stabiler Kennung in den Hash ein.
def _hash_file(hasher: Any, label: str, path: Path) -> None:
    hasher.update(label.encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(path.read_bytes())
    hasher.update(b"\0")


# Löst die tatsächlich konfigurierte EPW-Datei wie der Datahandler auf.
def _resolve_weather_path(config_path: Path) -> Path | None:
    try:
        from districtgenerator.data_handling.config import load_global_config

        config = load_global_config(env_file=str(config_path))
        if bool(config.location.use_german_zip):
            return None
        configured = Path(str(config.location.weather_file)).expanduser()
    except (AttributeError, ImportError, OSError, ValueError):
        return None

    if configured.is_absolute():
        candidates = (configured,)
    else:
        candidates = (
            config_path.parent / configured,
            Path.cwd() / configured,
            APP_ROOT / configured,
            DG_ROOT / "districtgenerator" / "data" / configured,
        )
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)


# Hasht Konfiguration, Gebäude, Wetter, DG-Quellen und Profiloptionen.
def build_profile_fingerprint(
    config_path: Path,
    building_csv_path: Path,
    *,
    include_backend_sources: bool = True,
) -> str:
    """Der Optimierungsfokus allein ändert die gemeinsame Vorbereitung nicht."""

    config_path = Path(config_path).resolve()
    building_csv_path = Path(building_csv_path).resolve()
    hasher = hashlib.sha256()
    hasher.update(f"prepared-schema:{PREPARED_SCENARIO_SCHEMA_VERSION}\n".encode("ascii"))
    hasher.update(without_objective(config_path.read_text(encoding="utf-8")).encode("utf-8"))
    _hash_file(hasher, "buildings", building_csv_path)

    weather_path = _resolve_weather_path(config_path)
    if weather_path is not None:
        _hash_file(hasher, "weather", weather_path)

    if include_backend_sources:
        package_root = DG_ROOT / "districtgenerator"
        for source_path in sorted(package_root.rglob("*.py")):
            _hash_file(
                hasher,
                str(source_path.relative_to(package_root)).replace("\\", "/"),
                source_path,
            )
    _hash_file(hasher, "adapter-model-preparation", Path(__file__).with_name("dg_model_preparation.py"))
    _hash_file(hasher, "adapter-profiles", Path(__file__).with_name("profile_service.py"))
    hasher.update(json.dumps(load_profile_options(scenario_dir_for_config(config_path)).snapshot(), sort_keys=True).encode())
    return hasher.hexdigest()
