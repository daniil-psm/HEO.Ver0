"""Portable provenance for a DG calculation and its input files."""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from dotenv import dotenv_values

from ..input.config_service import APP_ROOT, DG_ROOT
from .profile_service import load_profile_options

_PACKAGES = (
    "numpy", "pandas", "scipy", "pyomo",
    "teaser", "OpenDHW", "pydantic", "pydantic-settings", "holidays",
    "richardsonpy", "pyproj", "geopy", "pylightxl",
)
_ADAPTER_SOURCES = (
    "dg_model_preparation.py", "profile_service.py", "profile_fingerprint.py",
    "dg_comparison_service.py", "dg_project_snapshot.py",
)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _python_hash(path: Path) -> str:
    # A checkout with different line endings or comments runs the same code.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def _location(config_path: Path):
    from districtgenerator.data_handling.config import LocationConfig

    return LocationConfig(_env_file=str(config_path))


def _resolve_weather_path(config_path: Path) -> Path | None:
    location = _location(config_path)
    if location.use_german_zip:
        return None
    configured = Path(str(location.weather_file)).expanduser()
    candidates = ((configured,) if configured.is_absolute() else (
        config_path.parent / configured,
        Path.cwd() / configured,
        APP_ROOT / configured,
        DG_ROOT / "districtgenerator" / "data" / configured,
    ))
    return next((path.resolve() for path in candidates if path.is_file()), None)


def _german_weather_hash(config_path: Path) -> str:
    """Hash the TRY file selected by the DG postal-code lookup."""
    from openpyxl import load_workbook

    location = _location(config_path)
    data_dir = DG_ROOT / "districtgenerator" / "data"
    workbook = load_workbook(data_dir / "plz_geocoord_matched.xlsx", read_only=True,
                             data_only=True)
    station = "507755060854"  # DG fallback station for unknown postal codes.
    try:
        requested = str(location.zip).strip().zfill(5)
        for row in workbook.active.iter_rows(values_only=True):
            if str(row[0]).split(".", 1)[0].strip().zfill(5) == requested:
                station = str(row[3])[8:-9]
                break
    finally:
        workbook.close()
    year = str(location.TRYYear)
    kind = str(location.TRYType)
    weather = (data_dir / "weather" / f"TRY_{year[-4:]}_{kind}"
               / f"{year}_{station}_{kind}.dat")
    return _file_hash(weather)


def _git_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(APP_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def input_details(config_path: Path, building_path: Path) -> dict:
    """Capture portable inputs without inspecting the current software."""
    config_path = Path(config_path).resolve()
    building_path = Path(building_path).resolve()
    if str(DG_ROOT) not in sys.path:
        sys.path.insert(0, str(DG_ROOT))
    config = dict(dotenv_values(config_path))
    config.pop("OPTIMIZATION_FOCUS", None)
    scenario_dir = config_path.parent.parent.parent
    options = load_profile_options(scenario_dir).snapshot()
    options.pop("source", None)
    weather = _resolve_weather_path(config_path)
    uses_german_zip = bool(_location(config_path).use_german_zip)
    if weather is None and not uses_german_zip:
        raise FileNotFoundError("Die für die Optimierung konfigurierte Wetterdatei fehlt.")
    weather_hash = (_german_weather_hash(config_path) if uses_german_zip
                    else _file_hash(weather) if weather else None)
    # The configured location is represented by the selected file content.
    config.pop("WEATHER_FILE", None)
    inputs = {
        "config": config,
        "buildings_sha256": _file_hash(building_path),
        "weather_sha256": weather_hash,
        "profile_options": options,
    }
    return inputs


def current_input_sha256(config_path: Path, building_path: Path) -> str:
    return _digest(input_details(config_path, building_path))


def calculation_context(config_path: Path, building_path: Path) -> dict:
    """Capture effective input identity and the computation environment.

    Paths are deliberately omitted from the identity; file contents are used.
    The strict prepared-model cache continues to use its own fingerprint.
    """
    inputs = input_details(config_path, building_path)
    package_versions = {}
    solver = str(inputs["config"].get("SOLVER_NAME") or "gurobi").lower()
    solver_package = {"highs": "highspy", "gurobi": "gurobipy"}.get(solver)
    for package in (*_PACKAGES, *((solver_package,) if solver_package else ())):
        try:
            package_versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            package_versions[package] = None
    if solver == "cbc":
        executable = shutil.which("cbc")
        if executable:
            try:
                output = subprocess.run(
                    [executable, "-version"], capture_output=True,
                    text=True, timeout=2, check=True,
                )
                package_versions["cbc"] = output.stdout.strip() or output.stderr.strip()
            except (OSError, subprocess.SubprocessError):
                package_versions["cbc"] = None
        else:
            package_versions["cbc"] = None
    backend = DG_ROOT / "districtgenerator"
    source_hashes = {
        f"dg/{path.relative_to(backend).as_posix()}": _python_hash(path)
        for path in sorted(backend.rglob("*.py"))
    }
    source_hashes.update({
        f"adapter/{name}": _python_hash(Path(__file__).with_name(name))
        for name in _ADAPTER_SOURCES
    })
    software = {
        "python": ".".join(map(str, sys.version_info[:3])),
        "packages": package_versions,
        "sources_sha256": _digest(source_hashes),
        "source_files_sha256": source_hashes,
        "git_revision": _git_revision(),
    }
    # The Git revision is informative. Unrelated commits must not invalidate a run.
    computation = {key: value for key, value in software.items() if key != "git_revision"}
    return {
        "schema_version": 1,
        "input_sha256": _digest(inputs),
        "software_sha256": _digest(computation),
        "inputs": inputs,
        "software": software,
    }


def same_calculation(saved: object, current: dict) -> bool:
    return bool(
        isinstance(saved, dict)
        and saved.get("schema_version") == 1
        and saved.get("input_sha256") == current["input_sha256"]
        and saved.get("software_sha256") == current["software_sha256"]
    )
