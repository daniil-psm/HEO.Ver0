# Globale, tab-übergreifende Dash-Stores.

from copy import deepcopy

from dash import dcc, html


# Erzeugt den zentralen UI-Zustand der aktuellen HEO-Version.
#
# Initialisiert Navigation, Konfigurator, Eingabedaten und Ergebniszustand.
# Der Simulationszustand bleibt im Sitzungsspeicher; die übrigen Stores liegen
# im Arbeitsspeicher der Seite. Der Konfigurator-Standardzustand wird von
# der Anwendung übergeben und für den Store unabhängig kopiert.
def create_global_stores(
    default_weather_data: dict | None = None,
    default_heo_input_state: dict | None = None,
    default_dg_config_state: dict | None = None,
    default_building_scenario_state: dict | None = None,
    *,
    default_configurator_state: dict,
) -> html.Div:
    return html.Div(
        style={"display": "none"},
        children=[
            dcc.Store(id="unit-preferences-store", data={}, storage_type="session"),
            html.Div(id="unit-preferences-sync"),
            dcc.Store(
                id="weather-store",
                data=default_weather_data,
                storage_type="memory",
            ),
            dcc.Store(id="weather-upload-store", data=None, storage_type="memory"),
            dcc.Store(
                id="active-main-tab-store",
                data="dashboard-home",
                storage_type="memory",
            ),
            dcc.Store(
                id="navigation-request-store",
                data=None,
                storage_type="memory",
            ),
            dcc.Store(
                id="energy-view-store",
                data="project",
                storage_type="memory",
            ),
            dcc.Store(
                id="energy-objective-store",
                data="economic",
                storage_type="memory",
            ),
            dcc.Store(
                id="konfigurator-state-store",
                data=deepcopy(default_configurator_state),
                storage_type="memory",
            ),
            dcc.Store(
                id="konfigurator-selection-store",
                data=None,
                storage_type="memory",
            ),
            dcc.Store(
                id="simulation-state-store",
                data={
                    "status": "idle",
                    "running": False,
                    "scenario_name": None,
                    "progress": 0,
                    "phase": "Bereit",
                    "log": "",
                },
                storage_type="session",
            ),
            dcc.Store(
                id="konfig-progress-details-open-store",
                data=False,
                storage_type="memory",
            ),
            html.Div(id="simulation-navigation-guard"),
            dcc.Store(
                id="eingabe-config-view-store",
                data="project_load",
                storage_type="memory",
            ),
            dcc.Store(
                id="heo-input-draft-store",
                data=default_heo_input_state,
                storage_type="memory",
            ),
            dcc.Store(
                id="dg-config-draft-store",
                data=default_dg_config_state,
                storage_type="memory",
            ),
            dcc.Store(
                id="building-scenario-store",
                data=default_building_scenario_state,
                storage_type="memory",
            ),
            dcc.Store(
                id="building-layout-version-store",
                data=0,
                storage_type="memory",
            ),
            dcc.Store(id="demand-profile-store", storage_type="memory"),
            dcc.Store(id="energy-project-context-store", storage_type="memory"),
            dcc.Store(
                id="optimization-result-store",
                data=None,
                storage_type="memory",
            ),
        ],
    )
