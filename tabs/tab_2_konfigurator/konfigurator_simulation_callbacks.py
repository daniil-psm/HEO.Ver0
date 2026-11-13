# Prüft und speichert Eingaben und steuert die DG-Optimierung im Konfigurator.

from __future__ import annotations

import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import dash
from dash import Input, Output, State, html

from dg_adapter.input.config_service import DGConfigError
from dg_adapter.execution.dg_comparison_service import results_match_current
from dg_adapter.input.input_service import save_heo_scenario
from dg_adapter.execution.profile_service import (
    renew_random_profile_seed,
    validate_profile_seed_choice,
)
from dg_adapter.shared.dg_paths import scenario_dir_for_config
from dg_adapter.output import DGResultError
from dg_adapter.output.results_reader import load_complete_scenario_results
from dg_adapter.execution.dg_project_snapshot import build_topology_snapshot
from dg_adapter.execution.dg_simulation_service import (
    poll_scenario_simulation,
    start_scenario_simulation,
    stop_scenario_simulation,
)
from dg_adapter.input.validation import (
    validate_inputs,
)
from dg_adapter.input.parameter_catalog import DEFAULT_HEO_INPUT_STATE
from heo.model.buildings import building_state
from dg_adapter.input.parameter_catalog import fields_for_section
from .konfigurator_config import resolved_configurator_state

STOPPED_NOTICE_SECONDS = 5.0


COMPLETED_REDIRECT_SECONDS = 5.0








# Übersetzt die strukturierten Adapterfehler in die Meldungsliste der Oberfläche.
def configuration_validation_errors(heo_state, weather_upload, weather, buildings, config_state) -> list[str]:
    issues = validate_inputs(
        heo_state or DEFAULT_HEO_INPUT_STATE, buildings,
        weather_upload=weather_upload, weather_metadata=weather,
        config_state=resolved_configurator_state(config_state),
    )
    errors = [issue.message for issue in issues]
    resolved = resolved_configurator_state(config_state)
    try:
        validate_profile_seed_choice(
            resolved["profile_seed_mode"], resolved["profile_seed"],
        )
    except ValueError as exc:
        errors.append(str(exc))
    return list(dict.fromkeys(errors))


# Übergibt den HEO-Entwurf an den zentral prüfenden Builder und die Startskriptverwaltung.
def _persist(heo_state, weather_upload, weather, buildings, config_state):
    return save_heo_scenario(
        heo_state or DEFAULT_HEO_INPUT_STATE, list((buildings or {}).get("rows") or []),
        weather_upload=weather_upload, weather_metadata=weather,
        config_state=resolved_configurator_state(config_state),
    )


# Bindet Ergebnisindizes an die stabile Gebäudeidentität des Laufstarts.
def _topology_snapshot(buildings: dict | None) -> dict[str, Any]:
    return build_topology_snapshot(building_state(buildings))


# Ergänzt den Zustand um die aktuelle Gebäude-Topologie.
def with_topology_snapshot(
    optimization: dict | None,
    buildings: dict | None,
) -> dict | None:
    if optimization is None:
        return None
    if isinstance(optimization.get("topology_snapshot"), dict):
        return optimization
    return {
        **optimization,
        "topology_snapshot": _topology_snapshot(buildings),
    }


# Zeigt den Prüfbericht und verwirft ihn bei jeder Konfigurationsänderung.
@dash.callback(
    Output("konfig-validation-panel", "hidden"),
    Output("konfig-validation-result", "children"),
    Input("konfig-sidebar-validate", "n_clicks"),
    Input("heo-input-draft-store", "data"),
    Input("weather-upload-store", "data"),
    Input("weather-store", "data"),
    Input("building-scenario-store", "data"),
    Input("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def validate_configuration_action(
    n_clicks,
    heo,
    weather_upload,
    weather,
    buildings,
    config_state,
):
    if dash.ctx.triggered_id != "konfig-sidebar-validate" or not n_clicks:
        return True, None

    errors = configuration_validation_errors(
        heo,
        weather_upload,
        weather,
        buildings,
        config_state,
    )
    if not errors:
        return False, html.Div(
            "Konfiguration vollständig",
            className="konfig-validation-success",
        )
    return False, html.Div([
        html.Strong("Hinweise zur Konfiguration"),
        html.Ul([html.Li(message) for message in errors], className="konfig-validation-hints"),
    ])


# Speichert die geprüfte Konfiguration und zeigt das Ergebnis an.
@dash.callback(
    Output("konfig-action-status", "children"),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("optimization-result-store", "data", allow_duplicate=True),
    Input("konfig-sidebar-save", "n_clicks"),
    State("heo-input-draft-store", "data"), State("weather-upload-store", "data"),
    State("weather-store", "data"), State("building-scenario-store", "data"),
    State("konfigurator-state-store", "data"), prevent_initial_call=True,
)
def save_configuration(n_clicks, heo, weather_upload, weather, buildings, config_state):
    if not n_clicks:
        return (dash.no_update,) * 3
    state = resolved_configurator_state(config_state)
    try:
        config_result, building_result, run_result = _persist(
            heo, weather_upload, weather, buildings, state
        )
    except (DGConfigError, ValueError, TypeError, OSError) as exc:
        return [html.Strong("Nicht gespeichert: "), str(exc)], dash.no_update, dash.no_update
    changed = any((
        config_result["written"], building_result["written"], run_result["written"],
        config_result.get("profile_options_changed", False),
    ))
    stale = bool(changed and state.get("had_results"))
    state.update(
        dirty=False, source_scenario=config_result["scenario_name"], loaded=True,
        results_stale=stale,
    )
    message = f"„{config_result['scenario_name']}“ wurde gespeichert."
    if stale:
        message += " Die vorhandenen Ergebnisse gehören zur vorherigen Konfiguration; die Simulation muss neu gestartet werden."
    return message, state, None if stale else dash.no_update


# Übernimmt den gewählten Optimierungsfokus in den Zustand.
@dash.callback(
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Input("konfig-optimization-focus", "value"),
    State("konfigurator-state-store", "data"),
    prevent_initial_call=True,
)
def remember_optimization_focus(focus, config_state):
    if focus not in {"economic", "ecological", "comparison"}:
        return dash.no_update
    state = resolved_configurator_state(config_state)
    if state.get("optimization_focus", "comparison") == focus:
        return dash.no_update
    state["optimization_focus"] = focus
    return state


# Fragt den Laufstatus ab und übernimmt fertige Ergebnisse.
def _poll_simulation(state, simulation, objectives, buildings, details_open):
    requested = simulation.get("requested_objectives")
    if (
        isinstance(requested, (list, tuple))
        and requested
        and all(isinstance(item, str) and item in ("economic", "ecological") for item in requested)
        and len(set(requested)) == len(requested)
    ):
        objectives = tuple(requested)
    if state.get("stage") == "completed":
        now = time.time()
        if details_open:
            if simulation.get("details_closed_at") is not None:
                simulation = {**simulation, "details_closed_at": None}
                return "", dash.no_update, simulation, dash.no_update, dash.no_update, dash.no_update
            return (dash.no_update,) * 6
        try:
            details_closed_at = float(simulation["details_closed_at"])
        except (KeyError, TypeError, ValueError):
            simulation = {**simulation, "details_closed_at": now}
            return "", dash.no_update, simulation, dash.no_update, dash.no_update, dash.no_update
        if now - details_closed_at < COMPLETED_REDIRECT_SECONDS:
            return (dash.no_update,) * 6
        state["stage"] = "topology"
        request = {
            "tab": "dashboard-energiesystem",
            "view": "system",
            "nonce": time.time_ns(),
        }
        return "", state, dash.no_update, dash.no_update, dash.no_update, request
    if state.get("stage") == "stopped":
        try:
            stopped_at = float(simulation["stopped_at"])
        except (KeyError, TypeError, ValueError):
            stopped_at = 0.0
        if time.time() - stopped_at >= STOPPED_NOTICE_SECONDS:
            state["stage"] = "topology"
            return "", state, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        return "", dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    if not simulation.get("running") or simulation.get("origin") != "configurator":
        return (dash.no_update,) * 6
    try:
        polled = poll_scenario_simulation(simulation.get("scenario_name"))
    except (ValueError, OSError) as exc:
        failed = {
            **simulation,
            "running": False,
            "status": "failed",
            "phase": "Statusabfrage fehlgeschlagen",
            "error": f"Statusfehler: {exc}",
        }
        state["stage"] = "failed"
        return "", state, failed, dash.no_update, dash.no_update, dash.no_update
    polled["origin"] = "configurator"
    requested = polled.get("requested_objectives")
    if isinstance(requested, (list, tuple)) and requested:
        objectives = tuple(requested)
    else:
        polled["requested_objectives"] = list(objectives)
    if simulation.get("topology_snapshot"):
        polled["topology_snapshot"] = simulation["topology_snapshot"]
    if polled.get("running"):
        state["stage"] = "progress"
        # Fortschritt und Berechnungsschritt werden ausschließlich im
        # Main Panel dargestellt; die Seitenleiste bleibt aktionsbezogen.
        return "", state, polled, dash.no_update, dash.no_update, dash.no_update
    if polled.get("status") == "stopped":
        polled["stopped_at"] = time.time()
        state["stage"] = "stopped"
        return "", state, polled, dash.no_update, dash.no_update, dash.no_update
    if polled.get("status") != "completed":
        if polled.get("status") == "failed":
            state["stage"] = "failed"
            return "", state, polled, dash.no_update, dash.no_update, dash.no_update
        state["stage"] = "topology"
        return "", state, polled, dash.no_update, dash.no_update, dash.no_update
    try:
        package = load_complete_scenario_results(
            polled["scenario_name"], objectives=objectives,
        )
    except (DGResultError, ValueError, OSError) as exc:
        state["stage"] = "topology"
        return f"Simulation beendet, Ergebnisse unvollständig: {exc}", state, polled, dash.no_update, dash.no_update, dash.no_update
    completed_at = time.time()
    polled.update(
        phase="Optimierung abgeschlossen",
        completed_at=completed_at,
        details_closed_at=None if details_open else completed_at,
    )
    state.update(stage="completed", had_results=True, results_stale=False, dirty=False)
    state["optimization_focus"] = (
        objectives[0] if len(objectives) == 1 else "comparison"
    )
    optimization = {
        **package["optimization"],
        "topology_snapshot": polled.get("topology_snapshot")
        or _topology_snapshot(buildings),
    }
    return "Optimierung abgeschlossen. Ergebnisse wurden geladen.", state, polled, package["demands"], optimization, dash.no_update


# Stoppt den laufenden Optimierungsauftrag.
def _stop_simulation(state, simulation):
    try:
        stopped = stop_scenario_simulation(simulation.get("scenario_name"))
    except (ValueError, OSError) as exc:
        return f"Simulation konnte nicht gestoppt werden: {exc}", dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    stopped.update(
        origin="configurator",
        running=False,
        status="stopped",
        stopped_at=time.time(),
    )
    state["stage"] = "stopped"
    return "", state, stopped, dash.no_update, dash.no_update, dash.no_update


# Öffnet oder schließt die Einstellungsansicht.
def _toggle_simulation_settings(state, simulation):
    if simulation.get("origin") == "configurator" and simulation.get("status") == "failed":
        state["stage"] = "landing" if state.get("stage") == "landing" else "topology"
        state["simulation_mode"] = None
        return "", state, {
            "status": "idle", "running": False, "scenario_name": None,
            "progress": 0, "phase": "Bereit", "log": "",
        }, dash.no_update, dash.no_update, dash.no_update
    if state.get("simulation_mode") in {"choose", "standard", "custom"} and state.get("stage") == "topology":
        state["simulation_mode"] = None
    else:
        state.update(simulation_mode="choose", stage="topology")
    return (
        "", state, dash.no_update,
        dash.no_update, dash.no_update, dash.no_update,
    )


# Übernimmt die Auswahl zwischen Standard- und eigenen Einstellungen.
def _choose_simulation_settings(state, settings_mode):
    if settings_mode not in {"standard", "custom"} or state.get("simulation_mode") not in {"choose", "standard", "custom"}:
        return (dash.no_update,) * 6
    if state.get("simulation_mode") == settings_mode:
        return (dash.no_update,) * 6
    state["simulation_mode"] = settings_mode
    return "", state, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# Speichert den Entwurf, verwendet passende Ergebnisse oder startet den DG-Lauf.
def _start_simulation(state, settings_mode, focus, objectives, heo, weather_upload, weather, buildings):
    state.update(simulation_mode=settings_mode, stage="topology", optimization_focus=focus)
    if settings_mode == "standard":
        heo = deepcopy(heo or DEFAULT_HEO_INPUT_STATE)
        values = heo.setdefault("values", {})
        defaults = heo.setdefault("defaults", {})
        for section_key in ("time", "pyomo"):
            for field in fields_for_section(section_key):
                key = field.get("input_key") or field["env_key"]
                values[key] = deepcopy(defaults.get(key, field.get("default")))
        state.update(profile_seed_mode="fixed", profile_seed=20261013)
    try:
        config_result, building_result, run_result = _persist(
            heo, weather_upload, weather, buildings, state
        )
    except (DGConfigError, ValueError, TypeError, OSError) as exc:
        return [html.Strong("Simulation nicht gestartet: "), str(exc)], dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    scenario_name = config_result["scenario_name"]
    seed_regenerated = False
    if state.get("profile_seed_mode") == "random":
        try:
            state["profile_seed"] = renew_random_profile_seed(
                scenario_dir_for_config(Path(config_result["config_path"])),
            )
        except (ValueError, OSError) as exc:
            return [html.Strong("Simulation nicht gestartet: "), str(exc)], dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        seed_regenerated = True
    changed = any((
        config_result["written"], building_result["written"], run_result["written"],
        config_result.get("profile_options_changed", False), seed_regenerated,
    ))
    if (not changed and not state.get("results_stale")
            and results_match_current(
                scenario_dir_for_config(Path(config_result["config_path"])), objectives,
            )):
        try:
            package = load_complete_scenario_results(scenario_name, objectives=objectives)
        except DGResultError:
            package = None
        if package is not None:
            completed = {
                "scenario_name": scenario_name, "status": "completed", "running": False,
                "progress": 100, "phase": "Vorhandene Ergebnisse geladen", "log": "",
                "origin": "configurator",
            }
            state.update(stage="topology", simulation_mode=None, had_results=True, results_stale=False)
            request = {"tab": "dashboard-energiesystem", "view": "system", "nonce": time.time_ns()}
            optimization = with_topology_snapshot(
                package["optimization"], buildings,
            )
            return "Vorhandene Ergebnisse wurden geladen.", state, completed, package["demands"], optimization, request
    try:
        started = start_scenario_simulation(scenario_name, objectives=objectives)
    except (ValueError, OSError) as exc:
        return f"Simulation nicht gestartet: {exc}", dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    started["origin"] = "configurator"
    started["topology_snapshot"] = _topology_snapshot(buildings)
    state.update(stage="progress", simulation_mode=None, results_stale=False)
    return f"Simulation „{scenario_name}“ wurde gestartet.", state, started, dash.no_update, None, dash.no_update


# Verteilt Simulationsereignisse auf Start, Statusabfrage, Stopp und Einstellungen.
@dash.callback(
    Output("konfig-action-status", "children", allow_duplicate=True),
    Output("konfigurator-state-store", "data", allow_duplicate=True),
    Output("simulation-state-store", "data", allow_duplicate=True),
    Output("demand-profile-store", "data", allow_duplicate=True),
    Output("optimization-result-store", "data", allow_duplicate=True),
    Output("navigation-request-store", "data", allow_duplicate=True),
    Input("konfig-sidebar-simulate", "n_clicks"),
    Input("konfig-simulation-settings-mode", "value"),
    Input("konfig-simulation-start", "n_clicks"),
    Input("konfig-simulation-interval", "n_intervals"),
    State("heo-input-draft-store", "data"), State("weather-upload-store", "data"),
    State("weather-store", "data"), State("building-scenario-store", "data"),
    State("konfigurator-state-store", "data"), State("simulation-state-store", "data"),
    State("konfig-progress-details-open-store", "data"),
    State("konfig-optimization-focus", "value"),
    prevent_initial_call=True,
)
def simulation_action(_sim_clicks, settings_mode, start_clicks, _interval, heo, weather_upload, weather,
                      buildings, config_state, simulation_state, details_open=False, focus=None):
    trigger = dash.ctx.triggered_id
    state = resolved_configurator_state(config_state)
    simulation = simulation_state or {}
    focus = focus if focus in {"economic", "ecological", "comparison"} else state.get("optimization_focus", "comparison")
    objectives = ("economic", "ecological") if focus == "comparison" else (focus,)

    if trigger == "konfig-simulation-interval":
        return _poll_simulation(state, simulation, objectives, buildings, details_open)

    if simulation.get("running") and simulation.get("origin") == "configurator":
        return _stop_simulation(state, simulation)

    if trigger == "konfig-sidebar-simulate":
        return _toggle_simulation_settings(state, simulation)

    if trigger == "konfig-simulation-settings-mode":
        return _choose_simulation_settings(state, settings_mode)

    if trigger != "konfig-simulation-start" or not start_clicks or settings_mode not in {"standard", "custom"}:
        return (dash.no_update,) * 6
    if state.get("simulation_mode") not in {"choose", "standard", "custom"} or state.get("stage") != "topology":
        return (dash.no_update,) * 6

    return _start_simulation(state, settings_mode, focus, objectives, heo, weather_upload, weather, buildings)
