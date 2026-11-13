"""Bearbeitet HEO-Eingabewerte unabhängig vom DG-Schema und von Dash-Stores."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from heo.model.annual_series import reconcile_series
from heo.topology.definitions import CONFIGURABLE_CENTRAL_CODES


def clean_heo_state(source: dict[str, Any]) -> dict[str, Any]:
    """Setzt zentrale HEO-Geräte und den Stromnetzbezug in einem Entwurf zurück."""

    state = deepcopy(source)
    values = state.setdefault("values", {})
    for code in CONFIGURABLE_CENTRAL_CODES:
        values[f"C_{code}__FEASIBLE"] = False
    values.pop("C_H2BOI__FEASIBLE", None)
    state.get("saved_values", {}).pop("C_H2BOI__FEASIBLE", None)
    values["ENABLE_SUPPLY_EL"] = False
    return state


def selected_central_devices_from_input(heo_state: dict[str, Any] | None) -> list[str]:
    """Liest die ausgewählten Zentralgeräte aus einem gespeicherten HEO-Entwurf."""

    values = (heo_state or {}).get("values", {})
    return [
        code for code in CONFIGURABLE_CENTRAL_CODES
        if bool(values.get(f"C_{code}__FEASIBLE"))
    ]


def set_all_central_devices(state: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    """Schaltet alle zentral auswählbaren HEO-Geräte und den Strombezug gemeinsam um."""

    updated = deepcopy(state)
    values = updated.setdefault("values", {})
    for code in CONFIGURABLE_CENTRAL_CODES:
        values[f"C_{code}__FEASIBLE"] = enabled
    values.pop("C_H2BOI__FEASIBLE", None)
    updated.get("saved_values", {}).pop("C_H2BOI__FEASIBLE", None)
    values["ENABLE_SUPPLY_EL"] = enabled
    return updated


def set_range_values_enabled(
    state: dict[str, Any],
    drafts: dict[str, dict[str, Any]],
    keys: tuple[str, ...],
    *,
    enabled: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Schaltet Grenzwerte in einer Zustandskopie um und liefert Zustand und gesicherte Entwürfe."""

    updated = deepcopy(state)
    saved_drafts = deepcopy(drafts)
    overrides = {str(item).upper() for item in updated.get("overrides", [])}
    if enabled:
        for key in keys:
            draft = saved_drafts.pop(key, None)
            if draft is not None:
                updated.setdefault("values", {})[key] = draft["value"]
                if draft["override"] and key.upper() not in overrides:
                    updated.setdefault("overrides", []).append(key)
    else:
        for key in keys:
            if key in updated.get("values", {}):
                saved_drafts[key] = {
                    "value": updated["values"][key],
                    "override": key.upper() in overrides,
                }
            updated.setdefault("values", {}).pop(key, None)
        normalized_keys = {item.upper() for item in keys}
        updated["overrides"] = [
            item for item in updated.get("overrides", [])
            if str(item).upper() not in normalized_keys
        ]
    return updated, saved_drafts


def merge_input_values(
    state: dict[str, Any], entries: Iterable[tuple[str, Any]],
) -> dict[str, Any]:
    """Übernimmt bereits konvertierte Eingaben und gleicht bearbeitete Jahresreihen ab."""

    updated = deepcopy(state)
    target = updated.setdefault("values", {})
    defaults = updated.setdefault("defaults", {})
    for key, value in entries:
        if value is None or isinstance(value, str) and not value.strip():
            value = defaults.get(key)
        target[key] = value
    try:
        updated = reconcile_series(updated)
        updated.pop("support_year_error", None)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        updated["support_year_error"] = str(exc)
    return updated
