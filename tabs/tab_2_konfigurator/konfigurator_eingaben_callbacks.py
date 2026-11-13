# Verarbeitet Formular-, Geräte- und Gebäudeeingaben im Konfigurator.

from __future__ import annotations

import math
import json
from copy import deepcopy
from typing import Any

import dash
from dash import ALL, MATCH, Input, Output, State

from heo.model.annual_series import (
    ANNUAL_KEYS,
    edit_series,
    series_view,
    set_support_year_mode,
    support_year_mode,
)
from dg_adapter.shared.scenario_names import validate_scenario_name
from dg_adapter.input.input_mapper import heo_state_to_dg_state
from dg_adapter.execution.profile_service import validate_profile_seed_choice
from dg_adapter.input.parameter_catalog import DEFAULT_HEO_INPUT_STATE
from dg_adapter.input.form_values import parse_dg_field_value
from heo.model.buildings import building_state, update_building_values
from heo.topology.building import apply_building_candidate, synchronize_central_cooling
from heo.display.parameter_catalog import ACTIVATION_FIELD_GROUPS
from heo.topology.definitions import (
    CONFIGURABLE_CENTRAL_CODES,
    has_cooling_system,
    normalize_slot_order,
)
from heo.model.configuration import (
    merge_input_values,
    set_all_central_devices,
    set_range_values_enabled,
)
from heo.display.field_presentation import checkbox_field_value
from heo.display.parameter_dialog_layout import (
    COOLING_PERIOD_FIELDS,
    HEATING_PERIOD_FIELDS,
    POWER_SHARED_FIELDS,
    SHARED_NETWORK_FIELDS,
)
from .konfigurator_config import default_configurator_state, resolved_configurator_state
from dg_adapter.input.parameter_catalog import field_spec
from .konfigurator_formfelder import RANGE_PAIR_KEY_SEPARATOR, format_field_number
from heo.display.field_values import (
    dependent_panel_hidden,
)
from ui.components.sidebar import sidebar_nav_button_class
from heo.display.number_format import parse_german_number
from heo.display.building_fields import (
    BUILDING_INTEGER_INPUT_FIELDS,
    BUILDING_DECIMAL_INPUT_FIELDS,
)

# Liest die sichtbaren Dash-Feld-IDs und übergibt ihre Werte an Adapter und HEO-Modell.
def merge_visible_fields(state, ids, values):
    defaults = state.get("defaults", {})
    entries = (
        (
            key,
            parse_dg_field_value(key, raw_value, defaults.get(key)),
        )
        for component_id, raw_value in zip(ids or [], values or [])
        if isinstance(component_id, dict)
        if (key := component_id.get("key"))
    )
    return merge_input_values(state, entries)


# Ermittelt den Besitzer der Felder eines Parameterdialogs.
def _dialog_owner(selection: dict[str, Any] | None) -> str | None:
    kind = str((selection or {}).get("kind") or "")
    code = str((selection or {}).get("code") or "")
    if kind == "load":
        return "load"
    if kind == "network" and code == "HEAT_GRID":
        return "heat_network"
    if kind == "network" and code == "COOL_GRID":
        return "cool_network"
    if kind == "grid" and code == "GRID":
        return "power_grid"
    if kind == "grid" and code in {"AC_BUS", "DC_BUS", "INVERTER"}:
        return "power_bus"
    return None


# Merkt sich die Einblendung, in der ein mehrfach sichtbares Feld geändert wurde.
def _record_field_owner(
    config_state: dict[str, Any] | None,
    heo_state: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    trigger: Any,
    ids: list[Any] | None,
    values: list[Any] | None,
) -> dict[str, Any]:
    updated = resolved_configurator_state(config_state)
    owner = _dialog_owner(selection)
    key = trigger.get("key") if isinstance(trigger, dict) else None
    duplicated = set(
        HEATING_PERIOD_FIELDS + COOLING_PERIOD_FIELDS
        + SHARED_NETWORK_FIELDS + POWER_SHARED_FIELDS
    )
    if owner is None or not key or key not in duplicated:
        return updated
    current = (heo_state or {}).get("values", {}).get(
        key, (heo_state or {}).get("defaults", {}).get(key),
    )
    raw_value = next(
        (value for component_id, value in zip(ids or [], values or [])
         if isinstance(component_id, dict) and component_id.get("key") == key),
        current,
    )
    parsed = parse_dg_field_value(str(key), raw_value, current)
    if parsed == current:
        return updated
    group = next(
        (
            (enabled_key, *tuple(metadata.get("fields") or ()))
            for enabled_key, metadata in ACTIVATION_FIELD_GROUPS.items()
            if key in (enabled_key, *tuple(metadata.get("fields") or ()))
        ),
        (key,),
    )
    owners = updated.setdefault("field_owners", {})
    for grouped_key in group:
        owners[grouped_key] = owner
    return updated


# Schaltet alle auswählbaren Zentralgeräte und das Stromnetz um.
def _set_all_central_components(
    config_state,
    heo_state,
    weather,
    building_data,
    *,
    enabled: bool,
):
    state = resolved_configurator_state(config_state)
    heo = set_all_central_devices(
        heo_state or DEFAULT_HEO_INPUT_STATE, enabled=enabled,
    )
    selected = list(CONFIGURABLE_CENTRAL_CODES) if enabled else []

    state.update(
        central_devices=selected,
        slot_order=normalize_slot_order(selected),
        grid_enabled=enabled,
        add_menu=None,
        dirty=True,
    )
    buildings = synchronize_central_cooling(
        building_state(building_data),
        enabled=has_cooling_system(selected),
    )
    return (
        state,
        heo,
        heo_state_to_dg_state(heo, weather_metadata=weather),
        buildings,
        None,
    )


# Übernimmt die gemeinsame Auswahl zentraler Komponenten.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input("konfig-sidebar-select-all", "n_clicks"),
    Input("konfig-sidebar-deselect-all", "n_clicks"),
    State("konfigurator-state-store", "data"),
    State("heo-input-draft-store", "data"),
    State("weather-store", "data"),
    State("building-scenario-store", "data"),
    prevent_initial_call=True,
)
def set_all_central_components(
    select_clicks,
    deselect_clicks,
    config_state,
    heo_state,
    weather,
    building_data,
):
    trigger = dash.ctx.triggered_id
    if trigger == "konfig-sidebar-select-all" and select_clicks:
        enabled = True
    elif trigger == "konfig-sidebar-deselect-all" and deselect_clicks:
        enabled = False
    else:
        return (dash.no_update,) * 5
    return _set_all_central_components(
        config_state,
        heo_state,
        weather,
        building_data,
        enabled=enabled,
    )


# Übernimmt Änderungen an den Jahresreihen.
@dash.callback(
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "konfig-series-mode", "key": ALL}, "value"),
    Input({"type": "konfig-series-value", "key": ALL, "year": ALL}, "value"),
    State({"type": "konfig-series-mode", "key": ALL}, "id"),
    State({"type": "konfig-series-value", "key": ALL, "year": ALL}, "id"),
    State("heo-input-draft-store", "data"), State("weather-store", "data"),
    State("konfigurator-state-store", "data"),
    State("konfigurator-selection-store", "data"),
    prevent_initial_call=True,
)
def update_annual_series(modes, entries, mode_ids, entry_ids, heo, weather, config, selection=None, *, trigger_override=None):
    trigger = trigger_override or dash.ctx.triggered_id
    if not isinstance(trigger, dict) or trigger.get("key") not in ANNUAL_KEYS:
        return (dash.no_update,) * 3
    key = trigger["key"]
    state = deepcopy(heo or DEFAULT_HEO_INPUT_STATE)
    previous_mode, points, previous = series_view(state, key)
    mode = next((v for ident, v in zip(mode_ids, modes) if ident["key"] == key), previous_mode)
    raw = [value for ident, value in sorted(zip(entry_ids, entries), key=lambda pair: pair[0]["year"]) if ident["key"] == key]
    try:
        if trigger["type"] == "konfig-series-mode":
            if mode == previous_mode:
                return (dash.no_update,) * 3
            parsed = [previous[0]] if mode == "constant" else [previous[0]] * len(points)
        else:
            spec = field_spec(key)
            if raw == [format_field_number(value, spec) for value in previous] and key not in state.get("annual_errors", {}):
                return (dash.no_update,) * 3
            parsed = [parse_german_number(value, kind="decimal") / float(spec.get("display_scale") or 1) for value in raw]
        state = edit_series(state, key, mode, parsed)
        state.get("annual_errors", {}).pop(key, None)
        state.get("annual_drafts", {}).pop(key, None)
    except (ValueError, TypeError) as exc:
        if state.get("annual_drafts", {}).get(key) == raw:
            return (dash.no_update,) * 3
        state.setdefault("annual_errors", {})[key] = str(exc)
        state.setdefault("annual_drafts", {})[key] = raw
    config = deepcopy(config or default_configurator_state())
    if key not in state.get("annual_errors", {}):
        config = _record_field_owner(config, heo, selection, trigger, [trigger], [state["values"][key]])
    config.update(dirty=True, results_stale=bool(config.get("had_results")))
    return state, heo_state_to_dg_state(state, weather_metadata=weather), config


# Übernimmt geänderte Geräte- und Netzparameter in den Zustand.
@dash.callback(
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "konfig-field", "key": ALL}, "value"),
    State({"type": "konfig-field", "key": ALL}, "id"),
    State("heo-input-draft-store", "data"), State("weather-store", "data"),
    State("konfigurator-state-store", "data"),
    State("konfigurator-selection-store", "data"),
    State({"type": "konfig-advanced-section", "key": ALL}, "open"),
    State({"type": "konfig-advanced-section", "key": ALL}, "id"),
    prevent_initial_call=True,
)
def update_config_fields(
    values, ids, heo_state, weather, config_state, selection,
    section_open_values, section_ids,
):
    if not ids:
        return (dash.no_update,) * 3
    updated_heo = merge_visible_fields(heo_state or DEFAULT_HEO_INPUT_STATE, ids, values)
    trigger = dash.ctx.triggered_id
    if isinstance(trigger, dict) and trigger.get("key") == "ALBEDO":
        overrides = updated_heo.setdefault("overrides", [])
        if "ALBEDO" not in {str(key).upper() for key in overrides}:
            overrides.append("ALBEDO")
    updated_config = _record_field_owner(
        config_state, heo_state, selection, trigger, ids, values,
    )
    updated_config = _with_advanced_section_state(
        updated_config, section_open_values, section_ids,
    )
    updated_config["dirty"] = True
    return updated_heo, heo_state_to_dg_state(updated_heo, weather_metadata=weather), updated_config


# Übernimmt den aktuellen Offen-Zustand ohne einen zweiten Renderzyklus.
def _with_advanced_section_state(config_state, open_values, section_ids):
    updated = deepcopy(config_state or default_configurator_state())
    stored = dict(updated.get("open_sections") or {})
    for component_id, is_open in zip(section_ids or [], open_values or []):
        key = str((component_id or {}).get("key") or "")
        if key:
            stored[key] = bool(is_open)
    updated["open_sections"] = stored
    return updated


# Bewahrt geöffnete Parameterbereiche über Dialog-Neurenderings hinweg.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "konfig-advanced-section", "key": ALL}, "open"),
    State({"type": "konfig-advanced-section", "key": ALL}, "id"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def persist_advanced_sections(open_values, section_ids, config_state):
    if not section_ids:
        return dash.no_update
    updated = _with_advanced_section_state(config_state, open_values, section_ids)
    if updated.get("open_sections") == (config_state or {}).get("open_sections", {}):
        return dash.no_update
    return updated


# Zeigt abhängige Eingaben erst nach Aktivierung des Parameterblocks.
@dash.callback(
    Output({"type": "konfig-dependent-fields", "key": MATCH}, "hidden"),
    Input({"type": "konfig-field", "key": MATCH}, "value"),
)
def toggle_period_dates(consider_period):
    return dependent_panel_hidden(bool(consider_period), True)


# Blendet die beiden Werte eines MIN-/MAX-Paars gemeinsam ein.
@dash.callback(
    Output({"type": "konfig-range-dependent", "key": MATCH}, "hidden"),
    Input({"type": "konfig-range-toggle", "key": MATCH}, "value"),
)
def toggle_range_parameter(enabled):
    return dependent_panel_hidden(bool(enabled), True)


# Zeigt Gurobi-spezifische Optionen nur für diesen Solver.
@dash.callback(
    Output("konfig-gurobi-options-panel", "hidden"),
    Input({"type": "konfig-field", "key": "SOLVER_NAME"}, "value"),
)
def toggle_gurobi_settings(solver_name):
    return dependent_panel_hidden(str(solver_name).lower(), "gurobi")


# Zeigt nur die zur gewählten Eingabeart gehörenden Stützjahre.
@dash.callback(
    Output("konfig-support-year-count-panel", "hidden"),
    Output("konfig-support-year-list-panel", "hidden"),
    Input("konfig-support-year-mode", "value"),
)
def toggle_support_year_fields(mode):
    return mode != "count", mode != "years"


# Blendet das Zahlenfeld nur bei vorgegebenem Seed ein.
@dash.callback(
    Output("konfig-profile-seed-fixed-panel", "hidden"),
    Input("konfig-profile-seed-mode", "value"),
)
def toggle_profile_seed_field(mode):
    return mode != "fixed"


# Speichert die Auswahl zur Wiederverwendung des Profil-Seeds.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input("konfig-profile-seed-mode", "value"),
    Input("konfig-profile-seed-value", "value"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def remember_profile_seed_choice(mode, seed, config_state):
    if mode not in {"fixed", "random"}:
        return dash.no_update
    state = resolved_configurator_state(config_state)
    if mode == "fixed":
        next_seed = seed
        if isinstance(seed, str):
            try:
                parsed_seed = parse_german_number(seed, kind="integer")
            except ValueError:
                pass
            else:
                if parsed_seed.is_integer():
                    next_seed = int(parsed_seed)
    else:
        try:
            next_seed = validate_profile_seed_choice(
                "random", state.get("profile_seed"),
            )
        except ValueError:
            next_seed = 20261013
    if state.get("profile_seed_mode") == mode and state.get("profile_seed") == next_seed:
        return dash.no_update
    state.update(
        profile_seed_mode=mode,
        profile_seed=next_seed,
        dirty=True,
        results_stale=bool(state.get("had_results")),
    )
    return state


# Synchronisiert die Auswahl mit der Vorrangregel der DG-Konfiguration.
@dash.callback(
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input("konfig-support-year-mode", "value"),
    State("heo-input-draft-store", "data"),
    State("weather-store", "data"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def choose_support_year_mode(mode, heo_state, weather, config_state):
    if mode not in {"count", "years"}:
        return (dash.no_update,) * 3
    source = heo_state or DEFAULT_HEO_INPUT_STATE
    if mode == support_year_mode(source):
        return (dash.no_update,) * 3
    updated = set_support_year_mode(source, mode)
    config = deepcopy(config_state or default_configurator_state())
    config.update(dirty=True, results_stale=bool(config.get("had_results")))
    return updated, heo_state_to_dg_state(updated, weather_metadata=weather), config


# Deaktiviert Grenzen im DG und bewahrt die Eingaben für erneutes Aktivieren.
def _range_parameter_state(
    key, enabled, heo_state, weather, config_state,
):
    keys = tuple(
        item for item in str(key).split(RANGE_PAIR_KEY_SEPARATOR, 1) if item
    )
    updated_config = resolved_configurator_state(config_state)
    enabled_fields = dict(updated_config.get("range_enabled") or {})
    for range_key in keys:
        enabled_fields[range_key] = bool(enabled)
    updated_config["range_enabled"] = enabled_fields
    updated_config["dirty"] = True

    updated_heo, drafts = set_range_values_enabled(
        heo_state or DEFAULT_HEO_INPUT_STATE,
        updated_config.get("range_drafts") or {},
        keys,
        enabled=enabled,
    )
    updated_config["range_drafts"] = drafts
    return (
        updated_heo,
        heo_state_to_dg_state(updated_heo, weather_metadata=weather),
        updated_config,
    )


# Übernimmt geänderte Bereichsparameter in den Zustand.
@dash.callback(
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "konfig-range-toggle", "key": ALL}, "value"),
    State({"type": "konfig-range-toggle", "key": ALL}, "id"),
    State("heo-input-draft-store", "data"),
    State("weather-store", "data"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def update_range_parameter_state(
    enabled_values, toggle_ids, heo_state, weather, config_state,
):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return (dash.no_update,) * 3
    values_by_key = {
        str(component_id.get("key")): bool(value)
        for component_id, value in zip(toggle_ids or [], enabled_values or [])
    }
    key = str(trigger.get("key") or "")
    if not key or key not in values_by_key:
        return (dash.no_update,) * 3
    return _range_parameter_state(
        key, values_by_key[key], heo_state, weather, config_state,
    )


# Übernimmt geänderte Gebäudefelder in die Projektdaten.
@dash.callback(
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "konfig-building-field", "uid": ALL, "field": ALL}, "value"),
    State({"type": "konfig-building-field", "uid": ALL, "field": ALL}, "id"),
    State("building-scenario-store", "data"), State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def update_building_fields(values, ids, building_data, config_state):
    if not ids:
        return dash.no_update, dash.no_update
    normalized_ids = []
    for component_id in ids:
        normalized = dict(component_id) if isinstance(component_id, dict) else component_id
        if isinstance(normalized, dict) and "@" in str(normalized.get("field") or ""):
            field, category = str(normalized["field"]).split("@", 1)
            normalized["field"] = field
            normalized["category"] = category
        normalized_ids.append(normalized)
    standard_ids = []
    standard_values = []
    special_fields = {"central_heat", "cooling"}
    for component_id, raw in zip(normalized_ids, values):
        if (
            isinstance(component_id, dict)
            and component_id.get("field") not in special_fields
        ):
            field = str(component_id.get("field") or "")
            value = checkbox_field_value(raw)
            if field in BUILDING_INTEGER_INPUT_FIELDS | BUILDING_DECIMAL_INPUT_FIELDS:
                try:
                    number = parse_german_number(
                        value,
                        kind=(
                            "integer" if field in BUILDING_INTEGER_INPUT_FIELDS
                            else "decimal"
                        ),
                    )
                except (TypeError, ValueError):
                    continue
                value = (
                    int(
                        math.floor(number + 0.5)
                        if number >= 0 else math.ceil(number - 0.5)
                    )
                    if field in BUILDING_INTEGER_INPUT_FIELDS else number
                )
            if field in {"beta_PV", "gamma_PV"}:
                if field == "beta_PV":
                    value = max(0, min(90, value))
                else:
                    value = max(-180, min(180, value))
            if field == "EV":
                value /= 100.0
            standard_ids.append(component_id)
            standard_values.append(value)
    updated = update_building_values(
        building_data, standard_ids, standard_values,
    )
    rows = {int(row["uid"]): row for row in updated["rows"]}
    for component_id, raw in zip(normalized_ids, values):
        if not isinstance(component_id, dict):
            continue
        row = rows.get(int(component_id["uid"]))
        if row is None:
            continue
        field, value = component_id["field"], checkbox_field_value(raw)
        if field == "central_heat":
            apply_building_candidate(row, "heater", None if bool(value) else "HP")
        elif field == "cooling":
            row[field] = bool(value)
            for key in ("cooling_supply", "_cooling_decentral", "_central_cooling_opt_out"):
                row.pop(key, None)
    state = resolved_configurator_state(config_state)
    state["dirty"] = True
    return updated, state


# Übernimmt nur gültige Detail-IDs aus dem dynamischen Overlay.
def remember_parameter_details(state, ids, opened):
    remembered = state.setdefault("parameter_details", {})
    for ident, value in zip(ids or [], opened or []):
        if isinstance(ident, dict) and isinstance(ident.get("key"), str):
            remembered[ident["key"]] = bool(value)


# Wechselt den sichtbaren Bereich der Parameterübersicht.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input("konfig-sidebar-parameters", "n_clicks"),
    Input("konfig-parameters-close", "n_clicks"),
    Input({"type": "all-param-selector", "group": ALL, "key": ALL}, "n_clicks"),
    State({"type": "all-param-selector", "group": ALL, "key": ALL}, "id"),
    State("konfigurator-state-store", "data"),
    State("simulation-state-store", "data"),
    State({"type": "all-param-details", "key": ALL}, "open"),
    State({"type": "all-param-details", "key": ALL}, "id"),
    prevent_initial_call=True,
)
def navigate_parameters(open_clicks, close_clicks, clicks, ids, config, simulation, opened, details):
    if (simulation or {}).get("running"):
        return (dash.no_update,) * 2
    trigger = dash.ctx.triggered_id
    state = resolved_configurator_state(config)
    if isinstance(trigger, dict):
        if state.get("stage") != "parameters":
            return (dash.no_update,) * 2
        count = next((v for ident, v in zip(ids or [], clicks or []) if ident == trigger), 0)
        if not count:
            return (dash.no_update,) * 2
        state.setdefault("parameter_selection", {})[trigger["group"]] = trigger["key"]
    elif trigger == "konfig-sidebar-parameters" and open_clicks:
        if state.get("stage") == "parameters":
            state["stage"] = state.pop("parameter_return_stage", "topology")
        else:
            previous = state.get("stage")
            state["parameter_return_stage"] = (
                previous if previous not in {None, "landing", "project"} else "topology"
            )
            state["stage"] = "parameters"
    elif trigger == "konfig-parameters-close" and close_clicks:
        if state.get("stage") != "parameters":
            return (dash.no_update,) * 2
        state["stage"] = state.pop("parameter_return_stage", "topology")
    else:
        return (dash.no_update,) * 2
    remember_parameter_details(state, details, opened)
    return state, dash.no_update


# Kennzeichnet den ausgewählten Bereich der Parameterübersicht.
@dash.callback(
    Output("konfig-sidebar-parameters", "className"),
    Output("konfig-sidebar-parameters", "aria-expanded"),
    Input("konfigurator-state-store", "data"),
)
def parameter_button_class(config):
    active = (config or {}).get("stage") == "parameters"
    return sidebar_nav_button_class(active=active), "true" if active else "false"


# Übernimmt den Öffnungszustand der Parameterdetails.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "all-param-summary", "key": ALL, "default_open": ALL}, "n_clicks"),
    State({"type": "all-param-summary", "key": ALL, "default_open": ALL}, "id"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def toggle_overview_details(clicks, ids, config):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict) or (config or {}).get("stage") != "parameters":
        return dash.no_update
    count = next((count for ident, count in zip(ids or [], clicks or []) if ident == trigger), 0)
    if not count:
        return dash.no_update
    state = resolved_configurator_state(config)
    details = state.setdefault("parameter_details", {})
    key = trigger["key"]
    details[key] = not details.get(key, trigger["default_open"])
    return state


# Öffnet die Bearbeitung des ausgewählten Übersichtsparameters.
@dash.callback(
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("all-param-error", "children"),
    Input({"type": "all-param-control", "scope": ALL, "control": ALL}, "value"),
    State({"type": "all-param-control", "scope": ALL, "control": ALL}, "id"),
    State("heo-input-draft-store", "data"), State("building-scenario-store", "data"),
    State("konfigurator-state-store", "data"), State("weather-store", "data"),
    State("simulation-state-store", "data"),
    State({"type": "all-param-details", "key": ALL}, "open"),
    State({"type": "all-param-details", "key": ALL}, "id"),
    prevent_initial_call=True,
)
def edit_overview_parameter(values, ids, heo, buildings, config, weather, simulation, opened, details):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict) or (config or {}).get("stage") != "parameters" or (simulation or {}).get("running"):
        return (dash.no_update,) * 5
    pairs = list(zip(ids or [], values or []))
    found = [(ident, raw) for ident, raw in pairs if ident == trigger]
    if not found:
        return (dash.no_update,) * 5
    raw = found[0][1]
    original = json.loads(trigger["control"])
    kind = original.get("type")
    state, settings = deepcopy(heo or DEFAULT_HEO_INPUT_STATE), resolved_configurator_state(config)
    updated_buildings = dash.no_update
    try:
        if kind == "konfig-field":
            key = original["key"]
            sentinel = object()
            parsed = parse_dg_field_value(key, raw, sentinel)
            if parsed is sentinel:
                raise ValueError("Bitte einen gültigen Wert eingeben.")
            if key == "SCENARIO_NAME":
                parsed = validate_scenario_name(parsed)
            if key == "DISTRICT_AREA_M2" and float(parsed) <= 0:
                raise ValueError("Die Arealfläche muss größer als 0 m² sein.")
            spec = field_spec(key) or {}
            if spec.get("value_type") in {"dict", "list"} and isinstance(parsed, str):
                json.loads(parsed)
            state = merge_visible_fields(
                state, [original], [parsed if key == "SCENARIO_NAME" else raw],
            )
            if key == "ALBEDO" and key not in state.setdefault("overrides", []):
                state["overrides"].append(key)
            if key == "ENABLE_SUPPLY_EL":
                settings["grid_enabled"] = bool(state["values"][key])
        elif kind == "konfig-building-field":
            updated_buildings, settings = update_building_fields([raw], [original], buildings, settings)
            if updated_buildings == buildings:
                return (dash.no_update,) * 5
        elif kind == "konfig-range-toggle":
            state, _, settings = _range_parameter_state(original["key"], bool(raw), state, weather, settings)
        elif kind in {"konfig-series-mode", "konfig-series-value"}:
            local = [(json.loads(ident["control"]), value) for ident, value in pairs if ident["scope"] == trigger["scope"]]
            modes = [(ident, value) for ident, value in local if ident.get("type") == "konfig-series-mode"]
            entries = [(ident, value) for ident, value in local if ident.get("type") == "konfig-series-value"]
            state, _, settings = update_annual_series(
                [v for _, v in modes], [v for _, v in entries], [i for i, _ in modes], [i for i, _ in entries],
                state, weather, settings, trigger_override=original,
            )
            if state is dash.no_update:
                return (dash.no_update,) * 5
        else:
            return (dash.no_update,) * 5
        if state == heo and updated_buildings is dash.no_update and settings == resolved_configurator_state(config):
            return (dash.no_update,) * 5
        remember_parameter_details(settings, details, opened)
        settings.update(dirty=True, results_stale=bool(settings.get("had_results")))
        return state, heo_state_to_dg_state(state, weather_metadata=weather), updated_buildings, settings, ""
    except (ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        return (*((dash.no_update,) * 4), str(exc))
