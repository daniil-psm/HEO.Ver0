# Übersetzt DG-Ergebnisse in ein darstellungsneutrales HEO-Topologiemodell.

from __future__ import annotations
from .result_flows import _result_clusters
from ..shared.building_supply import cooling_supply

from typing import Any, Iterable

from ..execution.dg_project_snapshot import build_topology_snapshot
from ..shared.device_catalog import (
    DG_CENTRAL_DEVICE_CATALOG,
    building_heater_parts,
    central_device_abbreviation,
    decentral_device_abbreviation,
    normalize_central_device_code,
    normalize_building_heater,
)


CAPACITY_THRESHOLD = 1e-6
ACTIVITY_THRESHOLD = 1e-6

DEVICE_ACTIVITY_KEYS = {
    "PV": ("gen_power", "ts_gen_power"),
    "BAT": ("ch", "dch", "ts_ch", "ts_dch"),
    "HP": ("gen_heat", "cons_power", "ts_gen_heat", "ts_cons_power"),
    "GHP": ("gen_heat", "cons_power", "ts_gen_heat", "ts_cons_power"),
    "BHP": ("gen_heat", "cons_power", "ts_gen_heat", "ts_cons_power"),
    "H2HP": ("gen_heat", "cons_power", "ts_gen_heat", "ts_cons_power"),
    "OHP": ("gen_heat", "cons_power", "ts_gen_heat", "ts_cons_power"),
    "EH": ("gen_heat", "cons_power", "ts_gen_heat", "ts_cons_power"),
    "BOI": ("gen_heat", "cons_gas", "ts_gen_heat", "ts_cons_gas"),
    "BBOI": ("gen_heat", "cons_biomass", "ts_gen_heat", "ts_cons_biomass"),
    "OBOI": ("gen_heat", "cons_oil", "ts_gen_heat", "ts_cons_oil"),
    "H2BOI": (
        "gen_heat", "cons_hydrogen", "ts_gen_heat", "ts_cons_hydrogen",
    ),
    "CHP": (
        "gen_heat", "gen_power", "cons_gas",
        "ts_gen_heat", "ts_gen_power", "ts_cons_gas",
    ),
    "FC": (
        "gen_heat", "gen_power", "cons_hydrogen",
        "ts_gen_heat", "ts_gen_power", "ts_cons_hydrogen",
    ),
    "CC": ("gen_cool", "cons_power", "ts_gen_cool", "ts_cons_power"),
    "STC": ("gen_heat", "ts_gen_heat"),
    "TES": ("ch", "dch", "ts_ch", "ts_dch"),
    "TES_DHW": ("ch", "dch", "ts_ch", "ts_dch"),
    "EV": ("ch", "dch", "ts_ch", "ts_dch", "ts_charge"),
}


# Wandelt einen Ergebniswert in eine Zahl um.
def _number(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


# Interpretiert DG- und HEO-Wahrheitswerte.
def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "ja", "on"}


# Liefert den größten Absolutwert einer Ergebnisreihe.
def _magnitude(value: object) -> float:
    if isinstance(value, (list, tuple)):
        return max((_magnitude(item) for item in value), default=0.0)
    return abs(_number(value))


# Prüft, ob ein Gerät im Ergebnis tatsächlich aktiv ist.
def _device_active(device: dict | None, code: str) -> bool:
    values = device or {}
    return any(
        _magnitude(values.get(key)) > ACTIVITY_THRESHOLD
        for key in DEVICE_ACTIVITY_KEYS.get(code, ())
    )


# Sammelt Gebäudeergebnisse nach ihren Laufindizes.
def _building_result_sets(
    optimization_data: dict | None,
    result_indices: Iterable[int],
) -> list[list[dict]]:
    indices = [int(index) for index in result_indices]
    result: list[list[dict]] = [[] for _ in indices]
    for cluster in _result_clusters(optimization_data):
        for position, result_index in enumerate(indices):
            building = cluster.get(str(result_index))
            if isinstance(building, dict):
                result[position].append(building)
    return result


# Prüft Aktivität eines Gebäudes für ein Ergebnisfeld.
def _building_has_activity(results: Iterable[dict], key: str) -> bool:
    return any(_magnitude(result.get(key)) > ACTIVITY_THRESHOLD for result in results)


# Prüft, ob ein Gebäude ein Gerät tatsächlich nutzt.
def _building_device_active(results: Iterable[dict], code: str) -> bool:
    return any(
        _device_active(result.get(code) if isinstance(result.get(code), dict) else {}, code)
        for result in results
    )


# Wählt zentrale Geräte anhand der Optimierung aus.
def _central_devices(optimization_data: dict | None) -> list[dict[str, Any]]:
    capacities = (optimization_data or {}).get("capacities", {}).get("devices", {})
    result: list[dict[str, Any]] = []
    for raw_code, values in capacities.items():
        code = normalize_central_device_code(str(raw_code))
        capacity = _number((values or {}).get("value"))
        if capacity <= CAPACITY_THRESHOLD or code not in DG_CENTRAL_DEVICE_CATALOG:
            continue
        result.append(
            {
                "code": code,
                "label": central_device_abbreviation(code),
                "value": capacity,
                "unit": (
                    "kWh" if code in {"TES", "CTES"}
                    else str((values or {}).get("unit") or "kW")
                ),
                "area_m2": (values or {}).get("area_m2"),
            }
        )
    return result


# Übersetzt DG-Ergebnisse in HEO-Topologiedaten.
def normalize_topology_results(
    optimization_data: dict | None,
    building_state: dict | None,
) -> dict[str, Any]:
    """Baut aus Optimierung und Gebäudezustand die fachliche Ergebnis-Topologie."""

    snapshot = (optimization_data or {}).get("topology_snapshot") or {}
    snapshot_rows = snapshot.get("buildings") if isinstance(snapshot, dict) else None
    rows = list(
        snapshot_rows
        if isinstance(snapshot_rows, list)
        else (building_state or {}).get("rows") or []
    )
    central_devices = _central_devices(optimization_data)
    central_codes = {device["code"] for device in central_devices}
    building_results = _building_result_sets(
        optimization_data,
        (
            int(_number(row.get("result_index")))
            if isinstance(row, dict) and row.get("result_index") is not None
            else index
            for index, row in enumerate(rows)
        ),
    )
    buildings: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        results = building_results[index]
        heater = normalize_building_heater(row.get("heater"))
        heater_parts = building_heater_parts(heater)
        central_carriers: list[str] = []
        decentral_codes: list[str] = []

        # Der elektrische Anschluss wird nur bei einem tatsächlichen Gebäudebezug gezeigt.
        if _building_has_activity(results, "res_load"):
            central_carriers.append("ac")

        if heater == "heat_grid" and central_codes & {
            "HP", "GROUNDHP", "EB", "STC", "BOI", "WBOI",
            "BBOI", "GHP", "TES"
        }:
            central_carriers.append("heat")
        elif (
            heater
            and heater not in {"0", "none", "heat_grid"}
            and any(_building_device_active(results, part) for part in heater_parts)
        ):
            decentral_codes.append(heater)

        decentral_cooling = _building_device_active(results, "CC")
        if (
            cooling_supply(row) == "central"
            and central_codes & {"CC", "AC", "CTES"}
            and not decentral_cooling
        ):
            central_carriers.append("cooling")
        elif decentral_cooling:
            decentral_codes.append("CC")

        # Heizsysteme stammen ausschließlich aus der Gebäudekonfiguration.
        # DG liefert auch für nicht installierte Geräte Ergebnisfelder; solche
        # Läufe können darin sogar einen Strombezug ohne Wärmeerzeugung haben.
        for code in ("PV", "BAT", "STC", "TES", "TES_DHW", "EV"):
            if _building_device_active(results, code):
                decentral_codes.append(code)

        # Die aktuelle Gebäude-UI modelliert Trinkwarmwasser als elektrischen
        # Durchlauferhitzer; dieser ist eine reale dezentrale Gebäudekomponente.
        dhw_heater = str(row.get("dhw_heater") or "").strip()
        if _truthy(row.get("dhw")) or dhw_heater.upper() == "EH_DHW":
            decentral_codes.append("EH_DHW")
        else:
            # Warmwasser wird im neuen Gebäudezustand unabhängig von der
            # Heizkante zentral versorgt. Die Kennung bleibt für Phase 2 in
            # der neutralen Ergebnis-Topologie erhalten.
            central_carriers.append("dhw")
        if _truthy(row.get("EV")):
            decentral_codes.append("EV")

        unique_codes = list(dict.fromkeys(decentral_codes))
        buildings.append(
            {
                "uid": int(_number(row.get("uid")) if row.get("uid") is not None else index),
                "id": int(_number(row.get("id")) or index + 1),
                "name": str(row.get("name") or ""),
                "building_type": str(row.get("building") or ""),
                "central_carriers": list(dict.fromkeys(central_carriers)),
                "decentral_devices": [
                    {
                        "code": code,
                        "label": decentral_device_abbreviation(code),
                    }
                    for code in unique_codes
                ],
            }
        )

    return {
        "schema_version": 2,
        "scenario_name": str((optimization_data or {}).get("scenario_name") or ""),
        "central_devices": central_devices,
        "buildings": buildings,
    }
