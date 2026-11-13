"""Callbacks des Energiesystem-Tabs."""

from __future__ import annotations

import os
from urllib.parse import quote

import dash
from dash import ALL, Input, Output, State, html
from dash.exceptions import PreventUpdate

from dg_adapter.output import DGResultError
from dg_adapter.output.certificates import certificate_page_count, certificate_result_path
from dg_adapter.output.demand_profiles import demand_result_error_store, load_demand_results
from dg_adapter.output.results_reader import (
    comparison_variant_results_path, load_comparison_manifest,
    load_complete_comparison_results, load_complete_scenario_results,
    scenario_results_path,
)
from dg_adapter.shared.comparison_contract import DGComparisonError
from ui.components.sidebar import sidebar_nav_button_class
from dg_adapter.output.scenes import build_result_scene
from heo.topology.scene_storage import pack_pfc_scene, unpack_pfc_scene
from heo.model.result_selection import configured_scenario_name, comparison_is_available, system_objective

from .energiesystem_bedarfe import thermal_energy_figure_from_store
from dg_adapter.output.project_info import project_info_context
from ui.components.project_info import project_info_view
from .energiesystem_umgebung import ENVIRONMENT_SERIES_OPTIONS, environment_figure
from .energiesystem_layout import ENERGY_VIEWS, energy_info_page
from dg_adapter.output.pfc_results import (
    build_pfc_frame,
    cluster_options,
    pfc_timeline_marks,
    prepare_pfc_series,
    resolve_cluster_key,
)
from dg_adapter.output.sankey_results import topology_with_annual_edge_values
from .energiesystem_topologie import energy_topology_component
from .energiesystem_vergleich import (
    comparison_figure,
    objective_heading,
    variant_kpi_cards,
)


# Hält die zentrale Dashboard-Rückseite synchron zur Ergebnisansicht.
@dash.callback(
    Output("energy-dashboard-info-content", "children"),
    Input("energy-view-store", "data"),
    Input("optimization-result-store", "data"),
)
def update_energy_info(view: str, optimization_data: dict | None):
    return energy_info_page(
        view if view in ENERGY_VIEWS else "project", optimization_data
    )


# Schaltet die automatische Wiedergabe der Ergebniszeitschritte um.
def toggle_energy_play(
    n_clicks: int,
    is_playing: bool,
) -> tuple[bool, str, str]:
    new_state = not bool(is_playing)

    return (
        new_state,
        "⏸  Pause" if new_state else "▶  Play",
        "energy-play-button" if new_state else "energy-play-button energy-play-button-paused",
    )


# Leitet Zeitposition und Wiedergabe aus genau einem UI-Ereignis ab.
def resolve_pfc_control_event(
    triggered_id: object,
    *,
    n_intervals: int,
    is_playing: bool,
    slider_drag_value: int | float | None,
    slider_value: int | float | None,
    stored_step: int | float | None = None,
) -> tuple[int, bool, bool | None]:
    playing = bool(is_playing)
    current_step = slider_value if stored_step is None else stored_step
    tick = max(0, int(current_step or 0))
    changed_play_state: bool | None = None

    if triggered_id == "energy-pfc-time-slider":
        requested_tick = max(0, int(slider_drag_value or 0))
        # Dash synchronisiert eine programmgesteuert gesetzte Slider-Position
        # ebenfalls nach ``drag_value``. Nur eine tatsächlich neue Position ist
        # daher ein manueller Eingriff und darf die Wiedergabe pausieren.
        if requested_tick != tick:
            tick = requested_tick
            playing = False
            changed_play_state = False
    elif triggered_id == "energy-play-button":
        playing = not playing
        changed_play_state = playing
    elif triggered_id in {"energy-cluster-store", "energy-pfc-prepared-store"}:
        tick = 0
    elif triggered_id == "energy-ticker" and playing:
        tick += 1
    elif triggered_id is None:
        tick = max(0, int(n_intervals or 0))

    return tick, playing, changed_play_state


# Bereitet die statische Szene und Zeitreihen eines Ergebnisses vor.
def prepare_energy_pfc(
    optimization_data: dict | None,
    building_state: dict | None,
):
    scene = build_result_scene(
        optimization_data, building_state,
        include_buildings=True, center_parallel_ports=False,
    )
    series = prepare_pfc_series(optimization_data, scene.topology)
    return {"scene": pack_pfc_scene(scene), "series": series}


# Aktualisiert die Ergebnisansicht für Zeitraum und Optimierungsziel.
@dash.callback(
    Output("energy-pfc-frame", "children"),
    Output("energy-pfc-time-slider", "max"),
    Output("energy-pfc-time-slider", "value"),
    Output("energy-pfc-step-store", "data"),
    Output("energy-pfc-time-slider", "marks"),
    Output("energy-pfc-time-slider", "disabled"),
    Output("energy-pfc-time-label", "children"),
    Output("energy-pfc-step-label", "children"),
    Output("energy-play-store", "data"),
    Output("energy-play-button", "children"),
    Output("energy-play-button", "className"),
    Output("energy-pfc-step-count-store", "data"),
    Input("energy-pfc-prepared-store", "data"),
    Input("energy-cluster-store", "data"),
    Input("energy-ticker", "n_intervals"),
    Input("energy-play-store", "data"),
    Input("energy-play-button", "n_clicks"),
    Input("energy-pfc-time-slider", "drag_value"),
    State("energy-pfc-time-slider", "value"),
    State("energy-pfc-step-store", "data"),
    State("energy-pfc-step-count-store", "data"),
)
def update_energy_dashboard(
    prepared: dict | None,
    cluster_key: str | None,
    n_intervals: int,
    is_playing: bool,
    _play_clicks: int = 0,
    slider_drag_value: int | float | None = None,
    slider_value: int | float | None = 0,
    stored_step: int | float | None = None,
    previous_step_count: int | None = 0,
):
    if not prepared:
        raise PreventUpdate
    try:
        triggered = dash.ctx.triggered_id
    except dash.exceptions.MissingCallbackContextException:
        triggered = None
    try:
        changed_inputs = dash.ctx.triggered_prop_ids
    except (dash.exceptions.MissingCallbackContextException, AttributeError):
        changed_inputs = {}
    if "energy-pfc-prepared-store.data" in changed_inputs:
        triggered = "energy-pfc-prepared-store"
    elif "energy-cluster-store.data" in changed_inputs:
        triggered = "energy-cluster-store"

    tick, is_playing, changed_play_state = resolve_pfc_control_event(
        triggered,
        n_intervals=n_intervals,
        is_playing=is_playing,
        slider_drag_value=slider_drag_value,
        slider_value=slider_value,
        stored_step=stored_step,
    )
    play_store_value = (
        dash.no_update if changed_play_state is None else changed_play_state
    )

    button_text = "⏸  Pause" if is_playing else "▶  Play"
    button_class = (
        "energy-play-button konfig-secondary-button"
        if is_playing
        else (
            "energy-play-button konfig-secondary-button "
            "energy-play-button-paused"
        )
    )

    # Wert-Synchronisierung des Sliders und der Play-Store lösen weitere
    # Callback-Ereignisse aus, ohne den dargestellten Zeitschritt zu ändern.
    if (
        triggered == "energy-pfc-time-slider"
        and changed_play_state is None
        and tick == int(stored_step or 0)
        and bool(previous_step_count)
    ) or (triggered == "energy-ticker" and not is_playing):
        raise PreventUpdate
    if triggered in {"energy-play-button", "energy-play-store"} and previous_step_count:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            play_store_value,
            button_text,
            button_class,
            dash.no_update,
        )

    topology_base, geometry = unpack_pfc_scene(prepared["scene"])
    topology, pfc_frame = build_pfc_frame(
        None,
        topology_base,
        selected_key=cluster_key,
        tick=tick,
        prepared=prepared["series"],
    )
    component = energy_topology_component(
        view="pfc",
        topology=topology,
        scene_geometry=geometry,
        instance_id="energy-pfc",
        pfc_frame=pfc_frame,
    )

    slider_max = max(0, pfc_frame.step_count - 1)
    slider_disabled = pfc_frame.step_count <= 1
    step_label = (
        f"Zeitschritt {pfc_frame.step_index + 1} / {pfc_frame.step_count}"
        if pfc_frame.step_count > 0
        else "Zeitschritt 0 / 0"
    )

    return (
        component,
        slider_max,
        pfc_frame.step_index,
        pfc_frame.step_index,
        pfc_timeline_marks(pfc_frame.step_count, pfc_frame.step_hours),
        slider_disabled,
        pfc_frame.title,
        step_label,
        play_store_value,
        button_text,
        button_class,
        pfc_frame.step_count,
    )


# Bereitet das Energieflussdiagramm für die aktuelle Auswahl vor.
@dash.callback(
    Output("energy-sankey-frame", "children"),
    Input("optimization-result-store", "data"),
    Input("dg-config-draft-store", "data"),
    Input("building-scenario-store", "data"),
)
def prepare_energy_sankey(optimization_data, config_state, building_state):
    scene = build_result_scene(
        optimization_data, building_state,
        include_buildings=False, center_parallel_ports=False,
    )
    topology = topology_with_annual_edge_values(optimization_data, scene.topology)
    return energy_topology_component(
        view="sankey",
        topology=topology,
        scene_geometry=scene.geometry,
        instance_id="energy-sankey",
        config_state=config_state,
        optimization_data=optimization_data,
    )


# Wählt die sichtbare Topologieansicht aus.
@dash.callback(
    Output("energy-ticker", "disabled"),
    Output("energy-cluster-panel", "style"),
    Output("energy-sankey-frame", "style"),
    Output("energy-pfc-frame", "style"),
    Input("energy-view-store", "data"),
    Input("energy-play-store", "data"),
    Input("energy-pfc-step-count-store", "data"),
)
def show_energy_topology_view(view, is_playing, step_count):
    return (
        view != "pfc" or not bool(is_playing) or not bool(step_count),
        {"display": "flex" if view == "pfc" else "none"},
        {"display": "block" if view == "sankey" else "none"},
        {"display": "block" if view == "pfc" else "none"},
    )


# Schaltet zwischen den Bereichen des Ergebnisdashboards um.
@dash.callback(
    Output("energy-view-store", "data", allow_duplicate=True),
    Output("energy-view-project", "className"),
    Output("energy-view-environment", "className"),
    Output("energy-view-demands", "className"),
    Output("energy-view-system", "className"),
    Output("energy-view-sankey", "className"),
    Output("energy-view-pfc", "className"),
    Output("energy-open-dg-results", "className"),
    Output("energy-project-view", "style"),
    Output("energy-environment-view", "style"),
    Output("energy-demands-view", "style"),
    Output("energy-certificate-view", "style"),
    Output("energy-system-view", "style"),
    Output("energy-svg-frame", "style"),
    Output("energy-objective-panel", "style"),
    Input("energy-view-project", "n_clicks"),
    Input("energy-view-environment", "n_clicks"),
    Input("energy-view-demands", "n_clicks"),
    Input("energy-view-system", "n_clicks"),
    Input("energy-view-sankey", "n_clicks"),
    Input("energy-view-pfc", "n_clicks"),
    Input("energy-open-dg-results", "n_clicks"),
    Input("energy-objective-comparison", "n_clicks"),
    State("energy-view-store", "data"),
    State("energy-objective-availability-store", "data"),
    prevent_initial_call=True,
)
def switch_energy_view(
    project_clicks: int,
    environment_clicks: int,
    demands_clicks: int,
    system_clicks: int,
    sankey_clicks: int,
    pfc_clicks: int,
    results_clicks: int,
    comparison_clicks: int = 0,
    _current_view: str | None = None,
    comparison: dict | None = None,
) -> tuple:
    clicked_views = {
        "energy-view-project": (project_clicks, "project"),
        "energy-view-environment": (environment_clicks, "environment"),
        "energy-view-demands": (demands_clicks, "demands"),
        "energy-view-system": (system_clicks, "system"),
        "energy-view-sankey": (sankey_clicks, "sankey"),
        "energy-view-pfc": (pfc_clicks, "pfc"),
        "energy-open-dg-results": (results_clicks, "certificate"),
        "energy-objective-comparison": (
            comparison_clicks,
            "system" if _current_view == "system" else "certificate",
        ),
    }
    clicks, requested_view = clicked_views.get(dash.ctx.triggered_id, (0, None))
    # Beim Einfügen des Ergebnis-Tabs können die neuen Buttons mit n_clicks=0
    # als Auslöser gemeldet werden. Die bereits gerenderte Zielansicht behalten.
    if not clicks:
        raise PreventUpdate
    if dash.ctx.triggered_id == "energy-objective-comparison":
        if not comparison_is_available(comparison) or _current_view == "system":
            raise PreventUpdate
    view = requested_view

    base = sidebar_nav_button_class()
    active = sidebar_nav_button_class(active=True)

    def button_class(button_view: str) -> str:
        return active if view == button_view else base

    def content_style(content_view: str, display: str = "block") -> dict[str, str]:
        return {"display": display if view == content_view else "none"}

    return (
        view,
        button_class("project"),
        button_class("environment"),
        button_class("demands"),
        button_class("system"),
        button_class("sankey"),
        button_class("pfc"),
        button_class("certificate"),
        content_style("project"),
        content_style("environment", "grid"),
        content_style("demands", "grid"),
        content_style("certificate", "flex"),
        content_style("system", "grid"),
        {"display": "block" if view in {"sankey", "pfc"} else "none"},
        {
            "display": "none"
            if view in {"project", "environment", "demands"}
            else "flex"
        },
    )


# Aktiviert die verfügbaren Optimierungsziele anhand der Ergebnisse.
@dash.callback(
    Output("energy-objective-availability-store", "data"),
    Output("energy-objective-economic", "disabled"),
    Output("energy-objective-ecological", "disabled"),
    Output("energy-objective-comparison", "disabled"),
    Input("energy-comparison-store", "data"),
)
def set_energy_objective_availability(comparison):
    comparison = comparison or {}
    variants = comparison.get("variants") or {}
    ready = comparison.get("status") == "ready"
    availability = {
        "status": comparison.get("status"),
        "variants": {key: True for key in ("economic", "ecological") if key in variants},
        "manifest": {
            "comparison_complete": (comparison.get("manifest") or {}).get(
                "comparison_complete"
            )
        },
    }
    return (
        availability,
        not (ready and "economic" in variants),
        not (ready and "ecological" in variants),
        not comparison_is_available(comparison),
    )


# Wählt eine Ergebnisvariante für die aktuelle Ergebnisansicht.
@dash.callback(
    Output("energy-objective-store", "data"),
    Output("energy-objective-economic", "className"),
    Output("energy-objective-ecological", "className"),
    Output("energy-objective-comparison", "className"),
    Input("energy-objective-economic", "n_clicks"),
    Input("energy-objective-ecological", "n_clicks"),
    Input("energy-objective-comparison", "n_clicks"),
    Input("energy-objective-availability-store", "data"),
    Input("energy-view-store", "data"),
    State("energy-objective-store", "data"),
    prevent_initial_call=True,
)
def select_energy_objective(
    _economic_clicks,
    _ecological_clicks,
    _comparison_clicks,
    comparison,
    view,
    current_objective,
):
    objective = (
        current_objective
        if current_objective in {"economic", "ecological", "comparison"}
        else "economic"
    )
    if dash.ctx.triggered_id == "energy-objective-economic":
        objective = "economic"
    elif dash.ctx.triggered_id == "energy-objective-ecological":
        objective = "ecological"
    elif dash.ctx.triggered_id == "energy-objective-comparison":
        objective = "comparison"
    elif (
        dash.ctx.triggered_id in {"energy-objective-availability-store", "energy-view-store"}
        and view == "system"
    ):
        objective = "comparison"
    elif (
        dash.ctx.triggered_id == "energy-view-store"
        and view not in {"certificate", "system"}
        and objective == "comparison"
    ):
        objective = "economic"

    variants = (comparison or {}).get("variants") or {}
    if variants:
        objective = system_objective(
            objective,
            variants,
            comparison_available=comparison_is_available(comparison),
        )
    return (
        objective,
        sidebar_nav_button_class(active=objective == "economic"),
        sidebar_nav_button_class(active=objective == "ecological"),
        sidebar_nav_button_class(active=objective == "comparison"),
    )


dash.clientside_callback(
    """function(objective, comparison, current) {
        if (!comparison || comparison.status !== "ready") {
            return window.dash_clientside.no_update;
        }
        const variants = comparison.variants || {};
        const focus = objective === "comparison" ? "economic" : objective;
        const selected = variants[focus] || variants.economic || variants.ecological;
        if (!selected) return window.dash_clientside.no_update;
        if (current && selected.comparison_run_id
            && current.comparison_run_id === selected.comparison_run_id
            && current.objective === selected.objective
            && current.profile_hash === selected.profile_hash) {
            return window.dash_clientside.no_update;
        }
        return selected;
    }""",
    Output("optimization-result-store", "data", allow_duplicate=True),
    Input("energy-objective-store", "data"),
    Input("energy-comparison-store", "data"),
    State("optimization-result-store", "data"),
    prevent_initial_call=True,
)


# Lädt Varianten und gemeinsame Profile einmal pro Tab-/Szenariowechsel.
@dash.callback(
    Output("energy-comparison-store", "data"),
    Output("demand-profile-store", "data"),
    Input("active-main-tab-store", "data"),
    Input("dg-config-draft-store", "data"),
)
def update_energy_comparison_store(active_tab, config_state):
    if active_tab != "dashboard-energiesystem":
        return dash.no_update, dash.no_update
    scenario_name = configured_scenario_name(config_state)
    if not scenario_name:
        comparison = {
            "status": "missing",
            "scenario_name": "",
            "message": "Bitte zuerst ein Szenario auswählen oder speichern.",
            "variants": {},
        }
        return comparison, demand_result_error_store(
            scenario_name, DGResultError(comparison["message"])
        )
    try:
        try:
            latest = load_comparison_manifest(scenario_name)
        except DGComparisonError:
            latest = None
        requested = (
            tuple(latest.get("requested_objectives") or ())
            if latest and latest.get("status") == "completed"
            else None
        )
        package = (
            load_complete_scenario_results(scenario_name)
            if latest and latest.get("comparison_complete") is False
            else load_complete_comparison_results(scenario_name, objectives=requested)
            if requested
            else load_complete_comparison_results(scenario_name)
        )
        return package["comparison"], package["demands"]
    except (DGResultError, ValueError, OSError) as exc:
        comparison = {
            "status": "missing",
            "scenario_name": scenario_name,
            "message": str(exc),
            "variants": {},
        }
    # Bestehende Einzellauf-Profile bleiben ohne Vergleichspaket verfügbar.
    try:
        demands = load_demand_results(scenario_name)
    except (DGResultError, ValueError, OSError) as exc:
        demands = demand_result_error_store(scenario_name, exc)
    return comparison, demands


# Rendert die Topologie für den Systemvergleich.
def _comparison_topology_component(
    optimization_data: dict | None,
    config_state: dict | None,
    building_state: dict | None,
    *,
    instance_id: str,
):
    scene = build_result_scene(
        optimization_data, building_state, center_parallel_ports=True,
    )
    return energy_topology_component(
        view="system",
        topology=scene.topology,
        scene_geometry=scene.geometry,
        instance_id=instance_id,
        config_state=config_state,
        optimization_data=optimization_data,
    )


# Bereitet alle vorhandenen Fokusse einmal vor, auch wenn sie ausgeblendet sind.
@dash.callback(
    Output("energy-comparison-graph", "figure"),
    Output("energy-comparison-message", "children"),
    Output("energy-comparison-message", "style"),
    Output("energy-economic-heading", "children"),
    Output("energy-ecological-heading", "children"),
    Output("energy-economic-topology", "children"),
    Output("energy-ecological-topology", "children"),
    Output("energy-economic-kpis", "children"),
    Output("energy-ecological-kpis", "children"),
    Input("energy-comparison-store", "data"),
    Input("dg-config-draft-store", "data"),
    Input("building-scenario-store", "data"),
)
def prepare_energy_comparison_view(comparison, config_state, building_state):
    comparison = comparison or {}
    scenario_name = str(
        comparison.get("scenario_name")
        or configured_scenario_name(config_state)
        or "Szenario"
    )
    variants = comparison.get("variants") or {}
    economic = variants.get("economic")
    ecological = variants.get("ecological")
    ready = comparison.get("status") == "ready" and bool(variants)
    message = "" if ready else str(
        comparison.get("message")
        or "Noch kein abgeschlossener Optimierungslauf vorhanden."
    )
    return (
        comparison_figure(comparison)
        if comparison_is_available(comparison) or not ready
        else dash.no_update,
        message,
        {"display": "none" if not message else "block"},
        objective_heading(scenario_name, "economic"),
        objective_heading(scenario_name, "ecological"),
        _comparison_topology_component(
            economic,
            config_state,
            building_state,
            instance_id="comparison-economic",
        )
        if ready and economic
        else [],
        _comparison_topology_component(
            ecological,
            config_state,
            building_state,
            instance_id="comparison-ecological",
        )
        if ready and ecological
        else [],
        variant_kpi_cards(economic) if ready and economic else [],
        variant_kpi_cards(ecological) if ready and ecological else [],
    )


# Schaltet zwischen vorbereiteten Ansichten ohne erneutes Topologie-Rendering.
@dash.callback(
    Output("energy-system-view", "className"),
    Output("energy-comparison-chart-column", "style"),
    Output("energy-economic-column", "style"),
    Output("energy-ecological-column", "style"),
    Input("energy-objective-availability-store", "data"),
    Input("energy-objective-store", "data"),
)
def show_energy_objective(comparison, objective):
    comparison = comparison or {}
    variants = comparison.get("variants") or {}
    ready = comparison.get("status") == "ready" and bool(variants)
    selected = (
        system_objective(
            objective,
            variants,
            comparison_available=comparison_is_available(comparison),
        )
        if ready else "comparison"
    )
    is_comparison = selected == "comparison"
    return (
        "energy-comparison-view energy-content-view"
        + ("" if is_comparison else " is-single"),
        {"display": "flex" if is_comparison else "none"},
        {"display": "flex" if ready and selected in {"economic", "comparison"} else "none"},
        {"display": "flex" if ready and selected in {"ecological", "comparison"} else "none"},
    )


# Passt die Ausweisanzeige an die verfügbaren Vergleichsergebnisse an.
@dash.callback(
    Output("energy-certificate-pages", "className"),
    Input("energy-objective-store", "data"),
)
def set_certificate_comparison_layout(objective):
    return (
        "energy-certificate-pages is-comparison"
        if objective == "comparison"
        else "energy-certificate-pages"
    )


# Erstellt das Ausweisdokument für das ausgewählte Ergebnis.
def _certificate_document(scenario_name, objective):
    if not scenario_name:
        return {"error": "Bitte zuerst ein Szenario auswählen oder speichern."}
    try:
        certificate = certificate_result_path(scenario_name, objective)
        pages = certificate_page_count(scenario_name, objective)
    except (DGResultError, ValueError, OSError) as exc:
        return {"error": str(exc)}
    return {
        "scenario": scenario_name,
        "objective": objective,
        "pages": pages,
        "version": certificate.stat().st_mtime_ns,
    }


# Lädt die Metadaten des aktuellen Quartiersenergieausweises.
@dash.callback(
    Output("energy-certificate-document-store", "data"),
    Input("energy-view-store", "data"),
    Input("energy-open-dg-results", "n_clicks"),
    Input("energy-objective-store", "data"),
    State("dg-config-draft-store", "data"),
)
def update_energy_certificate(
    view,
    _results_clicks,
    objective,
    config_state,
):
    objective = str(objective or "economic").strip().lower()
    if objective == "comparison":
        objective = "economic"

    if view != "certificate":
        return dash.no_update

    return _certificate_document(configured_scenario_name(config_state), objective)


# Aktualisiert den ökologischen Energieausweis.
@dash.callback(
    Output("energy-certificate-ecological-document-store", "data"),
    Input("energy-view-store", "data"),
    Input("energy-open-dg-results", "n_clicks"),
    Input("energy-objective-store", "data"),
    State("dg-config-draft-store", "data"),
)
def update_ecological_certificate(view, _results_clicks, objective, config_state):
    if view != "certificate" or objective != "comparison":
        return dash.no_update
    return _certificate_document(configured_scenario_name(config_state), "ecological")


# Hält Dokument und Seite zusammen und verarbeitet auch schnelle Klickfolgen.
@dash.callback(
    Output("energy-certificate-page-store", "data"),
    Input("energy-certificate-previous", "n_clicks"),
    Input("energy-certificate-next", "n_clicks"),
    Input("energy-certificate-document-store", "data"),
    State("energy-certificate-page-store", "data"),
)
def navigate_energy_certificate(_previous, _next, document, current_page):
    current_page = current_page if isinstance(current_page, dict) else {"page": current_page}
    page_count = max(1, int((document or {}).get("pages") or 1))
    page = min(max(1, int(current_page.get("page") or 1)), page_count)
    previous_clicks = int(_previous or 0)
    next_clicks = int(_next or 0)
    if (
        dash.ctx.triggered_id == "energy-certificate-document-store"
        or current_page.get("document") != document
    ):
        page = 1
    else:
        page += max(0, next_clicks - int(current_page.get("next_clicks") or 0))
        page -= max(0, previous_clicks - int(current_page.get("previous_clicks") or 0))
    return {
        "page": min(max(1, page), page_count),
        "document": document,
        "previous_clicks": previous_clicks,
        "next_clicks": next_clicks,
    }


# Übernimmt die gewählte Seite des ökologischen Energieausweises.
@dash.callback(
    Output("energy-certificate-ecological-page-store", "data"),
    Input("energy-certificate-ecological-previous", "n_clicks"),
    Input("energy-certificate-ecological-next", "n_clicks"),
    Input("energy-certificate-ecological-document-store", "data"),
    State("energy-certificate-ecological-page-store", "data"),
)
def navigate_ecological_certificate(previous, next_clicks, document, current_page):
    return navigate_energy_certificate(previous, next_clicks, document, current_page)


# Übergibt die Zielseite an den Browser, der sie vor dem Anzeigen lädt.
@dash.callback(
    Output("energy-certificate-page-stage", "data-page-src"),
    Output("energy-certificate-page-stage", "data-page-label"),
    Output("energy-certificate-message", "children"),
    Output("energy-certificate-message", "style"),
    Output("energy-certificate-previous", "disabled"),
    Output("energy-certificate-next", "disabled"),
    Output("energy-certificate-toolbar", "style"),
    Input("energy-certificate-page-store", "data"),
)
def display_energy_certificate_page(page_state):
    page_state = page_state if isinstance(page_state, dict) else {"page": page_state}
    current_page = page_state.get("page")
    document = page_state.get("document")
    document = document or {}
    if document.get("error"):
        return (
            "",
            "Seite 1 / 1",
            document["error"],
            {"display": "block"},
            True,
            True,
            {"display": "none"},
        )
    if not document.get("scenario"):
        return (
            "",
            "Seite 1 / 1",
            "Quartiersenergieausweis wird geladen …",
            {"display": "block"},
            True,
            True,
            {"display": "none"},
        )

    page_count = max(1, int(document.get("pages") or 1))
    page = min(max(1, int(current_page or 1)), page_count)
    source = (
        "/dg-results/certificate/page.png?scenario="
        f"{quote(document['scenario'], safe='')}&page={page}"
        f"&objective={quote(str(document.get('objective') or 'economic'), safe='')}"
        f"&v={document.get('version', '')}"
    )
    return (
        source,
        f"Seite {page} / {page_count}",
        "",
        {"display": "none"},
        page <= 1,
        page >= page_count,
        {"display": "flex"},
    )


# Zeigt die gewählte Ausweisseite mit passendem Navigationsstatus.
@dash.callback(
    Output("energy-certificate-ecological-page-stage", "data-page-src"),
    Output("energy-certificate-ecological-page-stage", "data-page-label"),
    Output("energy-certificate-ecological-message", "children"),
    Output("energy-certificate-ecological-message", "style"),
    Output("energy-certificate-ecological-previous", "disabled"),
    Output("energy-certificate-ecological-next", "disabled"),
    Output("energy-certificate-ecological-toolbar", "style"),
    Input("energy-certificate-ecological-page-store", "data"),
)
def display_ecological_certificate_page(page_state):
    return display_energy_certificate_page(page_state)


# Öffnet den Ergebnisordner der gewählten Vergleichsvariante.
@dash.callback(
    Output("energy-certificate-folder-status", "data"),
    Input("energy-open-dg-results", "n_clicks"),
    State("energy-objective-store", "data"),
    State("dg-config-draft-store", "data"),
    prevent_initial_call=True,
)
def open_dg_results_folder(
    n_clicks,
    objective,
    config_state,
):
    objective = str(objective or "economic").strip().lower()

    if not n_clicks:
        raise PreventUpdate

    scenario_name = configured_scenario_name(config_state)
    if not scenario_name:
        return {"opened": False}

    try:
        result_path = (
            scenario_results_path(scenario_name)
            if objective == "comparison"
            else comparison_variant_results_path(scenario_name, objective)
        ).resolve()
        if not result_path.is_dir():
            raise DGResultError(
                f"Für das Szenario {scenario_name!r} ist noch kein results-Ordner vorhanden."
            )
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            raise OSError("Der Windows-Explorer ist auf diesem System nicht verfügbar.")
        startfile(str(result_path))
    except (DGResultError, ValueError, OSError) as exc:
        return {"opened": False, "error": str(exc)}

    return {"opened": True}


dash.clientside_callback(
    """function(comparison) {
        if (!comparison) return {};
        const manifest = comparison.manifest || {};
        return {
            project_snapshot: comparison.project_snapshot || null,
            manifest: {
                run_id: manifest.run_id,
                started_at: manifest.started_at,
                variants: Object.keys(manifest.variants || {})
            }
        };
    }""",
    Output("energy-project-context-store", "data"),
    Input("energy-comparison-store", "data"),
)


# Aktualisiert die Projektinformationen des ausgewählten Ergebnisses.
@dash.callback(
    Output("energy-project-content", "children"),
    Input("weather-store", "data"),
    Input("dg-config-draft-store", "data"),
    Input("building-scenario-store", "data"),
    Input("energy-project-central-selection", "data"),
    Input("energy-project-decentral-selection", "data"),
    Input("energy-project-building-selection", "data"),
    Input("energy-project-context-store", "data"),
)
def update_energy_project_view(
    weather_data,
    config_state,
    building_state,
    selected_central=None,
    selected_decentral=None,
    selected_building=None,
    comparison=None,
):
    context = project_info_context(
        weather_data, config_state, building_state,
        project_snapshot=(comparison or {}).get("project_snapshot"),
        run_metadata=(comparison or {}).get("manifest"),
    )
    return project_info_view(
        context,
        selected_central_device=selected_central,
        selected_decentral_device=selected_decentral,
        selected_building=selected_building,
    )


# Übernimmt die Auswahl eines Projektinformationsbereichs.
@dash.callback(
    Output("energy-project-central-selection", "data"),
    Output("energy-project-decentral-selection", "data"),
    Output("energy-project-building-selection", "data"),
    Input(
        {"type": "energy-project-selector", "group": "central", "key": ALL},
        "n_clicks",
    ),
    Input(
        {"type": "energy-project-selector", "group": "decentral", "key": ALL},
        "n_clicks",
    ),
    Input(
        {"type": "energy-project-selector", "group": "building", "key": ALL},
        "n_clicks",
    ),
    State("energy-project-central-selection", "data"),
    State("energy-project-decentral-selection", "data"),
    State("energy-project-building-selection", "data"),
    prevent_initial_call=True,
)
def select_energy_project_detail(
    _central_clicks,
    _decentral_clicks,
    _building_clicks,
    central,
    decentral,
    building,
):
    triggered = dash.ctx.triggered_id
    if not isinstance(triggered, dict):
        raise PreventUpdate
    group = triggered.get("group")
    key = triggered.get("key")
    if group == "central":
        central = key
    elif group == "decentral":
        decentral = key
    elif group == "building":
        building = key
    else:
        raise PreventUpdate
    return central, decentral, building


# Begrenzt die gleichzeitig gewählten Umgebungsreihen.
@dash.callback(
    Output("energy-environment-series", "options"),
    Input("energy-environment-series", "value"),
)
def limit_energy_environment_series(selected_series):
    selected = set((selected_series or [])[:2])
    limit_reached = len(selected) >= 2
    return [
        {
            **option,
            "disabled": limit_reached and option["value"] not in selected,
        }
        for option in ENVIRONMENT_SERIES_OPTIONS
    ]


# Aktualisiert das Umgebungsdiagramm anhand der Auswahl.
@dash.callback(
    Output("energy-environment-graph", "figure"),
    Input("weather-store", "data"),
    Input("energy-environment-series", "value"),
)
def update_energy_environment_graph(weather_data, selected_series):
    return environment_figure(
        weather=weather_data,
        selected_series=selected_series or [],
    )


# Aktualisiert das Bedarfsdiagramm anhand der Auswahl.
@dash.callback(
    Output("energy-demand-graph", "figure"),
    Input("demand-profile-store", "data"),
    Input("energy-demand-series", "value"),
)
def update_energy_demand_graph(demand_data, selected_series):
    return thermal_energy_figure_from_store(
        demand_data,
        selected_series=selected_series,
    )


# Lädt Clusterauswahl und PFC-Grunddaten in einem Callback.
@dash.callback(
    Output("energy-cluster-options", "children"),
    Output("energy-cluster-store", "data"),
    Output("energy-pfc-prepared-store", "data"),
    Input("optimization-result-store", "data"),
    Input("energy-pfc-mount-store", "data"),
    Input({"type": "energy-cluster-button", "cluster": ALL}, "n_clicks"),
    State("energy-cluster-store", "data"),
    State("building-scenario-store", "data"),
    State("energy-pfc-prepared-store", "data"),
)
def update_energy_cluster_controls(
    optimization_data: dict | None,
    _mounted: bool,
    _button_clicks: list[int | None],
    current_cluster: str | None,
    building_state: dict | None,
    current_prepared: dict | None,
):
    triggered = dash.ctx.triggered_id
    try:
        changed_inputs = dash.ctx.triggered_prop_ids
    except AttributeError:
        changed_inputs = {}
    result_changed = any(
        key in changed_inputs
        for key in (
            "optimization-result-store.data",
            "energy-pfc-mount-store.data",
        )
    )
    requested = (
        triggered.get("cluster")
        if isinstance(triggered, dict)
        and triggered.get("type") == "energy-cluster-button"
        else current_cluster
    )
    selected = resolve_cluster_key(optimization_data, requested)
    options = cluster_options(optimization_data)
    prepared = (
        dash.no_update
        if isinstance(triggered, dict) and current_prepared and not result_changed
        else prepare_energy_pfc(optimization_data, building_state)
    )
    if not options:
        return html.Div(
            "Keine Cluster verfügbar",
            className="energy-cluster-empty-message heo-field",
        ), None, prepared

    buttons = []
    for option in options:
        active = option.key == selected
        prefix, separator, description = option.label.partition(": ")
        children = [html.Span(prefix, className="energy-cluster-number")]
        if separator:
            children.append(
                html.Span(description, className="energy-cluster-description")
            )
        buttons.append(html.Button(
            children,
            id={"type": "energy-cluster-button", "cluster": option.key},
            n_clicks=0,
            className=(
                "energy-cluster-button konfig-primary-button "
                "energy-cluster-button-active"
                if active
                else "energy-cluster-button konfig-secondary-button"
            ),
            title=option.label,
            **{"aria-pressed": "true" if active else "false"},
        ))
    return buttons, selected, prepared
