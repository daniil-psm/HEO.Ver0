# Liest gespeicherte Gebäude und HEO-Metadaten; CSV-Erzeugung und Prüfung liegen in input/.

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .validation import _ev_fraction, _integer, _number, _flag
from . import scenario_paths
from ..shared.building_supply import supply_validation_errors


# Lädt lokale Namen nach DG-ID; fehlende/alte Szenarien bleiben gültig.
def _load_building_names(scenario_name: Any) -> dict[int, str]:

    path = scenario_paths.scenario_building_metadata_path(scenario_name)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[int, str] = {}
    for item in payload.get("buildings", []):
        try:
            building_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        result[building_id] = str(item.get("name") or "")
    return result


# Lädt eine Gebäude-csv in den HEO-Zustand
def load_building_scenario(scenario_name: Any, *, csv_path: Path | None = None) -> dict[str, Any]:

    csv_path = Path(csv_path) if csv_path is not None else scenario_paths.scenario_building_csv_path(scenario_name)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Gebäude-CSV nicht gefunden: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle, delimiter=";"))
    if not source_rows:
        raise ValueError(f"Die Gebäude-CSV ist leer: {csv_path}")

    local_names = _load_building_names(scenario_name)
    try:
        metadata = json.loads(scenario_paths.scenario_building_metadata_path(scenario_name).read_text(encoding="utf-8"))
        supply_metadata = {int(item["id"]): item.get("central_supply_disabled", {})
                           for item in metadata.get("buildings", [])}
    except (OSError, ValueError, KeyError, TypeError):
        supply_metadata = {}
    rows: list[dict[str, Any]] = []
    for position, source in enumerate(source_rows, start=1):
        source_id = _integer(source.get("id"), f"Gebäude {position} · ID")
        building_id = position
        legacy = dict(source, _central_supply_disabled=supply_metadata.get(source_id, {}))
        errors = supply_validation_errors(legacy)
        if errors:
            raise ValueError(f"Gebäude {source_id}: {errors[0]}")
        row = {
            "uid": position - 1,
            "auto_id": position,
            "id": building_id,
            "id_manual": False,
            "name": local_names.get(source_id, local_names.get(position, "")),
            "building": str(source.get("building") or "").strip() or None,
            "year": _integer(source.get("year"), f"Gebäude {building_id} · Baujahr"),
            "retrofit": _integer(
                source.get("retrofit"), f"Gebäude {building_id} · Sanierung"
            ),
            "construction_type": _integer(
                source.get("construction_type"),
                f"Gebäude {building_id} · Bauweise",
            ),
            "night_setback": bool(_flag(source.get("night_setback"))),
            "area": _number(source.get("area"), f"Gebäude {building_id} · Fläche"),
            "heater": str(source.get("heater") or "").strip(),
            "dhw_heater": str(source.get("dhw_heater") or "").strip(),
            "dhw": str(source.get("dhw_heater") or "").strip().lower()
            not in {"", "0", "false", "none"},
            "cooling": bool(_flag(source.get("cooling"))),
            "EV": _ev_fraction(source.get("EV")),
            "f_TES": _number(source.get("f_TES"), f"Gebäude {building_id} · f_TES"),
            "f_BAT": _number(source.get("f_BAT"), f"Gebäude {building_id} · f_BAT"),
            "f_PV1": _number(source.get("f_PV1"), f"Gebäude {building_id} · f_PV1"),
            "f_PV2": _number(source.get("f_PV2"), f"Gebäude {building_id} · f_PV2"),
            "f_STC": _number(source.get("f_STC"), f"Gebäude {building_id} · f_STC"),
            "beta_PV": _number(
                source.get("beta_PV") if source.get("beta_PV") not in {None, ""} else 35.0,
                f"Gebäude {building_id} · beta_PV",
            ),
            "gamma_PV": _number(
                source.get("gamma_PV"), f"Gebäude {building_id} · gamma_PV"
            ),
            "ev_charging": str(source.get("ev_charging") or "on_demand").strip(),
        }
        rows.append(row)

    return {
        "rows": rows,
        "next_uid": len(rows),
        "next_auto_id": len(rows) + 1,
        "source_path": str(csv_path.resolve()),
    }
