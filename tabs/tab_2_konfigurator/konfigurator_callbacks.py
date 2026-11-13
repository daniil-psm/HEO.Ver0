# Steuert Topologie, Auswahl und Navigation im Konfigurator.

from __future__ import annotations

import hashlib
import time
import json
from copy import deepcopy

import dash
from dash import ALL, Input, Output, State, html

from dg_adapter.input.input_mapper import heo_state_to_dg_state
from dg_adapter.input.parameter_catalog import DEFAULT_HEO_INPUT_STATE
from heo.model.buildings import (
    building_by_uid,
    building_state,
    duplicate_building,
    empty_building_state,
    move_building,
    new_central_building,
    remove_building,
)
from heo.topology.building import (
    apply_building_candidate,
    building_slot_for_candidate,
    synchronize_central_cooling,
)
from heo.topology.definitions import (
    CENTRAL_DEVICES,
    add_device_to_slot_order,
    has_cooling_system,
    remove_device_from_slot_order,
    remove_resource_from_slot_order,
)
from .konfigurator_config import resolved_configurator_state
from heo.model.site import state_with_effective_albedo
from dg_adapter.input.input_mapper import set_device_feasible
from .konfigurator_parameterdialoge import node_dialog
from .konfigurator_simulationsdialoge import (
    simulation_failure_notice,
    simulation_monitor,
    simulation_settings,
)
from .konfigurator_icons import sidebar_icon_content
from .konfigurator_topologie import render_configurator_topology

# Übernimmt eine im Browser abgelegte Gebäude-Reihenfolge zentral.
@dash.callback(
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input("konfig-building-drag-event", "value"),
    State("building-scenario-store", "data"),
    prevent_initial_call=True,
)
def move_building_from_topology(drag_event, buildings):
    if not drag_event:
        return dash.no_update, dash.no_update
    try:
        event = json.loads(drag_event)
        source_uid = int(event["source_uid"])
        before_uid = int(event["before_uid"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return dash.no_update, dash.no_update
    if source_uid == before_uid:
        return dash.no_update, dash.no_update
    return move_building(buildings, source_uid, before_uid), None


# Dupliziert das gewählte Gebäude, ohne den Parameterdialog zu öffnen.
@dash.callback(
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input({"type": "konfig-duplicate-building", "uid": ALL}, "n_clicks"),
    State({"type": "konfig-duplicate-building", "uid": ALL}, "id"),
    State("building-scenario-store", "data"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def duplicate_building_from_topology(clicks, ids, building_data, config_state):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return (dash.no_update,) * 3
    uid = int(trigger.get("uid", -1))
    lookup = {
        int(item.get("uid", -1)): count or 0
        for item, count in zip(ids or [], clicks or [])
        if isinstance(item, dict)
    }
    if lookup.get(uid, 0) <= 0:
        return (dash.no_update,) * 3

    current = building_state(building_data)
    if building_by_uid(current, uid) is None:
        return (dash.no_update,) * 3
    updated_buildings = duplicate_building(current, uid)
    updated_state = resolved_configurator_state(config_state)
    updated_state.update(add_menu=None, dirty=True)
    return updated_buildings, updated_state, None


# Erkennt Änderungen am Graphen ohne reine Formularzustände.
def topology_render_signature(state, buildings, selection, simulation, static_preview=False):
    graph_state = resolved_configurator_state(state)
    for key in ("dirty", "field_owners", "open_sections", "range_enabled", "parameter_selection"):
        graph_state.pop(key, None)
    simulation = simulation or {}
    relevant = {
        "static_preview": bool(static_preview),
        "state": graph_state,
        "buildings": buildings,
        "dimmed": bool(selection),
        "running": bool(simulation.get("running")) and simulation.get("origin") == "configurator",
        "failed": simulation.get("origin") == "configurator" and simulation.get("status") == "failed",
    }
    serialized = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# Aktualisiert den Konfiguratorzustand aus den Projekteingaben.
@dash.callback(
    Output("konfig-landing", "style"), Output("konfig-workbench", "style"),
    Output("konfig-topology-content", "children"), Output("konfig-inspector", "children"),
    Output("konfig-simulation-settings-content", "children"),
    Output("konfig-simulation-monitor-content", "children"),
    Output("konfig-simulation-choice", "hidden"),
    Output("konfig-simulation-interval", "disabled"),
    Output("konfig-sidebar-simulate", "children"),
    Output("konfig-sidebar-simulate", "hidden"),
    Output("konfig-parameters-overlay-content", "children"),
    Output("konfig-info-back-content", "children"),
    Output("konfig-info-back-content", "className"),
    Output("konfig-topology-render-signature", "data"),
    Input("konfigurator-state-store", "data"), Input("heo-input-draft-store", "data"),
    Input("building-scenario-store", "data"), Input("konfigurator-selection-store", "data"),
    Input("simulation-state-store", "data"), Input("weather-store", "data"),
    Input("konfig-sidebar-simulate", "n_clicks"),
    State("konfig-topology-render-signature", "data"),
    State("konfig-simulation-settings-mode", "value"),
    State("konfig-info-back-content", "className"),
    Input("dev-topology-static-store", "data"),
)
def refresh_configurator(
    state,
    heo_state,
    buildings,
    selection,
    simulation,
    weather,
    simulate_clicks,
    previous_topology_signature,
    settings_mode=None,
    previous_info_class_name=None,
    static_preview=False,
):
    signature = topology_render_signature(state, buildings, selection, simulation, static_preview)
    rendered = render_configurator(
        state, heo_state, buildings, selection, simulation, weather,
        simulate_clicks, render_topology=signature != previous_topology_signature,
        settings_mode=settings_mode, static_preview=static_preview,
    )
    from .konfigurator_layout import (
        info_content_class_name, info_document, info_document_kind,
    )

    info_kind = info_document_kind(state, simulation, rendered[6])
    info_class_name = info_content_class_name(info_kind)
    info_update = (
        (dash.no_update, dash.no_update)
        if info_class_name == previous_info_class_name
        else (info_document(info_kind), info_class_name)
    )
    return (*rendered, *info_update, signature)


# Rendert Topologie und Dialoge des aktuellen Konfiguratorzustands.
def render_configurator(
    state,
    heo_state,
    buildings,
    selection,
    simulation,
    weather,
    simulate_clicks,
    *,
    render_topology=True,
    settings_mode=None,
    static_preview=False,
):
    resolved = resolved_configurator_state(state)
    stage = resolved.get("stage") or "landing"
    # Bereits im Browser gespeicherte Zustände können noch auf die entfernte
    # Projektseite zeigen. Sie landen ebenfalls auf der neuen Startansicht.
    if stage == "project":
        stage = "landing"
    if stage == "simulation_settings":
        stage = "topology"
        resolved["simulation_mode"] = "custom"
    simulation = simulation or {}
    is_configurator_simulation = simulation.get("origin") == "configurator"
    running = bool(simulation.get("running")) and is_configurator_simulation
    # Der Simulationsstatus gewinnt bei getrennten Renderimpulsen der Stores.
    # Nach einem Neuladen steht der Konfigurator wieder auf ``landing``; ein
    # alter Sitzungsfehler darf diese Startansicht nicht erneut überdecken.
    failed = (
        is_configurator_simulation
        and simulation.get("status") == "failed"
        and stage in {"progress", "failed"}
    )
    if failed:
        stage = "failed"
    underlying_stage = (
        resolved.get("parameter_return_stage") or "topology"
        if stage == "parameters" else stage
    )
    # Beim erneuten Einfügen des Tabs startet n_clicks wieder bei 0.
    # Die Auswahl gehört daher zum gespeicherten Zustand des Konfigurators.
    choosing_optimization_settings = (
        resolved.get("simulation_mode") in {"choose", "standard", "custom"}
        and stage == "topology" and not running
    )
    returning_to_configurator = choosing_optimization_settings or failed
    dialog_heo_state = state_with_effective_albedo(
        heo_state or DEFAULT_HEO_INPUT_STATE, weather,
    )
    dialog_heo_state["_range_enabled"] = dict(resolved.get("range_enabled") or {})
    if running or stage in {"progress", "completed"}:
        simulation_content = simulation_monitor(simulation)
    elif stage == "stopped":
        simulation_content = html.Div(
            html.H2("Optimierung gestoppt"),
            className="konfig-simulation-stopped",
        )
    elif stage == "failed":
        simulation_content = simulation_failure_notice(simulation)
    else:
        simulation_content = None
    parameters_content = None
    if stage == "parameters" and not running:
        from .konfigurator_parameteruebersicht import parameter_overview
        parameters_content = parameter_overview(
            dialog_heo_state, buildings, weather, resolved,
        )
    selected_settings_mode = (
        settings_mode if settings_mode in {"standard", "custom"}
        else resolved.get("simulation_mode")
    )
    settings_content = (
        simulation_settings(heo_state or DEFAULT_HEO_INPUT_STATE, resolved)
        if choosing_optimization_settings and selected_settings_mode == "custom"
        else None
    )
    return (
        {} if stage == "landing" and not running else {"display": "none"},
        {} if stage in {"topology", "parameters", "simulation_settings", "progress", "completed", "stopped", "failed"} or running else {"display": "none"},
        render_configurator_topology(
            resolved, buildings, dimmed=bool(selection), static_preview=static_preview,
        ) if render_topology and underlying_stage == "topology" and not running and not choosing_optimization_settings else (
            dash.no_update if not render_topology else None
        ),
        node_dialog(
            selection,
            dialog_heo_state,
            buildings,
            resolved.get("field_owners"),
            resolved.get("open_sections"),
        ) if selection and not static_preview and underlying_stage == "topology" and not running and not choosing_optimization_settings else None,
        settings_content,
        simulation_content,
        not choosing_optimization_settings,
        not (running or stage in {"stopped", "completed"}),
        sidebar_icon_content(
            "square" if running else "circle-arrow-left" if returning_to_configurator else "play",
            "Optimierung stoppen" if running else "Zurück zum Konfigurator" if returning_to_configurator else "Optimierung starten",
        ),
        stage in {"stopped", "completed"},
        parameters_content,
    )


# Spiegelt die native Details-Stellung für die Abschlussnavigation.
@dash.callback(
    Output("konfig-progress-details-open-store", "data"),
    Input("konfig-progress-log-summary", "n_clicks"),
    Input("simulation-state-store", "data"),
    State("konfig-progress-details-open-store", "data"),
    prevent_initial_call=True,
)
def remember_progress_details_state(summary_clicks, simulation, details_open):
    trigger = dash.ctx.triggered_id
    if trigger == "konfig-progress-log-summary" and summary_clicks:
        return not bool(details_open)
    if trigger == "simulation-state-store":
        simulation = simulation or {}
        if simulation.get("running") and simulation.get("fresh"):
            return False
    return dash.no_update


# Öffnet die Ergebnisansicht einer abgeschlossenen Optimierung.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("navigation-request-store", "data", allow_duplicate=True),
    Input("konfig-completion-open-results", "n_clicks"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def open_completed_energy_system(n_clicks, config_state):
    if not n_clicks:
        return dash.no_update, dash.no_update
    state = resolved_configurator_state(config_state)
    state["stage"] = "topology"
    return state, {
        "tab": "dashboard-energiesystem",
        "view": "system",
        "nonce": time.time_ns(),
    }


# Wechselt vom Konfigurator zurück zur Projektauswahl.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input("konfig-sidebar-load", "n_clicks"), State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def return_to_loader(n_clicks, state):
    if not n_clicks:
        return dash.no_update, dash.no_update
    updated = resolved_configurator_state(state)
    updated.update(
        stage="landing",
        add_menu=None,
    )
    return updated, None


# Öffnet die Komponentenauswahl am gewählten Platzhalter.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "konfig-add-slot", "slot": ALL}, "n_clicks"),
    State({"type": "konfig-add-slot", "slot": ALL}, "id"),
    State("konfigurator-state-store", "data"), prevent_initial_call=True,
)
def open_add_menu(clicks, ids, state):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return dash.no_update
    lookup = {item["slot"]: count or 0 for item, count in zip(ids or [], clicks or [])}
    if lookup.get(trigger.get("slot"), 0) <= 0:
        return dash.no_update
    updated = resolved_configurator_state(state)
    updated["add_menu"] = {"slot": trigger["slot"]}
    return updated


# Schließt eine Kandidatenauswahl bei Klick auf eine freie Fläche.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "konfig-menu-dismiss", "scope": ALL}, "n_clicks"),
    State({"type": "konfig-menu-dismiss", "scope": ALL}, "id"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def close_add_menu_outside_candidates(clicks, ids, state):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return dash.no_update
    lookup = {
        item["scope"]: count or 0
        for item, count in zip(ids or [], clicks or [])
    }
    if lookup.get(trigger.get("scope"), 0) <= 0:
        return dash.no_update
    updated = resolved_configurator_state(state)
    if not updated.get("add_menu"):
        return dash.no_update
    updated["add_menu"] = None
    return updated


# Wählt einen Topologieknoten zur Bearbeitung aus.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input({"type": "konfig-node", "kind": ALL, "code": ALL}, "n_clicks"),
    State({"type": "konfig-node", "kind": ALL, "code": ALL}, "id"),
    State({"type": "konfig-node", "kind": ALL, "code": ALL}, "style"),
    State("konfigurator-state-store", "data"), prevent_initial_call=True,
)
def select_node(clicks, ids, styles, state):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return dash.no_update, dash.no_update
    lookup = {(item["kind"], item["code"]): count or 0 for item, count in zip(ids or [], clicks or [])}
    if lookup.get((trigger.get("kind"), trigger.get("code")), 0) <= 0:
        return dash.no_update, dash.no_update
    updated = resolved_configurator_state(state)
    updated["add_menu"] = None
    style_lookup = {
        (item["kind"], item["code"]): style or {}
        for item, style in zip(ids or [], styles or [])
    }
    style = style_lookup.get((trigger.get("kind"), trigger.get("code")), {})
    return updated, {
        "kind": trigger["kind"],
        "code": trigger["code"],
        "anchor": f"{trigger['kind']}:{trigger['code']}",
        "color": style.get("--node-color", "#43564d"),
    }


# Wählt den Gebäudebereich zum Hinzufügen einer Komponente.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input({"type": "konfig-building-slot", "uid": ALL, "slot": ALL, "value": ALL}, "n_clicks"),
    State({"type": "konfig-building-slot", "uid": ALL, "slot": ALL, "value": ALL}, "id"),
    State({"type": "konfig-building-slot", "uid": ALL, "slot": ALL, "value": ALL}, "style"),
    State("konfigurator-state-store", "data"), prevent_initial_call=True,
)
def choose_building_slot(clicks, ids, styles, state):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return dash.no_update, dash.no_update
    key = (trigger["uid"], trigger["slot"], trigger["value"])
    lookup = {(item["uid"], item["slot"], item["value"]): count or 0 for item, count in zip(ids or [], clicks or [])}
    if lookup.get(key, 0) <= 0:
        return dash.no_update, dash.no_update
    updated = resolved_configurator_state(state)
    if trigger.get("value"):
        updated["add_menu"] = None
        style_lookup = {
            (item["uid"], item["slot"], item["value"]): style or {}
            for item, style in zip(ids or [], styles or [])
        }
        style = style_lookup.get(key, {})
        code = f"{trigger['uid']}:{trigger['slot']}:{trigger['value']}"
        return updated, {
            "kind": "decentral",
            "code": code,
            "anchor": f"decentral:{code}",
            "color": style.get("--building-carrier-color", "#43564d"),
        }
    updated["add_menu"] = {"slot": f"building:{trigger['uid']}:{trigger['slot']}"}
    return updated, None


# Fügt die ausgewählte Komponente zum Entwurf hinzu.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input({"type": "konfig-candidate", "slot": ALL, "code": ALL}, "n_clicks"),
    State({"type": "konfig-candidate", "slot": ALL, "code": ALL}, "id"),
    State("konfigurator-state-store", "data"), State("heo-input-draft-store", "data"),
    State("weather-store", "data"), State("building-scenario-store", "data"),
    prevent_initial_call=True,
)
def add_candidate(clicks, ids, config_state, heo_state, weather, buildings):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return (dash.no_update,) * 5
    lookup = {(item["slot"], item["code"]): count or 0 for item, count in zip(ids or [], clicks or [])}
    if lookup.get((trigger["slot"], trigger["code"]), 0) <= 0:
        return (dash.no_update,) * 5
    state = resolved_configurator_state(config_state)
    heo = deepcopy(heo_state or DEFAULT_HEO_INPUT_STATE)
    current_buildings = building_state(buildings or empty_building_state())
    code, slot = trigger["code"], trigger["slot"]
    selection = None
    if code == "GRID":
        state["grid_enabled"] = True
        heo.setdefault("values", {})["ENABLE_SUPPLY_EL"] = True
    elif code == "BUILDING":
        current_buildings = new_central_building(current_buildings)
        # Das neue Gebäude wird unmittelbar konfiguriert. Der stabile ``uid``
        # ist dabei der Dialoganker; die sichtbare Gebäude-ID darf sich bei
        # späterem Umordnen weiterhin ändern.
        uid = int(current_buildings["rows"][-1]["uid"])
        selection = {
            "kind": "building",
            "code": str(uid),
            "anchor": f"building:{uid}",
        }
    elif slot.startswith("building:"):
        _, uid_text, _carrier = slot.split(":", 2)
        row = building_by_uid(current_buildings, int(uid_text))
        local_slot = building_slot_for_candidate(code)
        if row is not None and local_slot is not None:
            apply_building_candidate(row, local_slot, code)
    elif code in CENTRAL_DEVICES:
        # Wie im DG sind Speicher unabhängig von anderen Geräten freigebbar.
        # Bezugsgrenzen und Energiebilanzen bestimmen ihre nutzbare Auslegung.
        add_device_to_slot_order(state, code)
        heo = set_device_feasible(heo, code, True)
        current_buildings = synchronize_central_cooling(
            current_buildings,
            enabled=has_cooling_system(state.get("central_devices") or []),
        )
    state.update(add_menu=None, dirty=True)
    return state, heo, heo_state_to_dg_state(heo, weather_metadata=weather), current_buildings, selection


# Schließt den geöffneten Parameterdialog.
@dash.callback(
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input("konfig-close-dialog", "n_clicks"),
    Input("konfig-dialog-dismiss", "n_clicks"), prevent_initial_call=True,
)
def close_dialog(close_clicks, dismiss_clicks):
    return None if (close_clicks or dismiss_clicks) else dash.no_update


# Entfernt die ausgewählte Komponente aus dem Entwurf.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Input("konfig-remove-selected", "n_clicks"),
    # Der Dialog und damit sein Trash-Button existieren nur bei geöffneter
    # Node-Auswahl. Ohne optionalen Input blockiert Dash die gesamte Callback,
    # sodass auch ein direkt an der Node geklickter Trash-Button nichts auslöst.
    Input("konfig-dialog-remove-selected", "n_clicks", allow_optional=True),
    Input({"type": "konfig-remove-node", "kind": ALL, "code": ALL}, "n_clicks"),
    State({"type": "konfig-remove-node", "kind": ALL, "code": ALL}, "id"),
    State("konfigurator-selection-store", "data"), State("konfigurator-state-store", "data"),
    State("heo-input-draft-store", "data"), State("weather-store", "data"),
    State("building-scenario-store", "data"), prevent_initial_call=True,
)
def remove_selected(
    n_clicks, dialog_remove_clicks, direct_clicks, direct_ids, selection,
    config_state, heo_state, weather, building_data,
):
    trigger = dash.ctx.triggered_id
    if isinstance(trigger, dict):
        lookup = {
            (item["kind"], str(item["code"])): count or 0
            for item, count in zip(direct_ids or [], direct_clicks or [])
        }
        key = (trigger.get("kind"), str(trigger.get("code")))
        if lookup.get(key, 0) <= 0:
            return (dash.no_update,) * 5
        selection = {"kind": key[0], "code": key[1]}
    elif trigger == "konfig-dialog-remove-selected":
        if not dialog_remove_clicks:
            return (dash.no_update,) * 5
    elif not n_clicks:
        return (dash.no_update,) * 5
    if not selection:
        return (dash.no_update,) * 5
    state = resolved_configurator_state(config_state)
    heo = deepcopy(heo_state or DEFAULT_HEO_INPUT_STATE)
    buildings = building_state(building_data)
    kind, code = selection.get("kind"), str(selection.get("code") or "")
    if kind == "central" and code in CENTRAL_DEVICES:
        removed_devices = remove_device_from_slot_order(state, code)
        for device_code in removed_devices:
            heo = set_device_feasible(heo, device_code, False)
        buildings = synchronize_central_cooling(
            buildings,
            enabled=has_cooling_system(state.get("central_devices") or []),
        )
    elif kind == "resource":
        removed_devices = remove_resource_from_slot_order(state, code)
        for device_code in removed_devices:
            heo = set_device_feasible(heo, device_code, False)
        buildings = synchronize_central_cooling(
            buildings,
            enabled=has_cooling_system(state.get("central_devices") or []),
        )
    elif kind == "grid":
        state["grid_enabled"] = False
        heo.setdefault("values", {})["ENABLE_SUPPLY_EL"] = False
    elif kind == "building":
        buildings = remove_building(buildings, int(code))
    elif kind == "decentral":
        uid_text, slot, _device = code.split(":", 2)
        row = building_by_uid(buildings, int(uid_text))
        if row is not None and slot != "dhw_storage":
            apply_building_candidate(row, slot, None)
    state.update(dirty=True, add_menu=None)
    return state, heo, heo_state_to_dg_state(heo, weather_metadata=weather), buildings, None
