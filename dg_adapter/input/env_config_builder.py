# Erzeugt und speichert DG-Konfigurationen; die Szenarioverwaltung bleibt außerhalb des Builders.
from __future__ import annotations
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from ..shared.dg_paths import scenario_dir_for_config
from .weather_input import _decode_weather_upload

# Konvertiert einen Eingabewert entsprechend dem DG-Feldtyp und lehnt unzulässige Werte ab.
def _coerce_value(value: Any, field: dict[str, Any]) -> Any:
    value_type = field["value_type"]
    default = field["default"]

    if value_type == "bool":
        if isinstance(value, list):
            return bool(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        raise ValueError(f"{field['env_key']}: Boolean-Wert erwartet.")

    if value_type == "int":
        return int(value)
    if value_type == "float":
        return float(value)
    if value_type.startswith("optional-"):
        if value is None or str(value).strip().lower() in {"", "none", "null"}:
            return None
        if value_type == "optional-int":
            return int(value)
        if value_type == "optional-float":
            return float(value)
        return str(value)
    if value_type in {"list", "dict"}:
        if isinstance(value, (list, dict)):
            parsed = value
        else:
            text = str(value).strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                if value_type != "list":
                    raise ValueError(f"{field['env_key']}: gültiges JSON-Objekt erwartet.")
                parsed = [item.strip() for item in text.strip("[]").split(",") if item.strip()]

        if value_type == "list" and isinstance(parsed, (int, float)):
            parsed = [parsed]
        if field["env_key"] in {"CO2_TAX"}:
            return [float(item) for item in parsed]
        if value_type == "list" and isinstance(parsed, list) and default:
            if all(isinstance(item, int) and not isinstance(item, bool) for item in default):
                return [int(float(item)) for item in parsed]
            if all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in default):
                return [float(item) for item in parsed]
        return parsed

    if value is None:
        return ""
    text = str(value)
    if "\n" in text or "\r" in text:
        raise ValueError(f"{field['env_key']}: Zeilenumbrüche sind nicht zulässig.")
    return text


# Serialisiert einen Python-Wert für das DG-env-Format.
def _serialize_env_value(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


# Vergleicht Eingabe und Default ohne Unterschiede zwischen ganzzahligen und dezimalen Zahlen.
def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return left == right


# Erzeugt die Config-Zeilen aus Schema und Eingabewerten; schreibt nur Abweichungen und importierte Zusatzwerte.
def _render_config(
    sections: list[dict],
    values: dict[str, Any],
) -> tuple[str, int]:
    lines = [
        "# Automatisch vom Humanotop Energiesystem-Optimierer erzeugt.",
        "# Enthalten sind nur Abweichungen von den Defaults in data_handling/config.py.",
        "",
    ]
    changed_count = 0

    for section in sections:
        section_lines: list[str] = []
        for field in section["fields"]:
            env_key = field["env_key"]
            value = _coerce_value(values.get(env_key, field["default"]), field)
            if _same_value(value, field["default"]):
                continue
            section_lines.append(f"{env_key}={_serialize_env_value(value)}")
            changed_count += 1

        if section_lines:
            lines.append(f"# {section['class_name']}")
            lines.extend(section_lines)
            lines.append("")

    known = {field["env_key"] for section in sections for field in section["fields"]}
    extras = {key: value for key, value in values.items() if key not in known}
    if extras:
        lines.append("# Zusätzliche importierte Konfigurationswerte")
        for key, value in sorted(extras.items()):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValueError(f"Ungültiger Konfigurationsschlüssel: {key}")
            lines.append(f"{key}={_serialize_env_value(value)}")
            changed_count += 1
    return "\n".join(lines).rstrip() + "\n", changed_count


# Validiert und schreibt die .env.CONFIG in den Szenarioordner.
def save_dg_config(
    values: dict[str, Any],
    config_path: Path | None = None,
    weather_upload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from . import config_service as config_service
    from ..execution.profile_service import ensure_profile_options_file

    scenario_name = config_service.scenario_name_from_values(values)
    if config_path is None:
        config_path = config_service.scenario_config_path(scenario_name)
    else:
        config_path = Path(config_path).resolve()

    effective_values = dict(values)
    decoded_weather = None
    if weather_upload and not bool(effective_values.get("USE_GERMAN_ZIP")):
        decoded_weather = _decode_weather_upload(weather_upload, config_path.parent)
        if decoded_weather is not None:
            effective_values["WEATHER_FILE"] = decoded_weather[2]

    sections, _ = config_service.load_dg_config_state(config_path)
    content, changed_count = _render_config(sections, effective_values)

    config_unchanged = (
        config_path.exists() and config_path.read_text(encoding="utf-8") == content
    )
    weather_unchanged = True
    if decoded_weather is not None:
        weather_bytes, weather_path, _relative_path = decoded_weather
        weather_unchanged = weather_path.exists() and weather_path.read_bytes() == weather_bytes

    if config_unchanged and weather_unchanged:
        ensure_profile_options_file(scenario_dir_for_config(config_path))
        return {
            "written": False,
            "changed_count": changed_count,
            "scenario_name": scenario_name,
            "scenario_dir": str(scenario_dir_for_config(config_path)),
            "scenario_created": False,
            "config_path": str(config_path),
            "backup_path": None,
            "weather_path": str(decoded_weather[1]) if decoded_weather else None,
        }

    scenario_created = not scenario_dir_for_config(config_path).exists()
    config_service.DG_SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    backup_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".heo-config-",
            suffix=".tmp",
            dir=config_service.DG_SCENARIOS_DIR,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        config_service._run_bridge("validate", temporary_path)

        config_path.parent.mkdir(parents=True, exist_ok=True)
        if decoded_weather is not None and not weather_unchanged:
            weather_bytes, weather_path, _relative_path = decoded_weather
            weather_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".heo-weather-",
                suffix=".tmp",
                dir=weather_path.parent,
                delete=False,
            ) as weather_temporary_file:
                weather_temporary_file.write(weather_bytes)
                weather_temporary_path = Path(weather_temporary_file.name)
            os.replace(weather_temporary_path, weather_path)

        if config_path.exists():
            backup_path = config_path.with_name(f"{config_path.name}.bak")
            shutil.copy2(config_path, backup_path)

        os.replace(temporary_path, config_path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    ensure_profile_options_file(scenario_dir_for_config(config_path))
    return {
        "written": True,
        "changed_count": changed_count,
        "scenario_name": scenario_name,
        "scenario_dir": str(scenario_dir_for_config(config_path)),
        "scenario_created": scenario_created,
        "config_path": str(config_path),
        "backup_path": str(backup_path) if backup_path is not None else None,
        "weather_path": str(decoded_weather[1]) if decoded_weather else None,
    }

