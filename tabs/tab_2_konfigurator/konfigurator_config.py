# Hält nur den Dash-Zustand des Konfigurators und rekonstruiert ihn aus HEO-Daten.

from __future__ import annotations

from copy import deepcopy
from typing import Any

from heo.model.configuration import selected_central_devices_from_input
from heo.topology.definitions import CENTRAL_SLOT_KEYS, normalize_slot_order


# Legt den leeren Bedienzustand für den Konfigurator an.
def default_configurator_state() -> dict[str, Any]:
    return {
        "model": "heo-topology-configurator-v1",
        "stage": "landing",
        "central_devices": [],
        "slot_order": {slot: [] for slot in CENTRAL_SLOT_KEYS},
        "grid_enabled": False,
        "add_menu": None,
        "selected": None,
        "dirty": False,
        "loaded": False,
        "source_scenario": None,
        "had_results": False,
        "results_stale": False,
        "simulation_mode": None,
        "optimization_focus": "comparison",
        "profile_seed_mode": "fixed",
        "profile_seed": 20261013,
        "field_owners": {},
        "open_sections": {},
        "range_enabled": {},
    }


# Ergänzt fehlende Bedienwerte und ordnet die zentralen Topologie-Slots.
def resolved_configurator_state(state: dict[str, Any] | None) -> dict[str, Any]:
    result = default_configurator_state()
    result.update(deepcopy(state or {}))
    result["slot_order"] = normalize_slot_order(
        list(result.get("central_devices") or []),
        result.get("slot_order"),
    )
    return result


# Baut den Bedienzustand aus den gespeicherten HEO-Werten eines Szenarios auf.
def reconstruct_configurator_state(
    heo_state: dict[str, Any], *, scenario_name: str, has_results: bool,
) -> dict[str, Any]:
    values = (heo_state or {}).get("values", {})
    selected = selected_central_devices_from_input(heo_state)
    state = default_configurator_state()
    state.update(
        stage="topology",
        central_devices=selected,
        slot_order=normalize_slot_order(selected),
        grid_enabled=bool(values.get("ENABLE_SUPPLY_EL")),
        loaded=True,
        source_scenario=scenario_name,
        had_results=has_results,
    )
    return state
