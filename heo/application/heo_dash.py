# -*- coding: utf-8 -*-
"""Definition der Dash-Anwendung; Einrichtung und Start liegen in launcher.py."""

from __future__ import annotations

import sys
from pathlib import Path
from collections.abc import Callable

import dash
from dash import ALL, Input, Output, State, html
from flask import abort, request, send_file

from .asset_manifest import SCRIPTS, STYLESHEETS, asset_urls
from heo.model.buildings import DEFAULT_BUILDING_SCENARIO_STATE
from dg_adapter.input.parameter_catalog import DEFAULT_HEO_INPUT_STATE
from dg_adapter.input.weather_input import DEFAULT_WEATHER_DATA
from dg_adapter.input.input_mapper import heo_state_to_dg_state
from dg_adapter.output import DGResultError
from dg_adapter.output.certificates import certificate_result_path, render_certificate_page
from ui.components.dashboard import Dashboard
from tabs.tab_1_start import Dashboard_Home
from tabs.tab_2_konfigurator import create_configurator_dashboard
from tabs.tab_3_ergebnisse import Dashboard_Energiesystem, create_energy_dashboard
from ui.components.dev_tools import DevTools
from ui.components.header import Header
from ui.stores import create_global_stores
from tabs.tab_2_konfigurator.konfigurator_config import default_configurator_state


TabContentFactory = Callable[[], object]


def _static(component: object) -> TabContentFactory:
    """Verpackt eine bereits erzeugte Komponente als aufrufbare Tab-Inhaltsquelle."""

    return lambda: component


TAB_CONTENT: dict[str, TabContentFactory] = {
    "dashboard-home": _static(Dashboard_Home),
    "dashboard-konfigurator": create_configurator_dashboard,
    "dashboard-energiesystem": _static(Dashboard_Energiesystem),
}


def render_tab_content(
    tab_value: str | None,
    *,
    initial_energy_view: str | None = None,
    configurator_context: dict | None = None,
):
    """Liefert den angeforderten Haupt-Tab samt Kontext; unbekannte Tabs zeigen die Startseite."""

    if tab_value == "dashboard-konfigurator":
        return create_configurator_dashboard(**(configurator_context or {}))
    if tab_value == "dashboard-energiesystem" and initial_energy_view:
        return create_energy_dashboard(initial_view=initial_energy_view)
    factory = TAB_CONTENT.get(tab_value or "dashboard-home", TAB_CONTENT["dashboard-home"])
    return factory()


ENERGY_VIEWS = frozenset(
    {
        "project",
        "environment",
        "demands",
        "system",
        "sankey",
        "pfc",
        "certificate",
    }
)
RESULTS_TAB = "dashboard-energiesystem"


def resolve_energy_view(
    tab_value: str,
    navigation_requested: bool,
    navigation_request: dict | None,
    current_view: str | None,
) -> str:
    """Löst die Ergebnisansicht ohne konkurrierenden Store-Zwischenstand auf."""

    requested_view = (
        (navigation_request or {}).get("view")
        if tab_value == "dashboard-energiesystem" and navigation_requested
        else None
    )
    if requested_view in ENERGY_VIEWS:
        return requested_view
    return current_view if current_view in ENERGY_VIEWS else "project"


def resource_path(relative_path: str) -> str:
    """Löst einen Ressourcenpfad im Quellbaum oder im PyInstaller-Paket auf."""

    if hasattr(sys, "_MEIPASS"):
        return str(Path(sys._MEIPASS) / relative_path)
    return str(Path(__file__).resolve().parents[2] / relative_path)


app = dash.Dash(
    __name__,
    title="HEO – Humanotop Energiesystem-Optimierer",
    update_title=None,
    suppress_callback_exceptions=True,
    assets_folder=resource_path("assets"),
    # Die fachlichen Unterordner sollen die bisherige CSS-/JS-Reihenfolge
    # nicht verändern. Alle Browserdateien stehen dafür im Manifest.
    assets_ignore=r".*\.(?:css|js)$",
    external_stylesheets=asset_urls(Path(resource_path("assets")), STYLESHEETS),
    external_scripts=asset_urls(Path(resource_path("assets")), SCRIPTS),
)
app.index_string = app.index_string.replace(
    "{%favicon%}",
    f'<link rel="icon" type="image/png" href="{app.get_asset_url("images/Logo_klein_weiß.png")}">',
)


@app.server.route("/dg-results/certificate")
def serve_dg_certificate():
    """Stellt ausschließlich den Energieausweis des gewählten Szenarios bereit."""

    try:
        path = certificate_result_path(
            request.args.get("scenario"),
            request.args.get("objective"),
        )
    except (DGResultError, ValueError, OSError) as exc:
        abort(404, description=str(exc))
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=path.name,
        conditional=True,
    )


@app.server.route("/dg-results/certificate/page.png")
def serve_dg_certificate_page():
    """Liefert eine einzelne Energieausweis-Seite als PNG."""

    try:
        path = render_certificate_page(
            request.args.get("scenario"),
            request.args.get("page"),
            request.args.get("objective"),
        )
    except (DGResultError, ValueError, OSError) as exc:
        abort(404, description=str(exc))
    return send_file(
        path,
        mimetype="image/png",
        as_attachment=False,
        conditional=True,
    )

app.layout = html.Div(
    className="app-shell",
    children=[
        Header,
        create_global_stores(
            default_configurator_state=default_configurator_state(),
            default_weather_data=DEFAULT_WEATHER_DATA,
            default_heo_input_state=DEFAULT_HEO_INPUT_STATE,
            default_dg_config_state=heo_state_to_dg_state(DEFAULT_HEO_INPUT_STATE),
            default_building_scenario_state=DEFAULT_BUILDING_SCENARIO_STATE,
        ),
        Dashboard,
        DevTools,
    ],
)


@app.callback(
    Output("tab-content", "children"),
    Output({"type": "main-nav-tab", "value": ALL}, "className"),
    Output("active-main-tab-store", "data"),
    Output("energy-view-store", "data"),
    Input({"type": "main-nav-tab", "value": ALL}, "n_clicks"),
    Input("navigation-request-store", "data"),
    State({"type": "main-nav-tab", "value": ALL}, "id"),
    State("active-main-tab-store", "data"),
    State("simulation-state-store", "data"),
    State("energy-view-store", "data"),
    State("optimization-result-store", "data"),
    State("konfigurator-state-store", "data"),
    State("heo-input-draft-store", "data"),
    State("building-scenario-store", "data"),
    State("konfigurator-selection-store", "data"),
    State("weather-store", "data"),
)
def render_tab(
    _clicks,
    navigation_request,
    tab_ids,
    current_tab: str | None,
    simulation_state,
    energy_view: str | None,
    optimization_result,
    configurator_state=None,
    heo_state=None,
    buildings=None,
    selection=None,
    weather=None,
):
    """Liefert Tab-Inhalt, Navigationsklassen und aktive Ansichten für den aktuellen UI-Zustand."""

    tab_value = current_tab or "dashboard-home"
    simulation_running = bool((simulation_state or {}).get("running"))
    trigger_id = dash.ctx.triggered_id
    navigation_requested = (
        "navigation-request-store.data" in dash.ctx.triggered_prop_ids
        and bool(navigation_request)
    )
    # Während der Simulation bleibt deren Fortschritt im Konfigurator erreichbar.
    if simulation_running:
        tab_value = "dashboard-konfigurator"
    elif navigation_requested:
        tab_value = navigation_request.get("tab", tab_value)
    elif isinstance(trigger_id, dict):
        tab_value = trigger_id.get("value", tab_value)

    # Die Ergebnisansicht benötigt einen geladenen Ergebniszustand.
    if tab_value == RESULTS_TAB and optimization_result is None:
        tab_value = (
            current_tab
            if current_tab and current_tab != RESULTS_TAB
            else "dashboard-konfigurator"
        )

    # Auswahlmarkierung und Tab-Inhalt werden aus derselben entschiedenen Navigation erzeugt.
    classes = [
        "nav-tab nav-tab-selected"
        if tab_id["value"] == tab_value
        else "nav-tab"
        for tab_id in tab_ids
    ]
    initial_energy_view = resolve_energy_view(
        tab_value,
        navigation_requested,
        navigation_request,
        energy_view,
    )
    return (
        render_tab_content(
            tab_value,
            initial_energy_view=initial_energy_view,
            configurator_context={
                "state": configurator_state,
                "heo_state": heo_state,
                "buildings": buildings,
                "selection": selection,
                "simulation": simulation_state,
                "weather": weather,
            },
        ),
        classes,
        tab_value,
        initial_energy_view,
    )


@app.callback(
    Output({"type": "main-nav-tab", "value": ALL}, "disabled"),
    Input("simulation-state-store", "data"),
    Input("optimization-result-store", "data"),
    State({"type": "main-nav-tab", "value": ALL}, "id"),
)
def lock_main_navigation(simulation_state, optimization_result, tab_ids):
    """Liefert die Navigationssperren aus Simulationsstatus und Verfügbarkeit der Ergebnisse."""

    simulation_running = bool((simulation_state or {}).get("running"))
    results_loaded = optimization_result is not None
    return [
        simulation_running
        or (tab_id.get("value") == RESULTS_TAB and not results_loaded)
        for tab_id in tab_ids
    ]


app.clientside_callback(
    "function(preferences) { return window.HEOUnits.synchronize(preferences); }",
    Output("unit-preferences-sync", "children"),
    Input("unit-preferences-store", "data"),
)


app.clientside_callback(
    """
    function(simulationState) {
        window.__heoSimulationRunning = Boolean(
            simulationState && simulationState.running
        );
        if (!window.__heoBeforeUnloadGuardInstalled) {
            window.addEventListener("beforeunload", function(event) {
                if (window.__heoSimulationRunning) {
                    event.preventDefault();
                    event.returnValue = "";
                }
            });
            window.__heoBeforeUnloadGuardInstalled = true;
        }
        return window.__heoSimulationRunning ? "running" : "idle";
    }
    """,
    Output("simulation-navigation-guard", "children"),
    Input("simulation-state-store", "data"),
)


