# Brücke zwischen HEO-Frontend und DG-Backend für die Konfiguration

from __future__ import annotations

import argparse
import contextlib
import inspect
import io
import json
import re
import sys
import tokenize
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values


APP_ROOT = Path(__file__).resolve().parents[2]
DG_ROOT = APP_ROOT / "dg_backend"
DG_DATA_DIR = DG_ROOT / "districtgenerator" / "data"
DG_EXAMPLE_CONFIG = DG_DATA_DIR / ".env.CONFIG.EXAMPLE"

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
if str(DG_ROOT) not in sys.path:
    sys.path.insert(0, str(DG_ROOT))

from districtgenerator.data_handling import config as dg_config  # noqa: E402
from heo.model.annual_series import ANNUAL_KEYS, numbers  # noqa: E402


CONFIG_SPECS = (
    ("location", "LocationConfig"),
    ("time", "TimeConfig"),
    ("calendar", "CalendarConfig"),
    ("design_building", "DesignBuildingConfig"),
    ("eco", "EcoConfig"),
    ("heatgrid", "HeatGridConfig"),
    ("ehdo", "EHDOConfig"),
    ("physics", "PhysicsConfig"),
    ("pyomo", "PyomoConfig"),
    ("report", "ReportConfig"),
    ("central", "CentralDeviceConfig"),
    ("decentral", "DecentralDeviceConfig"),
)


FIELD_OPTIONS = {
    "TRYYEAR": ["TRY2015", "TRY2045"],
    "TRYTYPE": ["Jahr", "Somm", "Wint"],
    "THERMAL_MODEL_TYPE": ["5R1C", "7R2C"],
    "GENERATION": ["3rd", "4th", "5th"],
    "TOPOLOGY_OPTION": ["node", "road"],
    "TEMPERATURE_MODE": ["constant", "heating_curve"],
    "SOLVER_NAME": ["gurobi", "highs", "cbc"],
    "PAGESIZE": ["A4", "LETTER"],
    "LANGUAGE": ["de", "en"],
    "KPI_SAVE_TYPE": ["xlsx", "csv", "json"],
}


# Liest die Reihenfolge der Konfigurationsschlüssel aus der DG-Beispieldatei.
def _example_env_keys() -> list[str]:
    keys: list[str] = []
    for raw_line in DG_EXAMPLE_CONFIG.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.append(line.split("=", 1)[0].strip())
    return keys


# Ermittelt den editierbaren Feldtyp aus DG-Default und Typannotation.
def _field_type(default: Any, annotation: Any) -> str:
    # DG declares some floats with integer defaults (e.g. solar azimuth 0).
    # Their declared precision must also survive parsing and serialization.
    if annotation is float and isinstance(default, (int, float)):
        return "float"
    if isinstance(default, bool):
        return "bool"
    if isinstance(default, int):
        return "int"
    if isinstance(default, float):
        return "float"
    if isinstance(default, list):
        return "list"
    if isinstance(default, dict):
        return "dict"
    if isinstance(default, str):
        return "str"

    annotation_text = str(annotation)
    if "int" in annotation_text:
        return "optional-int"
    if "float" in annotation_text:
        return "optional-float"
    return "optional-str"


# Liest die Originalkommentare der DG-Modellfelder als Feldbeschreibungen.
@lru_cache(maxsize=None)
def _field_comments(model_class: type) -> dict[str, str]:
    comments: dict[str, str] = {}
    field_pattern = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*):")

    for source_line in inspect.getsource(model_class).splitlines():
        field_match = field_pattern.match(source_line)
        if field_match is None:
            continue

        comment = ""
        try:
            tokens = tokenize.generate_tokens(io.StringIO(source_line.lstrip() + "\n").readline)
            for token in tokens:
                if token.type == tokenize.COMMENT:
                    comment = token.string.lstrip("#").strip()
                    break
        except (IndentationError, tokenize.TokenError):
            pass

        comments[field_match.group(1)] = comment

    return comments


# Konvertiert einen env-Text anhand des Feldtyps und des DG-Defaults.
def _parse_env_value(raw: str | None, default: Any, value_type: str) -> Any:
    if raw is None:
        return default

    text = str(raw).strip()
    if value_type == "bool":
        return text.lower() in {"1", "true", "yes", "on"}
    if value_type == "int":
        return int(float(text))
    if value_type == "float":
        return float(text)
    if value_type.startswith("optional-"):
        if text.lower() in {"", "none", "null"}:
            return None
        if value_type == "optional-int":
            return int(float(text))
        if value_type == "optional-float":
            return float(text)
        return text
    if value_type in {"list", "dict"}:
        try:
            parsed = json.loads(text)
            return [parsed] if value_type == "list" and isinstance(parsed, (int, float)) else parsed
        except json.JSONDecodeError:
            if value_type == "list":
                items = [item.strip() for item in text.strip("[]").split(",") if item.strip()]
                if default and all(isinstance(item, int) for item in default):
                    return [int(float(item)) for item in items]
                if default and all(isinstance(item, (int, float)) for item in default):
                    return [float(item) for item in items]
                return items
            return text
    return text


# Bestimmt die Gruppe eines DG-Konfigurationsfeldes.
def _group_for(env_key: str, prefix: str) -> str:
    unprefixed = env_key[len(prefix):] if prefix and env_key.upper().startswith(prefix.upper()) else env_key
    if "__" not in unprefixed:
        return "GENERAL"

    return unprefixed.split("__", 1)[0].upper()


# Ordnet den DG-env-Schlüsseln ihre Modellfelder zu.
def _model_fields_by_env(model_class: type) -> dict[str, tuple[str, Any]]:
    prefix = str(model_class.model_config.get("env_prefix") or "")
    result: dict[str, tuple[str, Any]] = {}
    for field_name, field_info in model_class.model_fields.items():
        env_key = f"{prefix}{field_name}".upper()
        result[env_key] = (field_name, field_info)
    return result


# Erzeugt den Feldvertrag mit Typ, Default, aktuellem Wert und Beschreibung.
def _build_field(
    *,
    env_key: str,
    model_class: type,
    current_env: dict[str, str | None],
) -> dict[str, Any] | None:
    model_fields = _model_fields_by_env(model_class)
    match = model_fields.get(env_key.upper())
    if match is None:
        return None

    field_name, field_info = match
    default = field_info.get_default(call_default_factory=True)
    value_type = _field_type(default, field_info.annotation)
    comment = _field_comments(model_class).get(field_name, "")
    current_key = env_key.upper()
    has_override = current_key in current_env
    current = _parse_env_value(
        current_env.get(current_key),
        default,
        value_type,
    )
    if current_key in ANNUAL_KEYS and has_override:
        current = numbers(current_env[current_key])
    prefix = str(model_class.model_config.get("env_prefix") or "")
    group = _group_for(env_key, prefix)

    return {
        "env_key": env_key,
        "field_name": field_name,
        "group": group,
        "default": default,
        "value": current,
        "value_type": value_type,
        "help_text": comment,
        "annotation": str(field_info.annotation),
        "options": FIELD_OPTIONS.get(env_key.upper()),
        "has_override": has_override,
    }


# Baut das Konfigurationsschema aus den originalen DG-Modellen und optionalen Szenariowerten.
def build_schema(env_file: Path | None = None) -> dict[str, Any]:
    example_keys = _example_env_keys()
    current_values = (
        {str(key).upper(): value for key, value in dotenv_values(env_file).items()}
        if env_file is not None and env_file.exists()
        else {}
    )

    sections: list[dict[str, Any]] = []
    claimed: set[str] = set()

    for section_key, class_name in CONFIG_SPECS:
        model_class = getattr(dg_config, class_name)
        fields: list[dict[str, Any]] = []

        # Use the DG model as the complete schema; retain example ordering only.
        model_keys = _model_fields_by_env(model_class)
        ordered_keys = list(dict.fromkeys([
            *(key.upper() for key in example_keys if key.upper() in model_keys),
            *model_keys,
        ]))
        for env_key in ordered_keys:
            field = _build_field(
                env_key=env_key,
                model_class=model_class,
                current_env=current_values,
            )
            if field is None:
                continue
            field["additional_model_field"] = env_key not in {key.upper() for key in example_keys}
            fields.append(field)
            claimed.add(env_key.upper())

        if section_key == "location":
            scenario_field = _build_field(
                env_key="SCENARIO_NAME",
                model_class=dg_config.ScenarioName,
                current_env=current_values,
            )
            if scenario_field is not None:
                scenario_field["group"] = "SCENARIO"
                fields.insert(0, scenario_field)
                claimed.add("SCENARIO_NAME")

            weather_field = _build_field(
                env_key="WEATHER_FILE",
                model_class=model_class,
                current_env=current_values,
            )
            if weather_field is not None and not any(f["env_key"] == "WEATHER_FILE" for f in fields):
                fields.insert(1 if scenario_field is not None else 0, weather_field)
                claimed.add("WEATHER_FILE")

        sections.append(
            {
                "key": section_key,
                "class_name": class_name,
                "fields": fields,
            }
        )

    return {
        "sections": sections,
        "unmapped_env_keys": [key for key in current_values if key.upper() not in claimed],
        "extra_values": {key: value for key, value in current_values.items() if key not in claimed},
        "config_path": str(env_file) if env_file is not None else None,
        "example_path": str(DG_EXAMPLE_CONFIG),
    }


# Prüft eine Konfigurationsdatei mit den originalen DG-Konfigurationsklassen.
def validate_config(env_file: Path) -> None:
    classes = [getattr(dg_config, class_name) for _, class_name in CONFIG_SPECS]
    classes.append(dg_config.ScenarioName)

    with contextlib.redirect_stdout(sys.stderr):
        for model_class in classes:
            model_class(_env_file=str(env_file))


# Berechnet den Vergleichs-Hash in derselben Umgebung wie die Simulation
def build_profile_fingerprint(env_file: Path, building_file: Path) -> dict[str, str]:
    from dg_adapter.execution.profile_fingerprint import build_profile_fingerprint as build
    with contextlib.redirect_stdout(sys.stderr):
        profile_hash = build(env_file, building_file)
    return {"profile_hash": profile_hash}


# Verarbeitet den Bridge-Aufruf für Schema, Validierung oder Fingerprint und gibt JSON zurück.
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("schema", "validate", "fingerprint"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--building-file", type=Path)
    args = parser.parse_args()

    try:
        if args.action == "schema":
            result = build_schema(args.env_file)
        elif args.action == "validate":
            if args.env_file is None:
                raise ValueError("Für die Validierung fehlt --env-file.")
            validate_config(args.env_file)
            result = {"valid": True}
        else:
            if args.env_file is None or args.building_file is None:
                raise ValueError(
                    "Für den Fingerprint fehlen --env-file oder --building-file."
                )
            result = build_profile_fingerprint(args.env_file, args.building_file)

        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
