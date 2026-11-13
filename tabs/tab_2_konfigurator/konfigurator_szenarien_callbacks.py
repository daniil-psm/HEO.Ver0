# Verwaltet Szenarien sowie Projekt-, Standort- und Wetterdaten im Konfigurator.

from __future__ import annotations

import time
from copy import deepcopy
from typing import Any

import dash
from dash import ALL, MATCH, Input, Output, State, html

from dg_adapter.input.config_service import (
    DGConfigError,
    delete_dg_scenario,
    delete_dg_scenario_results,
    duplicate_dg_scenario,
    list_dg_scenarios,
    rename_dg_scenario,
    scenario_config_path,
    validate_new_scenario_name,
)
from dg_adapter.input.scenario_paths import scenario_building_csv_path
from dg_adapter.execution.calculation_context import current_input_sha256
from dg_adapter.input.input_mapper import heo_state_to_dg_state
from dg_adapter.input.input_service import load_heo_scenario
from dg_adapter.output import DGResultError
from dg_adapter.output.demand_profiles import demand_result_error_store, load_demand_results
from dg_adapter.output.results_reader import load_complete_scenario_results
from dg_adapter.input.site_lookup import lookup_german_site
from heo.model.site import (
    LOCATION_MODE_GERMANY,
    LOCATION_MODE_OTHER,
    LOCATION_MODE_PIDULA,
    german_location_label,
)
from dg_adapter.input.weather_input import DEFAULT_WEATHER_DATA, parse_weather_upload
from dg_adapter.input.parameter_catalog import DEFAULT_HEO_INPUT_STATE
from heo.model.buildings import (
    building_by_uid,
    building_state,
    empty_building_state,
    update_building_values,
)
from heo.model.configuration import clean_heo_state
from .konfigurator_config import (
    default_configurator_state,
    reconstruct_configurator_state,
    resolved_configurator_state,
)
from heo.display.field_values import (
    dependent_panel_hidden,
)
from ui.components.form_controls import (
    scenario_choice_rows,
)
from .konfigurator_eingaben_callbacks import merge_visible_fields, remember_parameter_details
from .konfigurator_simulation_callbacks import with_topology_snapshot

# Beschriftung des Ladebuttons während ein Szenario bearbeitet oder geladen wird.
def _scenario_load_button_loading_content() -> html.Span:
    return html.Span(
        [
            html.Span(
                className="konfig-button-loading-spinner",
                **{"aria-hidden": "true"},
            ),
            html.Span("Lädt"),
        ],
        className="konfig-button-loading-content",
    )


# Übernimmt Wetterdaten aus einem geladenen Projekt.
def _loaded_weather(config_state: dict, upload: dict | None):
    mode = config_state.get("location_mode")
    if mode == LOCATION_MODE_PIDULA:
        return DEFAULT_WEATHER_DATA, None
    if mode == LOCATION_MODE_GERMANY:
        return None, None
    if not upload:
        return None, None
    return parse_weather_upload(upload["contents"], upload["filename"]), upload


# Lädt das ausgewählte Projekt in die Eingabe- und Konfigurationszustände.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("weather-store", "data", allow_duplicate=True),
    Output("weather-upload-store", "data", allow_duplicate=True),
    Output("demand-profile-store", "data", allow_duplicate=True),
    Output("optimization-result-store", "data", allow_duplicate=True),
    Output("navigation-request-store", "data", allow_duplicate=True),
    Output("konfig-load-status", "children"),
    Input("konfig-load-project", "n_clicks"), State("konfig-scenario-select", "data"),
    prevent_initial_call=True,
    running=[
        (
            Output("konfig-load-project", "children"),
            _scenario_load_button_loading_content(),
            "Szenario laden",
        ),
        (Output("konfig-load-project", "disabled"), True, False),
    ],
)
def load_project(n_clicks, scenario_name):
    if not n_clicks:
        return (dash.no_update,) * 10
    if not scenario_name:
        return (*((dash.no_update,) * 9), "Bitte ein Szenario auswählen.")
    try:
        loaded = load_heo_scenario(scenario_name)
        heo = loaded["state"]
        buildings = building_state(loaded["buildings"])
        weather, upload = _loaded_weather(heo, loaded.get("weather_upload"))
        result_error = None
        input_notice = None
        try:
            package = load_complete_scenario_results(scenario_name)
            demands = package["demands"]
            optimization = package["optimization"]
            has_results = True
        except DGResultError as exc:
            result_error = exc
            has_results = False
            try:
                demands = load_demand_results(scenario_name)
            except (DGResultError, ValueError, OSError) as exc:
                demands = demand_result_error_store(scenario_name, exc)
            # Ein einzelnes Optimierungsbundle darf den Ergebnisse-Tab nicht
            # freischalten. Nur das oben vollständig und aktuell validierte
            # Gesamtpaket wird in den zentralen Ergebnis-Store übernommen.
            optimization = None
        if has_results:
            optimization = with_topology_snapshot(optimization, buildings)
        state = reconstruct_configurator_state(
            heo,
            scenario_name=scenario_name,
            has_results=has_results,
        )
        seed_choice = loaded.get("profile_seed_choice") or {
            "mode": "fixed", "seed": 20261013,
        }
        state.update(
            profile_seed_mode=seed_choice["mode"],
            profile_seed=seed_choice["seed"],
        )
        if has_results:
            comparison_manifest = ((package.get("comparison") or {}).get("manifest") or {})
            saved_context = (
                (comparison_manifest.get("variants") or {})
                .get(str(optimization.get("objective") or ""), {})
                .get("calculation_context") or {}
            )
            if saved_context.get("input_sha256"):
                try:
                    current_hash = current_input_sha256(
                        scenario_config_path(scenario_name),
                        scenario_building_csv_path(scenario_name),
                    )
                except (OSError, ValueError, TypeError) as exc:
                    input_notice = f"Der aktuelle Eingabestand konnte nicht geprüft werden: {exc}"
                else:
                    if current_hash != saved_context["input_sha256"]:
                        state["results_stale"] = True
                        input_notice = (
                            "Die Ergebnisse stammen aus einem früheren Eingabestand. "
                            "Für die aktuellen Eingaben bitte neu optimieren."
                        )
            requested = tuple(
                comparison_manifest.get("requested_objectives") or ()
            )
            if requested == ("economic", "ecological"):
                state["optimization_focus"] = "comparison"
            elif requested in {("economic",), ("ecological",)}:
                state["optimization_focus"] = requested[0]
    except (DGConfigError, ValueError, TypeError, OSError) as exc:
        return (*((dash.no_update,) * 9), [html.Strong("Nicht geladen: "), str(exc)])
    navigation = (
        {
            "tab": "dashboard-energiesystem",
            "view": "system",
            "nonce": time.time_ns(),
        }
        if has_results else dash.no_update
    )
    status = None
    if result_error is not None:
        status = (
            "Vorhandene Ergebnisse wurden nicht geladen, weil sie "
            f"unvollständig oder veraltet sind: {result_error}"
        )
    elif input_notice is not None:
        status = input_notice
    return (
        state,
        heo,
        heo_state_to_dg_state(heo),
        buildings,
        weather,
        upload,
        demands,
        optimization,
        navigation,
        status,
    )


# Aktualisiert Auswahl und Namen auch nach Speichern oder Umbenennen.
@dash.callback(
    Output("konfig-scenario-list", "children"),
    Input("konfigurator-state-store", "data"),
    Input("konfig-scenario-select", "data"),
    Input("konfig-scenario-edit", "data"),
    Input("konfig-scenario-delete-pending", "data"),
)
def refresh_scenario_rows(_state, selected, editing, deleting):
    scenarios = list_dg_scenarios()
    names = {str(item["name"]) for item in scenarios}
    effective_selected = selected if selected in names else (
        str(scenarios[0]["name"]) if scenarios else None
    )
    effective_editing = editing if editing in names else None
    return scenario_choice_rows(
        scenarios,
        selected=effective_selected,
        editing=effective_editing,
        deleting=deleting if deleting in names else None,
    )


# Übernimmt die Szenarioauswahl der Projektübersicht.
@dash.callback(
    Output("konfig-scenario-select", "data", allow_duplicate=True),
    Input({"type": "konfig-scenario-choice", "name": ALL}, "n_clicks"),
    State({"type": "konfig-scenario-choice", "name": ALL}, "id"),
    prevent_initial_call=True,
)
def select_landing_scenario(clicks, ids):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return dash.no_update
    clicked = {
        str(item["name"]): count or 0
        for item, count in zip(ids or [], clicks or [])
    }
    name = str(trigger.get("name") or "")
    return name if clicked.get(name, 0) > 0 else dash.no_update


# Erstellt eine Kopie des ausgewählten Szenarios.
@dash.callback(
    Output("konfig-scenario-select", "data", allow_duplicate=True),
    Output("konfig-scenario-edit", "data", allow_duplicate=True),
    Output("konfig-load-status", "children", allow_duplicate=True),
    Input({"type": "konfig-copy-scenario", "name": ALL}, "n_clicks"),
    State({"type": "konfig-copy-scenario", "name": ALL}, "id"),
    prevent_initial_call=True,
    running=[
        (
            Output("konfig-load-project", "children"),
            _scenario_load_button_loading_content(),
            "Szenario laden",
        ),
        (Output("konfig-load-project", "disabled"), True, False),
    ],
)
def copy_landing_scenario(clicks, ids):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return (dash.no_update,) * 3
    name = str(trigger.get("name") or "")
    click_lookup = {
        str(item["name"]): count or 0
        for item, count in zip(ids or [], clicks or [])
    }
    if click_lookup.get(name, 0) <= 0:
        return (dash.no_update,) * 3
    try:
        result = duplicate_dg_scenario(name)
    except (DGConfigError, ValueError, FileNotFoundError, FileExistsError, OSError) as exc:
        return dash.no_update, dash.no_update, [html.Strong("Nicht dupliziert: "), str(exc)]
    return (
        result["scenario_name"],
        None,
        None,
    )


# Entfernt das ausgewählte Szenario nach der Löschaktion.
@dash.callback(
    Output("konfig-scenario-delete-pending", "data"),
    Output("konfig-scenario-select", "data", allow_duplicate=True),
    Output("konfig-scenario-edit", "data", allow_duplicate=True),
    Output("konfig-load-status", "children", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("demand-profile-store", "data", allow_duplicate=True),
    Output("optimization-result-store", "data", allow_duplicate=True),
    Input({"type": "konfig-delete-scenario", "name": ALL}, "n_clicks"),
    Input("konfig-delete-results", "n_clicks"),
    Input("konfig-delete-entire", "n_clicks"),
    State({"type": "konfig-delete-scenario", "name": ALL}, "id"),
    State("konfig-scenario-select", "data"),
    State("konfig-scenario-delete-pending", "data"),
    State("konfigurator-state-store", "data"),
    State("demand-profile-store", "data"),
    State("optimization-result-store", "data"),
    State("simulation-state-store", "data"),
    prevent_initial_call=True,
)
def delete_landing_scenario(
    clicks, results_clicks, entire_clicks, ids, selected, pending,
    config_state, demand_data, optimization_data, simulation_state,
):
    trigger = dash.ctx.triggered_id
    if isinstance(trigger, dict) and trigger.get("type") == "konfig-delete-scenario":
        name = str(trigger.get("name") or "")
        click_lookup = {
            str(item["name"]): count or 0
            for item, count in zip(ids or [], clicks or [])
        }
        if click_lookup.get(name, 0) > 0:
            return name, *((dash.no_update,) * 6)
        return (dash.no_update,) * 7
    if not isinstance(trigger, str) or trigger not in {
        "konfig-delete-results", "konfig-delete-entire",
    }:
        return (dash.no_update,) * 7
    if not pending or (
        trigger == "konfig-delete-results" and not results_clicks
    ) or (
        trigger == "konfig-delete-entire" and not entire_clicks
    ):
        return (dash.no_update,) * 7
    scope = "results" if trigger == "konfig-delete-results" else "entire"
    if (
        (simulation_state or {}).get("running")
        and (simulation_state or {}).get("scenario_name") == pending
    ):
        return (
            None, dash.no_update, dash.no_update,
            "Während der Optimierung kann das Szenario nicht gelöscht werden.",
            *((dash.no_update,) * 3),
        )
    try:
        if scope == "results":
            result = delete_dg_scenario_results(pending)
        else:
            result = delete_dg_scenario(pending)
    except (DGConfigError, ValueError, FileNotFoundError, OSError) as exc:
        return (
            None, dash.no_update, dash.no_update,
            [html.Strong("Nicht gelöscht: "), str(exc)],
            *((dash.no_update,) * 3),
        )
    updated_config = dash.no_update
    if (config_state or {}).get("source_scenario") == pending:
        updated_config = deepcopy(config_state)
        updated_config.update(had_results=False, results_stale=False)
        if scope == "entire":
            updated_config.update(source_scenario=None, loaded=False)
    updated_demands = (
        None if (demand_data or {}).get("scenario_name") == pending
        else dash.no_update
    )
    updated_optimization = (
        None if (optimization_data or {}).get("scenario_name") == pending
        else dash.no_update
    )
    if scope == "results":
        return (
            None, dash.no_update, dash.no_update,
            f"Ergebnisse von „{result['display_name']}“ wurden gelöscht.",
            updated_config, updated_demands, updated_optimization,
        )
    remaining = list_dg_scenarios()
    next_selected = (
        str(remaining[0]["name"])
        if selected == pending and remaining else
        None if selected == pending else
        selected
    )
    return (
        None, next_selected, None, f"„{result['display_name']}“ wurde gelöscht.",
        updated_config, updated_demands, updated_optimization,
    )


# Öffnet die Löschoptionen für das gewählte Szenario.
@dash.callback(
    Output("konfig-scenario-delete-options", "hidden"),
    Input("konfig-scenario-delete-pending", "data"),
)
def show_scenario_delete_options(pending):
    return not bool(pending)


# Schließt die Löschoptionen der Szenarioauswahl.
@dash.callback(
    Output("konfig-scenario-delete-pending", "data", allow_duplicate=True),
    Input("konfig-delete-dismiss", "n_clicks"),
    prevent_initial_call=True,
)
def dismiss_scenario_delete_options(clicks):
    return None if clicks else dash.no_update


# Übernimmt den geänderten Namen eines Szenarios.
@dash.callback(
    Output("konfig-scenario-select", "data", allow_duplicate=True),
    Output("konfig-scenario-edit", "data", allow_duplicate=True),
    Output("konfig-load-status", "children", allow_duplicate=True),
    Input({"type": "konfig-scenario-name-input", "name": ALL}, "n_blur"),
    Input({"type": "konfig-confirm-scenario-name", "name": ALL}, "n_clicks"),
    State({"type": "konfig-scenario-name-input", "name": ALL}, "value"),
    State({"type": "konfig-scenario-name-input", "name": ALL}, "id"),
    State({"type": "konfig-confirm-scenario-name", "name": ALL}, "id"),
    State("konfig-scenario-select", "data"),
    prevent_initial_call=True,
)
def rename_landing_scenario(blur_counts, confirm_clicks, values, input_ids, confirm_ids, selected):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict):
        return (dash.no_update,) * 3
    if trigger.get("type") == "konfig-scenario-name-input":
        event_counts, event_ids = blur_counts, input_ids
    elif trigger.get("type") == "konfig-confirm-scenario-name":
        event_counts, event_ids = confirm_clicks, confirm_ids
    else:
        return (dash.no_update,) * 3
    activated = {
        str(item["name"]): count or 0
        for item, count in zip(event_ids or [], event_counts or [])
    }
    old_name = str(trigger.get("name") or "")
    if activated.get(old_name, 0) <= 0:
        return (dash.no_update,) * 3
    value_by_name = {
        str(item["name"]): value
        for item, value in zip(input_ids or [], values or [])
    }
    new_name = str(value_by_name.get(old_name) or "").strip()
    try:
        result = rename_dg_scenario(old_name, new_name)
    except FileNotFoundError as exc:
        existing = {str(item["name"]) for item in list_dg_scenarios()}
        if old_name not in existing and new_name in existing:
            return (dash.no_update,) * 3
        return dash.no_update, dash.no_update, [html.Strong("Nicht umbenannt: "), str(exc)]
    except (DGConfigError, ValueError, FileExistsError, OSError) as exc:
        return dash.no_update, dash.no_update, [html.Strong("Nicht umbenannt: "), str(exc)]
    if not result["renamed"]:
        return (dash.no_update,) * 3
    status = f"„{result['old_name']}“ wurde in „{result['new_name']}“ umbenannt."
    if result.get("results_stale"):
        status += " Vorhandene Optimierungsergebnisse müssen neu berechnet werden."
    return (
        result["scenario_name"] if selected == old_name else selected,
        None,
        status,
    )


# Wendet dieselbe Abhängigkeitsregel auf die Standortoptionen an.
@dash.callback(
    Output("konfig-location-germany", "hidden"), Output("konfig-location-other", "hidden"),
    Input("konfig-location-mode", "value"),
)
def location_panels(mode):
    return (
        dependent_panel_hidden(mode, LOCATION_MODE_GERMANY),
        dependent_panel_hidden(mode, LOCATION_MODE_OTHER),
    )


# Aktualisiert die immer direkt editierbare Überschrift nach Fokusverlust.
def _editable_heading_result(editing: bool, value: Any, fallback: Any) -> tuple:
    name = str(value or "").strip() or str(fallback or "").strip() or "Unbenannt"
    return (
        {"display": "none"},
        {},
        name,
        False,
    )


# Öffnet die Szenarioüberschrift und schließt sie bei Enter oder Fokusverlust.
@dash.callback(
    Output("konfig-project-name-heading", "style"),
    Output("konfig-project-name-input", "style"),
    Output("konfig-project-name-heading", "children"),
    Output("konfig-project-name-editing", "data"),
    Input("konfig-project-name-heading", "n_clicks"),
    Input("konfig-project-name-input", "n_blur"),
    Input("konfig-project-name-input", "n_submit"),
    State("konfig-project-name-input", "value"),
    State("konfig-project-name-heading", "children"),
    State("konfig-project-name-editing", "data"),
    prevent_initial_call=True,
)
def edit_project_name(n_clicks, n_blur, n_submit, value, current_name, editing):
    trigger = dash.ctx.triggered_id
    if trigger == "konfig-project-name-heading":
        return _editable_heading_result(True, value, current_name)
    if trigger == "konfig-project-name-input":
        return _editable_heading_result(False, value, current_name)
    return _editable_heading_result(bool(editing), value, current_name)


# Steuert die editierbare Überschrift einer Gebäude-Einblendung.
@dash.callback(
    Output({"type": "konfig-building-heading", "uid": MATCH}, "style"),
    Output({"type": "konfig-building-name", "uid": MATCH}, "style"),
    Output({"type": "konfig-building-heading", "uid": MATCH}, "children"),
    Output({"type": "konfig-building-heading-editing", "uid": MATCH}, "data"),
    Input({"type": "konfig-building-heading", "uid": MATCH}, "n_clicks"),
    Input({"type": "konfig-building-name", "uid": MATCH}, "n_blur"),
    Input({"type": "konfig-building-name", "uid": MATCH}, "n_submit"),
    State({"type": "konfig-building-name", "uid": MATCH}, "value"),
    State({"type": "konfig-building-heading", "uid": MATCH}, "children"),
    State({"type": "konfig-building-heading-editing", "uid": MATCH}, "data"),
    prevent_initial_call=True,
)
def edit_building_name(n_clicks, n_blur, n_submit, value, current_name, editing):
    trigger = dash.ctx.triggered_id
    if isinstance(trigger, dict) and trigger.get("type") == "konfig-building-heading":
        return _editable_heading_result(True, value, current_name)
    if isinstance(trigger, dict) and trigger.get("type") == "konfig-building-name":
        name = str(value or "").strip() or str(current_name or "").strip() or "Unbenannt"
        return _editable_heading_result(False, name, current_name)
    return _editable_heading_result(bool(editing), value, current_name)


# Speichert den Namen getrennt vom MATCH-Callback der Überschrift.
@dash.callback(
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input({"type": "konfig-building-name", "uid": ALL}, "n_blur"),
    Input({"type": "konfig-building-name", "uid": ALL}, "n_submit"),
    State({"type": "konfig-building-name", "uid": ALL}, "value"),
    State({"type": "konfig-building-name", "uid": ALL}, "id"),
    State("building-scenario-store", "data"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def save_building_name(
    blur_counts, submit_counts, values, ids, building_data, config_state,
):
    trigger = dash.ctx.triggered_id
    if not isinstance(trigger, dict) or trigger.get("type") != "konfig-building-name":
        return dash.no_update, dash.no_update
    uid = int(trigger["uid"])
    value_by_uid = {
        int(component_id["uid"]): value
        for component_id, value in zip(ids or [], values or [])
        if isinstance(component_id, dict) and "uid" in component_id
    }
    current_row = building_by_uid(building_state(building_data), uid) or {}
    name = (
        str(value_by_uid.get(uid) or "").strip()
        or str(current_row.get("name") or "").strip()
        or "Unbenannt"
    )
    return _updated_building_heading(uid, name, building_data, config_state)


# Speichert die Gebäudeüberschrift gemeinsam mit dem UI-Zustandswechsel.
def _updated_building_heading(uid, name, building_data, config_state):
    updated = update_building_values(
        building_data,
        [{"type": "konfig-building-field", "uid": int(uid), "field": "name"}],
        [str(name)],
    )
    state = resolved_configurator_state(config_state)
    state["dirty"] = True
    return updated, state


# Aktualisiert die Standortvorschau aus den Projekteingaben.
@dash.callback(Output("konfig-site-preview", "children"), Input("konfig-location-zip", "value"))
def site_preview(postal_code):
    try:
        site = lookup_german_site(postal_code)
    except (ValueError, OSError) as exc:
        return str(exc)
    return f"{german_location_label(site)} · {site['latitude']:.4f}°, {site['longitude']:.4f}°"


# Zeigt im Parameterfenster dieselben Standortfelder wie beim Erstellen.
@dash.callback(
    Output("all-param-project-location-germany", "hidden"),
    Output("all-param-project-location-other", "hidden"),
    Output("all-param-project-site-preview", "children"),
    Input("all-param-project-location-mode", "value"),
    Input("all-param-project-location-zip", "value"),
)
def overview_location_panels(mode, postal_code):
    preview = site_preview(postal_code) if mode == LOCATION_MODE_GERMANY else ""
    return (
        dependent_panel_hidden(mode, LOCATION_MODE_GERMANY),
        dependent_panel_hidden(mode, LOCATION_MODE_OTHER),
        preview,
    )


# Öffnet die Standortbearbeitung aus der Projektübersicht.
@dash.callback(
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("weather-store", "data", allow_duplicate=True),
    Output("weather-upload-store", "data", allow_duplicate=True),
    Output("all-param-error", "children", allow_duplicate=True),
    Input("all-param-project-location-mode", "value"),
    Input("all-param-project-location-zip", "value"),
    Input("all-param-project-location-name", "value"),
    Input("all-param-project-weather-upload", "contents"),
    State("all-param-project-weather-upload", "filename"),
    State("heo-input-draft-store", "data"),
    State("konfigurator-state-store", "data"),
    State("weather-store", "data"),
    State("weather-upload-store", "data"),
    State("simulation-state-store", "data"),
    State({"type": "all-param-details", "key": ALL}, "open"),
    State({"type": "all-param-details", "key": ALL}, "id"),
    prevent_initial_call=True,
)
def edit_overview_project_location(
    mode, postal_code, location_name, contents, filename, heo, config,
    weather, weather_upload, simulation, opened, details,
):
    trigger = dash.ctx.triggered_id
    no_change = (dash.no_update,) * 6
    if (
        (config or {}).get("stage") != "parameters"
        or (simulation or {}).get("running")
        or mode not in {LOCATION_MODE_PIDULA, LOCATION_MODE_GERMANY, LOCATION_MODE_OTHER}
    ):
        return no_change
    state = deepcopy(heo or DEFAULT_HEO_INPUT_STATE)
    settings = resolved_configurator_state(config)
    values = state.setdefault("values", {})
    previous_mode = state.get("location_mode", LOCATION_MODE_PIDULA)
    next_weather, next_upload = weather, weather_upload
    issue = ""

    def set_german_site():
        nonlocal issue
        try:
            site = lookup_german_site(postal_code)
        except (ValueError, OSError) as exc:
            values["ZIP"] = str(postal_code or "").strip()
            values["LOCATION_NAME"] = f"Deutschland · PLZ {values['ZIP']}"
            issue = str(exc)
        else:
            values["ZIP"] = site["zip"]
            values["LOCATION_NAME"] = german_location_label(site)

    try:
        if trigger == "all-param-project-location-mode":
            if mode == previous_mode:
                return no_change
            state["location_mode"] = mode
            if mode == LOCATION_MODE_GERMANY:
                set_german_site()
                next_weather, next_upload = None, None
            elif mode == LOCATION_MODE_PIDULA:
                values["LOCATION_NAME"] = state.get("defaults", {}).get("LOCATION_NAME", "Pidula, Estland")
                values["WEATHER_FILE"] = state.get("defaults", {}).get("WEATHER_FILE")
                next_weather, next_upload = DEFAULT_WEATHER_DATA, None
            else:
                name = str(state.get("custom_location_name") or "").strip()
                state["custom_location_name"] = name
                values["LOCATION_NAME"] = name
                values["WEATHER_FILE"] = ""
                next_weather, next_upload = None, None
        elif trigger == "all-param-project-location-zip" and mode == LOCATION_MODE_GERMANY:
            state["location_mode"] = mode
            set_german_site()
            if previous_mode != mode:
                next_weather, next_upload = None, None
        elif trigger == "all-param-project-location-name" and mode == LOCATION_MODE_OTHER:
            state["location_mode"] = mode
            if previous_mode != mode:
                values["WEATHER_FILE"] = ""
                next_weather, next_upload = None, None
            name = str(location_name or "").strip()
            values["LOCATION_NAME"] = name
            state["custom_location_name"] = name
        elif trigger == "all-param-project-weather-upload" and mode == LOCATION_MODE_OTHER:
            if not contents:
                return no_change
            state["location_mode"] = mode
            uploaded_name = filename or "weather.epw"
            next_weather = parse_weather_upload(contents, uploaded_name)
            next_upload = {"contents": contents, "filename": uploaded_name}
            values["WEATHER_FILE"] = uploaded_name
        else:
            return no_change
        if state == heo and next_weather == weather and next_upload == weather_upload:
            return no_change
        remember_parameter_details(settings, details, opened)
        settings.update(dirty=True, results_stale=bool(settings.get("had_results")))
        return (
            state, heo_state_to_dg_state(state, weather_metadata=next_weather),
            settings, next_weather, next_upload, issue,
        )
    except (ValueError, TypeError, KeyError, OSError) as exc:
        return *((dash.no_update,) * 5), str(exc)


# Übernimmt bereitgestellte Wetterdaten in den Projektzustand.
@dash.callback(
    Output("weather-store", "data", allow_duplicate=True),
    Output("weather-upload-store", "data", allow_duplicate=True),
    Output("konfig-weather-upload-name", "children"),
    Input("konfig-weather-upload", "contents"), State("konfig-weather-upload", "filename"),
    prevent_initial_call=True,
)
def receive_weather(contents, filename):
    if not contents:
        return dash.no_update, dash.no_update, dash.no_update
    try:
        parsed = parse_weather_upload(contents, filename or "weather.epw")
    except (ValueError, TypeError) as exc:
        return dash.no_update, dash.no_update, f"Nicht geladen: {exc}"
    return parsed, {"contents": contents, "filename": filename}, f"Geladen: {filename}"


# Schließt die Erfassung der Projektdaten ab.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("heo-input-draft-store", "data", allow_duplicate=True),
    Output("dg-config-draft-store", "data", allow_duplicate=True),
    Output("building-scenario-store", "data", allow_duplicate=True),
    Output("weather-store", "data", allow_duplicate=True),
    Output("weather-upload-store", "data", allow_duplicate=True),
    Output("konfigurator-selection-store", "data", allow_duplicate=True),
    Output("konfig-project-error", "children"),
    Output("konfig-create-result-store", "data"),
    Input("konfig-project-next", "n_clicks"),
    State({"type": "konfig-field", "key": ALL}, "value"),
    State({"type": "konfig-field", "key": ALL}, "id"),
    State("konfig-project-name-input", "value"),
    State("konfig-location-mode", "value"), State("konfig-location-zip", "value"),
    State("konfig-location-name", "value"), State("heo-input-draft-store", "data"),
    State("weather-upload-store", "data"), State("weather-store", "data"),
    State("konfigurator-state-store", "data"), prevent_initial_call=True,
)
def finish_project_data(n_clicks, values, ids, scenario_name, mode, postal_code, location_name,
                        heo_state, weather_upload, weather, config_state):
    if not n_clicks:
        return (dash.no_update,) * 9
    error_result = {"status": "error", "clicks": n_clicks}
    # Das Formular startet immer ein wirklich neues Microgrid. So werden nach
    # der Rückkehr aus einem geladenen Szenario keine alten Komponenten oder
    # nicht sichtbaren Parameter in das neue Projekt übernommen.
    updated_heo = merge_visible_fields(
        clean_heo_state(DEFAULT_HEO_INPUT_STATE), ids, values
    )
    updated_heo.setdefault("values", {})["SCENARIO_NAME"] = str(
        scenario_name or ""
    ).strip()
    updated_heo["location_mode"] = mode or LOCATION_MODE_PIDULA
    updated_heo.setdefault("values", {})["ZIP"] = postal_code
    if mode == LOCATION_MODE_OTHER:
        updated_heo["values"]["LOCATION_NAME"] = str(location_name or "").strip()
        updated_heo["custom_location_name"] = str(location_name or "").strip()
    scenario = str(updated_heo["values"].get("SCENARIO_NAME") or "").strip()
    area = updated_heo["values"].get("DISTRICT_AREA_M2")
    if not scenario:
        return *((dash.no_update,) * 7), "Bitte einen Szenarionamen eingeben.", error_result
    try:
        validate_new_scenario_name(scenario)
    except ValueError as exc:
        return *((dash.no_update,) * 7), str(exc), error_result
    try:
        if float(area) <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return *((dash.no_update,) * 7), "Die Arealfläche muss größer als 0 m² sein.", error_result
    if mode == LOCATION_MODE_OTHER and (not location_name or not weather_upload):
        return (
            *((dash.no_update,) * 7),
            "Für einen sonstigen Standort werden Name und EPW-Datei benötigt.",
            error_result,
        )
    if mode == LOCATION_MODE_GERMANY:
        try:
            lookup_german_site(postal_code)
        except (ValueError, OSError) as exc:
            return *((dash.no_update,) * 7), str(exc), error_result
    updated_config = default_configurator_state()
    create_token = str(time.time_ns())
    updated_config.update(
        stage="topology", dirty=True, add_menu=None, selected=None,
        create_token=create_token,
    )
    effective_weather = DEFAULT_WEATHER_DATA if mode == LOCATION_MODE_PIDULA else weather
    effective_upload = weather_upload if mode == LOCATION_MODE_OTHER else None
    if mode == LOCATION_MODE_GERMANY:
        effective_weather = None
    return (
        updated_config,
        updated_heo,
        heo_state_to_dg_state(updated_heo, weather_metadata=effective_weather),
        empty_building_state(),
        effective_weather,
        effective_upload,
        None,
        "",
        {"status": "success", "clicks": n_clicks, "token": create_token},
    )


dash.clientside_callback(
    """
    function(clicks, result) {
        if (window.HEOCreateTransition) {
            window.HEOCreateTransition.update(clicks, result);
        }
        return {clicks: clicks || 0, result: result || null};
    }
    """,
    Output("konfig-create-ui-store", "data"),
    Input("konfig-project-next", "n_clicks"),
    Input("konfig-create-result-store", "data"),
    prevent_initial_call=True,
)
