# Verwaltet gespeicherte Szenarien und liest DG-Konfigurationen; Builder und Prüfung liegen in input/.

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from ..execution.run_template import RUN_FILENAME, render_scenario_run
from ..shared.dg_paths import dg_input_dir, dg_profiles_dir, results_dir, scenario_dir_for_config, seed_control_dir
from ..shared.scenario_names import validate_scenario_name


APP_ROOT = Path(__file__).resolve().parents[2]
DG_ADAPTER_DIR = Path(__file__).resolve().parents[1]
DG_ROOT = APP_ROOT / "dg_backend"
DG_SCENARIOS_DIR = DG_ADAPTER_DIR / "scenarios"
DG_BRIDGE_PATH = DG_ADAPTER_DIR / "input" / "config_bridge.py"
DG_CONFIG_FILENAME = ".env.CONFIG"
SCENARIO_NAME_KEY = "SCENARIO_NAME"
HEO_SCENARIO_NAMES_FILENAME = ".heo_scenario_names.json"


# Fehler beim Lesen, Validieren oder Schreiben der DG-Konfiguration.
class DGConfigError(RuntimeError):
    pass


# Liefert den zentralen HEO-/DG-Pfad für ein Szenario.
def scenario_config_path(scenario_name: Any) -> Path:

    name = validate_scenario_name(scenario_name)
    return dg_input_dir(DG_SCENARIOS_DIR / name) / DG_CONFIG_FILENAME


# Liest den Szenarionamen aus dem GUI-Entwurf.
def scenario_name_from_values(values: dict[str, Any]) -> str:

    return validate_scenario_name(
        values.get(SCENARIO_NAME_KEY) or next_microgrid_name()
    )


def _occupied_scenario_names() -> set[str]:
    """Berücksichtigt auch Anzeigenamen und noch unvollständige Szenarioordner."""
    names = {path.name for path in DG_SCENARIOS_DIR.iterdir()} if DG_SCENARIOS_DIR.is_dir() else set()
    names.update(item["display_name"] for item in list_dg_scenarios())
    return names


def next_microgrid_name() -> str:
    """Liefert den kleinsten freien positiven Microgrid-Index."""
    occupied = _occupied_scenario_names()
    number = 1
    while f"Microgrid {number}" in occupied:
        number += 1
    return f"Microgrid {number}"


def validate_new_scenario_name(scenario_name: Any) -> str:
    name = validate_scenario_name(scenario_name)
    if name in _occupied_scenario_names():
        raise ValueError(f"Ein Szenario mit dem Namen „{name}“ existiert bereits. Bitte einen anderen Namen wählen.")
    return name


# Pfad der ausschließlich HEO-lokalen Anzeige-Namen.
def _scenario_name_registry_path() -> Path:

    return DG_SCENARIOS_DIR / HEO_SCENARIO_NAMES_FILENAME


# Liest die lokal vergebenen Anzeigenamen der gespeicherten Szenarien.
def _load_scenario_name_registry() -> dict[str, str]:
    path = _scenario_name_registry_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    names = payload.get("display_names", {}) if isinstance(payload, dict) else {}
    return {
        str(key): str(value) for key, value in names.items()
        if str(key).strip() and str(value).strip()
    }


# Speichert die Anzeigenamen atomar im Szenarioverzeichnis.
def _save_scenario_name_registry(names: dict[str, str]) -> None:
    DG_SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    path = _scenario_name_registry_path()
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False,
        dir=DG_SCENARIOS_DIR, prefix=".heo-scenario-names-", suffix=".tmp",
    ) as handle:
        json.dump({"display_names": names}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    try:
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


# Listet alle vollständig konfigurierten HEO-/DG-Szenarioordner auf.
def list_dg_scenarios() -> list[dict[str, Any]]:

    if not DG_SCENARIOS_DIR.is_dir():
        return []

    display_names = _load_scenario_name_registry()
    scenarios: list[dict[str, Any]] = []
    for scenario_dir in DG_SCENARIOS_DIR.iterdir():
        if not scenario_dir.is_dir():
            continue
        try:
            scenario_name = validate_scenario_name(scenario_dir.name)
        except ValueError:
            continue
        config_path = scenario_config_path(scenario_name)
        if not config_path.is_file():
            continue
        building_path = dg_input_dir(scenario_dir) / f"{scenario_name}.csv"
        run_path = scenario_dir / "run.py"
        scenarios.append(
            {
                "name": scenario_name,
                "display_name": display_names.get(scenario_name, scenario_name),
                "path": str(scenario_dir.resolve()),
                "config_path": str(config_path.resolve()),
                "building_path": str(building_path.resolve()),
                "has_buildings": building_path.is_file(),
                "run_path": str(run_path.resolve()),
                "has_run": run_path.is_file(),
                "modified_at": config_path.stat().st_mtime,
            }
        )
    return sorted(scenarios, key=lambda item: item["display_name"].casefold())


# Verwendet beim verwalteten HEO-Start denselben Interpreter wie die Oberfläche.
# Direkte Starts behalten die bisherige Auswahl der Backend-Umgebung.
def _dg_python() -> Path:
    configured_python = os.environ.get("HEO_DG_PYTHON")
    if configured_python:
        configured_path = Path(configured_python).expanduser()
        if not configured_path.is_absolute():
            configured_path = APP_ROOT / configured_path
        if not configured_path.is_file():
            raise DGConfigError(f"Der konfigurierte HEO-Python-Interpreter fehlt: {configured_path}")
        return configured_path
    candidate = DG_ROOT / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if candidate.is_file():
        return candidate
    return Path(sys.executable)


# Führt die DG-Konfigurationsbrücke aus und übersetzt ihre JSON-Antwort oder Fehlermeldung.
def _run_bridge(
    action: str,
    env_file: Path | None = None,
    building_file: Path | None = None,
) -> dict[str, Any]:
    command = [str(_dg_python()), str(DG_BRIDGE_PATH), action]
    if env_file is not None:
        command.extend(["--env-file", str(env_file)])
    if building_file is not None:
        command.extend(["--building-file", str(building_file)])

    process_environment = os.environ.copy()
    process_environment["PYTHONUTF8"] = "1"
    process_environment["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        command,
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=process_environment,
        timeout=60,
        check=False,
    )

    try:
        result = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        details = completed.stderr.strip() or completed.stdout.strip()
        raise DGConfigError(f"Ungültige Antwort der DG-Config-Bridge: {details}") from exc

    if completed.returncode != 0:
        error = result.get("error") or completed.stderr.strip() or "Unbekannter DG-Config-Fehler"
        raise DGConfigError(str(error))

    return result


# Prüft die Eingabepfade und liest den Profil-Fingerprint aus der DG-Umgebung.
def build_dg_profile_fingerprint(config_path: Path, building_path: Path) -> str:
    config_path = Path(config_path).resolve()
    building_path = Path(building_path).resolve()
    if not config_path.is_file():
        raise DGConfigError(f"DG-Konfiguration nicht gefunden: {config_path}")
    if not building_path.is_file():
        raise DGConfigError(f"Gebäude-CSV nicht gefunden: {building_path}")

    payload = _run_bridge("fingerprint", config_path, building_path)
    profile_hash = str(payload.get("profile_hash") or "")
    if re.fullmatch(r"[0-9a-f]{64}", profile_hash) is None:
        raise DGConfigError("Die DG-Config-Bridge lieferte keinen gültigen Profil-Hash.")
    return profile_hash


# Lädt Schema, Python-Defaults und gegebenenfalls bestehende Overrides.
def load_dg_config_state(
    config_path: Path | None = None,
) -> tuple[list[dict], dict]:

    if config_path is not None:
        config_path = Path(config_path).resolve()
    payload = _run_bridge(
        "schema",
        config_path if config_path is not None and config_path.exists() else None,
    )
    sections = payload["sections"]

    defaults: dict[str, Any] = {}
    values: dict[str, Any] = {}
    overrides: list[str] = []

    for section in sections:
        for field in section["fields"]:
            env_key = field["env_key"]
            defaults[env_key] = field["default"]
            values[env_key] = field["value"]
            if field["has_override"]:
                overrides.append(env_key)

    # Preserve imported extensions even when the installed DG has no editor for them.
    values.update(payload.get("extra_values") or {})
    state = {
        "values": values,
        "defaults": defaults,
        "saved_values": dict(values),
        "overrides": overrides,
        "config_path": str(config_path) if config_path is not None else None,
        "config_exists": bool(config_path and config_path.exists()),
        "load_error": None,
    }
    return sections, state




# Ersetzt den Szenarionamen in einem szenariospezifischen Dateinamen.
def _renamed_scenario_filename(filename: str, old_name: str, new_name: str) -> str:

    return filename.replace(old_name, new_name)


# Aktualisiert ausschließlich den SCENARIO_NAME-Eintrag der Config.
def _rewrite_scenario_config_name(config_path: Path, new_name: str) -> None:

    content = config_path.read_text(encoding="utf-8")
    replacement = f"{SCENARIO_NAME_KEY}={json.dumps(new_name, ensure_ascii=False)}"
    pattern = re.compile(rf"^{re.escape(SCENARIO_NAME_KEY)}=.*$", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(replacement, content, count=1)
    else:
        content = content.rstrip() + f"\n{replacement}\n"
    config_path.write_text(content, encoding="utf-8", newline="\n")


# Benennt ein vollständiges Szenario samt referenzierenden Dateien um.
#
# Die Operation läuft über einen temporären Ordner im Szenarioverzeichnis.
# Bei einem Fehler werden Dateinamen und Inhalte zurückgesetzt, bevor der
# ursprüngliche Ordnername wiederhergestellt wird.
def _rename_dg_scenario_files(
    old_name: Any, new_name: Any, *, registry_names: dict[str, str]
) -> dict[str, Any]:

    source_name = validate_scenario_name(old_name)
    target_name = validate_scenario_name(new_name)
    source_dir = DG_SCENARIOS_DIR / source_name
    target_dir = DG_SCENARIOS_DIR / target_name
    if source_name == target_name:
        return {
            "renamed": False,
            "old_name": source_name,
            "new_name": target_name,
            "scenario_dir": str(source_dir),
            "renamed_files": [],
        }
    if not source_dir.is_dir() or not scenario_config_path(source_name).is_file():
        raise FileNotFoundError(f"Szenario nicht gefunden: {source_name}")
    if target_dir.exists() and target_dir.resolve() != source_dir.resolve():
        raise FileExistsError(f"Ein Szenario namens „{target_name}“ existiert bereits.")

    planned_names: dict[Path, Path] = {}
    for path in source_dir.rglob("*"):
        if not path.is_file() or source_name not in path.name:
            continue
        renamed = path.with_name(
            _renamed_scenario_filename(path.name, source_name, target_name)
        )
        if renamed != path and renamed.exists():
            raise FileExistsError(f"Zieldatei existiert bereits: {renamed.name}")
        planned_names[path.relative_to(source_dir)] = renamed.relative_to(source_dir)

    temporary_dir = DG_SCENARIOS_DIR / f".heo-rename-{uuid.uuid4().hex}"
    current_dir = temporary_dir
    renamed_files: list[tuple[Path, Path]] = []
    original_contents: dict[Path, bytes | None] = {}
    os.replace(source_dir, temporary_dir)
    try:
        for source_relative, target_relative in planned_names.items():
            source_path = temporary_dir / source_relative
            target_path = temporary_dir / target_relative
            os.replace(source_path, target_path)
            renamed_files.append((source_path, target_path))

        config_path = dg_input_dir(temporary_dir) / DG_CONFIG_FILENAME
        original_contents[config_path.relative_to(temporary_dir)] = config_path.read_bytes()
        _rewrite_scenario_config_name(config_path, target_name)

        run_path = temporary_dir / RUN_FILENAME
        original_contents[Path(RUN_FILENAME)] = (
            run_path.read_bytes() if run_path.exists() else None
        )
        run_path.write_text(
            render_scenario_run(target_name), encoding="utf-8", newline="\n"
        )

        for json_path in temporary_dir.rglob("*.json"):
            relative = json_path.relative_to(temporary_dir)
            content = json_path.read_text(encoding="utf-8")
            updated = content.replace(source_name, target_name)
            if updated == content:
                continue
            original_contents.setdefault(relative, json_path.read_bytes())
            json_path.write_text(updated, encoding="utf-8", newline="\n")

        os.replace(temporary_dir, target_dir)
        current_dir = target_dir
        _save_scenario_name_registry(registry_names)
    except Exception:
        for relative, content in original_contents.items():
            path = current_dir / relative
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        for source_path, target_path in reversed(renamed_files):
            renamed_path = current_dir / target_path.relative_to(temporary_dir)
            original_path = current_dir / source_path.relative_to(temporary_dir)
            if renamed_path.exists():
                os.replace(renamed_path, original_path)
        if current_dir.exists() and not source_dir.exists():
            os.replace(current_dir, source_dir)
        raise

    return {
        "renamed": True,
        "old_name": source_name,
        "new_name": target_name,
        "scenario_dir": str(target_dir),
        "renamed_files": [
            str(target.relative_to(temporary_dir))
            for _source, target in renamed_files
        ],
    }


# Benennt Szenarioordner, szenariospezifische Dateien und Referenzen um.
def rename_dg_scenario(old_name: Any, new_name: Any) -> dict[str, Any]:

    scenario_name = validate_scenario_name(old_name)
    target_name = validate_scenario_name(new_name)
    source_dir = DG_SCENARIOS_DIR / scenario_name
    if not source_dir.is_dir() or not scenario_config_path(scenario_name).is_file():
        raise FileNotFoundError(f"Szenario nicht gefunden: {scenario_name}")

    names = _load_scenario_name_registry()
    previous_display_name = names.get(scenario_name, scenario_name)
    if target_name == scenario_name:
        alias_removed = scenario_name in names
        if alias_removed:
            names.pop(scenario_name)
            _save_scenario_name_registry(names)
        return {
            "renamed": alias_removed,
            "scenario_name": scenario_name,
            "old_name": previous_display_name,
            "new_name": scenario_name,
        }
    for folder in DG_SCENARIOS_DIR.iterdir():
        if (
            folder.is_dir()
            and folder.name != scenario_name
            and folder.name.casefold() == target_name.casefold()
        ):
            raise FileExistsError(f"Ein Szenario namens „{target_name}“ existiert bereits.")
    for item in list_dg_scenarios():
        if (
            item["name"] != scenario_name
            and item["display_name"].casefold() == target_name.casefold()
        ):
            raise FileExistsError(f"Ein Szenario namens „{target_name}“ existiert bereits.")

    results_stale = any(
        (source_dir / "results" / objective / "manifest.json").is_file()
        for objective in ("economic", "ecological")
    )
    names.pop(scenario_name, None)
    names.pop(target_name, None)
    _rename_dg_scenario_files(scenario_name, target_name, registry_names=names)
    return {
        "renamed": True,
        "scenario_name": target_name,
        "old_name": previous_display_name,
        "new_name": target_name,
        "results_stale": results_stale,
    }


# Ermittelt den nächsten freien Anzeigenamen für eine Szenariokopie.
def _scenario_copy_name(source_display_name: str) -> str:

    source_display_name = validate_scenario_name(source_display_name)
    suffix_match = re.fullmatch(r"(.+)-([2-9]\d*)", source_display_name)
    stem = suffix_match.group(1) if suffix_match else source_display_name

    scenarios = list_dg_scenarios()
    occupied = {
        str(value).casefold()
        for item in scenarios
        for value in (item["name"], item.get("display_name") or item["name"])
    }
    if DG_SCENARIOS_DIR.is_dir():
        occupied.update(
            path.name.casefold()
            for path in DG_SCENARIOS_DIR.iterdir()
            if path.is_dir()
        )
    suffix_pattern = re.compile(rf"^{re.escape(stem)}-([2-9]\d*)$", re.IGNORECASE)
    next_number = 2
    for value in occupied:
        match = suffix_pattern.fullmatch(value)
        if match:
            next_number = max(next_number, int(match.group(1)) + 1)

    while True:
        suffix = f"-{next_number}"
        candidate_stem = stem[:100 - len(suffix)].rstrip(". ")
        candidate = validate_scenario_name(f"{candidate_stem}{suffix}")
        if candidate.casefold() not in occupied:
            return candidate
        next_number += 1


# Dupliziert ein Szenario vollständig unter einem fortlaufenden Namen.
def duplicate_dg_scenario(scenario_name: Any) -> dict[str, Any]:

    source_name = validate_scenario_name(scenario_name)
    source_dir = DG_SCENARIOS_DIR / source_name
    if not source_dir.is_dir() or not scenario_config_path(source_name).is_file():
        raise FileNotFoundError(f"Szenario nicht gefunden: {source_name}")

    names = _load_scenario_name_registry()
    source_display_name = names.get(source_name, source_name)
    target_name = _scenario_copy_name(source_display_name)
    target_dir = DG_SCENARIOS_DIR / target_name
    if target_dir.exists():
        raise FileExistsError(f"Ein Szenario namens „{target_name}“ existiert bereits.")

    temporary_dir = DG_SCENARIOS_DIR / f".heo-copy-{uuid.uuid4().hex}"
    try:
        # Schließt erzeugte Laufdateien und Ergebnisse beim Kopieren eines Szenarios aus.
        def skip_generated(directory: str, names: list[str]) -> set[str]:
            relative = Path(directory).relative_to(source_dir)
            if relative == Path("."):
                return {"results"} & set(names)
            if relative == Path("common"):
                return {"dg_profiles"} & set(names)
            if relative == Path("common/heo_seed_control"):
                return {
                    "manifest.json", "prepared_scenario.p", "progress.json",
                    "simulation.log", "last_failure.json",
                } & set(names)
            return set()

        shutil.copytree(source_dir, temporary_dir, ignore=skip_generated)

        planned_names: list[tuple[Path, Path]] = []
        for path in temporary_dir.rglob("*"):
            if path.is_file() and source_name in path.name:
                renamed = path.with_name(
                    _renamed_scenario_filename(path.name, source_name, target_name)
                )
                if renamed != path and renamed.exists():
                    raise FileExistsError(f"Zieldatei existiert bereits: {renamed.name}")
                planned_names.append((path, renamed))
        for source_path, target_path in planned_names:
            os.replace(source_path, target_path)

        config_path = dg_input_dir(temporary_dir) / DG_CONFIG_FILENAME
        _rewrite_scenario_config_name(config_path, target_name)

        (temporary_dir / RUN_FILENAME).write_text(
            render_scenario_run(target_name), encoding="utf-8", newline="\n"
        )
        from ..execution.profile_service import ensure_profile_options_file
        ensure_profile_options_file(temporary_dir)
        for json_path in temporary_dir.rglob("*.json"):
            content = json_path.read_text(encoding="utf-8")
            updated = content.replace(source_name, target_name)
            if updated != content:
                json_path.write_text(updated, encoding="utf-8", newline="\n")

        os.replace(temporary_dir, target_dir)
        names[target_name] = target_name
        try:
            _save_scenario_name_registry(names)
        except Exception:
            shutil.rmtree(target_dir)
            raise
    except Exception:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        raise

    return {
        "duplicated": True,
        "source_name": source_name,
        "source_display_name": source_display_name,
        "scenario_name": target_name,
        "display_name": target_name,
        "scenario_dir": str(target_dir),
    }


# Löscht einen vollständigen DG-Szenarioordner auf ausdrücklichen UI-Befehl.
def delete_dg_scenario(scenario_name: Any) -> dict[str, Any]:

    name = validate_scenario_name(scenario_name)
    root = DG_SCENARIOS_DIR.resolve()
    scenario_path = DG_SCENARIOS_DIR / name
    target = scenario_path.resolve()
    if scenario_path.is_symlink() or target.parent != root or not target.is_dir():
        raise FileNotFoundError(f"Szenario nicht gefunden: {name}")

    shutil.rmtree(target)
    names = _load_scenario_name_registry()
    display_name = names.pop(name, name)
    _save_scenario_name_registry(names)
    return {"deleted": True, "scenario_name": name, "display_name": display_name}


# Entfernt die Ergebnisse und Zwischendaten eines Szenarios, ohne seine Eingaben zu ändern.
def delete_dg_scenario_results(scenario_name: Any) -> dict[str, Any]:
    name = validate_scenario_name(scenario_name)
    root = DG_SCENARIOS_DIR.resolve()
    scenario_path = DG_SCENARIOS_DIR / name
    target = scenario_path.resolve()
    if scenario_path.is_symlink() or target.parent != root or not target.is_dir() or not scenario_config_path(name).is_file():
        raise FileNotFoundError(f"Szenario nicht gefunden: {name}")

    control = seed_control_dir(target)
    if control.is_symlink():
        raise ValueError("Der Szenarioordner für Profil-Einstellungen darf kein symbolischer Link sein.")

    profiles = dg_profiles_dir(target)
    preserved_profile_child = None
    preserve_all_profiles = False
    profile_config = control / ".env.PROFILES"
    if profile_config.is_file():
        profile_values = dotenv_values(profile_config)
        if profile_values.get("PROFILE_MODE") == "saved" and profile_values.get("PROFILE_SOURCE"):
            source = Path(profile_values["PROFILE_SOURCE"]).expanduser()
            if not source.is_absolute():
                source = target / source
            source = source.resolve()
            profile_root = profiles.resolve()
            if source == profile_root:
                preserve_all_profiles = True
            elif source.is_relative_to(profile_root):
                preserved_profile_child = source.relative_to(profile_root).parts[0]

    # Beide Optimierungsziele und historische Ergebnisdateien liegen unter results.
    # DG-Profile sind Zwischendaten, außer wenn sie ausdrücklich als Eingabe dienen.
    for path in (results_dir(target), profiles):
        if path == profiles and (preserve_all_profiles or preserved_profile_child):
            if preserved_profile_child and path.is_dir() and not path.is_symlink():
                for child in path.iterdir():
                    if child.name == preserved_profile_child:
                        continue
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()

    if control.is_dir():
        for path in control.iterdir():
            if path.name == ".env.PROFILES":
                continue
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()

    # Python legt beim Ausführen von run.py einen weiteren Lauf-Cache an.
    cache = target / "__pycache__"
    if cache.is_dir() and not cache.is_symlink():
        shutil.rmtree(cache)
    elif cache.exists() or cache.is_symlink():
        cache.unlink()

    display_name = _load_scenario_name_registry().get(name, name)
    return {"deleted": True, "scenario_name": name, "display_name": display_name}
